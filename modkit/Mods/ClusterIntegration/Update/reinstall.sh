#!/bin/ksh
#
# Copyright (c) 2026 fifthBro
# https://fifthbro.github.io
#
# Licensed under CC BY-NC-SA 4.0
# https://creativecommons.org/licenses/by-nc-sa/4.0/
# NOT FOR COMMERCIAL USE
#
# reinstall.sh
#
# Convenience entry point for re-running the installer over SSH, without the
# ModKit boot cycle, after editing config_overrides.txt, gal_env.txt or the
# files under Update/ on the card:
#
#   ksh /fs/sdb0/Mods/ClusterIntegration/Update/reinstall.sh
#
# It runs install.sh with MOD_PATH set to this folder, exactly as the ModKit
# does (same gate, backups, manifest and marker files). install.sh stops gal
# and the cluster daemon; the HMI starts a new gal with the new environment
# at the next Android Auto session, and the daemon is restarted by the
# Persist script at the next boot (restart it by hand to avoid that:
#   /mnt/app/eso/bin/apps/cluster/cluster daemon verbose=2 &
# ). A changed JAR only takes effect after the HMI restarts, i.e. a reboot.

HERE="${0%/*}"
[[ "$HERE" == "$0" ]] && HERE="."
export MOD_PATH="$(cd "$HERE" && pwd)"
exec /bin/ksh "$MOD_PATH/install.sh"
