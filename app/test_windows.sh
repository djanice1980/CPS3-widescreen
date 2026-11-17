#!/usr/bin/env bash
# Test the built Windows app under Wine, in a fresh Wine prefix, on a private virtual display (Xvfb in a container,
# reachable only from this machine), so no window opens on your desktop:
#   app/test_windows.sh <work dir> [<pack .7z> <MAME rom dir> <formats>]
# Without a pack it only opens the window. <work dir>/shot.png is the window at the end, result.json what the app
# reported, out/ the files it made. Needs docker, wine and ImageMagick (magick).
# <work dir> must be new, empty, or an earlier test's folder (it has a .cps3ws-test file): it is replaced.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
work=$(realpath -m "$1") pack=${2:-} roms=${3:-} formats=${4:-darksoft,mame,mister}
[ "$formats" = all ] && formats=darksoft,mame,mister
EXE="$ROOT/build/app/CPS3-Widescreen-windows-x64.exe"
if [ -e "$work" ] && [ ! -e "$work/.cps3ws-test" ] && [ -n "$(ls -A "$work" 2>/dev/null)" ]; then
    echo "$work exists and is not a test folder of this script: give a new folder"; exit 2
fi
rm -rf "$work" && mkdir -p "$work/out" && touch "$work/.cps3ws-test"

if ! docker exec cps3ws-xvfb true 2>/dev/null; then
    docker rm -f cps3ws-xvfb >/dev/null 2>&1 || true
    docker run -d --name cps3ws-xvfb -p 127.0.0.1:6099:6099 ubuntu:24.04 sh -c 'export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq && apt-get install -y -qq xvfb x11-apps >/dev/null && exec Xvfb :99 -screen 0 1024x820x24 -listen tcp -ac' >/dev/null
    for _ in $(seq 1 100); do docker exec cps3ws-xvfb test -e /tmp/.X11-unix/X99 2>/dev/null && break; sleep 3; done
fi
export DISPLAY=127.0.0.1:99 WINEDEBUG=-all WINEPREFIX="$work/prefix" WINEDLLOVERRIDES="mscoree,mshtml="
wineboot -i >/dev/null 2>&1

win() { [ -n "$1" ] && winepath -w "$1" || true; }
run=false
[ -n "$pack" ] && run=true
python3 -I -c "
import json, sys
json.dump({'pack': sys.argv[1], 'roms': sys.argv[2], 'out': sys.argv[3], 'formats': sys.argv[4].split(','),
           'result': sys.argv[5], 'run': sys.argv[6] == 'true', 'quit_after_ms': 5000}, open(sys.argv[7], 'w'))
" "$(win "$(realpath -m "${pack:-/nonexistent}")")" "$(win "$(realpath -m "${roms:-/nonexistent}")")" "$(win "$work/out")" \
    "$formats" "$(win "$work/result.json")" "$run" "$work/conf.json"
[ -n "$pack" ] || python3 -I -c "
import json, sys; c = json.load(open(sys.argv[1])); c['pack'] = c['roms'] = ''; json.dump(c, open(sys.argv[1], 'w'))" "$work/conf.json"

CPS3WS_SELFTEST="$(win "$work/conf.json")" WINEDEBUG=-all wine "$EXE" >"$work/app.log" 2>&1 &
pid=$!
for _ in $(seq 1 1200); do
    [ -f "$work/result.json" ] && break
    kill -0 $pid 2>/dev/null || break
    sleep 1
done
sleep 1
docker exec cps3ws-xvfb sh -c 'xwd -root -display :99 -silent' > "$work/shot.xwd"
wait $pid || true
wineserver -w
magick "$work/shot.xwd" "$work/shot.png" && rm "$work/shot.xwd"
python3 -I -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except OSError:
    sys.exit('no result.json (crash before the window opened?)')
print('result:', d['result'], '| default save folder:', d.get('default_out'))
if d['result'] in ('failed', 'warning'):
    print('message:', d['message'])
" "$work/result.json"
