#!/usr/bin/env python3
"""New Generation's whole program from the decomp's link and a plain program to take its ROM pieces from.

    ng_stock.py <sfn.bin> <decomp tools dir> <bank 0 plain program> <out>

sfn.bin leaves the parts no source builds as filler: the decomp's tools/rom_pieces.tsv lists them (graphics,
bytes past the linked sections) and tools/gaps.tsv gives the alignment-gap bytes. This copies the pieces from the
bank, writes the gaps, and reports how the result differs from the bank (Darksoft changed two pointers).
"""
import sys

BASE = 0x06000000
sfn, tools, bank_path, out = sys.argv[1:5]
prog = bytearray(open(sfn, 'rb').read())
bank = open(bank_path, 'rb').read()
for line in open(f'{tools}/rom_pieces.tsv'):
    f = line.rstrip('\n').split('\t')
    if line.startswith('#') or f[0] == 'start' or len(f) < 2:
        continue
    a, e = int(f[0], 16) - BASE, int(f[1], 16) - BASE
    prog[a:e] = bank[a:e]
for line in open(f'{tools}/gaps.tsv'):
    f = line.rstrip('\n').split('\t')
    if line.startswith('#') or f[0] == 'address' or len(f) < 2:
        continue
    a, h = int(f[0], 16) - BASE, bytes.fromhex(f[1])
    prog[a:a + len(h)] = h
prog += bank[len(prog):]
diff = [i for i in range(len(prog)) if prog[i] != bank[i]]
print(f'{out}: differs from the bank in {len(diff)} bytes: ' + ' '.join(f'{BASE + i:08X}' for i in diff[:16]))
if len(diff) > 16:
    sys.exit('more than the known Darksoft changes: not the program the decomp builds')
open(out, 'wb').write(prog)
