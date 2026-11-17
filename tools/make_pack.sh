#!/usr/bin/env bash
# Make the widescreen CPS3 games from a Darksoft CPS-3 pack, as any of three outputs:
#   darksoft  the patched Darksoft pack (.zip) to flash to the UltraSIMM program and graphics SIMMs
#   mame      MAME NO CD ROM sets, one folder per game (MAME/README.txt says how to run them)
#   mister    MRA files and zips for Jotego's jtcps3 core (MiSTer/README.txt says where they go)
#
#   make_pack.sh <Darksoft CPS-3 pack .7z or extracted folder> <out dir> [--format darksoft,mame,mister|all]
#                [--roms <folder with your MAME CPS3 sets>]... [--build]
#
# By default the patches come from patches/ (prebuilt, in the repository): that needs only python3 + numpy, and 7z
# for a .7z. --build compiles them from source first (wine, make, the two decomps in vendor/, rom/sfiii3nr1.zip;
# see README) and refreshes patches/.
#
# --format defaults to darksoft. mame and mister take one thing from your MAME sets: a CPS3 NO CD BIOS chip (from
# sfiii3nr1.zip, which the build needs anyway in rom/, or any NO CD set such as redearthn, jojon, jojoban, sfiiina
# in a --roms folder; each game uses its own when there).
#
# Games: SFIII New Generation (bank 0), Warzard (bank 1), 3rd Strike (bank 5), Makoto Fix (bank 6) and 4rd Strike
# (bank 7) patched in both the Standard SH2 and the Custom SH2 program files, JoJo's Venture (bank 3) and JoJo's
# Heritage for the Future (bank 4) in the Standard SH2 file only (Darksoft's bank 3 and 4 Custom files are other
# revisions of the games), everything else as Darksoft has it. (2nd Impact, bank 2, has its own wide option.)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ $# -ge 2 ] || { sed -n '2,/^set -e/p' "$0" | sed '$d'; exit 2; }
PACK_IN=$(realpath -s "$1") OUT=$(realpath -m "$2")
shift 2
FORMATS=darksoft ROMS=("$ROOT/rom") BUILD=
while [ $# -gt 0 ]; do
    case $1 in
        --build) BUILD=1; shift ;;
        --format) FORMATS=$2; shift 2 ;;
        --roms) ROMS+=("$(realpath "$2")"); shift 2 ;;
        *) echo "unknown option $1"; exit 2 ;;
    esac
done
[ "$FORMATS" = all ] && FORMATS=darksoft,mame,mister
for f in ${FORMATS//,/ }; do
    case $f in darksoft|mame|mister) ;; *) echo "unknown format $f (darksoft, mame, mister, all)"; exit 2 ;; esac
done
B="$ROOT/build"
export WINEPREFIX="${WINEPREFIX:-$B/wineprefix}"

P="$ROOT/patches"
if [ -n "$BUILD" ]; then
    echo '== pack'
    if [ -d "$PACK_IN" ]; then
        PACK="$PACK_IN"
    else
        PACK="$B/darksoft-pack"
        rm -rf "$B/darksoft-extract" && mkdir -p "$B/darksoft-extract"
        7z x -bd -y -o"$B/darksoft-extract" "$PACK_IN" >/dev/null
        found=$(find "$B/darksoft-extract" -type d -name 'SIMM 1-2' | head -1)
        [ -n "$found" ] || { echo "no 'SIMM 1-2' folder in $PACK_IN"; exit 1; }
        rm -rf "$PACK" && mv "$(dirname "$found")" "$PACK" && rm -rf "$B/darksoft-extract"
    fi

    echo '== 3rd Strike build (bank 5 patch)'
    "$ROOT/tools/build_sfiii3.sh"

    echo '== Makoto Fix (bank 6) and 4rd Strike (bank 7) ports'
    mkdir -p "$B/banks"
    python3 -c "import sys; sys.path.insert(0, '$ROOT/tools'); from darksoft import read_program_bank
for b in (0, 1, 3, 4, 6, 7):
    open('$B/banks/bank%d-std.bin' % b, 'wb').write(read_program_bank('$PACK/SIMM 1-2', b, 'Standard'))
open('$B/banks/bank1-custom.bin', 'wb').write(read_program_bank('$PACK/SIMM 1-2', 1, 'Custom'))"
    cd "$ROOT/vendor/sfIII3-cps3-decomp"
    python3 "$ROOT/tools/port_bank.py" "$B/banks/bank6-std.bin" makoto 06700000 06740000 "$B/banks" | grep -v 'MESA\|pci id'
    # 4rd Strike keeps data of its own in 06620000-06780395: its module goes in the free end of SIMM2
    python3 "$ROOT/tools/port_bank.py" "$B/banks/bank7-std.bin" 4rd 06F00000 06F40000 "$B/banks" | grep -v 'MESA\|pci id'
    cd "$ROOT"

    echo '== New Generation (bank 0): the screen mode item'
    "$ROOT/tools/build_sfiiina.sh" "$B/banks/bank0-std.bin"

    echo '== JoJo HFTF (bank 4): wide mode and its screen mode item'
    python3 "$ROOT/tools/build_jojoba.py" jojoba "$B/banks/bank4-std.bin" "$B/jojoba" | grep -v 'MESA\|pci id'

    echo "== JoJo's Venture (bank 3): wide mode and its screen mode item"
    python3 "$ROOT/tools/build_jojoba.py" jojo "$B/banks/bank3-std.bin" "$B/jojo-v" | grep -v 'MESA\|pci id'

    echo '== Warzard (bank 1): wide mode and its screen mode item'
    python3 "$ROOT/tools/build_warzard.py" "$B/banks/bank1-std.bin" "$B/warzard" "$B/banks/bank1-custom.bin" | grep -v '^  '

    echo '== patches/'
    mkdir -p "$P"
    cp "$B/sfiiina/sfiiina-wide.json" "$P/bank0-sfiii-new-generation.json"
    cp "$B/sfiiina/sfiiina-code.json" "$P/bank0-sfiii-new-generation-code.json"
    cp "$B/warzard/warzard-wide.json" "$P/bank1-warzard.json"
    cp "$B/warzard/warzard-code.json" "$P/bank1-warzard-code.json"
    cp "$B/jojo-v/jojo-wide.json" "$P/bank3-jojos-venture.json"
    cp "$B/jojoba/jojoba-wide.json" "$P/bank4-jojos-bizarre-adventure.json"
    cp "$B/sfiii3/sfiii3nr1-wide.json" "$P/bank5-sfiii-3rd-strike.json"
    cp "$B/sfiii3/code.json" "$P/bank5-sfiii-3rd-strike-code.json"
    cp "$B/banks/makoto-wide.json" "$P/bank6-sfiii-makoto-fix.json"
    cp "$B/banks/makoto-code.json" "$P/bank6-sfiii-makoto-fix-code.json"
    cp "$B/banks/4rd-wide.json" "$P/bank7-sfiii-4rd-strike.json"
    cp "$B/banks/4rd-code.json" "$P/bank7-sfiii-4rd-strike-code.json"
fi
[ -f "$P/bank5-sfiii-3rd-strike.json" ] || { echo "no prebuilt patches in $P: run with --build"; exit 1; }

args=(--format "$FORMATS")
for r in "${ROMS[@]}"; do args+=(--roms "$r"); done
python3 -I "$ROOT/tools/cps3ws.py" "$PACK_IN" "$OUT" "${args[@]}"
