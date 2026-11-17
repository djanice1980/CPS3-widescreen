#!/usr/bin/env python3
"""Name the writers in an sstap.lua log from a linker map.

    tapnames.py <map> <tap.txt> [first frame] [last frame]

Groups by the function holding PR (the caller of the writer), keeping only entries active in the frame window.
"""
import bisect
import re
import sys
from collections import defaultdict

syms = sorted((int(a, 16), n) for n, a in re.findall(r"^_(\w+)\s+H'([0-9A-F]{8})\s+ENT", open(sys.argv[1], encoding='latin-1').read(), re.M))
addrs = [a for a, _ in syms]


def name(a):
    i = bisect.bisect_right(addrs, a) - 1
    return f'{syms[i][1]}+{a - syms[i][0]:X}' if i >= 0 else f'{a:08X}'


f0 = int(sys.argv[3]) if len(sys.argv) > 3 else 0
f1 = int(sys.argv[4]) if len(sys.argv) > 4 else 1 << 30
by = defaultdict(list)
for line in open(sys.argv[2]):
    m = re.match(r'(\w+) (\w+) n=(\d+) rows=(\d+)-(\d+) cols=(\d+)-(\d+) frames=(\d+)-(\d+)', line)
    pc, pr, n, r0, r1, c0, c1, a, b = m.groups()
    if int(b) < f0 or int(a) > f1:
        continue
    caller = name(int(pr, 16)).split('+')[0]
    by[caller].append((name(int(pc, 16)), int(n), int(r0), int(r1), int(c0), int(c1), int(a), int(b)))
for caller in sorted(by):
    rows = by[caller]
    print(f'{caller}: n={sum(r[1] for r in rows)} rows={min(r[2] for r in rows)}-{max(r[3] for r in rows)} '
          f'cols={min(r[4] for r in rows)}-{max(r[5] for r in rows)} frames={min(r[6] for r in rows)}-{max(r[7] for r in rows)} '
          f'via {sorted(set(r[0].split("+")[0] for r in rows))}')
