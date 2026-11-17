#!/usr/bin/env python3
# Per bank of the Darksoft program SIMMs: check the custom-cart images against the key-0 mask
# (dead security cart), compare the 3rd Strike banks with each other, and find version strings.
#   banks.py <darksoft "SIMM 1-2" dir>
import re
import sys

import numpy as np

import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ident_lib import load_words, mask_np  # noqa: E402

ROOT = sys.argv[1]
NBANK = 8
std = load_words(f'{ROOT}/Standard SH2/SIMM1_Jumper_U9_StandardSH2.bin', f'{ROOT}/Standard SH2/SIMM1_Jumper_U10_StandardSH2.bin')
cus = load_words(f'{ROOT}/Custom SH2/SIMM1_Jumper_U9_CustomSH2.bin', f'{ROOT}/Custom SH2/SIMM1_Jumper_U10_CustomSH2.bin')
per = len(std) // NBANK
addr = (np.arange(per, dtype=np.uint32) * 4 + 0x06000000).astype(np.uint32)
m0 = mask_np(addr, 0, 0)

for bank in range(NBANK):
    s = std[bank * per:(bank + 1) * per]
    c = cus[bank * per:(bank + 1) * per]
    x = s ^ c
    nz = x != 0
    # a word fully key-0 encrypted, or only one 16-bit half of it (one instruction of the pair)
    full = np.sum(nz & (x == m0))
    hi = np.sum(nz & ((x & 0xFFFF0000) == (m0 & 0xFFFF0000)) & ((x & 0xFFFF) == 0))
    lo = np.sum(nz & ((x & 0xFFFF) == (m0 & 0xFFFF)) & ((x & 0xFFFF0000) == 0))
    other = int(np.sum(nz)) - int(full) - int(hi) - int(lo)
    be = s.astype('>u4').tobytes()
    dates = sorted(set(re.findall(rb'9[6-9][01]\d[0-3]\d', be)))[:8]
    print(f'bank {bank}: differ={int(np.sum(nz))} key0-full={full} key0-hi={hi} key0-lo={lo} other={other}')
    title = re.findall(rb'[A-Z][A-Z0-9 .:\'&-]{14,}', be)[:6]
    print('    dates:', dates)
    print('    text :', title)

b = [std[k * per:(k + 1) * per] for k in range(NBANK)]
for i, j in ((5, 6), (5, 7), (6, 7), (0, 2)):
    d = np.nonzero(b[i] != b[j])[0]
    print(f'bank {i} vs {j}: {len(d)} words differ', '' if not len(d) else f'first at 0x{0x06000000 + d[0] * 4:08X}, last 0x{0x06000000 + d[-1] * 4:08X}')
