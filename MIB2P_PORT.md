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
