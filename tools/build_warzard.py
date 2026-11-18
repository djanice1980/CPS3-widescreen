#!/usr/bin/env python3
"""Build the widescreen patch of Warzard (Darksoft bank 1, Standard SH2 program, plain):

    build_warzard.py <bank 1 program (16 MB)> <out dir> [<bank 1 Custom SH2 program>]

With the Custom SH2 program (the same bank from the pack's Custom SH2 files) the copies of the game's code take
their instruction ranges from what Darksoft stored encrypted, and not only from this tool's flow analysis.

No source exists for Warzard, so the patch is built from addresses found in its program (below; found with MAME
taps and traces). src/warzard/wide.c is the module, its game addresses in a game.h written here (the compile and
link steps are tools/build_jojoba.py's). Steps:

 1. compile src/warzard/wide.c (SHC) and link it alone at MODULE: SIMM 2's address range, which Warzard (an 8 MB
    program) never reads (the BIOS reads only 06800000-06800007 at boot: checked in MAME);
 2. the text code (tools/wz_blocks.py finds it: every routine that loads a text tile map address, 25040000-
    25043FFF, or the one data table of such addresses): two verbatim copies in SIMM 2, A as it is and B with
    those addresses pointing at the module's RAM shadow, and at each way into that code a jump to a dispatcher
    that runs copy A in 4:3 and copy B in wide mode. Jumps, dispatchers and the relays for the copies' calls
    change no register and no flag. So in 4:3 the game runs its own instructions on the real text RAM, with
    nothing added to a frame but the dispatch of each text call (it is frame-identical to the unpatched game
    in MAME where the earlier design, a shadow in both modes copied every frame, was not);
 3. point the call literals at the module's wrappers (the fight camera step, the vertical blank's two scroll
    register writers, set screen mode); in wide mode the second of those also puts the shadow on the screen.
    The memory check's prints go through stubs that do the same after each line (no vertical blank is served
    while a check runs);
 4. (the window table's screen mode 7 row is already 3rd Strike's 496-pixel timing: checked, not changed);
 5. write <out>/warzard-wide-prog.bin, <out>/warzard-code.json (instruction ranges, for Custom carts) and
    <out>/warzard-wide.json (the patch, tools/make_patch.py).
"""
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from build_jojoba import compile_and_link, module_code, merge, run, WINDOW_ROW7_3S  # noqa: E402
from hook import trampoline  # noqa: E402
import wz_blocks  # noqa: E402

BASE = 0x06000000
SIZE = 0x01000000
MODULE = 0x06F00000         # PWIDE
MODULE_CONST = 0x06F03000   # CWIDE
STUBS = 0x06F04000
FREE = (0x06F00000, 0x06F40000)  # SIMM 2, never read by Warzard
COPIES_A = 0x06F10000       # the text code's copies: A as the game has it (4:3), B drawing into the shadow
COPIES_B = 0x06F20000
DISPATCH = 0x06F30000       # one dispatcher per entry into the text code
TABLE_B = 0x06F05400        # TEXT_TABLE with shadow addresses, for copy B
TEXT_SEL_OFFSET = 12        # in the module's RAM (VARS): 0 = run copy A, 4 = run copy B (src/warzard/wide.c)
CODE = (0x06000000, 0x06140000)  # the program's code (literal scan range)

SHADOW = 0x02040000  # 16 KB of RAM no code addresses and nothing writes (MAME: attract + play)
VARS = 0x02044000

TEXT_MAP = (0x25040000, 0x25044000)
# text tile map pointers in data ROM (the round win marks' cells, read by 06035A00): the only aligned text map
# addresses outside code literals but 06602108 (25040237: halfword pairs 25xx 0237 in a table, not a pointer)
TEXT_TABLE = (0x06696C90, 12)

G = dict(
    name='warzard', src='src/warzard/wide.c', module=MODULE, module_const=MODULE_CONST, menu=None,
    header=dict(VARS=VARS, SHADOW=SHADOW,
                LAYER0_X=0x02051C58,    # main layer x, latched for this frame's scroll registers
                SCREEN_X=0x02051BC0,    # global x offset in every layer and sprite scroll
                STAGE=0x020606E7,       # stage number (camera limits index)
                CAM_LIMITS=0x066F3E74,  # per stage: s16 camera x min, max (10 stages)
                CAMERA=0x0611B208,      # fight camera step
                SET_LAYER=0x06005508,   # set a layer's next x and y (layer, x, y)
                SCROLL=0x060055FC,      # vertical blank: layer and sprite scroll registers
                SET_MODE=0x06004484,
                GSCROLL=0x06004DB8,     # vertical blank: all 8 sprite scroll registers
                # the SCREEN MODE item (service menu game settings)
                CFG_WIDE=0x02017A0B,    # game settings byte 7 (spare): menu working copy
                LIVE_WIDE=0x02059E25,   # ... settings in effect (applied from the EEPROM image)
                CUR_MODE=0x02051BB8,    # screen mode last set
                PAD_NOW=0x02051A3C, PAD_PREV=0x02051A3E,
                PRINT8=0x0600649A,      # text records {x, y, attr, string}, a newline: the next record
                PRINT16=0x06006258,     # {kind, list}: kind 1, glyph programs {n, x, y, attr, n glyphs}, n 0 ends
                FONT_COPY=0x06005A20,   # (font RAM, source, tiles)
                EN_DRAW=0x0601D0F8, EN_CURSOR=0x02060744, EN_CURSOR_MOVE=0x0601DAD6, EN_HANDLERS=0x02001670,
                EN_INPUT=0x0601DA46, EN_VALUE=0x0601DBB8, EN_DRAW_CURSOR=0x0601DB30,
                EN_HELP_CHANGE=0x06693148, EN_HELP_EXIT=0x06693160,
                JP_DRAW=0x0601C6B2, JP_CURSOR=0x02060730, JP_CURSOR_MOVE=0x0601CF6E, JP_HANDLERS=0x020015E0,
                JP_INPUT=0x0601CEDA, JP_VALUE=0x0601D03C, JP_DRAW_CURSOR=0x0601CFC8, JP_CURSOR_REC=0x02001580,
                JP_HELP_CHANGE=0x02001538, JP_HELP_EXIT=0x02001540,
                WA_DST=0x2504F500,      # font RAM of glyph 13D4 (tiles 1D4-1D7: after the font, unused)
                APPLY_BODY=0x06F04040,  # the EEPROM image apply routine (its relocated start, below)
                EN_VALUES=0x06F05000, JP_VALUES=0x06F05020, WA_GLYPH=0x06F05040),
)
DATA = 0x06F05000           # menu data (above: values, glyph; then label lists)
APPLY = 0x0600F74C          # applies an EEPROM image (r4) to the settings: called by branches only, so its start
APPLY_START = bytes.fromhex('4F22 7FF0 1F43 52F3 7201 6320'.replace(' ', ''))  # (no PC-relative instruction)
# cursor movers: the last item (up from 0 wraps to it, down past it wraps to 0): English 7, Japanese 6
CURSOR_WRAPS = {0x0601DAF8: (0xE207, 0xE208), 0x0601DB20: (0xE307, 0xE308),
                0x0601CF92: (0xE206, 0xE207), 0x0601CFAC: (0xE306, 0xE307)}
EN_LABELS = 0x066930D0      # English page labels: title, 7 items, EXIT, then the help record that ends the list
EN_LABELS_LIT = 0x0601D1E8  # ... its literal in the page draw
JP_PAGE_LIT = 0x0601C790    # Japanese page labels ({kind 1, glyph program}), its literal in the page draw
JP_PAGE = 0x02001530        # ... (in the RAM copy of the data at 0671D920: program 06692E84)
JP_PROG = 0x06692E84
JP_WU = 0x1290              # katakana U: WA is U without its top stroke
JP_FONT = 0x06009BC0        # the Japanese menu font (glyph g: 4 tiles of 32 bytes at + (g - 0x1200) * 32)
JP = dict(sukuriin_moodo=[0x12B0, 0x1298, 0x1310, 0x13C8, 0x131C, 0x1304, 0x13C8, 0x12D0],
          noomaru=[0x12D8, 0x13C8, 0x12F8, 0x1314], waido=[0x13D4, 0x1288, 0x12D0, 0x1200])
# call literals: what they hold (checked) -> the module's wrapper
POINTERS = {
    **{lit: (0x0611B208, '_wide_camera') for lit in (0x0611D388, 0x0611E648, 0x0611FB80, 0x06120F18, 0x06122274,
                                                     0x061232DC, 0x06124644, 0x0612655C)},
    # the fight scene's own call that places the layers (every stage, the versus and bonus stages too)
    0x061198F8: (0x06005508, '_wide_set_layer'),
    0x0600247C: (0x060055FC, '_wide_scroll'),
    0x06002464: (0x06004DB8, '_wide_gscroll'),  # its only caller (the vertical blank, before 0600247C's)
    **{lit: (0x06004484, '_wide_set_screen_mode') for lit in (0x060017F4, 0x06002274, 0x06010790, 0x06010CFC,
                                                              0x0601105C)},
    # the game settings pages (data copied to RAM at boot): draw and step routines
    0x0671DA58: (0x0601D0F8, '_wide_en_draw'), 0x0671DA5C: (0x0601D2EC, '_wide_en_step'),
    0x0671D9C8: (0x0601C6B2, '_wide_jp_draw'), 0x0671D9CC: (0x0601C884, '_wide_jp_step'),
}
WINDOW_ROW7 = 0x06690D0C + 7 * 18


def wa_glyph(stock):
    """WA for the Japanese menu font: U (same strokes) without its top stroke (rows 1-3), 2 rows higher."""
    t = JP_FONT + (JP_WU - 0x1200) * 32 - BASE
    tiles = stock[t:t + 128]
    grid = [[0] * 16 for _ in range(16)]
    for i in range(4):
        for r in range(8):
            for k in range(4):
                v = tiles[i * 32 + r * 4 + k]
                y, x = (i // 2) * 8 + r, (i % 2) * 8 + 2 * k
                grid[y][x], grid[y][x + 1] = v >> 4, v & 15
    assert all(v == 0 for v in grid[0]) and any(grid[1]) and not any(grid[1][:6]) and any(grid[4])
    grid = grid[4:] + [[0] * 16 for _ in range(4)]
    grid = [[0] * 16 for _ in range(2)] + grid[:14]
    out = bytearray()
    for i in range(4):
        for r in range(8):
            for k in range(4):
                y, x = (i // 2) * 8 + r, (i % 2) * 8 + 2 * k
                out.append(grid[y][x] << 4 | grid[y][x + 1])
    return bytes(out)


def menu_data(stock):
    """The SCREEN MODE item's data at DATA: values (English records, Japanese {kind, program}), the WA glyph, the
    English label list, the Japanese page; returns (bytes, English list address, Japanese page address)."""
    out = bytearray()
    strings = []  # (offset of the pointer in out, text)

    def en_rec(x, y, ptr_or_text):
        out.extend(struct.pack('>HHHH', x, y, 2, 0))
        if isinstance(ptr_or_text, bytes):
            strings.append((len(out), ptr_or_text))
            out.extend(b'\0' * 4)
        else:
            out.extend(struct.pack('>I', ptr_or_text))

    def jp_prog(entries):
        b = b''.join(struct.pack('>4H', len(g), x, y, a) + struct.pack('>%dH' % len(g), *g) for x, y, a, g in entries)
        return b + b'\0' * 8

    # values: English {0, 0, 2, 0, string}, Japanese {kind 1, program at 0, 0}
    for t in (b'NORMAL\0', b'WIDE  \0'):
        en_rec(0, 0, t)
    out.extend(b'\0' * (0x20 - len(out)))
    jp_val_at = len(out)
    out.extend(b'\0' * 16)
    out.extend(b'\0' * (0x40 - len(out)))
    out.extend(wa_glyph(stock))
    # the English list: the page's records but EXIT, then SCREEN MODE, EXIT one row lower, the help record
    en_at = len(out)
    rec = lambda a: struct.unpack_from('>HHII', stock, a - BASE)
    recs = [rec(EN_LABELS + 12 * i) for i in range(10)]
    assert [r[1] for r in recs] == [1, 4, 6, 8, 10, 12, 14, 16, 18, 0x19]
    assert stock[recs[8][3] - BASE:recs[8][3] - BASE + 9] == b'8. EXIT\n\0'
    for x, y, attr, ptr in recs[:8]:
        out.extend(struct.pack('>HHII', x, y, attr, ptr))
    en_rec(3, 18, b'8. SCREEN MODE\n\0')
    en_rec(3, 20, b'9. EXIT\n\0')
    out.extend(struct.pack('>HHII', *recs[9]))
    # the Japanese program: the page's, SCREEN MODE before return (row 0x10), return one row lower
    entries, a = [], JP_PROG - BASE
    while True:
        n, x, y, attr = struct.unpack_from('>4H', stock, a)
        if n == 0:
            break
        entries.append([x, y, attr, list(struct.unpack_from('>%dH' % n, stock, a + 8))])
        a += 8 + 2 * n
    ret = [e for e in entries if e[1] == 0x10]
    assert len(ret) == 1 and len(ret[0][3]) == 9 and not any(e[1] == 0x12 for e in entries)
    i = entries.index(ret[0])
    ret[0][1] = 0x12
    entries.insert(i, [4, 0x10, 2, JP['sukuriin_moodo']])
    jp_page_at = len(out)
    out.extend(b'\0' * 8)
    jp_prog_at = len(out)
    out.extend(jp_prog(entries))
    vals = []
    for g in (JP['noomaru'], JP['waido']):
        vals.append(len(out))
        out.extend(jp_prog([(0, 0, 2, g)]))
    struct.pack_into('>IIII', out, jp_val_at, 0x00010000, DATA + vals[0], 0x00010000, DATA + vals[1])
    struct.pack_into('>II', out, jp_page_at, 0x00010000, DATA + jp_prog_at)
    for at, text in strings:
        while len(out) % 2:
            out.append(0)
        struct.pack_into('>I', out, at, DATA + len(out))
        out.extend(text)
    return bytes(out), DATA + en_at, DATA + jp_page_at


def apply_body(at):
    """The EEPROM image apply routine's start (APPLY_START, relocated), then a jump to the rest (r1: loaded there
    before use)."""
    assert at % 4 == 0
    code = APPLY_START + bytes.fromhex('D101412B0009') + b'\x00\x09'
    assert len(code) % 4 == 0 and len(APPLY_START) == 12
    # mov.l @(1,pc),r1 at +12: literal at ((at + 12) & ~3) + 4 + 4 = at + 20
    return code + struct.pack('>I', APPLY + len(APPLY_START)), [(at, len(code))]


# Literals that must keep the real text RAM address: the test menu's memory check tests the SS RAM itself
# (0600DB50: mov.l #0000C800,r5 / mov.l #25040000,r4 / bsr 0600D758, a save / pattern / restore word test).
# {literal: (value, the only routine that may load it)}
HARDWARE_LITERALS = {0x0600DBBC: (0x25040000, (0x0600DB34, 0x0600DBBC))}


# The test menu's memory check (0600E428: nine checks, back to back, in one task step) prints "CHECKING..." and
# each result with these two routines and never lets the scheduler run, so with text drawn through the shadow
# nothing reached the screen until every check was done. Inside the memory check's code (and only there) the
# literals that hold the two routines' addresses point at stubs that call the routine, then the module's flush.
MEM_CHECK = (0x0600D6C0, 0x0600E428)
MEM_PRINTS = {0x06005D5C: 12, 0x06005F1C: 7}   # routine: literals in MEM_CHECK holding its address
MEM_STUBS = 0x06F04100
PR_SAVE_OFFSET = 8                              # in the module's RAM (G_VARS): the caller's return address


def print_flush_stub(at, orig, flush, save):
    """orig(...) with the caller's registers and stack arguments as they are, then flush(); returns orig's r0."""
    assert at % 4 == 0
    code = [
        0xD100,  # mov.l @(save),r1
        0x002A,  # sts pr,r0
        0x2102,  # mov.l r0,@r1
        0xD000,  # mov.l @(orig),r0
        0x400B,  # jsr @r0
        0x0009,  # nop
        0x2F06,  # mov.l r0,@-r15
        0xD000,  # mov.l @(flush),r0
        0x400B,  # jsr @r0
        0x0009,  # nop
        0x60F6,  # mov.l @r15+,r0
        0xD100,  # mov.l @(save),r1
        0x6112,  # mov.l @r1,r1
        0x412A,  # lds r1,pr
        0x000B,  # rts
        0x0009,  # nop
    ]
    pool = at + 2 * len(code)
    for i, li in ((0, 0), (3, 1), (7, 2), (11, 0)):
        pc = at + 2 * i
        d = (pool + 4 * li - ((pc & ~3) + 4)) // 4
        assert 0 <= d < 256
        code[i] |= d
    blob = b''.join(struct.pack('>H', c) for c in code) + struct.pack('>III', save, orig, flush)
    return blob, [(at, 2 * len(code))]


def safe_jump(at, target):
    """A jump to target that changes no register and no flag: r0 goes on the stack and comes back in the jump's
    delay slot. 12 bytes at a 4-aligned address, 14 otherwise (the literal has to be 4-aligned)."""
    code = bytes.fromhex('2F06 D001 402B 60F6'.replace(' ', ''))  # mov.l r0,@-r15 / mov.l @(lit),r0 / jmp @r0 / mov.l @r15+,r0
    if at % 4 == 2:
        code += b'\x00\x09'
    # mov.l @(1,pc) at at+2: ((at + 2) & ~3) + 4 + 4
    assert ((at + 2) & ~3) + 8 == at + len(code), hex(at)
    return code + struct.pack('>I', target)


def dispatcher(at, sel, copy_a, copy_b):
    """Jump to copy_a or copy_b by the word at sel (0 or 4), every register and flag as the caller left them."""
    assert at % 4 == 0
    code = [
        0x2F06,  # mov.l r0,@-r15
        0x2F16,  # mov.l r1,@-r15
        0xD103,  # mov.l @(sel),r1      (at + 20)
        0x6112,  # mov.l @r1,r1         0 or 4
        0xC703,  # mova pair,r0         (at + 24)
        0x001E,  # mov.l @(r0,r1),r0
        0x61F6,  # mov.l @r15+,r1
        0x402B,  # jmp @r0
        0x60F6,  # mov.l @r15+,r0
        0x0009,  # pad
    ]
    blob = b''.join(struct.pack('>H', c) for c in code) + struct.pack('>III', sel, copy_a, copy_b)
    return blob, [(at, 18)]


def copy_block(stock, b, at, shadow, relay_at, custom):
    """One block at `at`. shadow: draw into the RAM shadow (copy B) instead of text RAM. Returns (bytes, relay
    bytes, code ranges). The copy is verbatim but for: calls (bsr) out of the block, which go through relays placed
    at relay_at (after the copy); pointers into the block, which follow the copy; and for copy B the text tile
    map addresses and the pointer to TEXT_TABLE."""
    lo, hi = b['lo'], b['hi']
    data = bytearray(stock[lo - BASE:hi - BASE])
    delta = at - lo
    assert at % 4 == 0 and relay_at % 4 == 0 and relay_at >= at + len(data)
    relays, ranges = bytearray(), []
    relay_of = {}
    for site, target in b['relays']:
        if target not in relay_of:
            relay_of[target] = relay_at + len(relays)
            ranges.append((relay_at + len(relays), 8))
            relays += safe_jump(relay_at + len(relays), target)
        d = relay_of[target] - (site + delta) - 4
        assert d % 2 == 0 and -4096 <= d <= 4094, f'relay out of reach from {site:08X}'
        struct.pack_into('>H', data, site - lo, 0xB000 | (d // 2 & 0xFFF))
    for w in b['self_pointers']:
        struct.pack_into('>I', data, w - lo, struct.unpack_from('>I', data, w - lo)[0] + delta)
    if shadow:
        for w in range(lo, hi, 4):
            v = struct.unpack_from('>I', stock, w - BASE)[0]
            if TEXT_MAP[0] <= v < TEXT_MAP[1] and w not in wz_blocks.HARDWARE_LITERALS:
                struct.pack_into('>I', data, w - lo, SHADOW + v - TEXT_MAP[0])
            elif v == TEXT_TABLE[0] and w not in b['code'] and (w + 2) not in b['code']:
                struct.pack_into('>I', data, w - lo, TABLE_B)
    # which halfwords are instructions: what the flow analysis reached and, with the Custom SH2 image at hand,
    # what Darksoft stored encrypted there (its own judgement of what is code, which the copy should share)
    is_code = set(a for a in b['code'] if lo <= a < hi)
    if custom:
        for a in range(lo, hi, 2):
            if custom[a - BASE:a - BASE + 2] != stock[a - BASE:a - BASE + 2]:
                is_code.add(a)
    run = None
    for a in range(lo, hi + 2, 2):
        if a in is_code and a < hi:
            run = a if run is None else run
        elif run is not None:
            ranges.append((run + delta, a - run))
            run = None
    return bytes(data), bytes(relays), ranges


def main():
    prog_path, out_dir = sys.argv[1], sys.argv[2]
    custom = open(sys.argv[3], 'rb').read() if len(sys.argv) > 3 else None   # the bank's Custom SH2 program
    os.makedirs(out_dir, exist_ok=True)
    stock = open(prog_path, 'rb').read()
    assert len(stock) == SIZE and (custom is None or len(custom) == SIZE)
    img = bytearray(stock)
    l = lambda a: struct.unpack_from('>I', stock, a - BASE)[0]
    code_ranges = []
    placed = []

    def put(addr, data):
        assert FREE[0] <= addr and addr + len(data) <= FREE[1], hex(addr)
        assert not any(lo < addr + len(data) and addr < hi for lo, hi in placed), f'{addr:08X} overlaps'
        img[addr - BASE:addr - BASE + len(data)] = data
        placed.append((addr, addr + len(data)))

    # 1. the module
    module, syms, spans = compile_and_link(out_dir, G, {})
    for lo, hi in spans:
        put(lo, module[lo - BASE:hi - BASE])
    print('module ' + ', '.join(f'{lo:08X}-{hi:08X}' for lo, hi in spans))
    code_ranges.extend(module_code(os.path.join(out_dir, 'wide.lis'), img, MODULE))

    # 2. the text code: two copies of every block that draws into the tile map, and a dispatcher at each entry.
    #    The game's own code is not changed but for the jumps at those entries, so in 4:3 it runs the stock
    #    instructions (copy A) on the real text RAM: no shadow, no copy, nothing added to a frame but the
    #    dispatch of a text call. Copy B draws into the shadow, which the module puts on the screen in wide mode.
    blocks, loaders, orphans = wz_blocks.analyze(stock)
    assert not orphans, orphans
    table = bytearray()
    a, n = TEXT_TABLE
    for i in range(n):
        assert TEXT_MAP[0] <= l(a + 4 * i) < TEXT_MAP[1]
        table += struct.pack('>I', SHADOW + l(a + 4 * i) - TEXT_MAP[0])
    put(TABLE_B, bytes(table))
    table_users = [BASE + i for i in range(0, SIZE, 4) if struct.unpack_from('>I', stock, i)[0] == TEXT_TABLE[0]]
    assert table_users and all(any(blk['lo'] <= w < blk['hi'] for blk in blocks) for w in table_users), table_users
    at_a, at_b, d_at = COPIES_A, COPIES_B, DISPATCH
    n_entries = n_relays = 0
    jumps = []   # (address, length) of the jumps written over entries
    for blk in blocks:
        assert not blk['leaving'] and not blk['data_out'], hex(blk['lo'])
        size = blk['hi'] - blk['lo']
        copies = {}
        for name, base, shadow in (('a', at_a, False), ('b', at_b, True)):
            data, relays, cr = copy_block(stock, blk, base, shadow, base + size, custom)
            put(base, data + relays)
            code_ranges.extend(cr)
            copies[name] = base - blk['lo']
        step = (size + 12 * len(blk['relays']) + 15) // 16 * 16
        at_a += step
        at_b += step
        n_relays += len(blk['relays'])
        for e in blk['entries']:
            blob, cr = dispatcher(d_at, VARS + TEXT_SEL_OFFSET, e + copies['a'], e + copies['b'])
            put(d_at, blob)
            code_ranges.extend(cr)
            t = safe_jump(e, d_at)
            # the jump may only cover code that runs nowhere but in the copies from now on
            assert blk['lo'] <= e and e + len(t) <= blk['hi'], hex(e)
            assert not any(x in blk['live'] for x in range(e, e + len(t))), f'{e:08X}: the jump would cover live code'
            assert not any(lo < e + len(t) and e < lo + ln for lo, ln in jumps), f'{e:08X}: jumps overlap'
            img[e - BASE:e - BASE + len(t)] = t
            jumps.append((e, len(t)))
            code_ranges.append((e, 8))
            d_at += 32
            n_entries += 1
    assert at_a <= COPIES_B and at_b <= DISPATCH and d_at <= FREE[1]
    if os.environ.get('WZ_TRIPWIRE'):
        # test build only: every instruction of the blocks that should never run again (all but the jumps and
        # the routines without a dispatcher) becomes "bra self". A missed entry then hangs the game instead of
        # quietly running the old code, so a test run that matches the unpatched game proves there was none.
        n_trip = 0
        for blk in blocks:
            for x in sorted(blk['code']):
                if blk['lo'] <= x < blk['hi'] and x not in blk['live'] and \
                        not any(lo <= x < lo + ln for lo, ln in jumps):
                    struct.pack_into('>H', img, x - BASE, 0xAFFE)
                    n_trip += 1
        print(f'TRIPWIRE build: {n_trip} dead instructions replaced by a halt. NOT for release.')
    print(f'text code: {len(blocks)} blocks ({at_a - COPIES_A} bytes a copy), {n_entries} entries, {n_relays} relays, '
          f'{len(loaders)} loads of a text address' + ('' if custom else '; NO Custom SH2 image: code ranges from flow only'))

    # 3. wrappers (the scheduler is not hooked: the shadow goes to the screen from the vertical blank's wrapper)
    for lit, (old, sym) in POINTERS.items():
        assert l(lit) == old, (hex(lit), hex(l(lit)))
        struct.pack_into('>I', img, lit - BASE, syms[sym])

    # the memory check's prints go through stubs that flush the shadow to the screen
    h16 = lambda a: struct.unpack_from('>H', stock, a - BASE)[0]
    at = MEM_STUBS
    for orig, count in MEM_PRINTS.items():
        blob, cr = print_flush_stub(at, orig, syms['_wide_text_flush'], VARS + PR_SAVE_OFFSET)
        put(at, blob)
        code_ranges.extend(cr)
        found = 0
        for a in range(MEM_CHECK[0], MEM_CHECK[1], 2):
            if h16(a) >> 12 == 0xD:
                lit = (a & ~3) + 4 + 4 * (h16(a) & 0xFF)
                if l(lit) == orig and struct.unpack_from('>I', img, lit - BASE)[0] == orig:
                    struct.pack_into('>I', img, lit - BASE, at)
                    found += 1
        assert found == count, (hex(orig), found)
        # ... and nothing outside the memory check loads one of those literals
        for a in range(CODE[0], CODE[1], 2):
            if h16(a) >> 12 == 0xD and not (MEM_CHECK[0] <= a < MEM_CHECK[1]):
                lit = (a & ~3) + 4 + 4 * (h16(a) & 0xFF)
                assert not (l(lit) == orig and struct.unpack_from('>I', img, lit - BASE)[0] == at), hex(a)
        at += (len(blob) + 15) // 16 * 16
    print(f'memory check: {sum(MEM_PRINTS.values())} print calls flush the text shadow')

    # the SCREEN MODE item: menu data, label lists, cursor wraps, the EEPROM image apply hook
    data, en_list, jp_page = menu_data(stock)
    put(DATA, data)
    for lit, (old, new) in ((EN_LABELS_LIT, (EN_LABELS, en_list)), (JP_PAGE_LIT, (JP_PAGE, jp_page))):
        assert l(lit) == old, hex(lit)
        struct.pack_into('>I', img, lit - BASE, new)
    for at, (old, new) in CURSOR_WRAPS.items():
        assert struct.unpack_from('>H', stock, at - BASE)[0] == old, hex(at)
        struct.pack_into('>H', img, at - BASE, new)
        code_ranges.append((at, 2))
    assert G['header']['APPLY_BODY'] == STUBS + 0x40
    assert stock[APPLY - BASE:APPLY - BASE + len(APPLY_START)] == APPLY_START
    blob, cr = apply_body(G['header']['APPLY_BODY'])
    put(G['header']['APPLY_BODY'], blob)
    code_ranges.extend(cr)
    t = trampoline(APPLY, syms['_wide_ee_apply'])
    assert len(t) == len(APPLY_START)
    img[APPLY - BASE:APPLY - BASE + len(t)] = t
    code_ranges.append((APPLY, 8))
    for k in ('EN_VALUES', 'JP_VALUES', 'WA_GLYPH'):
        assert DATA <= G['header'][k] < DATA + 0x80

    # 4. screen mode 7 is already the 496-pixel timing
    assert struct.unpack_from('>9h', stock, WINDOW_ROW7 - BASE) == WINDOW_ROW7_3S

    out_prog = os.path.join(out_dir, 'warzard-wide-prog.bin')
    open(out_prog, 'wb').write(img)
    code_json = os.path.join(out_dir, 'warzard-code.json')
    json.dump({'code': [[f'{a:08X}', n] for a, n in merge(code_ranges)]}, open(code_json, 'w'))
    print(run([sys.executable, os.path.join(ROOT, 'tools/make_patch.py'), prog_path, out_prog, 'warzard',
               os.path.join(out_dir, 'warzard-wide.json'), code_json]))
    for s in sorted(syms, key=syms.get):
        print(f'  {syms[s]:08X} {s}')


if __name__ == '__main__':
    main()
