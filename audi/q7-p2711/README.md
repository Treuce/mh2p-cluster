# Audi Q7 (MH2p, P2711): Android Auto map in the Virtual Cockpit

Google Maps from Android Auto, full width in the Virtual Cockpit. It shows the 3D driving view with the turn card, and the car marker stays above Audi's bottom info bar. It works over a cable and through wireless Android Auto adapters.

**Download:** [`builds/ClusterIntegration_v0034_q7_p2711_audi.zip`](../../builds/ClusterIntegration_v0034_q7_p2711_audi.zip)

**Tested on:**
- Car: 2020 Audi Q7 (US) with the Virtual Cockpit.
- Head unit: MH2p, firmware `MH2P_US_AUG35_P2711`.
- Phone: Samsung Galaxy, Google Maps.
- Connections: USB cable, AAWireless (DPI 150), and another wireless adapter.

Other MH2p Audis with the same 1920×722 cockpit should be close but are untested. Experimental: install only while parked, and keep the backups the installer makes.

## Install

**Requirements:** Android Auto already working on the car, and LawPaul's [NaviCompassIgnore](https://github.com/LawPaul) installed (otherwise the cockpit falls back to the compass once navigation starts). Read the main README's Audi section first.

1. Extract the zip to an empty FAT32 SD card. It already includes LawPaul's MH2p SD ModKit v2 loader (`Data/`, `Meta/`), unmodified, as upstream's Audi zip does.
2. Parked, with the engine running: insert the card and run the ModKit installation as described on [LawPaul's ModKit site](https://lawpaul.github.io/MH2p_SD_ModKit_Site/).
3. The installer backs up every file it replaces to `Mods/ClusterIntegration/Update/Backup/` on the card. Copy that folder somewhere safe.
4. Plug in the phone and start Google Maps navigation. The cockpit map should appear on the first connection.

If you use a wireless adapter with its own DPI setting, keep it moderate (150 worked). Some custom values made the phone drop the cockpit display.

**Uninstall:** put an empty `uninstall.txt` in `Mods/ClusterIntegration/` on the card and run the ModKit again. It restores the backed-up originals.

## Turning logs on (troubleshooting)

The zip writes no logs during normal use. To diagnose a problem, turn on what you need, re-run the ModKit install, and reproduce the problem. Turn it back off the same way afterwards.

| Log | How to turn it on | Where it goes |
|---|---|---|
| Installer | Always on | `Logs/ClusterIntegration.log` on the SD card, after each install |
| Java integration (session state, map hiding `KOMBI_MAP:`, turn events) | In `Mods/ClusterIntegration/config_overrides.txt`, change `enableExternalLogging=false` to `true` | `cluster.log` in the root of the USB stick in the car (it's always kept in RAM at `/tmp/cluster.log`) |
| Android Auto hook (service discovery, video channel) | Create `Mods/ClusterIntegration/gal_env.txt` with the two lines `GAL_CLUSTER_LOG=1` and `GAL_CLUSTER_LOG_ALL=1` (add `GAL_CLUSTER_SD_LOG=1` to also dump the service discovery) | RAM: `/tmp/gal_cluster.log`. Read it over SSH, or copy it to USB with `cp /tmp/*.log /fs/usb0_0/` |
| Cluster daemon (decoder, frame rate, `prepare`/`resume`/`stop` commands) | In both `Mods/ClusterIntegration/Persist/install.sh` and `Mods/ClusterIntegration/Update/gal`, add `verbose=2` after `daemon` on the line that starts the daemon (`... daemon verbose=2 >/dev/null 2>&1 &`) | `cluster_daemon.log` in the root of the first writable USB stick (falls back to `/tmp`), capped at 1 MB |

With SSH access (LawPaul's `mh2p-ssh-access` mod) you can turn on the daemon log for one session without reinstalling: stop the running daemon with `slay cluster`, then run `/mnt/app/eso/bin/apps/cluster/cluster daemon verbose=2 &`, then reconnect the phone. A reboot returns to normal.

Useful things to look for:
- `[daemon] polling` appears **once** per boot in `cluster_daemon.log`. Twice means two daemons are running.
- `decode_fps=` shows the video frame rate.
- `KOMBI_MAP: AA video rendering, hiding native cockpit map` in `cluster.log` confirms the native map was hidden.

## What this changes from upstream v0034 Audi

| Problem on the Q7 | Fix | Source |
|---|---|---|
| The native Audi cockpit map keeps drawing over the AA video (displayable 33). | `KombiMapGuard` suspends the native kombi map viewer while the AA video renders, and wakes it afterwards. | `lsd/.../nav/KombiMapGuard.java`, started from `AndroidAuto2Subsystem` |
| Black cockpit until a reconnect: the decoder started at the ring's current write position and skipped the session's SPS/PPS/IDR. | Decode from the ring start. | `src/cluster.c` |
| Map needed several reconnects: the gal wrapper and the Persist script each started a cluster daemon, and the two stole each other's commands. | Persist starts the daemon only when none is running. | `modkit/Mods/ClusterIntegration/Persist/install.sh` |
| Car marker hidden under Audi's bottom bar, turn card clipped by the curved edge. The hook sends a fixed 54-byte cluster template (`dhu_cluster_service[]`), so `GAL_CLUSTER_INSET_*` never reaches the phone. | Template rewritten in place for the Q7 cockpit (below). | `gal_cluster.so` at file offset `0x7384` |
| Settings | `codecRes=1080`, `mode="fill"`, `panY=0.0`, Java log to USB off. | `Mods/ClusterIntegration/config_overrides.txt` in the zip |
| Every user got a `cluster_daemon.log` on their USB stick: both places that start the daemon passed `verbose=2`. | Start the daemon without `verbose`; nothing is written to USB. | `Persist/install.sh`, `modkit/Mods/ClusterIntegration/Update/gal` |

**Cockpit template values:**
- `display_type`: CLUSTER (3D driving view; AUXILIARY gives a flat 2D map).
- Stream: 1080p.
- `height_margin`: 358. The daemon's `fill` crop shows rows 179–900, which is exactly the active area.
- UI margins: top 179, bottom 180.
- Content insets: bottom 195 (Audi's info bar), left and right 160 (curved edges).
- Density: 200.

The template bytes:

```
0a34080e1a30222a 0801 1001 20e602 28c801 38f403 40904e 48c801 5003
5a13 0a06 08b301 10b401 1209 10c301 18a001 20a001 3001 3801
```

The `cluster` daemon in the zip is upstream's build with the `src/cluster.c` change applied as two instructions (file offset `0x66ec`: `mov.w r11,#0`, `mov.w r4,#0`). The jar is upstream's Android-Auto-only jar rebuilt with `KombiMapGuard` (ECJ, `-source 1.5 -target jsr14`).

## Known limits

- **HUD:** no arrows or distance on the head-up display, only the street name. With the cockpit coded for the map (`navMapTransmissionMode=3`), the head unit drops the BAP arrow data.
- **Center screen:** while the cockpit map is active, it shows Google's route overview. That's Google's design for cars with a cluster display.
- **Frame rate:** about 10–15 fps while the map rotates. The phone's encoder limits this; the head unit decodes every frame.
- **Native map:** the Audi navigation map is hidden while Android Auto video runs in the cockpit, and comes back when AA disconnects.

## Credits

- **fifthBro:** the original MH2p cluster integration (hook, daemon, Java integration). https://fifthbro.github.io
- **jonny190/mh2p-cluster:** the Audi package this builds on, with Jonathan Davey and jakublamik. https://github.com/jonny190/mh2p-cluster
- **LawPaul:** MH2p SD ModKit (the loader in the zip's `Data/` and `Meta/` is his signed ModKit v2, included unmodified), NaviCompassIgnore and SSH access. https://lawpaul.github.io/MH2p_SD_ModKit_Site/
- **luka-dev:** mib2q-carplay-rgi, navigation event research used upstream. https://github.com/luka-dev/mib2q-carplay-rgi
- **Q7 P2711 fixes and profile:** Bhushan Ahire.

## License

Same as the rest of this repository: [CC BY-NC-SA 4.0](../../LICENSE.md). Non-commercial use only. Changes from upstream are listed above.

The zip contains no Audi, Harman or Google files. The ModKit loader in it belongs to LawPaul and keeps its own terms. Not affiliated with or endorsed by Audi, Volkswagen Group, Harman or Google. "Audi", "Android Auto" and "Google Maps" are trademarks of their owners and are used only to describe compatibility. Use at your own risk; modifying the head unit may affect your warranty.
