#!/usr/bin/env python3
"""Port the 3rd Strike widescreen build to another program of the same game (Makoto Fix, 4rd Strike: the 990608
program, moved and edited) and write a patch for that bank.

    port_bank.py <bank prog image> <name> <wide addr> <const addr> <out dir>
                 [--stock <prog> --map <map> --full <prog or ''> --hooks <tsv,...> --data <tsv or ''>]

Run from the decomp directory after its wide objects and listings are built in obj/wide_src (by default, after
tools/build_sfiii3.sh: 3rd Strike's stock.bin, sf3w.map, sf3w-hooked.bin and hooks). <bank prog image> is the
bank's plain (Standard SH2) 16 MB program. For New Generation (tools/build_sfiiina.sh) the decomp's own
build and map are the stock program, and there is no full widescreen build to compare with (--full '').

1. Aligns the stock (990512) program with the bank's on unique 16-byte windows: runs of the same offset.
2. Links the wide objects on their own (lnk DEFINE for every outside symbol they use). First with the stock
   addresses, which must give the very bytes of the full build (the check that this way of linking is sound),
   then with the bank's addresses:
     program symbols (06...): through the alignment; the bytes there must be the stock symbol's (whole size
       for data up to 256 bytes, the first 32 bytes of code);
     RAM symbols (02...): the stock program's literal pools hold the address; the bank's matching pools must
       agree on one value.
3. Each hooked routine must be the stock one in the bank (its literal-pool words may differ only by the mapping),
   or the patch would throw away the bank's own change to it.
4. Writes the trampolines, the module and the changed data words (--data, as tools/hook.py: each must sit in an
   aligned stretch and hold the old value) into the bank's image, the instruction ranges (for Custom SH2), and
   the patch: <out dir>/<name>-wide.json.
"""
import bisect
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from code_ranges import listing_code, merge, module_ranges  # noqa: E402
from hook import BASE, data_words, read_symbols, trampoline, write_word  # noqa: E402

OBJDIR = 'obj/wide_src'
SIZE = 0x1000000


def align(a, b, w=16):
    """[(start, end, delta)]: stock addresses start..end sit at +delta in b."""
    idx = {}
    for o in range(0, len(b) - w, 2):
        k = b[o:o + w]
        if k.count(0) > w // 2:
            continue
        idx[k] = -1 if k in idx else o
    segs = []
    for o in range(0, len(a) - w, 2):
        k = a[o:o + w]
        if k.count(0) > w // 2:
            continue
        p = idx.get(k)
        if p is None or p < 0:
            continue
        d = p - o
        if segs and segs[-1][2] == d:
            segs[-1][1] = o + w
        else:
            segs.append([o, o + w, d])
    return [(BASE + s, BASE + e, d) for s, e, d in segs if e - s >= 32]


class Mapper:
    def __init__(self, stock, target):
        self.stock, self.target = stock, target
        self.segs = align(stock, target)
        self.starts = [s for s, _, _ in self.segs]

    def rom(self, a):
        """The bank's address of stock address a, or None if a is not in an aligned stretch (or between two
        stretches with the same offset)."""
        i = bisect.bisect_right(self.starts, a) - 1
        if i < 0:
            return None
        s, e, d = self.segs[i]
        if a < e:
            return a + d
        if i + 1 < len(self.segs) and self.segs[i + 1][2] == d:
            return a + d
        return None

    def ram(self, value):
        """The bank's value for a RAM address the stock program keeps in literal pools; None if no pool has it
        or the bank's pools disagree."""
        key = value.to_bytes(4, 'big')
        votes = {}
        o = self.stock.find(key, 0x400, 0x13BD98)
        while o >= 0:
            if o % 4 == 0:
                t = self.rom(BASE + o)
                if t is not None:
                    v = int.from_bytes(self.target[t - BASE:t - BASE + 4], 'big')
                    votes[v] = votes.get(v, 0) + 1
            o = self.stock.find(key, o + 1, 0x13BD98)
        # unanimous, or nearly: a pool beside an edited stretch can be mis-paired
        if votes:
            best = max(votes, key=votes.get)
            if votes[best] >= 3 and votes[best] >= 20 * (sum(votes.values()) - votes[best]):
                return best, sum(votes.values())
            if len(votes) == 1:
                return best, votes[best]
        return None, votes

    def same(self, at, new_at, n):
        """The n bytes at stock at and bank new_at are the same, but for 4-byte words holding addresses that
        map (literal pools, pointer tables). Returns '' or what differs."""
        a = self.stock[at - BASE:at - BASE + n]
        b = self.target[new_at - BASE:new_at - BASE + n]
        if a == b:
            return ''
        if (new_at - at) % 4:
            return 'moved by a non-multiple of 4 and differs'
        for o in range(0, n, 2):
            if a[o:o + 2] == b[o:o + 2]:
                continue
            w = (at + o) & ~3
            sv = int.from_bytes(self.stock[w - BASE:w - BASE + 4], 'big')
            tv = int.from_bytes(self.target[w - at + new_at - BASE:w - at + new_at - BASE + 4], 'big')
            mapped = self.rom(sv) if sv >> 24 == 0x06 else self.ram(sv)[0] if sv >> 24 == 0x02 else None
            if mapped != tv:
                return f'differs at +{o:X} (stock {a[o:o + 2].hex()}, bank {b[o:o + 2].hex()})'
        return 


def run(cmd):
    env = dict(os.environ, WINEDEBUG='-all')
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return r.stdout + r.stderr


def link(name, wide, const, defines):
    """Link the wide objects alone; returns (16 MB image, map path, undefined symbols)."""
    objs = sorted(f for f in os.listdir(OBJDIR) if f.endswith('.obj'))
    sub = [f'INPUT {OBJDIR}/{o}'.replace('/', '\\') for o in objs]
    sub.append(f'START PWIDE({wide:08X}),CWIDE({const:08X})')
    sub += [f'DEFINE {s}({v:08X})' for s, v in sorted(defines.items())]
    sub += [f'OUTPUT tmp\\port\\{name}.abs', f'PRINT tmp\\port\\{name}.map', 'EXIT']
    os.makedirs('tmp/port', exist_ok=True)
    open(f'tmp/port/{name}.sub', 'w', newline='\r\n').write('\n'.join(sub) + '\n')
    for f in (f'tmp/port/{name}.abs', f'{name}.bin'):
        if os.path.exists(f):
            os.remove(f)
    out = run(['wine', 'bin/lnk.exe', f'-subcommand=tmp\\port\\{name}.sub'])
    undef = sorted(set(re.findall(r'UNDEFINED EXTERNAL SYMBOL\(\w+\.(\w+)\)', out)))
    if undef:
        return None, None, undef
    if '**' in out.replace('** 105', ''):
        sys.exit(f'link {name}:\n{out}')
    # rof2bin writes <abs name>.bin in the current directory
    out = run(['wine', 'bin/rof2bin.exe', '-s=06000000', '-e=07000000', '-v=00', f'tmp\\port\\{name}.abs'])
    for cand in (f'{name}.bin', f'tmp/port/{name}.bin'):
        if os.path.exists(cand):
            img = open(cand, 'rb').read()
            os.remove(cand)
            return img, f'tmp/port/{name}.map', []
    sys.exit(f'rof2bin wrote nothing for {name}:\n{out}')


def wide_span(map_path):
    text = open(map_path, encoding='latin-1').read()
    spans = []
    for sect in ('PWIDE', 'CWIDE'):
        m = re.search(rf"^{sect}\s+H'([0-9A-F]{{8}})\s+-\s+H'([0-9A-F]{{8}})", text, re.M)
        lo = int(m.group(1), 16)
        his = [int(h, 16) for h in re.findall(r"H'[0-9A-F]{8}\s+-\s+H'([0-9A-F]{8})",
                                               text[m.start():text.find('TOTAL ADDRESS', m.start())])]
        spans.append((lo, max(his) + 1))
    return spans


def routine_size(stock_syms_sorted, at):
    return stock_syms_sorted[bisect.bisect_right(stock_syms_sorted, at)] - at


def main():
    import argparse
    build = os.path.join(ROOT, 'build/sfiii3')
    ap = argparse.ArgumentParser()
    for a in ('target', 'name', 'wide', 'const', 'out_dir'):
        ap.add_argument(a)
    ap.add_argument('--stock', default=f'{build}/stock.bin')
    ap.add_argument('--map', default='sf3w.map')
    ap.add_argument('--full', default=f'{build}/sf3w-hooked.bin')
    ap.add_argument('--hooks', default=f'{ROOT}/src/sfiii3/hooks.tsv,{build}/hud_hooks.tsv')
    ap.add_argument('--data', default=f'{ROOT}/src/sfiii3/data.tsv')
    # a range the program never uses although it is not empty (New Generation: bytes past its linked sections
    # that an earlier build left in the image), allowed to take the module
    ap.add_argument('--unused', default='')
    args = ap.parse_args()
    name, wide, const, out_dir = args.name, int(args.wide, 16), int(args.const, 16), args.out_dir
    stock = open(args.stock, 'rb').read()[:SIZE]
    stock += bytes(SIZE - len(stock))  # a one-SIMM build: the rest as empty
    target = open(args.target, 'rb').read()[:SIZE]
    assert len(stock) == len(target) == SIZE
    syms = read_symbols(args.map)
    map_text = open(args.map, encoding='latin-1').read()

    # the outside symbols, from a link with none defined
    _, _, need = link('probe', 0x06700000, 0x06740000, {})
    print(f'{len(need)} outside symbols')

    missing = [s for s in need if s not in syms]
    if missing:
        sys.exit(f'not in the stock map: {missing}')
    # 1. the stock addresses must give the full build's bytes
    if args.full:
        full = open(args.full, 'rb').read()
        img, map_path, undef = link('stock', 0x06700000, 0x06740000, {s: syms[s] for s in need})
        for lo, hi in wide_span(map_path):
            if img[lo - BASE:hi - BASE] != full[lo - BASE:hi - BASE]:
                sys.exit(f'the standalone link differs from the full build in {lo:08X}-{hi:08X}')
        print('standalone link with stock addresses = the full build: OK')

    # 2. the bank's addresses
    m = Mapper(stock, target)
    print(f'{len(m.segs)} aligned stretches')
    starts = sorted(set(syms.values()))
    defines, problems = {}, []
    for s in need:
        a = syms[s]
        if a >> 24 == 0x06:
            t = m.rom(a)
            if t is None:
                problems.append(f'{s} {a:08X}: not in an aligned stretch')
                continue
            nxt = starts[bisect.bisect_right(starts, a)] if a < starts[-1] else a + 32
            size = min(nxt - a, 256)
            is_code = re.search(rf'^{s}\s+H\'{a:08X}\s+ENT', map_text, re.M)
            size = min(size, 32) if is_code else size
            why = m.same(a, t, size)
            if why:
                problems.append(f'{s} {a:08X} -> {t:08X}: the bank\'s bytes differ ({size} compared): {why}')
                continue
            defines[s] = t
        elif a >> 24 == 0x02:
            v, info = m.ram(a)
            if v is None:
                problems.append(f'{s} {a:08X}: RAM address not settled by the literal pools ({info})')
                continue
            defines[s] = v
        else:
            problems.append(f'{s} {a:08X}: neither program nor RAM')
    moved = {s: (syms[s], v) for s, v in defines.items() if v != syms[s]}
    print(f'mapped {len(defines)}; {len(moved)} moved; e.g. ' +
          ', '.join(f'{s} {a:08X}->{v:08X}' for s, (a, v) in list(moved.items())[:4]))
    ram_moved = {s: av for s, av in moved.items() if av[0] >> 24 == 0x02}
    print(f'RAM symbols moved: {len(ram_moved)}', ram_moved if ram_moved else '')

    # 3. the hooked routines
    hooks = []
    for path in args.hooks.split(','):
        for line in open(path):
            line = line.split('#')[0].strip()
            if line:
                hooks.append(line.split())
    hook_sites = {}
    for orig, repl in hooks:
        at = syms['_' + orig]
        t = m.rom(at)
        if t is None:
            problems.append(f'hook {orig} {at:08X}: not in an aligned stretch')
            continue
        why = m.same(at, t, routine_size(starts, at))
        if why:
            problems.append(f'hook {orig} {at:08X} -> {t:08X}: the bank\'s routine is not the stock one: {why}')
        hook_sites[orig] = (at, t)
    words = []
    for sym, off, was, now in data_words(args.data) if args.data else []:
        t = m.rom(syms['_' + sym] + off)
        if t is None:
            problems.append(f'data {sym}+{off}: not in an aligned stretch')
        words.append((t, was, now, f'{sym}+{off}'))
    if problems:
        sys.exit('cannot port:\n  ' + '\n  '.join(problems))
    print(f'{len(hook_sites)} hooked routines are the stock ones in the bank')

    img, map_path, undef = link(name, wide, const, defines)
    assert not undef, undef
    new = bytearray(target)
    for lo, hi in wide_span(map_path):
        ulo, uhi = (int(x, 16) for x in args.unused.split('-')) if args.unused else (0, 0)
        if any(target[lo - BASE:hi - BASE]) and not (ulo <= lo and hi <= uhi):
            sys.exit(f'{lo:08X}-{hi:08X} is not free in the bank')
        new[lo - BASE:hi - BASE] = img[lo - BASE:hi - BASE]
    for t, was, now, what in words:
        write_word(new, t, was, now, what)
        print(f'data {what} {t:08X}: {was} -> {now}')
    wsyms = read_symbols(map_path)
    spans = []
    for orig, repl in hooks:
        at, t = hook_sites[orig]
        code = trampoline(t, wsyms['_' + repl])
        new[t - BASE:t - BASE + len(code)] = code
        spans.append((t, len(code) - 4))
    for mod, base in module_ranges(map_path, 'PWIDE').items():
        for sct, off, hexcode in listing_code(f'{OBJDIR}/{mod}.lis'):
            assert sct == 'PWI' and new[base + off - BASE:base + off - BASE + 2].hex().upper() == hexcode
            spans.append((base + off, 2))
    os.makedirs(out_dir, exist_ok=True)
    open(f'{out_dir}/{name}-prog.bin', 'wb').write(target)
    open(f'{out_dir}/{name}-wide-prog.bin', 'wb').write(new)
    json.dump({'code': [[f'{a:08X}', n] for a, n in merge(spans)]}, open(f'{out_dir}/{name}-code.json', 'w'))
    print(run([sys.executable, '-I', os.path.join(ROOT, 'tools/make_patch.py'), f'{out_dir}/{name}-prog.bin',
               f'{out_dir}/{name}-wide-prog.bin', name, f'{out_dir}/{name}-wide.json',
               f'{out_dir}/{name}-code.json']).split('\n')[0])


if __name__ == '__main__':
    main()
