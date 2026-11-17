#!/usr/bin/env python3
"""Darksoft CPS-3 graphics SIMMs (SIMM 3-6) <-> MAME's graphics chips, for one game bank.

Each SIMMn_Final.bin is 8 banks of 16 MB. In a bank, MAME's chip simm<n>.<i> (2 MB) is every other byte:
odd bytes for even i, even bytes for odd i, starting (3 - i // 2) * 2 MB into that byte lane. Found by matching
3rd Strike's chips against bank 5; check() proves it on all 32 of them.
"""
import zipfile

import numpy as np

BANK = 0x1000000
CHIP = 0x200000


def chips(pack_gfx_dir, bank):
    out = {}
    for n in (3, 4, 5, 6):
        a = np.memmap(f'{pack_gfx_dir}/SIMM{n}_Final.bin', np.uint8, 'r')
        blk = np.asarray(a[bank * BANK:(bank + 1) * BANK])
        lanes = (blk[0::2], blk[1::2])
        for i in range(8):
            lane = lanes[1 - i % 2]
            o = (3 - i // 2) * CHIP
            out[f'sfiii3-simm{n}.{i}'] = lane[o:o + CHIP].tobytes()
    return out


def check(pack_gfx_dir, rom):
    got = chips(pack_gfx_dir, 5)
    with zipfile.ZipFile(rom) as z:
        bad = [k for k, v in got.items() if z.read(k) != v]
    return bad


if __name__ == '__main__':
    import sys
    bad = check(sys.argv[1], sys.argv[2])
    print('all 32 chips match' if not bad else f'mismatch: {bad}')
