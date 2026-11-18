#!/usr/bin/env python3
"""Check a widescreen link against the stock link and write the hooks into it.

    hook.py <stock sf3.bin> <wide sf3w.bin> <wide sf3w.map> <hooks.tsv> <out prog image> [<data.tsv>]

The wide link adds sections (PWIDE, CWIDE) in space the stock program leaves empty. Everything else must be
byte-identical to the stock link; the script stops if it is not. Then, for each line "original<TAB>replacement"
of hooks.tsv (C names), the start of the original routine is overwritten with a jump to the replacement:

    mov.l  @(disp,pc),r0     ; D001
    jmp    @r0               ; 402B
    nop                      ; 0009
    [pad to 4]
    .long  replacement

r0 is a scratch register in the Hitachi SH calling convention, so the replacement sees the original's arguments.

data.tsv lists 16-bit data words of the game to change in place: "symbol<TAB>byte offset<TAB>old<TAB>new". Each is
written only where the old value is found.
"""
import re
import sys

BASE = 0x06000000


def read_symbols(map_path):
    syms = {}
    for m in re.finditer(r"^(_\w+)\s+H'([0-9A-F]{8})\s+(?:ENT|DAT)", open(map_path, encoding='latin-1').read(), re.M):
        syms[m.group(1)] = int(m.group(2), 16)
    return syms


def section_ranges(map_path, names):
    """(start, end) of each named section, from the map's per-module lines."""
    text = open(map_path, encoding='latin-1').read()
    out = []
    for name in names:
        for m in re.finditer(rf"^{name}\s+H'([0-9A-F]{{8}})\s+-\s+H'([0-9A-F]{{8}})", text, re.M):
            out.append((int(m.group(1), 16), int(m.group(2), 16)))
    return out


def data_words(path):
    """[(symbol, byte offset, old, new)] of a data.tsv."""
    out = []
    for line in open(path):
        line = line.split('#')[0].strip()
        if line:
            sym, off, old, new = line.split()
            out.append((sym, int(off), int(old), int(new)))
    return out


def write_word(img, at, old, new, what):
    have = int.from_bytes(img[at - BASE:at - BASE + 2], 'big', signed=True)
    if have != old:
        sys.exit(f'{what} at {at:08X} holds {have}, not {old}')
    img[at - BASE:at - BASE + 2] = new.to_bytes(2, 'big', signed=True)


def trampoline(at, target):
    code = bytes.fromhex('D001402B0009')
    if at % 4 == 0:
        code += b'\x00\x09'  # pad (a nop) so the literal is 4-aligned
    # mov.l @(1,pc): (at & ~3) + 4 + 4 holds the literal in both cases
    lit = (at & ~3) + 8
    assert at + len(code) == lit, (hex(at), len(code))
    return code + target.to_bytes(4, 'big')


def main():
    stock_path, wide_path, map_path, hooks_path, out_path = sys.argv[1:6]
    data_path = sys.argv[6] if len(sys.argv) > 6 else None
    stock = open(stock_path, 'rb').read()
    wide = bytearray(open(wide_path, 'rb').read())
    if len(stock) != len(wide):
        sys.exit(f'size differs: stock {len(stock)}, wide {len(wide)}')
    added = section_ranges(map_path, ['PWIDE', 'CWIDE', 'DWIDE', 'BWIDE'])
    if not added:
        sys.exit('no WIDE sections in the map')
    if any(a < 0x06000000 for a, _ in section_ranges(map_path, ['DWIDE', 'BWIDE'])):
        sys.exit('wide module has RAM data (DWIDE/BWIDE): not supported')
    lo, hi = min(a for a, _ in added), max(b for _, b in added)
    print(f'wide sections {lo:08X}-{hi:08X} ({hi - lo + 1} bytes)')
    # everything outside the added sections must be the stock link's
    outside = [i for i in range(0, lo - BASE) if stock[i] != wide[i]][:5]
    outside += [i for i in range(hi + 1 - BASE, len(stock)) if stock[i] != wide[i]][:5]
    if outside:
        sys.exit('the wide link moved stock bytes, first at ' + ', '.join(f'{BASE + i:08X}' for i in outside))
    if any(stock[lo - BASE:hi + 1 - BASE]):
        sys.exit('the wide sections overlap stock bytes')

    syms = read_symbols(map_path)
    starts = sorted(set(syms.values()))
    for path in hooks_path.split(','):
        for line in open(path):
          line = line.split('#')[0].strip()
          if not line:
              continue
          orig, repl = line.split()
          at, target = syms['_' + orig], syms['_' + repl]
          code = trampoline(at, target)
          nxt = min(a for a in starts if a > at)
          if at + len(code) > nxt:
              sys.exit(f'{orig} at {at:08X} is {nxt - at} bytes: too short for a {len(code)}-byte jump')
          wide[at - BASE:at - BASE + len(code)] = code
          print(f'hook {orig} {at:08X} -> {repl} {target:08X}')
    for sym, off, old, new in data_words(data_path) if data_path else []:
        write_word(wide, syms['_' + sym] + off, old, new, f'{sym}+{off}')
        print(f'data {sym}+{off} {syms["_" + sym] + off:08X}: {old} -> {new}')
    open(out_path, 'wb').write(wide)


if __name__ == '__main__':
    main()
