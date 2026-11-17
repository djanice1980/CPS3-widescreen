#!/usr/bin/env python3
"""Pair the PC-relative literals of matching functions in two CPS3 programs (found with sigfind.py).

    litmap.py <from prog> <to prog> <from addr>=<to addr>[:<halfwords>] ...

Walks both in lockstep (default 64 halfwords; stops when the masked instructions stop matching) and prints
each MOV.L / MOV.W literal: from-value -> to-value.
"""
import re
import struct
import sys

sys.path.insert(0, __import__('os').path.dirname(__file__))
from sigfind import mask  # noqa: E402

BASE = 0x06000000


def main():
    a, b = open(sys.argv[1], 'rb').read(), open(sys.argv[2], 'rb').read()
    h = lambda d, x: struct.unpack_from('>H', d, x - BASE)[0]
    l = lambda d, x: struct.unpack_from('>I', d, x - BASE)[0]
    for arg in sys.argv[3:]:
        m = re.match(r'([0-9A-Fa-f]+)=([0-9A-Fa-f]+)(?::(\d+))?$', arg)
        x, y, n = int(m.group(1), 16), int(m.group(2), 16), int(m.group(3) or 64)
        print(f'== {x:08X} -> {y:08X}')
        seen = set()
        for i in range(n):
            p, q = x + 2 * i, y + 2 * i
            o1, o2 = h(a, p), h(b, q)
            if o1 & mask(o1) != o2 & mask(o1):
                print(f'   (differs at +{2 * i:X})')
                break
            if o1 >> 12 == 0xD:
                v1, v2 = l(a, (p & ~3) + 4 + 4 * (o1 & 0xFF)), l(b, (q & ~3) + 4 + 4 * (o2 & 0xFF))
            elif o1 >> 12 == 0x9:
                v1, v2 = h(a, p + 4 + 2 * (o1 & 0xFF)), h(b, q + 4 + 2 * (o2 & 0xFF))
            else:
                continue
            if (v1, v2) not in seen:
                seen.add((v1, v2))
                print(f'   +{2 * i:3X}  {v1:08X} -> {v2:08X}' + ('' if v1 == v2 else '   *'))


if __name__ == '__main__':
    main()
