#!/usr/bin/env python3
"""List the decomp's functions that put cells on the text layer, and whether they already place by screen mode.

    ss_writers.py <decomp src dir>

A function counts as a writer if it calls one of the text-page primitives; "aware" if it reads DE_X or
Game_setting.Screen_Mode (its own wide placement).
"""
import os
import re
import sys

PRIMS = ('tilemap_put_cell', 'sc_ram_to_vram', 'sc_ram_to_vram_opc', 'sq_paint_chenge', 'tilemap_clear_rect',
         'scfont_sqput', 'tilemap_print_string', 'tilemap_print_string_attr', 'tilemap_print_hex_block',
         'score8x16_put', 'score16x24_put', 'Disp_Digit16x24', 'Disp_Digit8x16', 'sc_attr_put', 'sc_celllist_put',
         'sc_celllist_put_scr', 'sc_celllist_put_pos')
FUNC = re.compile(r'^[A-Za-z_][\w \*]*?\b(\w+)\s*\(([^;]*)$', re.M)

src = sys.argv[1]
for fn in sorted(os.listdir(src)):
    if not fn.endswith('.c'):
        continue
    text = open(os.path.join(src, fn), encoding='latin-1').read()
    starts = [(m.start(), m.group(1)) for m in FUNC.finditer(text) if m.group(1) not in ('if', 'for', 'while', 'switch')]
    for i, (pos, name) in enumerate(starts):
        body = text[pos:starts[i + 1][0] if i + 1 < len(starts) else len(text)]
        calls = sorted({p for p in PRIMS if re.search(rf'\b{p}\s*\(', body) and p != name})
        if not calls:
            continue
        aware = 'DE_X' in body or 'Screen_Mode' in body
        print(f'{fn:22} {name:32} {"aware" if aware else "-":5} {",".join(calls)}')
