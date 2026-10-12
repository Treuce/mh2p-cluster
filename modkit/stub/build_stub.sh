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
        System.out.println("stub loads and runs under -Xverify:all");
    }
}
JAVA
javac --release 8 -nowarn -d "$T" -cp "$HERE/compile-deps" "$T/StubCheck.java" \
    "$HERE/compile-deps/org/osgi/framework/BundleContext.java" "$HERE/compile-deps/de/audi/atip/log/LogChannel.java"
java -Xverify:all -cp "$T:$OUT" StubCheck
echo "built: $CLS"

# Package the class as its own jar for the Audi SD package. install.sh adds
# it to /mnt/app/eso/hmi/lsd/jars on Audi units whose HMI image does not
# provide the class (lsd.sh puts every jar in that directory on the JVM boot
# class path ahead of /ifs/lsd.jxe). The name keeps the ClusterIntegration_
# prefix so uninstall.sh removes it with the mod's other jars.
JAR_OUT="$HERE/../Mods/ClusterIntegration/Update/audi/ClusterIntegration_StorageMountHandler_stub.jar"
mkdir -p "$(dirname "$JAR_OUT")"
python3 - "$OUT" "$JAR_OUT" <<'PYS'
import os, sys, zipfile
out, jar = sys.argv[1], sys.argv[2]
entry = "de/audi/app/car/adi/legacy/sportchrono/StorageMountHandler.class"
with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(zipfile.ZipInfo("META-INF/MANIFEST.MF", (1980, 1, 1, 0, 0, 0)),
               "Manifest-Version: 1.0\nCreated-By: mh2p-cluster modkit/stub/build_stub.sh\n\n")
    info = zipfile.ZipInfo(entry, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(info, open(os.path.join(out, entry), "rb").read())
print("packaged: " + jar)
PYS
