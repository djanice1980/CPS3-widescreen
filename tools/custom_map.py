#!/usr/bin/env python3
"""The instruction map of a bank's Standard SH2 program: which halfwords the CPU fetches as instructions.

    custom_map.py make <pack dir> <bank> <game name> <out .json>
    custom_map.py validate <pack dir> <bank>

A Custom SH2 (security cart, key 0) image stores instruction halfwords XORed with the key-0 mask and data plain.
For banks 0, 1, 5 and 6 Darksoft's Custom file is the Standard program stored that way, so the patch only has to
say which of its own bytes are instructions. For the two JoJo games (banks 3 and 4) Darksoft's Custom files hold
another revision of the game, which the patch does not fit. `make` works out the split of the Standard program
itself, so that a Custom image of the revision the patch is made for can be written (tools/patch_darksoft.py
--custom-map). Sources, per halfword:

  flow     tools/sh2map.py: recursive descent through the plain program from every reference;
  sweep    the same analysis' unreferenced stretches that explore cleanly as code;
  lineup   Darksoft's Custom file of the other revision, where the two revisions line up: a Standard halfword in
           a run of 8 or more halfwords equal to the Custom file's is data there; equal after XOR with the mask of
           the Custom address, an instruction.

  instruction = flow, or sweep unless Darksoft's file has that stretch as data. Everything else is data.

What the analysis leaves unknown stays data even where Darksoft's file has an instruction: those are the byte
tables of the compiler's shift routines, which Darksoft's files store encrypted although the routines read them
(seen in MAME: JoJo HFTF reads 061C36E8 as data; 3rd Strike has the same table at 0612D8EC).

The map file holds no program bytes: the SHA-256 of the Standard bank it describes and the lengths of the
alternating data / instruction runs.

`validate` runs the program-only part (flow and sweep) on a bank whose Custom file is the same program and
compares with Darksoft's split (Standard XOR Custom).
"""
import hashlib
import json
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cps3crypt import mask_table  # noqa: E402
from darksoft import read_program_bank  # noqa: E402

BASE = 0x06000000
SIZE = 0x01000000
LINEUP_BYTES = 0x200000    # the programs' code lies in the first 2 MB


# the map file

def encode_runs(inst):
    """Lengths of the alternating runs of a bool array, the first a data run (0 if it starts with an instruction)."""
    inst = np.asarray(inst, bool)
    edges = np.nonzero(np.diff(inst.view(np.int8)))[0] + 1
    bounds = np.concatenate(([0], edges, [len(inst)]))
    runs = np.diff(bounds).tolist()
    if inst[0]:
        runs = [0] + runs
    if len(runs) % 2 == 0:          # ends with an instruction run: fine; drop a trailing data run instead
        return runs
    return runs[:-1]


def decode_runs(runs, n):
    inst = np.zeros(n, bool)
    at = 0
    for k, length in enumerate(runs):
        if k & 1:
            inst[at:at + length] = True
        at += length
    if at > n:
        raise ValueError('the map is longer than the program')
    return inst


def load(path):
    """{'sha256': ..., 'inst': bool per halfword of 06000000-06FFFFFF, ...} from a map file."""
    m = json.load(open(path))
    if m.get('format') != 'cps3ws-custom-map-1':
        sys.exit(f'{path} is not a Custom SH2 instruction map')
    m['inst'] = decode_runs(m['runs'], SIZE // 2)
    if int(m['inst'].sum()) != m['instructions']:
        sys.exit(f'{path} is damaged (its runs do not add up)')
    return m


def patched_instructions(inst, runs, base=BASE):
    """The map of the patched program: a halfword the patch changes is an instruction if the patch says so (its
    'code' ranges, from the compiler's listing and the map of the code it copies); the others keep the stock
    program's split."""
    out = inst.copy()
    for r in runs:
        addr, old, new = int(r['addr'], 16), bytes.fromhex(r['old']), bytes.fromhex(r['new'])
        code = {o + k for o, n in r['code'] for k in range(0, n, 2)}
        for k in range(0, len(new), 2):
            if old[k:k + 2] != new[k:k + 2]:
                out[(addr + k - base) // 2] = k in code
    return out


def encrypt(plain, inst, base):
    """plain (bytes of base ..) with the halfwords marked in inst (bool per halfword) XORed with the key-0 mask."""
    hw = np.frombuffer(bytes(plain), dtype='>u2').astype(np.uint16)
    idx = np.nonzero(inst)[0]
    if len(idx):
        lo, hi = int(idx[0]) & ~1, (int(idx[-1]) | 1) + 1
        m = mask_table(base + 2 * lo, 2 * (hi - lo))
        sel = inst[lo:hi]
        hw[lo:hi][sel] ^= m[sel]
    return hw.astype('>u2').tobytes()


# lining the two revisions up

def run_mask(v, n=8):
    """True where v is True in a run of at least n."""
    v = np.asarray(v, bool)
    d = np.diff(np.concatenate(([0], v.view(np.int8), [0])))
    out = np.zeros(len(v), bool)
    for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
        if b - a >= n:
            out[a:b] = True
    return out


def lineup(sb, cb, nbytes=LINEUP_BYTES, minrun=8, log=print):
    """(as instruction, as data): bool per halfword of the first nbytes of the Standard program sb, from the Custom
    file cb of another revision."""
    m = mask_table(BASE, nbytes)
    std = np.frombuffer(sb[:nbytes], dtype='>u2').astype(np.uint16)
    cus = np.frombuffer(cb[:nbytes], dtype='>u2').astype(np.uint16)
    dec = cus ^ m
    db = dec.astype('>u2').tobytes()
    # offsets: 12-byte windows of the Standard file found once in the Custom file, as stored or decoded
    votes = Counter()
    for img in (cb[:nbytes], db):
        idx = {}
        for o in range(0, nbytes - 12, 4):
            k = img[o:o + 12]
            if k.count(0) < 4 and len(set(k)) > 5:
                idx[k] = -1 if k in idx else o
        for o in range(0, nbytes - 12, 4):
            p = idx.get(sb[o:o + 12])
            if p is not None and p >= 0:
                votes[p - o] += 1
    top = sorted(d for d, c in votes.items() if c >= 4)
    log(f'the two revisions line up at {len(top)} offsets')
    n = len(std)
    used = std != 0
    as_data = np.zeros(n, bool)
    as_code = np.zeros(n, bool)
    for d in top:
        h = d // 2
        a0, a1 = max(0, -h), min(n, n - h)
        s = std[a0:a1]
        as_data[a0:a1] |= run_mask((cus[a0 + h:a1 + h] == s) & used[a0:a1], minrun)
        as_code[a0:a1] |= run_mask((dec[a0 + h:a1 + h] == s) & used[a0:a1] & (m[a0 + h:a1 + h] != 0), minrun)
    both = as_code & as_data          # lines up both ways at different offsets: says nothing
    return as_code & ~both, as_data & ~both


def analyze(std, log=print):
    """(flow, sweep, known data, code regions) as bool arrays per halfword, from tools/sh2map.py."""
    import sh2map
    f = sh2map.analyze(std, BASE, log)
    n = len(std) // 2

    def arr(addrs):
        a = np.zeros(n, bool)
        a[[(x - BASE) // 2 for x in addrs if BASE <= x < BASE + len(std)]] = True
        return a
    flow = arr(f.flow_code)
    sweep = arr(f.code - f.flow_code)
    data = arr(set(f.lit) | f.table_hw)
    region = np.zeros(n, bool)
    for lo, hi in f.regions:
        region[(lo - BASE) // 2:(hi - BASE) // 2] = True
    return flow, sweep, data, region, f


def make(pack, bank, game, out, log=print):
    root = os.path.join(pack, 'SIMM 1-2')
    std = read_program_bank(root, bank, 'Standard')
    cus = read_program_bank(root, bank, 'Custom')
    flow, sweep, data, region, f = analyze(std, log)
    li, ld = lineup(std, cus, log=log)
    n = len(std) // 2
    as_i, as_d = np.zeros(n, bool), np.zeros(n, bool)
    as_i[:len(li)], as_d[:len(ld)] = li, ld
    unknown = region & ~flow & ~sweep & ~data
    inst = flow | (sweep & ~as_d)
    if (inst & data).any() or (inst & ~region).any():
        sys.exit('the map contradicts itself')      # cannot happen by construction
    rows = [('flow', flow), ('sweep', sweep), ('PC-relative data, switch tables', data), ('unknown', unknown)]
    stats = {}
    log(f'bank {bank}: code ' + ', '.join(f'{lo:08X}-{hi:08X}' for lo, hi in f.regions))
    log(f'{"":34}{"halfwords":>10}{"Custom: instr.":>16}{"Custom: data":>14}{"no counterpart":>16}{"-> instr.":>11}')
    for name, sel in rows:
        row = [int(sel.sum()), int((sel & as_i).sum()), int((sel & as_d).sum()),
               int((sel & ~as_i & ~as_d).sum()), int((sel & inst).sum())]
        stats[name] = row
        log(f'{name:34}{row[0]:10}{row[1]:16}{row[2]:14}{row[3]:16}{row[4]:11}')
    runs = encode_runs(inst)
    m = {'format': 'cps3ws-custom-map-1', 'game': game, 'bank': bank, 'base': f'{BASE:08X}',
         'standard_sha256': hashlib.sha256(std).hexdigest(),
         'code_regions': [[f'{lo:08X}', f'{hi:08X}'] for lo, hi in f.regions],
         'instructions': int(inst.sum()), 'evidence': stats, 'runs': runs}
    assert np.array_equal(decode_runs(runs, n), inst)
    with open(out, 'w') as h:
        json.dump(m, h, separators=(',', ':'))
        h.write('\n')
    log(f'{out}: {m["instructions"]} instruction halfwords in {len(runs) // 2} runs')


def validate(pack, bank, log=print):
    root = os.path.join(pack, 'SIMM 1-2')
    std = read_program_bank(root, bank, 'Standard')
    cus = read_program_bank(root, bank, 'Custom')
    s16, c16 = np.frombuffer(std, dtype='>u2'), np.frombuffer(cus, dtype='>u2')
    m = mask_table(BASE, len(std))
    blind = m == 0                         # mask 0: both forms are the same bytes
    truth = (c16 == (s16 ^ m)) & ~blind
    if not truth.any() or int(((c16 != s16) & ~truth).sum()) > 16:
        sys.exit(f'bank {bank}: the Custom file is not the Standard program with its instructions encrypted')
    flow, sweep, data, region, f = analyze(std, log)
    both = (flow | sweep) & ~blind
    flow = flow & ~blind
    log(f"bank {bank}: Darksoft's Custom file has {int(truth.sum())} instruction halfwords")
    for name, sel in (('flow', flow), ('flow and sweep', both)):
        log(f'  {name:15}: {int((sel & truth).sum())} agree, {int((truth & ~sel).sum())} of Darksoft\'s not found, '
            f'{int((sel & ~truth).sum())} found that Darksoft stores plain')
    return int((truth & ~both).sum()), int((both & ~truth).sum())


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 5 and argv[0] == 'make':
        make(argv[1], int(argv[2]), argv[3], argv[4])
    elif len(argv) == 3 and argv[0] == 'validate':
        validate(argv[1], int(argv[2]))
    else:
        sys.exit(__doc__.split('\n\n')[0] + '\n\n' + '\n'.join(__doc__.split('\n')[2:4]))


if __name__ == '__main__':
    main()
