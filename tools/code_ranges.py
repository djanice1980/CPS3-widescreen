#!/usr/bin/env python3
"""Which bytes of a widescreen build are SH-2 instructions (the rest is data).

    code_ranges.py <prog image> <map> <listing dir> <hooks.tsv[,hooks.tsv...]> <out .json>

A Custom SH2 (security cart) image stores instruction halfwords encrypted and data plain, so the patch has to say
which of its new bytes the CPU fetches as instructions. That comes from the compiler, not from guessing:

- the added modules (PWIDE): SHC's object listing (-show=object) of each module marks every line an instruction
  or a .DATA/.RES directive; the map gives each module's address. Every instruction's code in the listing is
  checked against the image.
- constants (CWIDE): data.
- the hooks (tools/hook.py's trampolines): mov.l / jmp / nop (and the pad nop) are instructions, the
  replacement's address after them is data.

Writes {"code": [[addr hex, length], ...]}: the instruction byte ranges, merged.
"""
import json
import os
import re
import sys

from hook import BASE, read_symbols, trampoline

LINE = re.compile(r'^(\w{3}| {3}) ([0-9A-F]{8}) (\S+)\s+(?:\w+:\s+)?(\.?[A-Z][\w.]*)')


def module_ranges(map_path, section):
    """{module: start} for one section, from the map's per-module lines (a range line, then the module name)."""
    lines = open(map_path, encoding='latin-1').read().split('\n')
    out, i = {}, 0
    while i < len(lines):
        if re.match(rf'^{section}\s+H\'', lines[i]):
            j = i
            while j + 1 < len(lines):
                m = re.search(r"H'([0-9A-F]{8})\s+-\s+H'([0-9A-F]{8})", lines[j])
                name = lines[j + 1].split()
                if not m or not name:
                    break
                out[name[0]] = int(m.group(1), 16)
                j += 2
            break
        i += 1
    return out


def listing_code(lis_path):
    """[(section, offset, code hex)] of the instruction lines of an SHC object listing."""
    out, sct = [], None
    for line in open(lis_path, encoding='latin-1'):
        s = re.match(r'^([A-Z][A-Z ]{2}) [0-9A-F]{8} ', line)
        if s:
            sct = s.group(1).strip()  # the section name is printed where it starts, often on a label line
        m = LINE.match(line.rstrip('\n'))
        if not m:
            continue
        if m.group(1).strip():
            sct = m.group(1)
        code, mnem = m.group(3), m.group(4)
        if mnem.startswith('.'):
            continue  # .DATA / .RES / .ALIGN: data
        if not re.fullmatch(r'[0-9A-F]{4}', code):
            sys.exit(f'{lis_path}: unexpected instruction line: {line.rstrip()}')
        out.append((sct, int(m.group(2), 16), code))
    return out


def merge(spans):
    out = []
    for a, n in sorted(spans):
        if out and a <= out[-1][0] + out[-1][1]:
            out[-1][1] = max(out[-1][1], a + n - out[-1][0])
        else:
            out.append([a, n])
    return out


def main():
    prog_path, map_path, lis_dir, hooks_paths, out_path = sys.argv[1:6]
    prog = open(prog_path, 'rb').read()
    starts = module_ranges(map_path, 'PWIDE')
    spans = []
    for mod, base in starts.items():
        lis = os.path.join(lis_dir, mod + '.lis')
        code = listing_code(lis)
        for sct, off, hexcode in code:
            if sct != 'PWI':
                sys.exit(f'{lis}: instruction in section {sct}, not PWIDE')
            at = base + off
            if prog[at - BASE:at - BASE + 2].hex().upper() != hexcode:
                sys.exit(f'{mod}: listing says {hexcode} at {at:08X}, image has {prog[at - BASE:at - BASE + 2].hex()}')
            spans.append((at, 2))
        print(f'{mod}: {len(code)} instructions at {base:08X}')
    syms = read_symbols(map_path)
    n = 0
    for path in hooks_paths.split(','):
        for line in open(path):
            line = line.split('#')[0].strip()
            if line:
                orig, repl = line.split()
                at = syms['_' + orig]
                t = trampoline(at, syms['_' + repl])
                assert prog[at - BASE:at - BASE + len(t)] == t, orig
                spans.append((at, len(t) - 4))
                n += 1
    print(f'{n} hooks')
    code = merge(spans)
    json.dump({'code': [[f'{a:08X}', n] for a, n in code]}, open(out_path, 'w'), indent=0)
    print(f'{out_path}: {sum(n for _, n in code)} instruction bytes in {len(code)} ranges')


if __name__ == '__main__':
    main()
