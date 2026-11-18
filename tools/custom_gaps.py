#!/usr/bin/env python3
"""Stock instructions a widescreen patch brings to life that Darksoft's Custom SH2 file stores plain.

    custom_gaps.py <pack dir> <bank> <patch .json> <code ranges .json>

Darksoft's Custom SH2 image of a game is the Standard program with every instruction halfword XORed with the
key-0 mask and the data left plain. Which halfwords are instructions came from an analysis of the stock program,
and that analysis has gaps: an instruction nothing in the stock game refers to can be stored plain (3rd Strike:
the first instruction of the SCREEN MODE item routine at 060A3F1A, which the stock settings page no longer
lists). The stock game never fetches such a halfword, so it does not matter there. A patch that calls the routine
makes it matter: the security cart's CPU would XOR the plain halfword with the mask and execute garbage.

This finds those halfwords for one bank, by the code flow of the program (tools/sh2map.py) before and after the
patch: a stock halfword (one the patch neither changes nor lists as its own instruction) that
  - the PATCHED program reaches as an instruction, and
  - the STOCK program does not, and
  - the pack's Custom file stores plain (equal to the Standard file's, where the mask is not 0).
The list goes into both files of the patch, as addresses and lengths only:
  <patch .json>         "stock_code": [[address hex, bytes], ...]   tools/patch_darksoft.py encrypts these
  <code ranges .json>   "stock": [[address hex, bytes], ...]        tools/check_custom.py expects them encrypted
tools/make_pack.sh --build runs this for every bank after it has refreshed patches/.

Instructions that the stock program reaches too and Darksoft stores plain are Darksoft's own gaps: they are in
the unpatched Custom file as well, the patch does not change them, and this only prints them. (Some of what the
flow analysis reports there is data: a table of pointers can read as instructions.)

A bank whose Custom file is not stored encrypted (4rd Strike's is the Standard program) gets empty lists.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sh2map  # noqa: E402
from cps3crypt import mask_table  # noqa: E402
from darksoft import read_program_bank  # noqa: E402

BASE = 0x06000000


def spans(addrs):
    """[[first address, bytes]] of the runs of consecutive halfword addresses."""
    out = []
    for a in sorted(addrs):
        if out and a == out[-1][0] + out[-1][1]:
            out[-1][1] += 2
        else:
            out.append([a, 2])
    return out


def chain(f, a):
    """How the flow got to a: the reference that led to it, and the ones that led to that."""
    seed, out = f.owner.get(a), []
    while seed is not None and len(out) < 5:
        out.append(f'{seed:08X} ({f.seed_src.get(seed)})')
        seed = f.parent.get(seed)
    return ' <- '.join(out)


def rewrite(path, key, value):
    """Set one key of a JSON file, keeping the file's layout (the indent it was written with)."""
    raw = open(path).read()
    doc = json.loads(raw)
    indent = next((i for i in (None, 0, 1, 2) if json.dumps(doc, indent=i) == raw), 1)
    doc.pop(key, None)
    doc[key] = value
    open(path, 'w').write(json.dumps(doc, indent=indent))


def find(std, cus, patch, log=print):
    """(the patch's list, Darksoft's own gaps), each [[address, bytes]]. std, cus: the bank's stock Standard
    and Custom images (16 MB, big-endian bytes)."""
    s16 = np.frombuffer(std, dtype='>u2')
    c16 = np.frombuffer(cus, dtype='>u2')
    m = mask_table(BASE, len(std))
    if not ((c16 == (s16 ^ m)) & (c16 != s16)).any():
        log('the Custom file is not stored encrypted: nothing to list')
        return [], []
    plain = (c16 == s16) & (m != 0)                 # Darksoft stores these halfwords plain
    patched = bytearray(std)
    own, changed = set(), set()                     # the patch's instructions; the halfwords it changes
    for r in patch['runs']:
        a, old, new = int(r['addr'], 16), bytes.fromhex(r['old']), bytes.fromhex(r['new'])
        if std[a - BASE:a - BASE + len(old)] != old:
            sys.exit(f'run {r["addr"]}: the Standard bank does not hold the bytes the patch replaces')
        patched[a - BASE:a - BASE + len(new)] = new
        own |= {a + o + k for o, n in r['code'] for k in range(0, n, 2)}
        changed |= {a + k for k in range(0, len(new), 2) if old[k:k + 2] != new[k:k + 2]}
    quiet = lambda line: None  # noqa: E731
    before = sh2map.analyze(std, BASE, log=quiet)
    after = sh2map.analyze(bytes(patched), BASE, log=quiet)
    stock = lambda a: a not in own and a not in changed and plain[(a - BASE) // 2]  # noqa: E731
    mine = spans(a for a in after.flow_code if a not in before.flow_code and stock(a))
    theirs = spans(a for a in after.flow_code if a in before.flow_code and stock(a))
    log(f'code flow: {len(before.flow_code)} instructions before the patch, {len(after.flow_code)} after')
    log(f'stock instructions only the patched program reaches, stored plain in the Custom file: '
        f'{sum(n for _, n in mine) // 2} halfwords in {len(mine)} runs')
    for a, n in mine:
        log(f'  {a:08X}+{n // 2}  reached from {chain(after, a)}')
    log(f'left as they are (the stock program reaches them too; Darksoft\'s own, or data that reads as code): '
        f'{sum(n for _, n in theirs) // 2} halfwords in {len(theirs)} runs')
    for a, n in theirs:
        log(f'  {a:08X}+{n // 2}  reached from {chain(before, a)}')
    return mine, theirs


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    pack, bank, patch_path, code_path = argv[0], int(argv[1]), argv[2], argv[3]
    root = os.path.join(pack, 'SIMM 1-2')
    patch = json.load(open(patch_path))
    print(f'bank {bank} ({os.path.basename(patch_path)}):')
    mine, _ = find(read_program_bank(root, bank, 'Standard'), read_program_bank(root, bank, 'Custom'), patch,
                   log=lambda line: print('  ' + line))
    out = [[f'{a:08X}', n] for a, n in mine]
    rewrite(patch_path, 'stock_code', out)
    rewrite(code_path, 'stock', out)


if __name__ == '__main__':
    main()
