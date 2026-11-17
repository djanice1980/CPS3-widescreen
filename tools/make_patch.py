#!/usr/bin/env python3
"""Turn a widescreen build into a patch: the byte runs where it differs from the stock program.

    make_patch.py <stock prog> <wide prog> <game name> <out .json> [<code ranges .json>]

Each run carries the stock bytes it replaces, so the patcher can refuse an image that is not the one the patch
was made for. Both images are 06000000-06FFFFFF, plain (decrypted).

With tools/code_ranges.py's output, each run also lists the byte ranges of its new contents that are instructions
("code": [[offset in the run, length], ...]); a Custom SH2 image needs those encrypted and the rest plain.
"""
import json
import sys

BASE = 0x06000000
stock = open(sys.argv[1], 'rb').read()
wide = open(sys.argv[2], 'rb').read()
game, out = sys.argv[3], sys.argv[4]
code = json.load(open(sys.argv[5]))['code'] if len(sys.argv) > 5 else None
code = [(int(a, 16), n) for a, n in code] if code else None
assert len(stock) == len(wide)

runs = []
i = 0
while i < len(stock):
    if stock[i] == wide[i]:
        i += 1
        continue
    j = i
    while j < len(stock) and (stock[j] != wide[j] or (j + 8 < len(stock) and stock[j:j + 8] != wide[j:j + 8])):
        j += 1
    # whole 16-bit units, so a custom-cart encryption step can work on halfwords
    a, b = i & ~1, (j + 1) & ~1
    run = {'addr': f'{BASE + a:08X}', 'old': stock[a:b].hex(), 'new': wide[a:b].hex()}
    if code is not None:
        lo, hi = BASE + a, BASE + b
        run['code'] = [[max(c, lo) - lo, min(c + n, hi) - max(c, lo)] for c, n in code if c < hi and c + n > lo]
        assert all(o % 2 == 0 and n % 2 == 0 for o, n in run['code'])
    runs.append(run)
    i = b
if code is not None:
    covered = sum(n for r in runs for _, n in r['code'])
    if covered != sum(n for _, n in code):
        sys.exit(f'instruction ranges outside the patch runs ({covered} of {sum(n for _, n in code)} bytes covered)')
json.dump({'game': game, 'base': f'{BASE:08X}', 'runs': runs}, open(out, 'w'), indent=1)
print(f'{out}: {len(runs)} runs, {sum(len(r["new"]) // 2 for r in runs)} bytes')
for r in runs:
    print(f'  {r["addr"]} {len(r["new"]) // 2} bytes')
