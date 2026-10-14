# Audi P2873 local port

Base: jonny190/mh2p-cluster at ae1b8fe3a6a679f33dee9a93ab7adf43772c83d0.
Local branch: codex/mib2p-disconnect-reconnect. Upstream attribution and
CC BY-NC-SA 4.0 notices are retained.

This checkout is the new functional base. The separate
../mib2p-android-auto-cluster checkout retains the earlier implementation,
tests and firmware audits. Lifecycle requirements are adapted here; its GPL
implementation is not copied into the upstream CC source.

The existing builds/ archives remain unmodified upstream reference releases.
They do not contain our source changes. Published upstream source is older than
the packaged release; rebuilding it is not evidence of equivalence to that
release. This port does not install or execute any payload on an MMI.

Target: A6 C8 / MH2p_ER_AUG35_P2873. Upstream reports a working map on an
e-tron 55 with that firmware train. A6 operation and OEM display restoration
still require vehicle verification. QNX SDK and NvMedia/Screen headers are
required to build the native player.

## Disconnect/reconnect implementation

The new owner is wired into AndroidAutoClusterIntegration, reached by the
upstream Subsystem activation/deactivation/DSI-unavailable callbacks. Subsystem
deinit stops/joins it; init permits a fresh owner only after the old worker has
exited. This is an adaptation of our earlier lifecycle requirements, not a
binary-compatible replacement of our SQ5 transport or display manager hooks.

- One Java monitor serializes lifecycle and BAP producers. Disconnect invalidates
  heartbeat, delayed arrival and popup tasks, clears cached AA navigation and
  retires the player generation. Cleanup clears BAP only if we owned AA output;
  it does not clear OEM guidance at an untouched startup.
- Video loss also retires the child rather than leaving a paused splash on33.
  A later valid availability notification in the same live AA connection can
  start a fresh child after the stop/restore barrier.
- A versioned whole-file request/acknowledgement protocol replaces the lossy
  read/truncate cluster_ctl path in rebuilt AA-only players. Prepare and render
  are separate acknowledged actions, so a rapid pair cannot overwrite prepare.
- Random Java owner and daemon identities plus monotonically increasing
  generation/sequence counters reject old acknowledgements, replays and attempts
  to render a retired generation. A duplicate request cannot renew the lease.
- The daemon services control every100ms independently of new video frames.
  Java publishes every250ms. Frozen replies fail the Java owner after2s (an
  unacknowledged command after3s); absence of fresh native requests expires a5s
  lease. These are scheduled deadlines, not real-time guarantees.
- Native stop signals only its exact unreaped child, escalates from SIGTERM to
  SIGKILL after1s, then waits another1s. A failure to prove exit reports ERROR;
  it cannot acknowledge STOPPED or permit a replacement child. No idle/boot
  splash is spawned. Child exit is a process ownership barrier, not a claim
  that we have audited every Nvidia fence.
- A daemon lock prevents duplicate owners. A saved child PID blocks replacement
  while an orphan could still own33. A reservation is recorded before fork; a
  crash in the fork/PID-publication gap leaves PENDING and requires recovery,
  rather than reporting a false release. Saved PIDs are never killed blindly.
  The child checks parent loss in its decode polling loop; this cannot interrupt
  a blocked vendor call.
- OEM map recreation requests run only after an owned STOPPED acknowledgement.
  Missing/throwing IMapClusterService keeps restoration pending and blocks
  reconnect takeover. Accepted requests are logged as visibility UNCONFIRMED.
  We do not force an OEM hide/show cycle or replace its composition with our
  earlier custom-source routing assumptions.
- Helper failure, malformed/stalled status, command errors and daemon replacement
  retire the owner. They require a fresh activation, not automatic resurrection
  from another video callback. Invalid/out-of-session DSI notifications are ignored.

Configuration defaults to `enableLifecyclePort: false`, including the source
config. Map control additionally requires enableMapRender and h264. There is
no fallback to the old command file, and an old release daemon without the new
status protocol cannot start this port. No installer/archive was rebuilt.

## Verification performed on the PC

1. Production C admission/parser/lease code compiled and passed retirement,
   owner/daemon mismatch, replay, busy-child, rollback, malformed and overflow
   controls. The actual POSIX daemon adapter also passed an MSVC syntax build
   with warnings treated as errors and POSIX declarations supplied; this is not
   a QNX build, fork test or Screen test.
2. Changed Integration, Subsystem and lifecycle helpers compiled using pinned
   Eclipse4.20 with source/target1.4 against the normalized saved P2873 stock
   API and upstream Audi dependency stub. Production output is class major48.
   Nine decompiler Object casts around typed enum comparisons had to be removed
   for that source to compile. This is not stock method-body fidelity proof.
3. Java tests passed unplug/reconnect, delayed notifications, old acknowledgements,
   unavailable restoration, crash/restart, malformed/frozen status, write failure,
   clock rollback and command timeout. Tests execute our helpers, not firmware.
4. A separate compiled C peer using the production parser/admission code passed
   100 Java/native process connect/disconnect cycles. Child/display effects are
   simulated; QNX process/decoder/display behaviour is not simulated proof.
5. Actual-file tests passed read/write and malformed-size rejection. Windows JDK
   rename-over-existing fails; the test verifies that this preserves the old
   snapshot and fails closed. QNX J9 atomic replacement MUST be checked before
   enabling. A delete-before-rename workaround would reintroduce the race and
   is intentionally absent.

Reproduce in this checkout (use your installed Python/compiler paths):

```powershell
cmake -S tests -B build-local/native -G "Visual Studio 17 2022" -A x64
cmake --build build-local/native --config Debug
ctest --test-dir build-local/native -C Debug --output-on-failure
python scripts/test_lifecycle.py --stock-api ../mib2p-android-auto-cluster/android_auto/mh2p/build-java-routing-transport/stock-api.jar --compile-integration --native-peer build-local/native/Debug/lifecycle_native_peer.exe
```

## Still required before a vehicle candidate

- Close the release/source gap, build the complete AA-only class families and
  native player with the proper QNX/Nvidia headers. ECJ generates synthetic
  accessor names different from upstream javac: never combine its rebuilt
  Subsystem with old packaged/stock Subsystem inner classes. The shipped ZIPs
  and native binaries do not contain these changes.
- Wire the receiver/playback owner into gal_cluster.c. Its existing static
  endpoint flag, global router pointer and untagged raw H.264 ring are unchanged.
  They still need our receiver-generation admission, per-owner replies and
  audited detachment/drain before reuse. The current Java generation cannot
  identify a late DSI callback that is already delivered into a new connection
  without a generation tag at its native/subscription boundary.
- Add authoritative decoder/presentation readiness and stream-generation/codec
  reset evidence. PREPARED/RUNNING here acknowledge process actions, not valid
  pictures, surface fences or physical pixels. The source33 binding and actual
  IMapClusterService availability/restoration need target observation. If that
  service is absent, reconnect remains blocked after takeover; no fallback has
  been invented from unsupported native calls.
- Verify J9 atomic file replacement, /tmp access, random source, process signals,
  child reaping and orphan handling on QNX. An interrupted PENDING reservation
  deliberately blocks startup until recovered; it does not authorise deleting
  the marker while a child may live.
- Extend the SD recovery kit to this repo's GAL/gal.real, helper, ClusterIntegration
  JARs and Persist installation before installing any candidate. The existing
  recovery script targets the earlier port and was not changed here.
- Confirm repeated unplug/reconnect, loss without final frames, helper/GAL crash,
  cold boot and NavCompass coexistence in the A6, including actual OEM map return.

The first draft is wired into this base's source and host-tested. It is not a
vehicle-ready installer or a claim of confirmed physical OEM restoration.
