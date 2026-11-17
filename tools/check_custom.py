#!/usr/bin/env python3
"""Check a patched Custom SH2 bank against the patched Standard one and the pack it came from.

    check_custom.py <original pack dir> <patched pack dir> <bank> <code ranges .json>

Rebuilds the Custom image the patch should give, independently of patch_darksoft.py: every halfword the
patched Standard image changed is expected encrypted (key 0) if the compiler's listing says it is an instruction
(<code ranges .json>, from tools/code_ranges.py) and the bank stores instructions encrypted, plain otherwise;
every other halfword must be the original Custom image's, except the memory-test sum byte. Then decrypts the
patched Custom image with that classification and compares it with the patched Standard image.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cps3crypt import mask_table  # noqa: E402
from darksoft import read_program_bank  # noqa: E402

BASE = 0x06000000
SUM_FIX = [0x067FEE06, 0x06FFEE06]  # the halfwords holding the sum bytes


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    pack, patched, bank, code_path = argv[0], argv[1], int(argv[2]), argv[3]
    ld = lambda p, k: np.frombuffer(read_program_bank(os.path.join(p, 'SIMM 1-2'), bank, k), dtype='>u2')
    os_, oc = ld(pack, 'Standard'), ld(pack, 'Custom')
    ps, pc = ld(patched, 'Standard'), ld(patched, 'Custom')
    m = mask_table(BASE, len(os_) * 2)
    code = np.zeros(len(os_), bool)
    for a, n in json.load(open(code_path))['code']:
        i = (int(a, 16) - BASE) // 2
        code[i:i + n // 2] = True
    sumfix = np.zeros(len(os_), bool)
    sumfix[[(a - BASE) // 2 for a in SUM_FIX]] = True

    encrypted_bank = bool(((oc == (os_ ^ m)) & (oc != os_)).any())
    changed = ps != os_
    expect = oc.copy()
    enc_new = changed & code & encrypted_bank
    expect[changed] = ps[changed]
    expect[enc_new] = ps[enc_new] ^ m[enc_new]
    bad = (pc != expect) & ~sumfix
    print(f'bank {bank}: stores instructions {"encrypted" if encrypted_bank else "plain"}; '
          f'{int(changed.sum())} halfwords changed by the patch, {int(enc_new.sum())} of them stored encrypted')
    if bad.any():
        idx = np.where(bad)[0][:8]
        sys.exit('MISMATCH at ' + ', '.join(f'{BASE + 2 * i:08X} (has {pc[i]:04X}, expected {expect[i]:04X})'
                                             for i in idx))
    # decrypt: the original Custom image's encrypted halfwords plus the patch's new instructions
    was_enc = (oc == (os_ ^ m)) & (oc != os_) & ~changed
    dec = pc.copy()
    sel = was_enc | enc_new
    dec[sel] ^= m[sel]
    diff = (dec != ps) & ~sumfix
    if diff.any():
        sys.exit(f'decrypted Custom differs from Standard in {int(diff.sum())} halfwords')
    for name, img in (('Standard', ps), ('Custom', pc)):
        for s in (0, 1):
            half = img[s * len(img) // 2:(s + 1) * len(img) // 2].astype('>u2').tobytes()
            print(f'  {name} SIMM{s + 1} byte sum {sum(half) % 256:02X}', end='')
    print('\nOK: ' + ('Custom = Standard with the new instructions encrypted; decrypts back to Standard'
                     if encrypted_bank else 'Custom = Standard (this bank\'s Custom image is stored plain)'))


if __name__ == '__main__':
    main()
