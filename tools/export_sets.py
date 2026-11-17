#!/usr/bin/env python3
"""MAME ROM sets and MiSTer (jtcps3) MRA files for the patched games of a widescreen Darksoft pack.

    export_sets.py <patched pack dir> --roms <MAME roms dir> [--roms ...] [--stock <unpatched pack dir>]
                   [--mame <out dir>] [--mister <out dir>]

<patched pack dir> holds "SIMM 1-2" and "SIMM 3-6" as tools/make_pack.sh writes them (build/ds-final). Program and
graphics come from there (Standard SH2 files); the only thing taken from your MAME sets is a CPS3 NO CD BIOS chip
(see cps3sets.BIOSES), decrypted and re-encrypted with the key of the set each game is written as.

--mame:   <out>/<game>/<MAME set>.zip, one folder per game (three of them are "sfiii3n"), plus README.txt.
--mister: <out>/_Arcade/_CPS3 Widescreen/<game> (widescreen).mra and <out>/games/mame/<id>.zip, plus README.txt.
--stock:  the unpatched pack, to prove each game's patch stays inside the SIMMs its MAME machine has.
"""
import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cps3sets as C  # noqa: E402
from darksoft import read_program_bank  # noqa: E402
from darksoft_gfx import variants  # noqa: E402

MAME_README = '''Widescreen CPS3 games for MAME (made from a Darksoft CPS-3 pack; tested with MAME 0.289)

Each folder holds one game as the MAME NO CD set named in it. The files differ from MAME's own sets, so MAME
reports wrong checksums and runs the game anyway. Several folders may hold a set named sfiii3n: Makoto Fix and
4rd Strike are 3rd Strike hacks; Warzard always runs on the 3rd Strike machine, because MAME's Red Earth machine
has no second program SIMM, where the widescreen code lives; and New Generation and the JoJo games run on it too
when your MAME sets had no BIOS of their own (a CPS3 BIOS only works with its own game's machine and key).

Run a game with its folder as the ROM path AND its own nvram folder, for example:

    mame -rompath "sfiii-3rd-strike" -nvram_directory "sfiii-3rd-strike/nvram" sfiii3nr1

The nvram folder matters: MAME saves CPS3 program SIMMs to nvram/<set>/ and boots from those copies afterwards,
so sharing an nvram folder with the unpatched game (or with another folder here that has the same set name)
boots whichever program ran there first.

Games and their sets:
{table}

Turn widescreen on in the game's service menu (F2 in MAME): SCREEN MODE, then save.

The BIOS each set uses, taken from your MAME sets. The BIOS sets the region: on a 3rd Strike Japan BIOS,
Warzard and the JoJo games play as their Japanese versions.
{bios}
'''

MISTER_README = '''Widescreen CPS3 games for MiSTer (Jotego's jtcps3 core; made from a Darksoft CPS-3 pack)

Copy the folders to the MiSTer SD card root (/media/fat):
    _Arcade/_CPS3 Widescreen/*.mra   -> /media/fat/_Arcade/_CPS3 Widescreen/
    games/mame/*.zip                  -> /media/fat/games/mame/
The core itself (jtcps3) must already be installed in /media/fat/_Arcade/cores/, and while Jotego's CPS3 core is
in beta it also needs jtbeta.zip in games/mame, the same as his own CPS3 MRAs. Each MRA uses only its own zip, so
your normal CPS3 zips stay untouched. Turn widescreen on in the game's service menu: SCREEN MODE, then save.

These MRAs follow Jotego's published CPS3 MRAs (same header, ROM order and interleave); the tool checks that each
one assembles to the program it was made from. They have not been run on a MiSTer.
{table}
'''


def mra_file_name(title):
    return title.replace(': ', ' - ').replace(' / ', ' - ').replace('/', '-') + ' (widescreen).mra'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('patched')
    ap.add_argument('--roms', action='append', default=[], required=True)
    ap.add_argument('--stock')
    ap.add_argument('--mame')
    ap.add_argument('--mister')
    a = ap.parse_args(argv)
    s12, s36 = os.path.join(a.patched, 'SIMM 1-2'), os.path.join(a.patched, 'SIMM 3-6')

    found = C.find_bioses(a.roms)
    if not found:
        sys.exit('no CPS3 NO CD BIOS found: put one of your MAME sets ' + ', '.join(C.BIOS_ZIPS) +
                 ' (as .zip) in a --roms folder')
    for fam, lst in found.items():
        for crc, plain, where in lst:
            if not C.bios_plain_ok(plain):
                sys.exit(f'{where}: decrypts to no valid reset vector with the {fam} key')
            print(f'BIOS {crc} ({C.BIOSES[crc][1]}) from {where}')

    mame_rows, mister_rows, bios_rows = [], [], []
    games = []
    for g in C.GAMES:
        vs = variants(s36, g['bank'])
        if not vs:
            games.append(g)
            continue
        unknown = [v for v in vs if v not in g.get('gfx', {})]
        if unknown:
            sys.exit(f'{g["title"]}: the pack has graphics files {vs} for bank {g["bank"]}; '
                     f'cps3sets.GAMES does not say what {unknown} are')
        for v in vs:
            games.append(dict(g, **g['gfx'][v], gfx_variant=v))
    for g0 in games:
        picked = C.pick_bios(g0, found)
        if not picked:
            print(f'== {g0["title"]}: SKIPPED, needs its own NO CD set or a 3rd Strike NO CD set (sfiii3n/sfiii3nr1)')
            continue
        g, crc, plain, where = picked
        fam = g['bios']
        files, prog = C.set_chips(g, s12, s36, plain)
        simms = C.MACHINES[g['machine']]
        # the program SIMMs the machine has must hold the whole patch
        if a.stock:
            stock = read_program_bank(os.path.join(a.stock, 'SIMM 1-2'), g['bank'], 'Standard')
            for simm in (1, 2):
                lo, hi = (simm - 1) * 0x800000, simm * 0x800000
                if simm not in simms and stock[lo:hi] != prog[lo:hi]:
                    sys.exit(f'{g["slug"]}: the patch changes SIMM {simm}, which MAME machine {g["machine"]} lacks')
        # chips decrypt back to the patched program
        for simm in (1, 2):
            if simm in simms:
                enc = bytearray(0x800000)
                for i in range(4):
                    enc[i::4] = files[f'{g["prefix"]}-simm{simm}.{i}']
                base = 0x06000000 + (simm - 1) * 0x800000
                assert C.crypt_words(bytes(enc), base, g['key']) == prog[base - 0x06000000:base - 0x06000000 + 0x800000]
        note = '' if g['own'] else (' (runs on the 3rd Strike machine: Warzard always does)' if g0['bios'] is None
                                    else ' (runs on the 3rd Strike machine: no BIOS of its own in your sets)')
        bios_rows.append(f'  {g["slug"] + ":":34} {C.BIOSES[crc][1]}{note}')
        print(f'== {g["title"]}: bank {g["bank"]} as {g["mame"]}, BIOS {C.BIOSES[crc][1]}{note}')

        zip_path = None
        if a.mame:
            d = os.path.join(a.mame, g['slug'])
            os.makedirs(d, exist_ok=True)
            zip_path = os.path.join(d, g['mame'] + '.zip')
            C.write_zip(zip_path, files)
            mame_rows.append(f'  {g["slug"] + "/":34} {g["mame"]:10} {g["title"]}')
            print(f'  {zip_path}')
        if a.mister:
            zd = os.path.join(a.mister, 'games', 'mame')
            md = os.path.join(a.mister, '_Arcade', '_CPS3 Widescreen')
            os.makedirs(zd, exist_ok=True)
            os.makedirs(md, exist_ok=True)
            zname = g['id'] + '.zip'
            if zip_path:
                shutil.copyfile(zip_path, os.path.join(zd, zname))
            else:
                C.write_zip(os.path.join(zd, zname), files)
            text = C.mra_text(g, zname, fam, files, '0' * 32)
            stream = C.assemble(text, lambda name, _z: files[name])
            text = C.mra_text(g, zname, fam, files, C.md5(stream))
            # the stream's header points at SIMM 1 (and 2): decrypt them, compare with the patched program
            h = stream[:32]
            for simm in (1, 2):
                if simm in simms:
                    at = 32 + (int.from_bytes(h[2 * C.STREAM.index(simm):][:2], 'big') << 16)
                    base = 0x06000000 + (simm - 1) * 0x800000
                    raw = bytearray(stream[at:at + 0x800000])  # program SIMMs go in as 16-bit little endian
                    raw[0::2], raw[1::2] = raw[1::2], raw[0::2]
                    got = C.crypt_words(bytes(raw), base, g['key'])
                    assert got == prog[base - 0x06000000:base - 0x06000000 + 0x800000], (g['slug'], simm)
            assert C.crypt_words(stream[32:32 + C.BIOS_SIZE], 0, g['key']) == plain
            mra = os.path.join(md, mra_file_name(g['title']))
            open(mra, 'w', encoding='utf-8', newline='\n').write(text)
            mister_rows.append(f'  {os.path.basename(mra)}  ->  games/mame/{zname}')
            print(f'  {mra} (assembles to {len(stream):#x} bytes, md5 {C.md5(stream)})')

    if a.mame:
        open(os.path.join(a.mame, 'README.txt'), 'w', encoding='utf-8', newline='\n').write(
            MAME_README.format(table='\n'.join(mame_rows), bios='\n'.join(bios_rows)))
    if a.mister:
        open(os.path.join(a.mister, 'README.txt'), 'w', encoding='utf-8', newline='\n').write(MISTER_README.format(table='\n'.join(mister_rows)))


if __name__ == '__main__':
    main()
