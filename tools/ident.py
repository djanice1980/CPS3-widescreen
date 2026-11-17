#!/usr/bin/env python3
# Identify each Darksoft UltraSIMM program bank against MAME's CPS3 ROM CRCs, and work out
# which key the "Custom SH2" images are encrypted with.
#   ident.py <darksoft "SIMM 1-2" dir> <mame cps3.cpp>
import re
import sys
import zlib

import numpy as np

ROOT, CPP = sys.argv[1], sys.argv[2]
NBANK = 8

KEYS = {
    'redearth': (0x9e300ab1, 0xa175b82c),
    'sfiii': (0xb5fe053e, 0xfc03925a),
    'jojo': (0x02203ee3, 0x01301972),
    'sfiii3': (0xa55432b4, 0x0c129981),
    'jojoba': (0x23323ee3, 0x03021972),
}


def rotl16(v, n):
    return ((v << n) | (v >> (16 - n))) & 0xFFFF


def rotxor(val, xorval):
    res = (val + rotl16(val, 2)) & 0xFFFF
    return rotl16(res, 4) ^ (res & (val ^ xorval))


def mask_np(addr, key1, key2):
    # vectorised cps3_mask over a uint32 array of addresses
    a = (addr ^ np.uint32(key1)).astype(np.uint32)
    lo = (a & 0xFFFF).astype(np.uint32)
    hi = (a >> 16).astype(np.uint32)

    def rx(val, xv):
        res = (val + (((val << 2) | (val >> 14)) & 0xFFFF)) & 0xFFFF
        r4 = ((res << 4) | (res >> 12)) & 0xFFFF
        return (r4 ^ (res & (val ^ xv))) & 0xFFFF

    val = lo ^ 0xFFFF
    val = rx(val, key2 & 0xFFFF)
    val = val ^ hi ^ 0xFFFF
    val = rx(val, key2 >> 16)
    val = val ^ lo ^ (key2 & 0xFFFF)
    val = val.astype(np.uint32)
    return (val | (val << 16)).astype(np.uint32)


def load_words(u9, u10):
    a = np.frombuffer(open(u9, 'rb').read(), dtype='<u2').astype(np.uint32)
    b = np.frombuffer(open(u10, 'rb').read(), dtype='<u2').astype(np.uint32)
    return (a << 16) | b  # program words, per bank contiguous


crcs = {}
for m in re.finditer(r'ROM_LOAD\(\s*"([^"]+)",[^)]*CRC\(([0-9a-f]{8})\)', open(CPP).read()):
    crcs.setdefault(int(m.group(2), 16), []).append(m.group(1))


def lane_crcs(words):
    be = words.astype('>u4').tobytes()
    arr = np.frombuffer(be, dtype=np.uint8).reshape(-1, 4)
    return [zlib.crc32(arr[:, i].tobytes()) for i in range(4)]


for simm, base in ((1, 0x06000000), (2, 0x06800000)):
    std = load_words(f'{ROOT}/Standard SH2/SIMM{simm}_Jumper_U9_StandardSH2.bin',
                     f'{ROOT}/Standard SH2/SIMM{simm}_Jumper_U10_StandardSH2.bin')
    cus = load_words(f'{ROOT}/Custom SH2/SIMM{simm}_Jumper_U9_CustomSH2.bin',
                     f'{ROOT}/Custom SH2/SIMM{simm}_Jumper_U10_CustomSH2.bin')
    per = len(std) // NBANK
    addr = (np.arange(per, dtype=np.uint32) * 4 + base).astype(np.uint32)
    masks = {k: mask_np(addr, *v) for k, v in KEYS.items()}
    print(f'=== SIMM{simm} ({per * 4 // 1024 // 1024} MB per bank)')
    for bank in range(NBANK):
        s = std[bank * per:(bank + 1) * per]
        c = cus[bank * per:(bank + 1) * per]
        if not s.any():
            print(f' bank {bank}: empty')
            continue
        # which key turns standard into custom?
        x = s ^ c
        nz = x != 0
        custom_key = 'identical' if not nz.any() else None
        if custom_key is None:
            for k, mk in masks.items():
                if np.array_equal(x, mk):
                    custom_key = k
                    break
            if custom_key is None:
                for k, mk in masks.items():
                    frac = np.mean(x == mk)
                    if frac > 0.5:
                        custom_key = f'{k} ({frac:.4%} of words)'
                        break
        if custom_key is None:
            custom_key = f'unknown ({np.mean(nz):.2%} differ)'
        # match standard (plain) and each encryption against MAME CRCs
        found = []
        for label, w in [('plain', s)] + [(k, s ^ mk) for k, mk in masks.items()]:
            names = [crcs.get(cr, ['?'])[0] if cr in crcs else None for cr in lane_crcs(w)]
            if any(names):
                found.append(f'{label}: {names}')
        print(f' bank {bank}: custom={custom_key}')
        for f in found:
            print('    ', f)
