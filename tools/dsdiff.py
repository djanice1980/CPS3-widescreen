#!/usr/bin/env python3
"""Compare a program image (06000000-06FFFFFF, plain) with one bank of the Darksoft program SIMMs.

    dsdiff.py <prog.bin> <darksoft "SIMM 1-2" dir> <bank> [Standard|Custom]

Prints each run of differing bytes with its address (and both sides' bytes for short runs).
"""
import sys

import numpy as np

from darksoft import read_program_bank

prog_path, root, bank = sys.argv[1], sys.argv[2], int(sys.argv[3])
kind = sys.argv[4] if len(sys.argv) > 4 else 'Standard'

prog = np.frombuffer(open(prog_path, 'rb').read(), dtype=np.uint8)
ds = np.frombuffer(read_program_bank(root, bank, kind), dtype=np.uint8)
n = min(len(prog), len(ds))
diff = np.nonzero(prog[:n] != ds[:n])[0]
print(f'{len(diff)} bytes differ of {n}')
runs = []
if len(diff):
    start = prev = diff[0]
    for d in diff[1:]:
        if d - prev > 16:
            runs.append((start, prev))
            start = d
        prev = d
    runs.append((start, prev))
for a, b in runs[:80]:
    size = b - a + 1
    line = f'  {0x06000000 + a:08X}-{0x06000000 + b:08X} ({size} bytes)'
    if size <= 24:
        line += f'  prog={prog[a:b + 1].tobytes().hex()}  ds={ds[a:b + 1].tobytes().hex()}'
    print(line)
if len(runs) > 80:
    print(f'  ... {len(runs) - 80} more runs')
