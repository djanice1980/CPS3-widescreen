#!/usr/bin/env bash
# Test the built Linux app in a distribution's container on a virtual display (Xvfb inside the container, so no
# window opens on your desktop):
#   app/test_linux.sh <image> <work dir> [<pack .7z> <MAME rom dir> <formats>]
# Without a pack it only opens the window (startup test). <work dir>/shot.png is the window at the end;
# <work dir>/result.json what the app reported; <work dir>/out the files it made.
#   TAB=1               show the Instructions tab (for the screenshot)
#   PICK=zenity|kdialog install that desktop file chooser, press the app's real "Choose folder..." button for the
#                       MAME ROM folder (the field holds "/pickme/", so the chooser opens there) and accept the
#                       chooser that opens. result.json then has "picked": {"before": "/pickme/", "after":
#                       "/pickme"}: the field was set from the chooser's answer. chooser.png is the chooser on
#                       screen. (Typing a path into the chooser with xdotool races its auto-complete.)
# <work dir> must be new, empty, or an earlier test's folder (it has a .cps3ws-test file): it is replaced.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
image=$1 work=$(realpath -m "$2") pack=${3:-} roms=${4:-} formats=${5:-darksoft,mame,mister}
[ "$formats" = all ] && formats=darksoft,mame,mister
APPBIN="$ROOT/build/app/CPS3-Widescreen-linux-x86_64"
if [ -e "$work" ] && [ ! -e "$work/.cps3ws-test" ] && [ -n "$(ls -A "$work" 2>/dev/null)" ]; then
    echo "$work exists and is not a test folder of this script: give a new folder"; exit 2
fi
rm -rf "$work" && mkdir -p "$work/out" && touch "$work/.cps3ws-test"
run=false
[ -n "$pack" ] && run=true
python3 -I -c "
import json, sys
json.dump({'pack': '/pack/' + sys.argv[1].split('/')[-1] if sys.argv[1] else '',
           'roms': '/pickme/' if sys.argv[7] else '/roms' if sys.argv[2] else '',
           'out': '/w/out', 'formats': sys.argv[3].split(','), 'result': '/w/result.json',
           'run': sys.argv[4] == 'true', 'quit_after_ms': 5000, 'tab': int(sys.argv[6]), 'pick': bool(sys.argv[7])},
          open(sys.argv[5], 'w'))
" "$pack" "$roms" "$formats" "$run" "$work/conf.json" "${TAB:-0}" "${PICK:-}"
mounts=(-v "$APPBIN:/app/CPS3-Widescreen:ro" -v "$work:/w")
[ -n "$pack" ] && mounts+=(-v "$(dirname "$(realpath "$pack")"):/pack:ro")
[ -n "$roms" ] && mounts+=(-v "$(realpath "$roms"):/roms:ro")
extra=""
[ -n "${PICK:-}" ] && extra="$PICK xdotool xdg-utils"
case $image in
    ubuntu*|debian*) setup="export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq xvfb x11-apps x11-utils libxft2 fontconfig fonts-dejavu-core $extra >/dev/null 2>&1" ;;
    fedora*) setup="dnf install -y -q xorg-x11-server-Xvfb xwd xwininfo libXft fontconfig dejavu-sans-fonts $extra >/dev/null 2>&1" ;;
    arch*) setup="pacman -Syu --noconfirm --needed xorg-server-xvfb xorg-xwd xorg-xwininfo libxft fontconfig ttf-dejavu $extra >/dev/null 2>&1" ;;
esac
cat > "$work/inside.sh" <<EOF
$setup
mkdir -p /pickme
Xvfb :99 -screen 0 1024x820x24 -nolisten tcp >/dev/null 2>&1 &
sleep 2
export DISPLAY=:99
cd /w && CPS3WS_SELFTEST=/w/conf.json /app/CPS3-Widescreen > /w/app.log 2>&1 &
pid=\$!
if [ -n "${PICK:-}" ]; then
    # wait for the chooser's window (its title is the one the app asked for), then use it like a person would
    for i in \$(seq 1 40); do
        xwininfo -root -tree 2>/dev/null | grep -q 'Choose your MAME ROM folder' && break
        sleep 1
    done
    sleep 3
    xwininfo -root -tree 2>/dev/null | grep 'Choose your MAME ROM folder' | head -2 > /w/chooser.txt
    xwd -root -silent > /w/chooser.xwd
    win=\$(xdotool search --name 'Choose your MAME ROM folder' | tail -1)
    xdotool windowfocus "\$win" 2>/dev/null
    if [ "${PICK:-}" = zenity ]; then
        # GTK: Return opens the highlighted folder; click the OK button (bottom right corner of the chooser)
        eval "\$(xdotool getwindowgeometry --shell "\$win")"
        xdotool mousemove \$((X + WIDTH - 40)) \$((Y + HEIGHT - 30)) click 1
    else
        xdotool key Return
    fi
    sleep 3
    xwininfo -root -tree 2>/dev/null | grep -q 'Choose your MAME ROM folder' && { echo "chooser still open: closing it" >> /w/chooser.txt; xdotool key Escape; }
fi
for i in \$(seq 1 900); do
    [ -f /w/result.json ] && break
    kill -0 \$pid 2>/dev/null || break
    sleep 1
done
sleep 1
xwd -root -silent > /w/shot.xwd
wait \$pid; echo app exit \$?
chown -R $(id -u):$(id -g) /w
EOF
docker run --rm "${mounts[@]}" "$image" sh /w/inside.sh
magick "$work/shot.xwd" "$work/shot.png" && rm "$work/shot.xwd"
[ -f "$work/chooser.xwd" ] && magick "$work/chooser.xwd" "$work/chooser.png" && rm "$work/chooser.xwd"
python3 -I -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except OSError:
    sys.exit('no result.json (crash before the window opened?)')
print('result:', d['result'], '| helpers:', d.get('helpers'), '| picked:', d.get('picked'))
if d['result'] in ('failed', 'warning'):
    print('message:', d['message'])
" "$work/result.json"
cat "$work/app.log"
