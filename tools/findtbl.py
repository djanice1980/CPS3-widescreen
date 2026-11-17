#!/usr/bin/env python3
# Find the decomp's screen_window_tbl (s16 big-endian) in each Darksoft program bank, and report
# the bank's address of it and of a few function entry points from the decomp's functions.tsv.
#   findtbl.py <darksoft "SIMM 1-2" dir> <decomp functions.tsv>
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ident_lib import load_words  # noqa: E402

ROOT, TSV = sys.argv[1], sys.argv[2]
std = load_words(f'{ROOT}/Standard SH2/SIMM1_Jumper_U9_StandardSH2.bin', f'{ROOT}/Standard SH2/SIMM1_Jumper_U10_StandardSH2.bin')
per = len(std) // 8
tbl = struct.pack('>9h', 38, 80, 379, 454, 3, 21, 245, 262, 96)

funcs = {}
for line in open(TSV):
    p = line.rstrip('\n').split('\t')
    if len(p) >= 3 and p[2] in ('set_screen_mode', 'display_mode_setup', 'range_x_check', 'game_config_force_wide'):
        funcs[p[2]] = (int(p[0], 16), int(p[1]))

for bank in range(8):
    data = std[bank * per:(bank + 1) * per].astype('>u4').tobytes()
    at = data.find(tbl)
    where = f'0x{0x06000000 + at:08X}' if at >= 0 else 'not found'
    print(f'bank {bank}: screen_window_tbl at {where}')
    if at >= 0:
        for name, (addr, size) in funcs.items():
            off = addr - 0x06000000
            print(f'    {name:24s} {addr:08X}: {data[off:off + 8].hex()}')
