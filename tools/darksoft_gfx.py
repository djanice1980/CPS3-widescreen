#!/usr/bin/env python3
"""Darksoft CPS-3 graphics SIMMs (SIMM 3-6) <-> MAME's graphics chips, for one game bank.

Each SIMMn_Final.bin is 8 banks of 16 MB. In a bank, MAME's chip simm<n>.<i> (2 MB) is every other byte:
odd bytes for even i, even bytes for odd i, starting (3 - i // 2) * 2 MB into that byte lane. Found by matching
3rd Strike's chips against bank 5; check() proves it on all 32 of them.

Packs can hold more than one file for a SIMM: the 2021-04-02 pack has SIMM5_Final_MakotoFIX.bin and
SIMM5_Final_reTHIRD.bin, which differ only in bank 6 (Makoto Fix's graphics, and the same with the
reTHIRD mod).
Such a file is named by its suffix ('_MakotoFIX'); variants() says which suffixes give different graphics for a bank.
"""
import glob
import os
import zipfile

import numpy as np

BANK = 0x1000000
CHIP = 0x200000


def gfx_files(pack_gfx_dir):
    """{SIMM n: {suffix: path}} for SIMM<n>_Final<suffix>.bin; the old single files have suffix ''."""
    out = {}
    for n in (3, 4, 5, 6):
        stem = f'SIMM{n}_Final'
        fs = sorted(glob.glob(f'{glob.escape(pack_gfx_dir)}/{stem}*.bin'))
        if not fs:
            raise FileNotFoundError(f'{pack_gfx_dir}: no {stem}*.bin')
        out[n] = {os.path.basename(f)[len(stem):-4]: f for f in fs}
    return out


def bank_block(path, bank):
    return np.asarray(np.memmap(path, np.uint8, 'r')[bank * BANK:(bank + 1) * BANK])


def variants(pack_gfx_dir, bank):
    """The suffixes of the files that hold different graphics for this bank ([] when every SIMM has one choice)."""
    out = []
    for n, fs in gfx_files(pack_gfx_dir).items():
        paths = list(fs.values())
        first = bank_block(paths[0], bank)
        if any(not np.array_equal(first, bank_block(p, bank)) for p in paths[1:]):
            out += list(fs)
    return out


def chips(pack_gfx_dir, bank, variant=None):
    out = {}
    for n, fs in gfx_files(pack_gfx_dir).items():
        if variant in fs:
            path = fs[variant]
        else:
            path = next(iter(fs.values()))
            if any(not np.array_equal(bank_block(path, bank), bank_block(p, bank)) for p in fs.values()):
                raise ValueError(f'SIMM {n} bank {bank}: the files {sorted(fs)} differ, say which one to use')
        blk = bank_block(path, bank)
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
