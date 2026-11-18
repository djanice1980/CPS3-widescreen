#!/usr/bin/env python3
"""Apply a widescreen patch to one game bank of a Darksoft CPS-3 UltraSIMM pack.

    patch_darksoft.py <pack dir> <patch .json> <bank 0-7> <out dir> [--kind Standard|Custom|both]
                      [--in-place] [--custom-map <map .json>]

<pack dir> holds "SIMM 1-2" and "SIMM 3-6" as the Darksoft pack has them. <out dir> gets a copy of the pack with
the program SIMM files (SIMM1/SIMM2, U9 and U10) of the chosen kind(s) patched; the graphics SIMMs are copied as
they are (only "SIMM 1-2" and "SIMM 3-6" are copied, nothing else that is in <pack dir>). With --in-place, <out dir> must already be such a copy (another bank of it patched, say) and is
patched where it is. Before writing anything it checks, run by run, that the bank holds the stock bytes the
patch expects.

The test menu's memory test checks each program SIMM's byte sum (mod 256) against a value the board stores, and
Darksoft keeps that sum with one adjusting byte (06x7FEE07): the patcher sets that byte again so each file's sum
is what it was.

Custom SH2 images (for an original security cart, its key reset to 0) store each instruction halfword XORed with
the key-0 mask of its address and data plain. The patch lists which of its new bytes are instructions (from the
compiler's listings, tools/code_ranges.py); those are stored encrypted, the rest plain. A bank whose Custom image
Darksoft stored unencrypted (4rd Strike's is the same file as its Standard one) is patched the same way, plain.

--custom-map is for a bank whose Custom image is not the program the patch was made for (Darksoft's Custom files
of the two JoJo games hold another revision): the bank's Custom image is written anew from its Standard program,
patched, with every instruction halfword encrypted. Which halfwords of the Standard program are instructions is
what the map says (tools/custom_map.py); the map names the program it describes by its SHA-256, and any other
program is refused. The new image's byte sums are the Standard image's, as Darksoft has them for the banks whose
Custom file is the Standard program.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import custom_map  # noqa: E402
from cps3crypt import mask16  # noqa: E402
from darksoft import NBANK, read_simm_words, simm_paths, split_simm_words  # noqa: E402

SIMM_BASE = {1: 0x06000000, 2: 0x06800000}
SUM_FIX = {1: 0x067FEE07, 2: 0x06FFEE07}


def halfwords(b):
    return [int.from_bytes(b[i:i + 2], 'big') for i in range(0, len(b), 2)]


def code_halfwords(run):
    """Offsets (bytes, in the run) of the halfwords that are instructions."""
    return {o + k for o, n in run['code'] for k in range(0, n, 2)}


def stored_form(bank, runs, base, kind):
    """'plain' or 'encrypted': how this bank's image stores instructions, judged from the bytes the patch
    replaces. Stops if a halfword matches neither form of the stock bytes."""
    if kind == 'Standard':
        form = 'plain'
    enc = 0
    for r in runs:
        addr, old = int(r['addr'], 16), bytes.fromhex(r['old'])
        off = addr - base
        for k, s in enumerate(halfwords(old)):
            a = addr + 2 * k
            v = int.from_bytes(bank[off + 2 * k:off + 2 * k + 2], 'big')
            m = mask16(a)
            if v == s:
                continue
            if kind == 'Custom' and v == s ^ m:
                enc += 1
                continue
            return None, f'{a:08X} holds {v:04X}, the patch expects {s:04X}'
    if kind == 'Custom':
        form = 'encrypted' if enc else 'plain'
    return form, None


def patch_bank(bank, runs, base, form):
    for r in runs:
        addr, old, new = int(r['addr'], 16), bytes.fromhex(r['old']), bytes.fromhex(r['new'])
        off = addr - base
        code = code_halfwords(r)
        for k, (o, n) in enumerate(zip(halfwords(old), halfwords(new))):
            if o == n:
                continue  # keep the image's own form of bytes the patch does not change
            if form == 'encrypted' and 2 * k in code:
                n ^= mask16(addr + 2 * k)
            bank[off + 2 * k:off + 2 * k + 2] = n.to_bytes(2, 'big')


def rebuild_custom(src, patch, bank_no, cmap):
    """The bank's Custom image made from its Standard program: patched, then every instruction halfword (the
    map's, and the patch's own) XORed with the key-0 mask. Returns the entries main() writes."""
    root = os.path.join(src, 'SIMM 1-2')
    banks, sums = {}, {}
    for simm in (1, 2):
        words = read_simm_words(*simm_paths(root, simm, 'Standard'))
        per = len(words) // NBANK
        banks[simm] = bytearray(words[bank_no * per:(bank_no + 1) * per].astype('>u4').tobytes())
        sums[simm] = sum(banks[simm]) % 256
    if hashlib.sha256(bytes(banks[1] + banks[2])).hexdigest() != cmap['standard_sha256']:
        sys.exit(f'Standard bank {bank_no} is not the program the Custom SH2 map was made for; nothing written')
    inst = custom_map.patched_instructions(cmap['inst'], patch['runs'])
    half = len(inst) // 2
    out = []
    for simm in (1, 2):
        base = SIMM_BASE[simm]
        runs = [r for r in patch['runs'] if base <= int(r['addr'], 16) < base + 0x800000]
        form, err = stored_form(banks[simm], runs, base, 'Standard')
        if err:
            sys.exit(f'Standard SIMM{simm} bank {bank_no}: {err}: not the program this patch was made for; '
                     'nothing written')
        patch_bank(banks[simm], runs, base, 'plain')
        sel = inst[(simm - 1) * half:simm * half]
        image = bytearray(custom_map.encrypt(banks[simm], sel, base))
        fix = SUM_FIX[simm] - base
        if sel[fix // 2]:
            sys.exit('the map marks the sum byte as an instruction')
        image[fix] = (image[fix] + sums[simm] - sum(image)) % 256
        assert sum(image) % 256 == sums[simm]
        u9, u10 = simm_paths(root, simm, 'Custom')
        words = read_simm_words(u9, u10).copy()
        per = len(words) // NBANK
        words[bank_no * per:(bank_no + 1) * per] = np.frombuffer(bytes(image), dtype='>u4').astype(np.uint32)
        out.append(('Custom', simm, u9, u10, words, len(runs), int(sel.sum()), sums[simm]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('pack')
    ap.add_argument('patch')
    ap.add_argument('bank', type=int)
    ap.add_argument('out')
    ap.add_argument('--kind', default='both', choices=['Standard', 'Custom', 'both'])
    ap.add_argument('--in-place', action='store_true')
    ap.add_argument('--custom-map')
    a = ap.parse_args(argv)
    patch = json.load(open(a.patch))
    kinds = ['Standard', 'Custom'] if a.kind == 'both' else [a.kind]
    if 'Custom' in kinds and any('code' not in r for r in patch['runs']):
        sys.exit(f'{a.patch} does not say which bytes are instructions: remake it with tools/code_ranges.py')

    src = a.out if a.in_place else a.pack
    if not os.path.isdir(os.path.join(src, 'SIMM 1-2')):
        sys.exit(f'{src}: no "SIMM 1-2" folder (give the folder that holds "SIMM 1-2" and "SIMM 3-6")')

    # read and patch everything in memory first; write only if every bank checks out
    out = []
    for kind in kinds:
        if kind == 'Custom' and a.custom_map:
            out += rebuild_custom(src, patch, a.bank, custom_map.load(a.custom_map))
            continue
        loaded = []
        for simm in (1, 2):
            runs = [r for r in patch['runs'] if SIMM_BASE[simm] <= int(r['addr'], 16) < SIMM_BASE[simm] + 0x800000]
            if not runs:
                continue
            u9, u10 = simm_paths(os.path.join(src, 'SIMM 1-2'), simm, kind)
            words = read_simm_words(u9, u10)
            per = len(words) // NBANK
            bank = bytearray(words[a.bank * per:(a.bank + 1) * per].astype('>u4').tobytes())
            before = sum(bank) % 256
            form, err = stored_form(bank, runs, SIMM_BASE[simm], kind)
            if err:
                sys.exit(f'{kind} SIMM{simm} bank {a.bank}: {err}: not the program this patch was made for; '
                         'nothing written')
            loaded.append((simm, u9, u10, words, per, bank, runs, form, before))
        # the storage form is the bank's, not a SIMM's: a SIMM whose replaced bytes were never encrypted (empty
        # SIMM 2 space, as in Warzard) shows no evidence; any encrypted SIMM decides it for the whole bank
        form = 'encrypted' if any(f == 'encrypted' for *_, f, _b in loaded) else 'plain'
        for simm, u9, u10, words, per, bank, runs, _, before in loaded:
            patch_bank(bank, runs, SIMM_BASE[simm], form)
            fix = SUM_FIX[simm] - SIMM_BASE[simm]
            bank[fix] = (bank[fix] + before - sum(bank)) % 256
            assert sum(bank) % 256 == before
            words = words.copy()
            words[a.bank * per:(a.bank + 1) * per] = np.frombuffer(bytes(bank), dtype='>u4').astype(np.uint32)
            out.append((kind, simm, u9, u10, words, len(runs), form, before))

    if not a.in_place:
        if os.path.exists(a.out):
            sys.exit(f'{a.out} exists: give a new directory (or --in-place to patch it)')
        # only the pack's own two folders: the folder that holds them may be the user's Downloads
        os.makedirs(a.out)
        for sub in ('SIMM 1-2', 'SIMM 3-6'):
            shutil.copytree(os.path.join(a.pack, sub), os.path.join(a.out, sub))
    for kind, simm, u9, u10, words, nruns, form, before in out:
        u9 = os.path.join(a.out, os.path.relpath(u9, src))
        u10 = os.path.join(a.out, os.path.relpath(u10, src))
        b9, b10 = split_simm_words(words)
        open(u9, 'wb').write(b9)
        open(u10, 'wb').write(b10)
        if isinstance(form, int):
            print(f'{kind} SIMM{simm} bank {a.bank}: written anew from the patched Standard program, {form} '
                  f'instruction halfwords encrypted (key 0), byte sum {before:02X} as the Standard file')
            continue
        note = {'plain': 'instructions plain', 'encrypted': 'instructions encrypted (key 0)'}[form]
        print(f'{kind} SIMM{simm} bank {a.bank}: {nruns} runs patched, {note}, byte sum kept at {before:02X}')


if __name__ == '__main__':
    main()
