#!/usr/bin/env bash
#
# build_stub.sh — compile the StorageMountHandler stand-in and rewrite its
# class-file version to 48 (Java 1.4), which is what the MH2p HMI JVM loads.
#
# Modern javac cannot target 1.4, so the class is compiled for Java 8 with no
# debug attributes and the version bytes are patched afterwards. That is safe
# because the stub's methods contain no branches (no StackMapTable needed),
# no invokedynamic and no other post-1.4 constructs; the script verifies the
# result with javap and by loading and calling the class.
#
# Usage: modkit/stub/build_stub.sh      (writes modkit/stub/out/...class)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v javac >/dev/null || { echo "error: javac not found (a JDK is required)" >&2; exit 1; }
OUT="$HERE/out"
rm -rf "$OUT" && mkdir -p "$OUT"
javac --release 8 -g:none -nowarn -d "$OUT" \
    "$HERE/compile-deps/org/osgi/framework/BundleContext.java" \
    "$HERE/compile-deps/de/audi/atip/log/LogChannel.java" \
    "$HERE/src/de/audi/app/car/adi/legacy/sportchrono/StorageMountHandler.java"
# keep only the stub; the placeholders must never ship
rm -rf "$OUT/org" "$OUT/de/audi/atip"
CLS="$OUT/de/audi/app/car/adi/legacy/sportchrono/StorageMountHandler.class"
# bytes 4-5 minor version, 6-7 major version (big-endian): set to 0.48
python3 - "$CLS" <<'PY'
import sys
p = sys.argv[1]
b = bytearray(open(p, "rb").read())
assert b[:4] == b"\xca\xfe\xba\xbe", "not a class file"
b[4:8] = b"\x00\x00\x00\x30"
open(p, "wb").write(b)
PY
javap -v "$CLS" | grep -E "major version|StackMapTable|invokedynamic" | sed 's/^/  /'
if javap -v "$CLS" | grep -qE "StackMapTable|invokedynamic"; then
    echo "error: stub contains post-1.4 constructs" >&2; exit 1
fi
# load and call it on this JVM with the placeholders on the classpath
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cat > "$T/StubCheck.java" <<'JAVA'
public class StubCheck {
    public static void main(String[] a) throws Exception {
        Class<?> c = Class.forName("de.audi.app.car.adi.legacy.sportchrono.StorageMountHandler");
        Object o = c.getConstructor(org.osgi.framework.BundleContext.class, de.audi.atip.log.LogChannel.class).newInstance(null, null);
        c.getMethod("init").invoke(o);
        c.getMethod("mountStorageRW", String.class).invoke(o, "/fs/sda0");
        System.out.println("stub loads and runs (class file major " + (((int) new java.io.DataInputStream(StubCheck.class.getResourceAsStream("/de/audi/app/car/adi/legacy/sportchrono/StorageMountHandler.class")).skipBytes(6) == 6 ? "" : "") + ")");
    }
}
JAVA
javac --release 8 -nowarn -d "$T" -cp "$HERE/compile-deps" "$T/StubCheck.java" \
    "$HERE/compile-deps/org/osgi/framework/BundleContext.java" "$HERE/compile-deps/de/audi/atip/log/LogChannel.java"
java -Xverify:all -cp "$T:$OUT" StubCheck
echo "built: $CLS"
