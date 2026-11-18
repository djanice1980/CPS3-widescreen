#!/usr/bin/env python3
"""Check a patched Custom SH2 bank against the patched Standard one and the pack it came from.

    check_custom.py <original pack dir> <patched pack dir> <bank> <code ranges .json> [<custom map .json>]

Rebuilds the Custom image the patch should give, independently of patch_darksoft.py. In a bank that stores
instructions encrypted (key 0), expected encrypted: every halfword the compiler's listing says is an instruction
of the patch (<code ranges .json> "code", from tools/code_ranges.py), changed or not, and the stock instructions
the patch brings to life ("stock", from tools/custom_gaps.py). Expected plain: the other halfwords the patched
Standard image changed. Every other halfword must be the original Custom image's, except the memory-test sum
byte. Whatever stock address the patch itself refers to is checked without the "stock" list. Then decrypts the
patched Custom image with that classification and compares it with the patched Standard image.

With a custom map (tools/custom_map.py; the two JoJo banks, whose Custom image in the pack is another revision):
the patched Custom image must be the patched Standard program with exactly these halfwords XORed with the key-0
mask: the listing's instructions (changed or not), the map's among the halfwords the patch left as they were,
and none of the other halfwords it changed. The original
Standard bank must be the program the map names, and each SIMM's byte sum must be the Standard file's.
"""
import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import custom_map  # noqa: E402
from cps3crypt import mask_table  # noqa: E402
from darksoft import read_program_bank  # noqa: E402

BASE = 0x06000000
SUM_FIX = [0x067FEE06, 0x06FFEE06]  # the halfwords holding the sum bytes


def byte_sums(img):
    half = len(img) // 2
    return [sum(img[s * half:(s + 1) * half].astype('>u2').tobytes()) % 256 for s in (0, 1)]


def check_rebuilt(os_, ps, pc, m, code, sumfix, bank, cmap):
    """A Custom image written anew from the Standard program (patch_darksoft.py --custom-map)."""
    if hashlib.sha256(os_.astype('>u2').tobytes()).hexdigest() != cmap['standard_sha256']:
        sys.exit(f'bank {bank}: the Standard bank is not the program the custom map was made for')
    changed = ps != os_
    inst = cmap['inst'].copy()
    inst[changed] = code[changed]
    inst |= code            # an instruction of the patch that equals the stock bytes at its address is one too
    lo, hi = np.nonzero(inst)[0][[0, -1]]
    expect = ps.copy()
    expect[inst] ^= m[inst]
    bad = (pc != expect) & ~sumfix
    print(f'bank {bank}: Custom image written from the Standard program; {int(inst.sum())} instruction halfwords '
          f'({int((changed & inst).sum())} of the {int(changed.sum())} the patch changed), code '
          f'{BASE + 2 * int(lo):08X}-{BASE + 2 * int(hi) + 1:08X}')
    if bad.any():
        idx = np.where(bad)[0][:8]
        sys.exit('MISMATCH at ' + ', '.join(f'{BASE + 2 * i:08X} (has {pc[i]:04X}, expected {expect[i]:04X})'
                                             for i in idx))
    # nothing outside the map may be encrypted, nothing inside it plain (a halfword whose mask is 0 has one form)
    plain_inst = inst & (pc == ps) & (m != 0)
    enc_data = ~inst & (pc != ps) & ~sumfix
    if plain_inst.any() or enc_data.any():
        sys.exit(f'{int(plain_inst.sum())} instructions stored plain, {int(enc_data.sum())} data halfwords changed')
    ss, cs = byte_sums(ps), byte_sums(pc)
    print('  ' + '  '.join(f'{name} SIMM{k + 1} byte sum {v[k]:02X}' for name, v in (('Standard', ss), ('Custom', cs))
                           for k in (0, 1)))
    if ss != cs:
        sys.exit('the Custom image\'s byte sums are not the Standard image\'s')
    print('OK: Custom = the patched Standard program with its instructions encrypted (key 0); decrypts back to it')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    pack, patched, bank, code_path = argv[0], argv[1], int(argv[2]), argv[3]
    map_path = argv[4] if len(argv) > 4 else None
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
    if map_path:
        return check_rebuilt(os_, ps, pc, m, code, sumfix, bank, custom_map.load(map_path))

    encrypted_bank = bool(((oc == (os_ ^ m)) & (oc != os_)).any())
    changed = ps != os_
    expect = oc.copy()
    # every instruction of the patch, also one that equals the stock bytes at its address (Darksoft's file may
    # hold those plain), and the stock instructions the patch brings to life ("stock", tools/custom_gaps.py)
    stock = np.zeros(len(os_), bool)
    for a, n in json.load(open(code_path)).get('stock', []):
        i = (int(a, 16) - BASE) // 2
        stock[i:i + n // 2] = True
    if (stock & (changed | code)).any():
        sys.exit(f'{code_path}: "stock" lists halfwords the patch changes or lists as its own instructions')
    enc_new = code & encrypted_bank
    enc_stock = stock & encrypted_bank
    expect[changed] = ps[changed]
    expect[enc_new] = ps[enc_new] ^ m[enc_new]
    expect[enc_stock] = os_[enc_stock] ^ m[enc_stock]
    bad = (pc != expect) & ~sumfix
    print(f'bank {bank}: stores instructions {"encrypted" if encrypted_bank else "plain"}; '
          f'{int(changed.sum())} halfwords changed by the patch; stored encrypted: {int(enc_new.sum())} instruction '
          f'halfwords of the patch ({int((enc_new & ~changed).sum())} of them equal to the stock bytes) and '
          f'{int(enc_stock.sum())} stock ones it brings to life')
    if bad.any():
        idx = np.where(bad)[0][:8]
        sys.exit('MISMATCH at ' + ', '.join(f'{BASE + 2 * i:08X} (has {pc[i]:04X}, expected {expect[i]:04X})'
                                             for i in idx))
    # decrypt: the original Custom image's encrypted halfwords, the patch's instructions and the listed stock ones
    was_enc = (oc == (os_ ^ m)) & (oc != os_) & ~changed
    dec = pc.copy()
    sel = was_enc | enc_new | enc_stock
    dec[sel] ^= m[sel]
    diff = (dec != ps) & ~sumfix
    if diff.any():
        sys.exit(f'decrypted Custom differs from Standard in {int(diff.sum())} halfwords')
    if encrypted_bank:
        # not from the list: what the patch itself refers to must not be an instruction stored plain
        nref, plain = plain_references(ps, pc, m, changed, code, sumfix)
        print(f'  the patch names or branches to {nref} stock addresses; stored plain where code follows: '
              f'{len(plain)}')
        if plain:
            sys.exit('STORED PLAIN: ' + ', '.join(f'{t:08X} ({why} at {src:08X})' for t, src, why in plain[:8])
                     + ': a stock instruction the patch runs that the Custom file does not encrypt; '
                     'tools/custom_gaps.py makes the list (make_pack.sh --build)')
    for name, img in (('Standard', ps), ('Custom', pc)):
        for s in (0, 1):
            half = img[s * len(img) // 2:(s + 1) * len(img) // 2].astype('>u2').tobytes()
            print(f'  {name} SIMM{s + 1} byte sum {sum(half) % 256:02X}', end='')
    print('\nOK: ' + ('Custom = Standard with the new instructions encrypted; decrypts back to Standard'
                     if encrypted_bank else 'Custom = Standard (this bank\'s Custom image is stored plain)'))


def plain_references(ps, pc, m, changed, code, sumfix, ahead=8):
    """A check that does not use the "stock" list. Every stock address the patch refers to: one its new data
    names (a 32-bit value at an even offset of the words it changed) or one its instructions branch to (bsr, bra,
    bt, bf). A branch target is an instruction and must be stored encrypted. A named address may be data; it is
    taken as an instruction stored plain when it is plain and one of the next `ahead` halfwords is encrypted
    (3rd Strike's 060A3F1A: the first instruction of a routine nothing in the stock game refers to).
    Returns (number of stock addresses referred to, [(address, where from, 'named' or 'branch target')])."""
    n = len(ps)
    inst_plain = (pc == ps) & (m != 0)
    inst_enc = (pc != ps) & ~sumfix
    ours = changed | code
    refs = {}
    v = (ps[:-1].astype(np.uint32) << 16) | ps[1:]
    data = (changed[:-1] | changed[1:]) & ~code[:-1] & ~code[1:]
    for i in np.nonzero(data & (v >= BASE + 0x400) & (v < BASE + 2 * n) & (v & 1 == 0))[0]:
        refs.setdefault(int(v[i]), (BASE + 2 * int(i), 'named'))
    for i in np.nonzero(code)[0]:
        op, a = int(ps[i]), BASE + 2 * int(i)
        if op >> 12 in (0xA, 0xB):
            d = op & 0xFFF
            refs[a + 4 + 2 * (d - 0x1000 if d & 0x800 else d)] = (a, 'branch target')
        elif op & 0xF900 == 0x8900:
            d = op & 0xFF
            refs[a + 4 + 2 * (d - 0x100 if d & 0x80 else d)] = (a, 'branch target')
    out, count = [], 0
    for t, (src, why) in sorted(refs.items()):
        i = (t - BASE) // 2
        if not 0 <= i < n or ours[i]:
            continue
        count += 1
        if inst_plain[i] and (why == 'branch target' or inst_enc[i + 1:i + 1 + ahead].any()):
            out.append((t, src, why))
    return count, out


if __name__ == '__main__':
    main()
