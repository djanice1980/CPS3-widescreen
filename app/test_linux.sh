#!/usr/bin/env bash
# Test the built Linux app in a distribution's container on a virtual display (Xvfb inside the container, so no
# window opens on your desktop):
#   app/test_linux.sh <image> <work dir> [<pack .7z> <MAME rom dir> <formats>]
# Without a pack it only opens the window (startup test). <work dir>/shot.png is the window at the end;
# <work dir>/result.json what the app reported; <work dir>/out the files it made.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
image=$1 work=$(realpath -m "$2") pack=${3:-} roms=${4:-} formats=${5:-darksoft,mame,mister}
[ "$formats" = all ] && formats=darksoft,mame,mister
APPBIN="$ROOT/build/app/CPS3-Widescreen-linux-x86_64"
rm -rf "$work" && mkdir -p "$work/out"
run=false
[ -n "$pack" ] && run=true
python3 -I -c "
import json, sys
json.dump({'pack': '/pack/' + sys.argv[1].split('/')[-1] if sys.argv[1] else '', 'roms': '/roms' if sys.argv[2] else '',
           'out': '/w/out', 'formats': sys.argv[3].split(','), 'result': '/w/result.json',
           'run': sys.argv[4] == 'true', 'quit_after_ms': 5000, 'tab': int(sys.argv[6])}, open(sys.argv[5], 'w'))
" "$pack" "$roms" "$formats" "$run" "$work/conf.json" "${TAB:-0}"
mounts=(-v "$APPBIN:/app/CPS3-Widescreen:ro" -v "$work:/w")
[ -n "$pack" ] && mounts+=(-v "$(dirname "$(realpath "$pack")"):/pack:ro")
[ -n "$roms" ] && mounts+=(-v "$(realpath "$roms"):/roms:ro")
case $image in
    ubuntu*|debian*) setup='export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq xvfb x11-apps libxft2 fontconfig fonts-dejavu-core >/dev/null' ;;
    fedora*) setup='dnf install -y -q xorg-x11-server-Xvfb xwd libXft fontconfig dejavu-sans-fonts >/dev/null' ;;
    arch*) setup='pacman -Sy --noconfirm --needed xorg-server-xvfb xorg-xwd libxft fontconfig ttf-dejavu >/dev/null' ;;
esac
docker run --rm "${mounts[@]}" "$image" sh -c "
    $setup
    Xvfb :99 -screen 0 1024x820x24 -nolisten tcp >/dev/null 2>&1 &
    sleep 2
    cd /w && DISPLAY=:99 CPS3WS_SELFTEST=/w/conf.json /app/CPS3-Widescreen > /w/app.log 2>&1 &
    pid=\$!
    for i in \$(seq 1 900); do
        [ -f /w/result.json ] && break
        kill -0 \$pid 2>/dev/null || break
        sleep 1
    done
    sleep 1
    xwd -root -display :99 -silent > /w/shot.xwd
    wait \$pid; echo app exit \$?
    chown -R $(id -u):$(id -g) /w
"
magick "$work/shot.xwd" "$work/shot.png" && rm "$work/shot.xwd"
grep -o '\"result\": \"[a-z]*\"' "$work/result.json" 2>/dev/null || echo "no result.json (startup test or crash)"
cat "$work/app.log"
