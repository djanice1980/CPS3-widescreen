#!/usr/bin/env bash
# Build the 3rd Strike (sfiii3nr1) widescreen program.
#   1. the stock decomp build (must match the arcade's SHA-1)
#   2. src/sfiii3/*.c compiled with the same compiler and linked as extra sections at WIDE_ADDR
#   3. tools/hook.py: everything else unchanged, hooks written
#   4. build/sfiii3/sfiii3nr1.zip for MAME (your set with the two program SIMMs replaced)
# Needs: wine, python3 (numpy for the Darksoft tools), make, and rom/sfiii3nr1.zip.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DECOMP="$ROOT/vendor/sfIII3-cps3-decomp"
OUT="$ROOT/build/sfiii3"
WIDE_ADDR=06700000   # code; free in sfiii3nr1: 066166E4-06787FFF is zero-filled
WIDE_CONST=06740000  # constants
export WINEPREFIX="${WINEPREFIX:-$ROOT/build/wineprefix}"
export WINEDEBUG=-all
mkdir -p "$OUT"

# rof2bin makes temporary files in the root of the current drive: give the decomp a drive of its own
[ -d "$WINEPREFIX" ] || wineboot -i >/dev/null 2>&1 || true
ln -sfn "$DECOMP" "$WINEPREFIX/dosdevices/s:"
[ -f "$DECOMP/rom/sfiii3nr1.zip" ] || cp -L "$ROOT/rom/sfiii3nr1.zip" "$DECOMP/rom/"
chmod +x "$DECOMP"/bin/*.exe

cd "$DECOMP"
quiet() { grep -v 'MESA\|pci id\|SECTION *= \|^: ' || true; }
echo '== stock build'
make PYTHON=python3 SHC_TMP=tmp 2>&1 | quiet | tail -3
cp sf3.bin "$OUT/stock.bin"

echo '== wide module'
export SHC_LIB=bin MDL_EQ_CONST=3 MDL_IV_WEB_ORDER=1 PEP_RETURN_EXIT=2 MDL_GCSE=26
rm -rf obj/wide_src && mkdir -p obj/wide_src tmp/wide
cp "$ROOT"/src/sfiii3/*.c obj/wide_src/
# the fight HUD's routines, copied from the decomp with their columns centred (tools/gen_hud.py)
python3 -I "$ROOT/tools/gen_hud.py" src "$ROOT/src/sfiii3/hud.tsv" obj/wide_src/hud_gen.c "$OUT/hud_hooks.tsv"
for c in obj/wide_src/*.c; do
    n=$(basename "$c" .c)
    SHC_TMP='tmp\wide' bin/shc.exe "obj\\wide_src\\$n.c" -cpu=sh2 -division=cpu -endian=big -pic=0 \
        -extra=m=8,a=8 -nortnext -include=include -optimize=1 -speed -object="obj\\wide_src\\$n.obj" \
        -listfile="obj\\wide_src\\$n.lis" -show=object \
        >"obj/wide_src/$n.log" 2>&1 || { cat "obj/wide_src/$n.log"; exit 1; }
    grep ') : ' "obj/wide_src/$n.log" || true
done

# the stock link script, plus the module and its sections
python3 -I - "$WIDE_ADDR" "$WIDE_CONST" obj/wide_src/*.obj <<'PY'
import sys
addr, caddr, objs = sys.argv[1], sys.argv[2], sys.argv[3:]
out = []
for line in open('sf3.sub'):
    line = line.rstrip('\n')
    if line.startswith('START '):
        line += f',PWIDE({addr}),CWIDE({caddr})'
    elif line == 'OUTPUT sf3.abs':
        out += ['INPUT ' + o.replace('/', '\\') for o in objs]
        line = 'OUTPUT sf3w.abs'
    elif line == 'PRINT sf3.map':
        line = 'PRINT sf3w.map'
    out.append(line)
open('sf3w.sub', 'w', newline='\r\n').write('\n'.join(out) + '\n')
PY
rm -f sf3w.abs sf3w.bin
if bin/lnk.exe -subcommand=sf3w.sub 2>&1 | grep -E '^\*\*|duplicate|UNDEFINED'; then
    echo 'link reported problems (above)'; exit 1
fi
bin/rof2bin.exe -s=06000000 -e=07000000 -v=00 sf3w.abs 2>&1 | grep -i 'cannot\|error' || true
[ -f sf3w.bin ] || { echo 'rof2bin wrote no sf3w.bin'; exit 1; }

echo '== hooks'
python3 -I "$ROOT/tools/hook.py" "$OUT/stock.bin" sf3w.bin sf3w.map "$ROOT/src/sfiii3/hooks.tsv,$OUT/hud_hooks.tsv" "$OUT/sf3w-hooked.bin"
cp sf3w.map "$OUT/"

echo '== MAME set'
python3 tools/cps3rom.py pack "$OUT/sf3w-hooked.bin" build/cg.bin rom/sfiii3nr1.zip "$OUT" 2>&1 | grep -v 'DIFFERS' || true
cp "$OUT/prog.bin" "$OUT/sfiii3nr1-wide-prog.bin"

echo '== patch'
# which of the patch's bytes are instructions (for Custom SH2 images, which store those encrypted)
python3 "$ROOT/tools/code_ranges.py" "$OUT/sf3w-hooked.bin" sf3w.map obj/wide_src \
    "$ROOT/src/sfiii3/hooks.tsv,$OUT/hud_hooks.tsv" "$OUT/code.json"
python3 -I "$ROOT/tools/make_patch.py" "$OUT/stock.bin" "$OUT/sf3w-hooked.bin" sfiii3nr1 "$OUT/sfiii3nr1-wide.json" \
    "$OUT/code.json" | head -1
ls -la "$OUT/sfiii3nr1.zip" "$OUT/sfiii3nr1-wide-prog.bin"
