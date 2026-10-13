#!/bin/ksh
#
# Copyright (c) 2026 fifthBro
# https://fifthbro.github.io
#
# Licensed under CC BY-NC-SA 4.0
# https://creativecommons.org/licenses/by-nc-sa/4.0/
# NOT FOR COMMERCIAL USE
#
# cluster.sh
#

# The gal wrapper starts the daemon too when AA comes up before this runs.
# Two daemons race for /tmp/cluster_ctl and drop commands (blank cockpit until
# a reconnect), so only start one when none is running. The bracket keeps grep
# from matching itself.
if [[ -x "/eso/bin/apps/cluster/cluster" ]]; then
        if ! PATH="$PATH:/bin:/usr/bin:/mnt/app/armle/usr/bin:/mnt/app/armle/bin" pidin ar 2>/dev/null | grep 'cluster[ ]daemon' >/dev/null 2>&1; then
                /eso/bin/apps/cluster/cluster daemon >/dev/null 2>&1 &
        fi
fi

