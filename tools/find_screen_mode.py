#!/usr/bin/env python3
"""Find a CPS3 game's set_screen_mode (the routine that reads the 8-mode screen window table) and its callers.

    find_screen_mode.py <plain program image>

The table (8 rows of 9 halfwords, row 0 = 38, 80, 379, 454, 3, 21, 245, 262, 96) is the same in every CPS3
game seen so far. Its address sits in one literal pool; the mov.l that loads it is in the routine; the routine's
start is the address after it that other code calls (a literal equal to it, loaded for jsr). For each call the
"mov #imm,r4" setting the mode argument (before the jsr or in its delay slot) is reported.
"""
import struct
import sys

BASE = 0x06000000
x = open(sys.argv[1], 'rb').read()
hw = lambda a: struct.unpack('>H', x[a - BASE:a - BASE + 2])[0]
tbl = BASE + x.find(struct.pack('>9h', 38, 80, 379, 454, 3, 21, 245, 262, 96))
lits = [BASE + i for i in range(0, 0x800000, 4) if x[i:i + 4] == struct.pack('>I', tbl)]
print(f'table {tbl:08X}, literal(s) {[hex(a) for a in lits]}')
literal_index = {}
for i in range(0, 0x800000, 4):
    literal_index.setdefault(struct.unpack('>I', x[i:i + 4])[0], []).append(BASE + i)
for lit in lits:
    loads = [a for a in range(lit - 1020, lit, 2) if hw(a) >> 12 == 0xD and ((a & ~3) + 4 + (hw(a) & 0xFF) * 4) == lit]
    print(f'  loaded by mov.l at {[hex(a) for a in loads]}')
    for ld in loads:
        # the nearest start before the load that something calls
        for start in range(ld, ld - 0x400, -2):
            refs = literal_index.get(start, [])
            if refs:
                print(f'  routine starts {start:08X}, {len(refs)} literal(s) hold it')
                for r in refs:
                    # mov.l @(disp,pc),Rn loading r, then jsr @Rn: look for mov #imm,r4 near the jsr
                    for a in range(r - 1020, r, 2):
                        h = hw(a)
                        if h >> 12 == 0xD and ((a & ~3) + 4 + (h & 0xFF) * 4) == r:
                            n = (h >> 8) & 0xF
                            for j in range(a, a + 24, 2):
                                if hw(j) == (0x400B | n << 8):
                                    near = [(k, hw(k)) for k in range(j - 12, j + 4, 2) if hw(k) >> 8 == 0xE4]
                                    print(f'    call: load {a:08X}, jsr {j:08X}, mov #imm,r4: '
                                          + ', '.join(f'{k:08X}={v & 0xFF}' for k, v in near))
                                    break
                break
