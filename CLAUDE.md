# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A mod for Porsche PCM5 / Audi MH2p (MIB2+) head units that puts Android Auto (and, on Porsche, CarPlay) navigation on the instrument cluster: turn-by-turn through the cluster's BAP interface and, since v0020, the phone's cluster map as H.264 video. Upstream is fifthBro's Porsche work; this fork adds the Audi e-tron port. README.md is the user-facing document and is kept current; read its Audi sections before touching anything under `modkit/`.

Three pieces run on the head unit (QNX 6.6 on NVIDIA Tegra, IBM J9 JVM at Java 1.4 class-file level, OSGi HMI):

- **Java** (`lsd/`): classes dropped into `/mnt/app/eso/hmi/lsd/jars/` shadow stock HMI classes, because `lsd.sh` puts every jar in that directory on `-Xbootclasspath` ahead of `/ifs/lsd.jxe` (with `-noverify`). `AndroidAuto2Subsystem` is the shadowed stock class; it constructs `nav/AndroidAutoClusterIntegration`, the bridge from the Android Auto DSI listener callbacks to `CombiBAPServiceNavi` (BAP) and to the cluster daemon (through the `/tmp/cluster_ctl` FIFO). `AndroidAuto2EventListener` is shadowed too: its constructor is the only place that subscribes the DSI attributes, and the mod's copy subscribes 7 and 8 (next turn, distance), which stock Audi does not.
- **Native hook** (`src/gal_cluster.c`): `LD_PRELOAD`ed into the Android Auto receiver `gal` by a ksh wrapper that replaces `/mnt/app/eso/bin/apps/gal` (original kept as `gal.real`). It interposes libautoreceiver C++ symbols, injects a cluster VideoSink service (ids 14/21) into the head unit's service discovery response, and copies the phone's cluster H.264 stream into shared memory. `src/dio_manager_preload.c` is the CarPlay equivalent (route guidance over iAP2), Porsche only.
- **Cluster daemon** (`src/cluster.c`): decodes the stream with NvMedia and posts it as a QNX Screen window bound to displayable `33`, the cluster map slot; it sizes that window to the detected cluster display (`DISP_W`/`DISP_H`) and blits with `mode` letter/fill/stretch plus zoom/pan from the `prepare` command the Java side sends. `cluster_config.json` (installed next to the daemon, overridable by a copy at an SD/USB root) is read by all three.

The shipped binaries and JAR in `builds/` are **newer than the sources** in `src/` and `lsd/` (extra logging, display auto-detection, the `carConfig` schema). Treat the sources as documentation of behaviour, verify against the binaries (`strings`, `javap`, capstone with the daemon's intact symbol table), and never rebuild from `src/` expecting parity. There is no QNX toolchain here; nothing native is rebuilt in this repository.

## Install mechanics (modkit/)

Everything the Audi port changes lives in `modkit/`, as an overlay on the release zip; the LawPaul SD ModKit runs `Mods/ClusterIntegration/Update/install.sh` during boot with the card inserted (`Persist/install.sh` runs on every boot and starts the daemon). Markers next to `Update/` on the card drive behaviour: `diag.txt`, `enable_carplay.txt`, `force_install.txt`, `no_stub.txt`, `uninstall.txt`, plus `config_overrides.txt` (values for the installed config, `BLOCK.KEY` form for the inline `gal_h264`/`mirror` objects) and `gal_env.txt` (`GAL_CLUSTER_*` variables exported by the `gal` wrapper). Every file the installer touches is backed up to `Update/Backup/` on the card and recorded in `Backup/manifest.txt`; `uninstall.sh` (and `rollback.sh` / `reinstall.sh` over SSH) restore from that.

Hard-won facts about the unit the scripts must survive (an e-tron on P2873, see the README verification section):
- Only QNX ksh (ksh88/pdksh level): no bash, `local`, arrays beyond `set -A`, or `$RANDOM`. Test with `mksh`.
- `grep` has no `-a`, no `\|` alternation, and never matches inside a binary file; `awk` is gawk-like but NUL-blind; no `sum`, `cmp`, `diff`, `od`, `cksum`, `md5sum`, `tr`, `uniq`, `unzip`, `strings`; `wc`, `awk`, `sed` live under `/mnt/app/armle`, which the installer appends to PATH. Any check that needs a missing tool must say `skipped`, never report a negative.
- The card is FAT32: 2-second timestamps, so a backup copy never carries the unit file's exact mtime (`files_same` verifies backups without the mtime rule; `files_identical` uses it to decide whether the unit's copy is current, because `cp -p` from the card keeps the card's time).
- `/tmp` is RAM. A bare `shutdown` over SSH halts the HMI and leaves the OS running with dark screens; the HMI is restarted by holding the MMI knob ten seconds.
- The Audi image lacks `de.audi.app.car.adi.legacy.sportchrono.StorageMountHandler`, so `Update/audi/ClusterIntegration_StorageMountHandler_stub.jar` (a no-op, class-file version 48, built by `modkit/stub/build_stub.sh`) is installed on Audi. The full JAR's CarPlay classes do not link against the Audi image; `enable_carplay.txt` is documented as broken there.

## Commands

```bash
# Rebuild the Audi SD package from the Porsche release zip (overlays modkit/Mods,
# derives aa_only/<name>_aa.jar = release JAR minus the carplay package)
modkit/build_sd_package.sh builds/ClusterIntegration_v0034_beta2_candidate_90d0b76.zip \
                           builds/ClusterIntegration_v0034_beta2_candidate_90d0b76_audi.zip
# (the build also refreshes the tracked modkit/Mods/.../aa_only/*_aa.jar)

# Rebuild the StorageMountHandler stand-in (JDK required) and its jar under Update/audi/
modkit/stub/build_stub.sh

# Compare the shadowed classes against a unit's stock jars (JDK + unzip);
# pass the FULL release JAR and a folder holding the unit's lsd.jar
modkit/check_hmi_signatures.sh Mods/ClusterIntegration/Update/ClusterIntegration_v0034_beta2_candidate_90d0b76.jar <folder>

# Shell syntax check of the ModKit scripts (QNX ksh stand-in)
mksh -n modkit/Mods/ClusterIntegration/Update/install.sh

# Full test run: every gate under three simulated unit toolsets. Needs root
# (the scripts write /mnt/app, /fs, /ifs), mksh, python3, zip, unzip, readelf.
sudo modkit/test/run_tests.sh
# One toolset, or one gate once the environment exists:
sudo modkit/test/run_tests.sh /tmp/mh2p-test audi_qnxgrep
sudo modkit/test/gate_toolsets.sh /tmp/mh2p-test . audi_qnxgrep
```

The gate scripts assert on the installer's log lines, so a wording change in `install.sh` output usually needs a matching change in `modkit/test/gate_*.sh`. Add a test for every installer behaviour change; the toolset simulations (`modkit/test/setup_env.sh`) are what caught the real failures on the car (binary-blind grep, FAT timestamps, missing wc).

## Working conventions

- Changes land on `main` through a PR (the owner's standing instruction: merge to main). Commit messages explain the on-car evidence that motivated the change; the README's Audi sections are updated in the same change.
- Never package a class as "pure stock" on the strength of a signature comparison; diff the bytecode (`javap -c -p`) against the unit's class.
- On-car diagnostics use `awk` for pattern alternation (`grep` cannot), and `/tmp/cluster.log`, `/tmp/cluster_daemon.log`, `/tmp/gal_preload.log`, `/tmp/gal_cluster.log` (the last only with `GAL_CLUSTER_LOG=1`). `GAL_CLUSTER_SD_LOG=1` dumps the head unit's service discovery response to `/tmp/aa_sdresp_*.bin`.
- Stock classes pulled from a unit's `lsd.jar` are untrusted input: keep them outside the repository (for example `../etron-stock/`) and inspect them with `javap`, never run them.

## Open items on the e-tron (as of the last session)

- Cockpit fit is solved (`codecRes=1080`, `mode=fill`, `panY=0.248`, top inset 358); Google ignores the left/right insets, so its turn card stays flush right, clipped by the housing.
- BAP manoeuvres are sent (`BAP_MANEUVER`/`BAP_DISTANCE` in `cluster.log`) but the cockpit draws no Audi-style arrow yet.
- After Android Auto disconnects the cockpit goes black instead of returning to the Audi map, and the steering-wheel zoom only drives the hidden Audi map: the mod cannot find the HMI's cluster map-viewer control (`DSIMapViewerControl` instance 3 / `IMapClusterService`) on the e-tron (no `KOMBI_MAP:` lines). All three need the Audi HMI's navigation and BAP classes (`de/audi/tghu/*`, `org/dsi/ifc/map/*`, `de/audi/atip/interapp/combi/bap/*`, `de/audi/app/terminalmode/*`) extracted from the unit's `lsd.jar`.
- LawPaul's `NavCompassIgnore` ModKit mod (separate `Mods/` folder on the same card) stops the cockpit switching to its compass when navigation starts; its classes do not overlap with this mod's.
