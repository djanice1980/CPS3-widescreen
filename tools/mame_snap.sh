#!/usr/bin/env bash
# Run a CPS3 set headless in MAME (no window, no sound) and save snapshots from MAME itself.
#   mame_snap.sh <set name> <roms dir> <run dir> <exit frame> <snap frames> [inputs] [pokes]
# inputs: "frame|:PORT|Field name|1;frame|:PORT|Field name|0;..."   pokes: "hexaddr=hexbyte,..."
# The run dir keeps nvram between runs; delete it for a first boot. Snapshots: <run dir>/snap/<set>/NNNN.png
set -euo pipefail
set_name=$1 roms=$2 run=$3 exit_frame=$4 frames=$5 inputs=${6:-} pokes=${7:-}
tools="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$run"/{nvram,snap,cfg}
rm -rf "$run/snap/$set_name"
cd "$run"
SNAP_FRAMES="$frames" SNAP_EXIT="$exit_frame" SNAP_INPUTS="$inputs" SNAP_POKE="$pokes" \
    mame "$set_name" -rompath "$roms" -nvram_directory nvram -snapshot_directory snap -cfg_directory cfg \
    -video none -sound none -nothrottle -skip_gameinfo -seconds_to_run 3600 \
    -autoboot_script "$tools/snap.lua" 2>&1 | grep -v '^$\|might not run correctly\|WRONG CHECKSUMS\|EXPECTED:\|FOUND:\|sfiii3-simm[12]' || true
ls "$run/snap/$set_name" 2>/dev/null | wc -l | xargs echo snapshots:
