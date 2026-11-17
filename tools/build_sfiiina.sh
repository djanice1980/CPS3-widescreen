#!/usr/bin/env bash
# Build the New Generation (Darksoft bank 0) widescreen menu patch.
#   build_sfiiina.sh <bank 0 plain program, 16 MB>
# 1. the New Generation decomp's own link (sfn.bin, sfn.map): with bank 0's ROM pieces it is bank 0 exactly,
#    but for two pointers Darksoft changed
# 2. src/sfiiina/*.c compiled with New Generation's compiler settings, with object listings
# 3. tools/port_bank.py: the module linked alone against sfn.map's addresses, the hook written, the patch made
#    (build/sfiiina/sfiiina-wide.json and sfiiina-code.json)
# The module goes in 06444000+: bytes past the program's linked sections (06443022-0646A892, the decomp's
# tools/rom_pieces.tsv), left there by an earlier build; nothing in the program points into them.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NG="$ROOT/vendor/sfIII-cps3-decomp"
OUT="$ROOT/build/sfiiina"
BANK=$(realpath "$1")
export WINEPREFIX="${WINEPREFIX:-$ROOT/build/wineprefix}"
export WINEDEBUG=-all
mkdir -p "$OUT"
[ -d "$WINEPREFIX" ] || wineboot -i >/dev/null 2>&1 || true
# rof2bin makes temporary files in the root of the current drive: the decomp gets drive s: while this runs
ln -sfn "$NG" "$WINEPREFIX/dosdevices/s:"
trap 'ln -sfn "$ROOT/vendor/sfIII3-cps3-decomp" "$WINEPREFIX/dosdevices/s:"' EXIT
chmod +x "$NG"/bin/*.exe
cd "$NG"

echo '== New Generation decomp link'
make PYTHON=python3 SHC_TMP=tmp sfn.bin 2>&1 | grep -v 'MESA\|pci id\|SECTION *= \|^: ' | tail -2 || true

echo '== wide module'
export SHC_LIB=bin XJUMP_2I=2 MDL_IV_AUTOINC=1 MDL_MOD_CONST=3 MDL_IMM_REG=191 MDL_EQ_CONST=3 MDL_GCSE=26 \
    MDL_IV_START0=6 PEP_SWITCH_END=3 PEP_RETURN_EXIT=1   # New Generation's compiler revision (its Makefile)
rm -rf obj/wide_src && mkdir -p obj/wide_src tmp/wide
cp "$ROOT"/src/sfiiina/*.c obj/wide_src/
for c in obj/wide_src/*.c; do
    n=$(basename "$c" .c)
    SHC_TMP='tmp\wide' bin/shc.exe "obj\\wide_src\\$n.c" -cpu=sh2 -division=cpu -endian=big -pic=0 \
        -extra=m=8,a=8 -nortnext -include=include -optimize=1 -speed -object="obj\\wide_src\\$n.obj" \
        -listfile="obj\\wide_src\\$n.lis" -show=object >"obj/wide_src/$n.log" 2>&1 || true
    if grep ') : ' "obj/wide_src/$n.log" || [ ! -f "obj/wide_src/$n.obj" ]; then echo "$n.c did not compile"; exit 1; fi
done

echo '== port to bank 0'
python3 -I "$ROOT/tools/ng_stock.py" sfn.bin tools "$BANK" "$OUT/stock.bin"
python3 "$ROOT/tools/port_bank.py" "$BANK" sfiiina 06444000 06445000 "$OUT" --stock "$OUT/stock.bin" --map sfn.map \
    --full '' --hooks "$ROOT/src/sfiiina/hooks.tsv" --unused 06443022-0646A892 | grep -v 'MESA\|pci id'
