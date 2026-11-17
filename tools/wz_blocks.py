#!/usr/bin/env python3
"""Which parts of Warzard's program draw into the text tile map, and how they are entered and left.

    wz_blocks.py <bank 1 plain program (16 MB)>      prints the analysis

tools/build_warzard.py uses analyze() to copy that code: the game keeps running its own text code in 4:3 (a copy
with the stock literals) and a second copy that draws into the module's RAM shadow in wide mode.

Terms:
  loader   a mov.l @(disp,PC) whose literal is a text tile map address (25040000-25043FFF);
  block    a contiguous range holding every routine with a loader, closed under branches (bra, bt, bf): control
           leaves a block only by calls and returns, and its PC-relative data lies inside it. A block is copied
           verbatim, so its branches and literal pools stay valid;
  entry    an address in a block that something outside it reaches: a bsr, a branch, or a pointer (a literal a
           mov.l loads, or a word in the data ROM). Each entry gets a jump to a dispatcher;
  relay    a bsr inside a block whose target is outside it (PC-relative: it has to be redirected in a copy).
"""
import os
import struct
import sys
from bisect import bisect_right
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sh2flow import Prog  # noqa: E402

BASE = 0x06000000
CODE = (0x06000000, 0x06140000)
TEXT_MAP = (0x25040000, 0x25044000)
# the memory check's SS RAM test: its literal is the hardware's address, not a place to draw (build_warzard.py)
HARDWARE_LITERALS = {0x0600DBBC}
# data tables of text tile map addresses: code that loads a table's address draws through it, so it is text code too
TEXT_TABLES = {0x06696C90}


def s(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


def analyze(stock):
    p = Prog(stock, BASE)
    h, l = p.h, p.l
    # The program's code, by recursive descent: from every pointer into the code area held in the data ROM, then
    # from every call target and every pointer a reached mov.l loads, until nothing new turns up. (Reading every
    # halfword as a possible instruction takes data for calls and gives entries that are not there.)
    in_code = lambda v: CODE[0] <= v < CODE[1] and not v & 1
    pointer_at = defaultdict(list)    # code address -> where a pointer to it is kept
    for i in range(CODE[1] - BASE, len(stock) - 3, 4):
        v = struct.unpack_from('>I', stock, i)[0]
        if in_code(v):
            pointer_at[v].append(BASE + i)
    seeds = set(pointer_at) | {l(BASE), CODE[0]} & set(range(CODE[0], CODE[1]))
    seeds = {x for x in seeds if in_code(x)}
    code_all, done = set(), set()
    loaders = {}                       # loader -> literal address
    lit_loaded_by = defaultdict(list)  # literal address -> the mov.l instructions that load it
    bsr_to = defaultdict(list)
    branch_to = defaultdict(list)      # bra / bt / bf target -> sites
    while True:
        if not seeds - done:
            # pointer tables kept inside the code area (task and state tables): 4-aligned words that no reached
            # instruction covers and that hold a code address
            for w in range(CODE[0], CODE[1], 4):
                if w in code_all or (w + 2) in code_all:
                    continue
                v = l(w)
                if in_code(v) and v not in done and (v in code_all or True):
                    if w not in pointer_at[v]:
                        pointer_at[v].append(w)
                    seeds.add(v)
            if not seeds - done:
                break
        new = sorted(seeds - done)
        done |= set(new)
        code, refs, _ = p.reach(new, limit=CODE)
        fresh = code - code_all
        code_all |= code
        for a, t, kind in refs:
            if a not in fresh:
                continue
            if kind == 'bsr':
                bsr_to[t].append(a)
                if in_code(t):
                    seeds.add(t)
            elif kind in ('bra', 'bt', 'bf'):
                branch_to[t].append(a)
            elif kind == 'movl' and t < CODE[1]:
                lit_loaded_by[t].append(a)
                v = l(t)
                if (TEXT_MAP[0] <= v < TEXT_MAP[1] or v in TEXT_TABLES) and t not in HARDWARE_LITERALS:
                    loaders[a] = t
                elif in_code(v):
                    pointer_at[v].append(t)
                    seeds.add(v)
    starts = sorted(done)

    def hull(seeds):
        """(lo, hi, code) of everything reachable from seeds by branches, with the PC-relative data it reads."""
        code, refs, _ = p.reach(seeds)
        lo, hi = min(code), max(code) + 2
        for _, t, kind in refs:
            if kind in ('movl', 'mova'):
                lo, hi = min(lo, t), max(hi, t + 4)
            elif kind == 'movw':
                lo, hi = min(lo, t), max(hi, t + 2)
        return lo, hi, code

    # a block per loader: the routine it is in (the nearest known start that reaches it), grown until stable
    blocks = []
    orphans = []   # loaders in code nothing refers to (no call, branch or pointer in the whole image): dead code
    for a in sorted(loaders):
        if any(lo <= a < hi for lo, hi, _ in blocks):
            continue
        i = bisect_right(starts, a) - 1
        while i >= 0 and a - starts[i] < 0x2000:
            lo, hi, code = hull([starts[i]])
            if a in code:
                break
            i -= 1
        else:
            orphans.append(a)
            continue
        while True:
            seeds = [e for e in starts if lo <= e < hi] + [t for t in branch_to if lo <= t < hi]
            nlo, nhi, code = hull(seeds)
            nlo, nhi = min(lo, nlo), max(hi, nhi)
            if (nlo, nhi) == (lo, hi):
                break
            lo, hi = nlo, nhi
        blocks.append((lo, hi, code))
    # merge blocks that touch
    blocks.sort()
    merged = []
    for lo, hi, code in blocks:
        if merged and lo < merged[-1][1]:
            m = merged[-1]
            merged[-1] = (m[0], max(m[1], hi), m[2] | code)
        else:
            merged.append((lo, hi, code))
    # entries that need a dispatcher: starts from which a loader can be reached (by branches, or by a call to
    # another start of the same block that reaches one). Routines that only share a block with text code are
    # left as they are.
    loader_set = set(loaders)

    def reaches_loader(e, lo, hi, seen):
        if e in seen:
            return False
        seen.add(e)
        code, refs, _ = p.reach([e], limit=(lo, hi))
        if code & loader_set:
            return True
        return any(kind == 'bsr' and lo <= t < hi and reaches_loader(t, lo, hi, seen) for _, t, kind in refs)

    # re-close merged blocks (a merge can add starts) and collect what the build needs
    out = []
    for lo, hi, _ in merged:
        while True:
            seeds = sorted(set(e for e in starts if lo <= e < hi) | set(t for t in branch_to if lo <= t < hi))
            nlo, nhi, code = hull(seeds)
            nlo, nhi = min(lo, nlo), max(hi, nhi)
            if (nlo, nhi) == (lo, hi):
                break
            lo, hi = nlo, nhi
        # a mov.l in the block that the descent did not reach (code nothing refers to) and that loads a text
        # address from just past the block: the literal comes along, so the copy is whole
        for a in range(lo, hi, 2):
            if h(a) >> 12 == 0xD:
                t = (a & ~3) + 4 + 4 * (h(a) & 0xFF)
                if hi <= t < hi + 64 and TEXT_MAP[0] <= l(t) < TEXT_MAP[1]:
                    hi = t + 4
        lo &= ~3
        hi = (hi + 3) & ~3
        code_all, refs, unknown = p.reach(seeds)
        inside = lambda x: lo <= x < hi
        # every way in: from outside the block, or by a call from inside it (the original body stays as it is,
        # so a routine without text code that runs there must find a dispatcher at any text routine it calls)
        entries = set()
        for e in seeds:
            if (bsr_to.get(e) or any(not inside(c) for c in branch_to.get(e, [])) or pointer_at.get(e)) \
                    and reaches_loader(e, lo, hi, set()):
                entries.add(e)
        relays = sorted((a, t) for a, t, kind in refs if kind == 'bsr' and inside(a) and not inside(t))
        leaving = sorted((a, t, kind) for a, t, kind in refs if kind in ('bra', 'bt', 'bf') and inside(a) and not inside(t))
        data_out = sorted((a, t, kind) for a, t, kind in refs if kind in ('movl', 'movw', 'mova') and inside(a) and not inside(t))
        # words of the block that code outside it reads PC-relative (a neighbour's literal pool inside our range)
        shared = sorted(lit for lit, by in lit_loaded_by.items() if inside(lit) and any(not inside(b) for b in by))
        targets = set(t for _, t, kind in refs if kind in ('bra', 'bt', 'bf') and inside(t))
        # what still runs in place: routines of the block that have no dispatcher (they reach no loader), with
        # the PC-relative data they read. A dispatcher's jump must not be written over any of it.
        others = [e for e in seeds if e not in entries and
                  (bsr_to.get(e) or pointer_at.get(e) or any(not inside(c) for c in branch_to.get(e, [])))]
        live = set()
        if others:
            ocode, orefs, _ = p.reach(others, limit=(lo, hi))
            for a in ocode:
                live.update((a, a + 1))
            for _, t, kind in orefs:
                if kind in ('movl', 'mova'):
                    live.update(range(t, t + 4))
                elif kind == 'movw':
                    live.update((t, t + 1))
        for w in shared:
            live.update(range(w, w + 4))
        out.append(dict(lo=lo, hi=hi, code=code_all, entries=sorted(entries), relays=relays, leaving=leaving,
                        data_out=data_out, shared=shared, targets=targets, live=live, others=others,
                        loaders=sorted((a, lit) for a, lit in loaders.items() if inside(a)),
                        self_pointers=sorted(w for w in range(lo, hi, 4) if inside(l(w)) and not l(w) & 1
                                             and w not in code_all and (w + 2) not in code_all),
                        computed=sorted(a for kind, a in unknown if kind == 'computed' and inside(a))))
    return out, loaders, orphans


def main():
    stock = open(sys.argv[1], 'rb').read()
    blocks, loaders, orphans = analyze(stock)
    print(f'{len(loaders)} loaders; {len(blocks)} blocks, {sum(b["hi"] - b["lo"] for b in blocks)} bytes')
    print('loaders in unreferenced code (left alone):', [f'{a:08X}' for a in orphans])
    for b in blocks:
        missing = [a for a, _ in b['loaders'] if a not in b['code']]
        ent = b['entries']
        close = [(x, y) for x, y in zip(ent, ent[1:]) if y - x < 14]
        print(f'{b["lo"]:08X}-{b["hi"]:08X} {b["hi"] - b["lo"]:6} bytes: {len(b["loaders"])} loaders, {len(ent)} entries, '
              f'{len(b["relays"])} relays, {len(b["computed"])} computed jumps, {len(b["self_pointers"])} self pointers')
        for what, v in (('LEAVING', b['leaving']), ('DATA OUTSIDE', b['data_out']), ('SHARED WORDS', b['shared']),
                        ('LOADERS NOT REACHED', missing), ('ENTRIES < 14 APART', close)):
            if v:
                print('   ', what, len(v), [tuple(hex(x) if isinstance(x, int) else x for x in (i if isinstance(i, tuple) else (i,))) for i in v][:8])
        far = [(a, t) for a, t in b['relays'] if min(a - b['lo'], b['hi'] - a) > 3800]
        if far:
            print('    RELAYS FAR FROM BOTH ENDS', [(hex(a), hex(t)) for a, t in far])


if __name__ == '__main__':
    main()
