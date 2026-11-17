#!/usr/bin/env python3
"""Build the widescreen patch of Warzard (Darksoft bank 1, Standard SH2 program, plain):

    build_warzard.py <bank 1 program (16 MB)> <out dir>

No source exists for Warzard, so the patch is built from addresses found in its program (below; found with MAME
taps and traces). src/warzard/wide.c is the module, its game addresses in a game.h written here (the compile and
link steps are tools/build_jojoba.py's). Steps:

 1. compile src/warzard/wide.c (SHC) and link it alone at MODULE: SIMM 2's address range, which Warzard (an 8 MB
    program) never reads (the BIOS reads only 06800000-06800007 at boot: checked in MAME);
 2. point every code literal that addresses the text tile map (25040000-25043FFF, the wrap bound 25043FFF too),
    and the one pointer table in data ROM that does, at the RAM shadow, in both modes (the module copies the shadow to text RAM once the frame's text is drawn);
 3. point the call literals at the module's wrappers (the fight camera step, the vertical blank's two scroll register
    writers, set screen mode); the task scheduler's end-of-pass step calls the module's frame step first;
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

BASE = 0x06000000
SIZE = 0x01000000
MODULE = 0x06F00000         # PWIDE
MODULE_CONST = 0x06F03000   # CWIDE
STUBS = 0x06F04000
FREE = (0x06F00000, 0x06F10000)  # SIMM 2, never read by Warzard
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
                SCHED_PASS=0x0205192C,  # task scheduler pass counter
                CAMERA=0x0611B208,      # fight camera step
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
    0x0600247C: (0x060055FC, '_wide_scroll'),
    0x06002464: (0x06004DB8, '_wide_gscroll'),  # its only caller (the vertical blank, before 0600247C's)
    **{lit: (0x06004484, '_wide_set_screen_mode') for lit in (0x060017F4, 0x06002274, 0x06010790, 0x06010CFC,
                                                              0x0601105C)},
    # the game settings pages (data copied to RAM at boot): draw and step routines
    0x0671DA58: (0x0601D0F8, '_wide_en_draw'), 0x0671DA5C: (0x0601D2EC, '_wide_en_step'),
    0x0671D9C8: (0x0601C6B2, '_wide_jp_draw'), 0x0671D9CC: (0x0601C884, '_wide_jp_step'),
}
# the task scheduler's end of a pass over its 24 tasks (r13 == 24): 06001978-06001983 become a jump to the stub
SCHED_HOOK = 0x06001978
SCHED_HOOK_CODE = bytes.fromhex('D21D 6221 2821 60B0 8803 8D08'.replace(' ', ''))
SCHED_LIT = 0x060019F0      # its mov.l's literal (a register address, 240C0006)
SCHED_T = 0x06001996        # the bt/s target (its slot, mov r14,r13, runs on both paths)
SCHED_F = 0x06001986        # after the slot
WINDOW_ROW7 = 0x06690D0C + 7 * 18


def sched_stub(at, frame_step, lit_value):
    """Call frame_step, then the replaced code: r2 = *(u16 *)lit; *(u16 *)r8 = r2; r0 = *(u8 *)r11; r13 = r14;
    to SCHED_T if r0 == 3, else SCHED_F."""
    assert at % 4 == 0
    code = [
        0xD100,  # mov.l @(frame),r1
        0x410B,  # jsr @r1
        0x0009,  # nop
        0xD200,  # mov.l @(lit),r2
        0x6221,  # mov.w @r2,r2
        0x2821,  # mov.w r2,@r8
        0x60B0,  # mov.b @r11,r0
        0x6DE3,  # mov r14,r13
        0x8803,  # cmp/eq #3,r0
        0x8B02,  # bf +2 (to the F jump)
        0xD100,  # mov.l @(t),r1
        0x412B,  # jmp @r1
        0x0009,  # nop
        0xD100,  # mov.l @(f),r1
        0x412B,  # jmp @r1
        0x0009,  # nop
    ]
    pool = at + 2 * len(code)
    assert pool % 4 == 0
    lits = [frame_step, lit_value, SCHED_T, SCHED_F]
    for i, li in ((0, 0), (3, 1), (10, 2), (13, 3)):
        pc = at + 2 * i
        d = (pool + 4 * li - ((pc & ~3) + 4)) // 4
        assert 0 <= d < 256 and (pool + 4 * li - ((pc & ~3) + 4)) % 4 == 0
        code[i] |= d
    # bf at index 9 -> index 13: disp = (13*2 - (9*2 + 4)) / 2 = 2
    blob = b''.join(struct.pack('>H', c) for c in code) + b''.join(struct.pack('>I', v) for v in lits)
    return blob, [(at, 2 * len(code))]


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


def text_literals(stock):
    """Literal pool words that code loads (mov.l) and that hold a text tile map address: {literal addr: value}."""
    h = lambda a: struct.unpack_from('>H', stock, a - BASE)[0]
    out = {}
    for a in range(CODE[0], CODE[1], 2):
        op = h(a)
        if op >> 12 == 0xD:
            lit = (a & ~3) + 4 + 4 * (op & 0xFF)
            v = struct.unpack_from('>I', stock, lit - BASE)[0]
            if TEXT_MAP[0] <= v < TEXT_MAP[1]:
                out[lit] = v
    return out


def main():
    prog_path, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    stock = open(prog_path, 'rb').read()
    assert len(stock) == SIZE
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

    # 2. text tile map literals -> the shadow
    lits = text_literals(stock)
    a, n = TEXT_TABLE
    for i in range(n):
        assert TEXT_MAP[0] <= l(a + 4 * i) < TEXT_MAP[1]
        lits[a + 4 * i] = l(a + 4 * i)
    for lit, v in sorted(lits.items()):
        struct.pack_into('>I', img, lit - BASE, SHADOW + v - TEXT_MAP[0])
    print(f'{len(lits)} text tile map literals and pointers moved to the shadow')

    # 3. wrappers and the scheduler hook
    for lit, (old, sym) in POINTERS.items():
        assert l(lit) == old, (hex(lit), hex(l(lit)))
        struct.pack_into('>I', img, lit - BASE, syms[sym])
    assert stock[SCHED_HOOK - BASE:SCHED_HOOK - BASE + len(SCHED_HOOK_CODE)] == SCHED_HOOK_CODE
    blob, cr = sched_stub(STUBS, syms['_wide_text_frame'], l(SCHED_LIT))
    put(STUBS, blob)
    code_ranges.extend(cr)
    t = trampoline(SCHED_HOOK, STUBS)
    assert len(t) == len(SCHED_HOOK_CODE)
    img[SCHED_HOOK - BASE:SCHED_HOOK - BASE + len(t)] = t
    code_ranges.append((SCHED_HOOK, 8))

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
