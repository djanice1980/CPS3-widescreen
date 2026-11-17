#!/usr/bin/env python3
# Probe Darksoft UltraSIMM dual-flash (SIMM1/2) interleave: assemble big-endian 32-bit
# program words from the U9 and U10 images under several hypotheses and look for
# long ASCII strings in each 8 MB bank.
import re
import sys

u9_path, u10_path = sys.argv[1], sys.argv[2]
u9 = open(u9_path, 'rb').read()
u10 = open(u10_path, 'rb').read()
BANK = len(u9) // 8  # bytes per chip per bank


def assemble(a, b, swap_a, swap_b, order):
    # a, b: 16-bit lanes. order 0: a is high half, 1: b is high half
    out = bytearray(len(a) * 2)
    def lane(x, swap):
        if not swap:
            return x
        y = bytearray(len(x))
        y[0::2] = x[1::2]
        y[1::2] = x[0::2]
        return bytes(y)
    a = lane(a, swap_a)
    b = lane(b, swap_b)
    hi, lo = (a, b) if order == 0 else (b, a)
    out[0::4] = hi[0::2]
    out[1::4] = hi[1::2]
    out[2::4] = lo[0::2]
    out[3::4] = lo[1::2]
    return bytes(out)


pat = re.compile(rb'[ -~]{12,}')
for bank in range(8):
    a = u9[bank * BANK:(bank + 1) * BANK]
    b = u10[bank * BANK:(bank + 1) * BANK]
    best = None
    for swap_a in (0, 1):
        for swap_b in (0, 1):
            for order in (0, 1):
                d = assemble(a, b, swap_a, swap_b, order)
                hits = pat.findall(d)
                score = sum(len(h) for h in hits)
                if best is None or score > best[0]:
                    best = (score, swap_a, swap_b, order, d, hits)
    score, sa, sb, order, d, hits = best
    words = [int.from_bytes(d[i:i + 4], 'big') for i in range(0, 16, 4)]
    print(f'bank {bank}: score={score} swapU9={sa} swapU10={sb} U9high={order == 0} '
          f'head={" ".join(f"{w:08X}" for w in words)}')
    for h in sorted(set(hits), key=len, reverse=True)[:6]:
        print('    ', h[:90])
