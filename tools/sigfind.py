#!/usr/bin/env python3
"""Find code from one CPS3 program in another (same compiler, other build): masked instruction signatures.

    sigfind.py <from prog> <to prog> <addr>[:<halfwords>] ...

Each address's code (default 24 halfwords) is matched with PC-relative displacements masked (MOV.L/MOV.W/MOVA
low byte, BRA/BSR 12 bits, BT/BF 8 bits), so code that moved still matches. Prints every match.
"""
import re
import struct
import sys

import numpy as np

BASE = 0x06000000


def mask(op):
    top = op >> 12
    if top in (0x9, 0xD) or op & 0xFF00 == 0xC700:
        return 0xFF00
    if top in (0xA, 0xB):
        return 0xF000
    if op & 0xFF00 in (0x8900, 0x8B00, 0x8D00, 0x8F00):
        return 0xFF00
    return 0xFFFF


def main():
    a = open(sys.argv[1], 'rb').read()
    b = np.frombuffer(open(sys.argv[2], 'rb').read(), dtype='>u2').astype(np.uint32)
    for arg in sys.argv[3:]:
        m = re.match(r'([0-9A-Fa-f]+)(?::(\d+))?$', arg)
        addr, n = int(m.group(1), 16), int(m.group(2) or 24)
        ops = [struct.unpack_from('>H', a, addr - BASE + 2 * i)[0] for i in range(n)]
        ms = [mask(o) for o in ops]
        cand = np.ones(len(b) - n, dtype=bool)
        for i, (o, k) in enumerate(zip(ops, ms)):
            cand &= (b[i:len(b) - n + i] & k) == (o & k)
        hits = [BASE + 2 * int(i) for i in np.nonzero(cand)[0]]
        print(f'{addr:08X}:{n} -> ' + (' '.join(f'{h:08X}' for h in hits[:8]) or 'none') +
              (f' (+{len(hits) - 8})' if len(hits) > 8 else ''))


if __name__ == '__main__':
    main()
