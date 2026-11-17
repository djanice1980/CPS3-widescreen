#!/usr/bin/env python3
"""Build the widescreen patch of a CPS3 JoJo game (Darksoft Standard SH2 program, plain):

    build_jojoba.py jojoba <bank 4 program (16 MB)> <out dir>    Heritage for the Future (bank 4)
    build_jojoba.py jojo <bank 3 program (16 MB)> <out dir>      JoJo's Venture (bank 3)

No source exists for these games, so the patch is built from addresses found in their programs (GAMES below;
Venture's were mapped from HFTF's with tools/sigfind.py and tools/litmap.py: the same engine, the same code at
other addresses). src/jojoba/wide.c is the module for both, its game addresses in a game.h written here. Steps:

 1. compile src/jojoba/wide.c (SHC) and link it alone at MODULE (free, zero-filled, never read: checked in MAME);
 2. copy the text routines twice: copy A as they are, copy B drawing into the module's RAM shadow of the text
    tile map (its text-RAM literals changed); each routine's entry gets a jump to a dispatcher that runs copy B
    in wide mode, copy A otherwise. The copies are verbatim contiguous blocks, so their branches and literal
    pools stay valid; tools/sh2flow.py checks that nothing in them reaches outside the block;
 3. point the method tables at the module's wrappers (camera task, screen offset step and reset, set screen
    mode, text plane base); the task scheduler's end-of-pass step calls the module's frame step (the shadow to
    text RAM) first;
 4. screen mode 7 row of the window table: 3rd Strike's 496-pixel timing instead of the unused 512;
 5. the SCREEN MODE item in the service menu's game settings and the boot step that applies it (games with 'menu');
 6. write <out>/<game>-wide-prog.bin, <out>/<game>-code.json (instruction ranges, for Custom carts) and
    <out>/<game>-wide.json (the patch, tools/make_patch.py).
"""
import json
import os
import re
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from sh2flow import Prog  # noqa: E402
from hook import trampoline  # noqa: E402
from code_ranges import listing_code  # noqa: E402

BASE = 0x06000000
SIZE = 0x01000000
DECOMP = os.path.join(ROOT, 'vendor/sfIII3-cps3-decomp')  # SHC lives here

MODULE = 0x065C0000         # PWIDE
MODULE_CONST = 0x065C3000   # CWIDE
DISPATCH = 0x065C4000
COPIES = 0x065C5000
FREE = (0x06500000, 0x065D7A60)  # zero-filled, no reads during attract + play (MAME read tap)
# the module's RAM (src/jojoba/wide.c says why it is here and not at 0207F000, where the Darksoft region byte and
# no-CD flag are)
WIDE_FLAG = 0x0207C000   # holds WIDE_MARK in wide mode
WIDE_MARK = 0x5A
TEXT_DIRTY = 0x0207C008  # set by copy B (and the plane base getter): the shadow changed
DARKSOFT_BYTES = (0x0207F000, 0x0207F100)  # the module must not have a pointer into this range (checked below)

SHADOW = 0x02074000  # the tile map's RAM shadow (src/jojoba/wide.c), 16 KB of RAM the game never uses
# copy B's literals: text RAM tile map start and end -> the shadow's; the 16 KB wrap mask (FFFE3FFF clears the
# overflow of a 25040000-based pointer) can't wrap a shadow pointer, so it keeps the pointer: text past the
# map's last row (never on screen) lands in the 16 KB after the shadow, also unused RAM
COPY_B_LITERALS = {0x25040000: SHADOW, 0x25044000: SHADOW + 0x4000, 0xFFFE3FFF: 0xFFFFFFFF}
# the task scheduler (main loop), after each pass over the tasks: mask interrupts, call 0600091C(9)
SCHED_HOOK = 0x060006BC
SCHED_HOOK_CODE = bytes.fromhex('91390002 2019CBF0 400EB129 E409'.replace(' ', ''))
SCHED_HOOK_BACK = 0x060006CA
MENU_TABLES = 0x065C3800        # the SCREEN MODE item's menu tables (after the module's constants)
JP_SCREEN_MODE = [0x0004, 0x000A, 0x0001, 0x8F, 0x85, 0xBE, 0x29, 0xC4, 0xB9, 0x29, 0xA0, 0x0000]  # katakana SCREEN MODE
WINDOW_ROW7_STOCK = (35, 117, 629, 454, 3, 21, 245, 262, 101)  # both games: an unused 512-pixel mode
WINDOW_ROW7_3S = (35, 118, 613, 454, 3, 21, 245, 262, 101)

GAMES = {
    'jojoba': dict(
        # the text routines: contiguous blocks and the entries the game calls (the last: clear the tile map and
        # home the console print pointer)
        text_blocks=[
            (0x061B2E88, 0x061B3438, [0x061B2E88, 0x061B30B2, 0x061B30FE, 0x061B3150, 0x061B3222, 0x061B325C,
                                      0x061B32C6, 0x061B32F8, 0x061B3352]),
            (0x061C17AE, 0x061C1DC6, [0x061C17AE, 0x061C17FE, 0x061C188C, 0x061C19DC, 0x061C1A26, 0x061C1B00,
                                      0x061C1C90]),
            (0x061C0E8E, 0x061C0EE8, [0x061C0E8E]),
        ],
        # method table slots and the literal that installs the camera task method
        pointers={
            0x06176810: (0x06176C02, '_wide_camera'),
            0x06278768: (0x061BE49C, '_wide_scroll_publish'),
            0x06278758: (0x061BE35E, '_wide_scroll_reset'),
            0x06278750: (0x061C66A0, '_wide_set_screen_mode'),
            0x062787A4: (0x061BE760, '_wide_ss_base'),
        },
        window_row7=0x062607A0 + 7 * 18,
        header=dict(CAMERA_X=0x0203145C, STAGE_NO=0x02031459, CAM_LIMITS=0x061D9FD8, SCROLL_OFS=0x0205DDBE,
                    SCHED_PASS=0x020167D0, CAMERA=0x06176C02, SCROLL_PUBLISH=0x061BE49C, SCROLL_RESET=0x061BE35E,
                    SET_MODE=0x061C66A0,
                    REGION=0x0205BFDC, CFG_WIDE=0x0205C057, CFG_SNAP=0x0205C027, EE_WIDE=0x0205C087,
                    PRINT_EN=0x061C188C, PRINT_JP=0x061C24CC, EE_LOAD=0x061B7AA4),
        menu=dict(
            # the service menu's game settings (task at 0619DAF8): its tables, extended by SCREEN MODE (item id 7)
            # before EXIT. The menu reads them through these literals; the RAM tables (initialised data, ROM image
            # at RAM + data_rom) stay.
            data_rom=0x06270F98 - 0x0200EB5C,
            regions=9,                  # 0, 1 Japanese; the rest English
            items=7,                    # settings before EXIT
            literals={                  # literal: what it holds (checked), the new table's name
                0x0619DCAC: (0x062192F7, 'last'),      # last cursor index, per region (all 7)
                0x0619DEE8: (0x0200EB80, 'ids'),       # per region: cursor index -> item id (all 062192F0: 0..7)
                0x0619E6AC: (0x0200EB80, 'ids'),
                0x0619DEEC: (0x0200EBB0, 'change'),    # item id -> change handler (r4: 0 right / shot 1, 1 left)
                0x0619E6B0: (0x0200EBCC, 'draw'),      # item id -> value drawer
                0x0619DC94: (0x0200EB5C, 'en_exit'),   # per region: English EXIT label (06219248)
                0x0619DC9C: (0x06219300, 'cur_en'),    # cursor x, y per index (English, then Japanese)
                0x0619DEDC: (0x06219300, 'cur_en'),
                0x0619DCA0: (0x06219310, 'cur_jp'),
                0x0619DEE0: (0x06219310, 'cur_jp'),
                0x0619DB80: (0x06218FEC, 'jp_text'),   # the Japanese screen's text (title, items, scales, EXIT)
            },
            last=0x062192F7, ids=0x062192F0, ids_ram=0x0200EB80, en_exit=0x06219248, en_exit_ram=0x0200EB5C,
            change_ram=0x0200EBB0, draw_ram=0x0200EBCC, selectable_ram=0x0200EBA4,
            cur_en=0x06219300, cur_jp=0x06219310,
            jp_text=(0x06218FEC, 0x062190DC),
            jp_exit=0x062190C2,         # its last record: EXIT at y 11 (row 10 is empty)
            boot_load=(0x06003034, 0x061B7AA4),  # literal: the boot's settings load, then the screen mode is fixed
        ),
    ),
    'jojo': dict(
        text_blocks=[
            (0x061617E0, 0x06161D90, [0x061617E0, 0x06161A0A, 0x06161A56, 0x06161AA8, 0x06161B7A, 0x06161BB4,
                                      0x06161C1E, 0x06161C50, 0x06161CAA]),
            (0x0616F752, 0x0616FD6A, [0x0616F752, 0x0616F7A2, 0x0616F830, 0x0616F980, 0x0616F9CA, 0x0616FAA4,
                                      0x0616FC34]),
            (0x0616EE36, 0x0616EE8C, [0x0616EE36]),
        ],
        pointers={
            0x06128A94: (0x06128E82, '_wide_camera'),
            0x06200EB8: (0x0616C440, '_wide_scroll_publish'),
            0x06200EA8: (0x0616C302, '_wide_scroll_reset'),
            0x06200EA0: (0x0617464C, '_wide_set_screen_mode'),
            0x06200EF4: (0x0616C704, '_wide_ss_base'),
        },
        window_row7=0x061ED310 + 7 * 18,
        header=dict(CAMERA_X=0x0202D040, STAGE_NO=0x0202D03D, CAM_LIMITS=0x061846A4, SCROLL_OFS=0x0205567A,
                    SCHED_PASS=0x020123B4, CAMERA=0x06128E82, SCROLL_PUBLISH=0x0616C440, SCROLL_RESET=0x0616C302,
                    SET_MODE=0x0617464C,
                    REGION=0x02054814, CFG_WIDE=0x02054897, CFG_SNAP=0x02054867, EE_WIDE=0x020548C7,
                    PRINT_EN=0x0616F830, PRINT_JP=0x06170470, EE_LOAD=0x06165B40),
        # the same menu as HFTF (task 0614CECC, same text), 8 regions; its ROM tables are packed at odd addresses
        menu=dict(
            data_rom=0x061FA890 - 0x0200B8E4,
            regions=8,
            items=7,
            literals={
                0x0614D054: (0x061B0127, 'last'),
                0x0614D280: (0x0200B904, 'ids'),
                0x0614D970: (0x0200B904, 'ids'),
                0x0614D284: (0x0200B930, 'change'),
                0x0614D974: (0x0200B94C, 'draw'),
                0x0614D03C: (0x0200B8E4, 'en_exit'),
                0x0614D044: (0x061B012F, 'cur_en'),
                0x0614D26C: (0x061B012F, 'cur_en'),
                0x0614D048: (0x061B013F, 'cur_jp'),
                0x0614D270: (0x061B013F, 'cur_jp'),
                0x0614CF44: (0x061AFE1C, 'jp_text'),
            },
            last=0x061B0127, ids=0x061B0120, ids_ram=0x0200B904, en_exit=0x061B0078, en_exit_ram=0x0200B8E4,
            change_ram=0x0200B930, draw_ram=0x0200B94C, selectable_ram=0x0200B924,
            cur_en=0x061B012F, cur_jp=0x061B013F,
            jp_text=(0x061AFE1C, 0x061AFF0C),
            jp_exit=0x061AFEF2,
            boot_load=(0x06002FEC, 0x06165B40),
        ),
    ),
}

def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, errors='replace', **kw)
    return r.stdout + r.stderr


def compile_and_link(out_dir, G, defines):
    env = dict(os.environ, SHC_LIB='bin', SHC_TMP='tmp\\jojoba')
    objdir = 'obj/jojoba'
    os.makedirs(os.path.join(DECOMP, objdir), exist_ok=True)
    os.makedirs(os.path.join(DECOMP, 'tmp/jojoba'), exist_ok=True)
    src = os.path.join(DECOMP, objdir, 'wide.c')
    # the game's addresses go where wide.c includes game.h (SHC does not find a header next to the source)
    hdr = [f'/* {G["name"]}: game.h, written by tools/build_jojoba.py */']
    hdr += [f'#define G_{k} 0x{v:08X}' for k, v in sorted(G['header'].items())]
    hdr += [f'#define G_HAS_MENU {1 if G["menu"] else 0}']
    c = open(os.path.join(ROOT, G.get('src', 'src/jojoba/wide.c'))).read()
    inc = '#include "game.h"'
    assert c.count(inc) == 1
    open(src, 'w').write(c.replace(inc, '\n'.join(hdr)))
    log = run(['wine', 'bin/shc.exe', 'obj\\jojoba\\wide.c', '-cpu=sh2', '-division=cpu', '-endian=big', '-pic=0',
               '-nortnext', '-optimize=1', '-speed', '-object=obj\\jojoba\\wide.obj',
               '-listfile=obj\\jojoba\\wide.lis', '-show=object'], cwd=DECOMP, env=env)
    if ') : ' in log or not os.path.exists(os.path.join(DECOMP, objdir, 'wide.obj')):
        sys.exit('wide.c did not compile:\n' + log)
    lis = open(os.path.join(DECOMP, objdir, 'wide.lis'), encoding='latin-1').read()
    module, module_const = G.get('module', MODULE), G.get('module_const', MODULE_CONST)
    start = f'PWIDE({module:08X})' + (f',CWIDE({module_const:08X})' if re.search(r'^CWI ', lis, re.M) else '')
    sub = ['INPUT obj\\jojoba\\wide.obj', 'START ' + start]
    sub += [f'DEFINE {s}({v:08X})' for s, v in sorted(defines.items())]
    sub += ['OUTPUT tmp\\jojoba\\wide.abs', 'PRINT tmp\\jojoba\\wide.map', 'EXIT']
    open(os.path.join(DECOMP, 'tmp/jojoba/wide.sub'), 'w', newline='\r\n').write('\n'.join(sub) + '\n')
    for f in ('tmp/jojoba/wide.abs', 'wide.bin', 'tmp/jojoba/wide.bin'):
        if os.path.exists(os.path.join(DECOMP, f)):
            os.remove(os.path.join(DECOMP, f))
    out = run(['wine', 'bin/lnk.exe', '-subcommand=tmp\\jojoba\\wide.sub'], cwd=DECOMP)
    if 'UNDEFINED' in out or '**' in out.replace('** 105', ''):
        sys.exit('link:\n' + out)
    out = run(['wine', 'bin/rof2bin.exe', '-s=06000000', '-e=07000000', '-v=00', 'tmp\\jojoba\\wide.abs'], cwd=DECOMP)
    for cand in ('wide.bin', 'tmp/jojoba/wide.bin'):
        p = os.path.join(DECOMP, cand)
        if os.path.exists(p):
            img = open(p, 'rb').read()
            os.remove(p)
            break
    else:
        sys.exit('rof2bin wrote nothing:\n' + out)
    mp = open(os.path.join(DECOMP, 'tmp/jojoba/wide.map'), encoding='latin-1').read()
    syms = {m.group(1): int(m.group(2), 16)
            for m in re.finditer(r"^(_\w+)\s+H'([0-9A-F]{8})\s+(?:ENT|DAT)", mp, re.M)}
    spans = [(int(a, 16), int(b, 16) + 1) for a, b in re.findall(r"^[PC]WIDE\s+H'([0-9A-F]{8})\s+-\s+H'([0-9A-F]{8})",
                                                                   mp, re.M)]
    for f in ('wide.lis', 'wide.c'):
        os.replace(os.path.join(DECOMP, objdir, f), os.path.join(out_dir, f))
    return img, syms, spans


def dispatcher(at, copy_a, copy_b):
    """Jump to copy_b if the wide flag is set (and mark the shadow dirty), else copy_a. Uses r0 and T (free at a
    routine's entry); r1 is saved on the stack around its use."""
    code = [
        0xD000,  # mov.l @(flag),r0       (displacements filled below)
        0x6000,  # mov.b @r0,r0
        0x8800 | WIDE_MARK,  # cmp/eq #WIDE_MARK,r0
        0x8902,  # bt wide                (index 7: disp = (7*2 - (3*2 + 4)) / 2)
        0xD000,  # mov.l @(a),r0
        0x402B,  # jmp @r0
        0x0009,  # nop
        0x2F16,  # wide: mov.l r1,@-r15
        0xD100,  # mov.l @(dirty),r1
        0x2100,  # mov.b r0,@r1           (the flag's value: not 0)
        0x61F6,  # mov.l @r15+,r1
        0xD000,  # mov.l @(b),r0
        0x402B,  # jmp @r0
        0x0009,  # nop
    ]
    n = len(code) * 2
    pool = at + n + ((at + n) % 4)  # 4-aligned literal pool after the code
    pad = pool - (at + n)
    lits = [WIDE_FLAG, copy_a, copy_b, TEXT_DIRTY]

    def movl(i, lit_index):
        pc = at + 2 * i
        d = (pool + 4 * lit_index - ((pc & ~3) + 4)) // 4
        assert 0 <= d < 256 and (pool + 4 * lit_index - ((pc & ~3) + 4)) % 4 == 0
        return code[i] | d
    code[0] = movl(0, 0)
    code[4] = movl(4, 1)
    code[8] = movl(8, 3)
    code[11] = movl(11, 2)
    blob = b''.join(struct.pack('>H', c) for c in code) + b'\x00\x09' * (pad // 2)
    blob += b''.join(struct.pack('>I', v) for v in lits)
    return blob, [(at, n)]


def sched_stub(at, frame_step):
    """Call frame_step, then do the scheduler's replaced code: mask interrupts (SR.I = 15) and call 0600091C(9)
    returning to SCHED_HOOK_BACK."""
    assert at % 4 == 0
    code = [
        0xD100,  # mov.l @(frame),r1
        0x410B,  # jsr @r1
        0x0009,  # nop
        0xD000,  # mov.l @(back),r0
        0x402A,  # lds r0,pr
        0xD100,  # mov.l @(mask),r1
        0x0002,  # stc sr,r0
        0x2019,  # and r1,r0
        0xCBF0,  # or #F0,r0
        0x400E,  # ldc r0,sr
        0xD100,  # mov.l @(091c),r1
        0x412B,  # jmp @r1
        0xE409,  # mov #9,r4
        0x0009,  # pad
    ]
    pool = at + 2 * len(code)
    assert pool % 4 == 0
    lits = [frame_step, SCHED_HOOK_BACK, 0xFFFFFF0F, 0x0600091C]
    for i, li in ((0, 0), (3, 1), (5, 2), (10, 3)):
        pc = at + 2 * i
        d = (pool + 4 * li - ((pc & ~3) + 4)) // 4
        assert 0 <= d < 256
        code[i] |= d
    blob = b''.join(struct.pack('>H', c) for c in code) + b''.join(struct.pack('>I', v) for v in lits)
    return blob, [(at, 2 * (len(code) - 1))]


def main():
    game, prog_path, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    G = dict(GAMES[game], name=game)
    os.makedirs(out_dir, exist_ok=True)
    stock = open(prog_path, 'rb').read()
    assert len(stock) == SIZE
    img = bytearray(stock)
    p = Prog(stock, BASE)
    code_ranges = []  # (addr, len) of new instructions

    def put(addr, data):
        assert FREE[0] <= addr and addr + len(data) <= FREE[1], hex(addr)
        assert not any(img[addr - BASE:addr - BASE + len(data)]), f'{addr:08X} not free'
        img[addr - BASE:addr - BASE + len(data)] = data

    def copy_block(lo, hi, entries, at, shifted):
        """Verbatim copy of lo..hi at `at` (same address mod 4); returns {entry: copy address}."""
        assert at % 4 == lo % 4
        code, refs, unknown = p.reach(entries)
        if unknown:
            sys.exit(f'{lo:08X}: computed jumps {unknown}')
        out = [(a, t, k) for a, t, k in refs if not lo <= t < hi]
        if out:
            sys.exit(f'{lo:08X}-{hi:08X} reaches outside: {out[:4]}')
        if any(not lo <= a < hi for a in code):
            sys.exit(f'{lo:08X}-{hi:08X}: code outside the block')
        blk = bytearray(stock[lo - BASE:hi - BASE])
        if shifted:
            pools = sorted({t for a, t, k in refs if k == 'movl' and p.l(t) in COPY_B_LITERALS})
            for t in pools:
                struct.pack_into('>I', blk, t - lo, COPY_B_LITERALS[p.l(t)])
            print(f'  {lo:08X}: {len(pools)} text RAM literal(s) moved to the shadow')
        put(at, bytes(blk))
        code_ranges.extend((at + a - lo, 2) for a in sorted(code))
        return {e: at + e - lo for e in entries}

    # 2. text routine copies and dispatchers
    at = COPIES
    copies = []
    for lo, hi, entries in G['text_blocks']:
        a_at = (at + 15) // 16 * 16 + lo % 4
        a = copy_block(lo, hi, entries, a_at, False)
        b_at = (a_at + hi - lo + 15) // 16 * 16 + lo % 4
        b = copy_block(lo, hi, entries, b_at, True)
        at = b_at + hi - lo
        copies.append((entries, a, b))
    assert at < 0x065D0000

    # 1. the module
    module, syms, spans = compile_and_link(out_dir, G, {})
    for lo, hi in spans:
        put(lo, module[lo - BASE:hi - BASE])
    print('module ' + ', '.join(f'{lo:08X}-{hi:08X}' for lo, hi in spans))
    code_ranges.extend(module_code(os.path.join(out_dir, 'wide.lis'), img))

    d_at = DISPATCH
    for entries, a, b in copies:
        for e in entries:
            blob, cr = dispatcher(d_at, a[e], b[e])
            put(d_at, blob)
            code_ranges.extend(cr)
            # the routine's entry jumps to the dispatcher
            t = trampoline(e, d_at)
            img[e - BASE:e - BASE + len(t)] = t
            code_ranges.append((e, 6))
            d_at += (len(blob) + 15) // 16 * 16

    # the scheduler step: a stub runs the frame step, then what the replaced code did
    assert stock[SCHED_HOOK - BASE:SCHED_HOOK - BASE + len(SCHED_HOOK_CODE)] == SCHED_HOOK_CODE
    blob, cr = sched_stub(d_at, syms['_wide_text_frame'])
    put(d_at, blob)
    code_ranges.extend(cr)
    t = trampoline(SCHED_HOOK, d_at)
    assert len(t) <= len(SCHED_HOOK_CODE)
    img[SCHED_HOOK - BASE:SCHED_HOOK - BASE + len(t)] = t
    code_ranges.append((SCHED_HOOK, 6))

    # 3. method pointers
    for slot, (old, sym) in G['pointers'].items():
        assert p.l(slot) == old, (hex(slot), hex(p.l(slot)))
        struct.pack_into('>I', img, slot - BASE, syms[sym])

    # 5. the SCREEN MODE menu item and the boot latch
    assert max(hi for lo, hi in spans) <= MENU_TABLES
    M = G['menu']
    if M:
        tables = menu_tables(stock, p, syms, M)
        for name, (addr, blob) in tables.items():
            put(addr, blob)
        for lit, (old, name) in M['literals'].items():
            assert p.l(lit) == old, hex(lit)
            struct.pack_into('>I', img, lit - BASE, tables[name][0])
        lit, old = M['boot_load']
        assert p.l(lit) == old
        struct.pack_into('>I', img, lit - BASE, syms['_wide_boot_load'])

    # 4. screen mode 7 width
    row = G['window_row7']
    assert struct.unpack_from('>9h', stock, row - BASE) == WINDOW_ROW7_STOCK
    struct.pack_into('>9h', img, row - BASE, *WINDOW_ROW7_3S)

    # the Darksoft region byte and no-CD flag: the patch must add no pointer to them (the game's own stay)
    def darksoft_pointers(image):
        return [BASE + i for i in range(0, SIZE, 4)
                if DARKSOFT_BYTES[0] <= struct.unpack_from('>I', image, i)[0] < DARKSOFT_BYTES[1]]
    assert darksoft_pointers(img) == darksoft_pointers(stock), 'the patch points into the Darksoft bytes'

    out_prog = os.path.join(out_dir, f'{game}-wide-prog.bin')
    open(out_prog, 'wb').write(img)
    merged = merge(code_ranges)
    code_json = os.path.join(out_dir, f'{game}-code.json')
    json.dump({'code': [[f'{a:08X}', n] for a, n in merged]}, open(code_json, 'w'))
    print(run([sys.executable, os.path.join(ROOT, 'tools/make_patch.py'), prog_path, out_prog, game,
               os.path.join(out_dir, f'{game}-wide.json'), code_json]))
    for s in sorted(syms, key=syms.get):
        print(f'  {syms[s]:08X} {s}')


def menu_tables(stock, p, syms, M):
    """The game settings menu's tables with SCREEN MODE: {name: (address, bytes)}, laid out from MENU_TABLES."""
    def rom(a, n):
        return stock[a - BASE:a - BASE + n]
    # the stock tables are what the menu assumes: the same for every region, 7 settings + EXIT
    assert rom(M['last'], M['regions']) == bytes([M['items']] * M['regions'])
    assert all(p.l(M['ids_ram'] + M['data_rom'] + 4 * r) == M['ids'] for r in range(M['regions']))
    assert rom(M['ids'], M['items'] + 1) == bytes(range(M['items'] + 1))
    assert all(p.l(M['en_exit_ram'] + M['data_rom'] + 4 * r) == M['en_exit'] for r in range(M['regions']))
    assert rom(M['cur_en'], 16) == bytes.fromhex('01050107 0109010b 010d010f 01110113'.replace(' ', ''))
    assert rom(M['cur_jp'], 16) == bytes.fromhex('02030204 02050206 02070208 0209020b'.replace(' ', ''))
    # the per-cursor 'selectable' flags (RAM 0200EBA4, 12 bytes): index 8 (EXIT now) must be on
    assert rom(M['selectable_ram'] + M['data_rom'], 12)[:M['items'] + 2] == bytes([1] * (M['items'] + 2))
    jp = bytearray(rom(M['jp_text'][0], M['jp_text'][1] - M['jp_text'][0]))
    exit_rec = M['jp_exit'] - M['jp_text'][0]
    assert struct.unpack_from('>3H', jp, exit_rec) == (4, 0x0B, 1) and jp[-2:] == b'\0\0'
    jp[-2:] = b'\xff\xff'  # then SCREEN MODE in the free row 10 above EXIT (FFFF: another record follows)
    jp += b''.join(struct.pack('>H', h) for h in JP_SCREEN_MODE)

    out, at = {}, MENU_TABLES

    def add(name, blob, align=4):
        nonlocal at
        at = (at + align - 1) // align * align
        out[name] = (at, bytes(blob))
        at += len(blob)
    add('last', [M['items'] + 1] * 16)  # (16: also any region past the 9 known)
    add('id_list', list(range(M['items'] + 2)))
    add('ids', b''.join(struct.pack('>I', out['id_list'][0]) for _ in range(M['regions'])))
    change = [p.l(M['change_ram'] + M['data_rom'] + 4 * i) for i in range(M['items'])] + [syms['_wide_cfg_change']]
    draw = [p.l(M['draw_ram'] + M['data_rom'] + 4 * i) for i in range(M['items'])] + [syms['_wide_cfg_draw']]
    add('change', b''.join(struct.pack('>I', v) for v in change))
    add('draw', b''.join(struct.pack('>I', v) for v in draw))
    add('en_exit', b''.join(struct.pack('>I', syms['_wide_en_labels']) for _ in range(M['regions'])))
    add('cur_en', rom(M['cur_en'], 16) + bytes([1, 0x15]))
    add('cur_jp', rom(M['cur_jp'], 14) + bytes([2, 0x0A, 2, 0x0B]))
    add('jp_text', jp)
    return out


def module_code(lis, img, module=MODULE):
    """Instruction halfwords of the module (one object: PWIDE starts at module), checked against the image."""
    out = []
    for sct, off, hexcode in listing_code(lis):
        if sct != 'PWI':
            sys.exit(f'{lis}: instruction in section {sct}')
        at = module + off
        if img[at - BASE:at - BASE + 2].hex().upper() != hexcode:
            sys.exit(f'listing says {hexcode} at {at:08X}, image has {img[at - BASE:at - BASE + 2].hex()}')
        out.append((at, 2))
    return out


def merge(ranges):
    out = []
    for a, n in sorted(ranges):
        if out and a <= out[-1][0] + out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][0] + out[-1][1], a + n) - out[-1][0])
        else:
            out.append((a, n))
    return out


if __name__ == '__main__':
    main()
