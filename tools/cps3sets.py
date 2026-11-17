"""CPS3 NO CD ROM sets (MAME) and MRA files (MiSTer, Jotego's jtcps3 core) made from Darksoft bank images.

The facts here, and where they come from:
- Keys: MAME 0.289 src/mame/capcom/cps3.cpp (init_crypt calls). A NO CD set stores the whole program encrypted:
  every 32-bit word XORed with cps3_mask(address, key1, key2), and the BIOS the same way with its byte offset as
  the address (decrypt_bios). Checked here against MAME's CRCs: Darksoft's unpatched banks, encrypted with these
  keys, give MAME's exact chips for jojonr2 / jojobanr2 / sfiii3nr1 SIMM 2 and New Generation's SIMM 1.
- Machines (which SIMMs a set has): cps3.cpp machine configs. redearth/sfiii have no SIMM 2.
- Chip layout: a program SIMM is four 2 MB chips, chip i = byte i (from the top) of each big-endian word; a
  graphics SIMM is MAME's simm<n>.<i> as tools/darksoft_gfx.py makes them.
- MRA layout: Jotego's jtcores cores/cps3/cfg/mame2mra.toml and the released MRAs in jotego/jtbin. A 32-byte
  header (region start offsets in 64 kB units, the key, the decryption mode, the BIOS region field), then BIOS,
  SIMM 1, 3, 4, 5, 2, 6. assemble() reproduces the published asm_md5 of sfiii3nr1 from a real set.
"""
import hashlib
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

from cps3crypt import mask_table
from darksoft import read_program_bank
from darksoft_gfx import chips as gfx_chips

KEYS = {'sfiii': (0xB5FE053E, 0xFC03925A), 'redearth': (0x9E300AB1, 0xA175B82C),
        'jojo': (0x02203EE3, 0x01301972), 'jojoba': (0x23323EE3, 0x03021972),
        'sfiii3': (0xA55432B4, 0x0C129981)}

# NO CD BIOS chips MAME 0.289 knows: crc -> (key family, what it is). CD BIOSes would look for a CD drive.
BIOSES = {'ca2b715f': ('sfiii', 'New Generation, Asia (sfiiin)'),
          '73e32463': ('sfiii', 'New Generation, Asia (sfiiina)'),
          '7a4f0851': ('redearth', 'Red Earth, Asia (redearthn)'),
          '05b4f953': ('jojo', "JoJo's Venture, Asia (jojon)"),
          '4dab19f5': ('jojoba', "JoJo's Bizarre Adventure, Japan (jojoban)"),
          '1ee2d679': ('jojoba', "JoJo's Bizarre Adventure, Europe (jojobaner1)"),
          '1edc6366': ('sfiii3', '3rd Strike, Japan (sfiii3n)'),
          'a12ebcd1': ('sfiii3', '3rd Strike, Asia (sfiii3na)')}
# MAME set zips that can hold those chips (NO CD clones, and their parents for merged sets)
BIOS_ZIPS = ['sfiiina', 'sfiiin', 'sfiii', 'redearthn', 'redearthnr1', 'redearth', 'jojonr2', 'jojonr1', 'jojon',
             'jojo', 'jojobanr2', 'jojobanr1', 'jojoban', 'jojobaner1', 'jojobaner2', 'jojoba', 'sfiii3nr1',
             'sfiii3n', 'sfiii3nar1', 'sfiii3na', 'sfiii3']

# MAME machine -> {SIMM: chips}; program SIMMs 1-2 have 4 chips, graphics SIMMs 3-6 have 2 or 8
MACHINES = {'sfiii': {1: 4, 3: 8, 4: 8, 5: 2}, 'jojo': {1: 4, 2: 4, 3: 8, 4: 8, 5: 2},
            'jojoba': {1: 4, 2: 4, 3: 8, 4: 8, 5: 8}, 'sfiii3': {1: 4, 2: 4, 3: 8, 4: 8, 5: 8, 6: 8}}

BUTTONS6 = ('<buttons names="Light Punch,Middle Punch,Heavy Punch,Light Kick,Middle Kick,Heavy Kick,Start,Coin,'
            'Core credits" default="A,B,X,Y,L,R,Start,Select,-" count="6"/>')
BUTTONS_JOJO = ('<buttons names="Light,Middle,Heavy,Stand On,-,-,Start,Coin,Core credits" '
                'default="A,B,X,Y,Start,Select,-" count="4"/>')

# The 128-byte EEPROM image the jtcps3 MRAs preload (index 2), from mame2mra.toml, by the set the game is.
EEPROM = {
    'sfiiina': '01 01 00 00 00 00 01 00 02 00 00 01 00 00 01 02 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 '
               '01 01 02 00 00 00 00 01 01 23 05 95 20 44 32 53 01 01 00 00 00 00 01 00 02 00 00 01 00 00 01 02 '
               '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 01 02 00 00 00 00 01 01 23 05 95 20 44 32 53 '
               + '00 ' * 32,
    'redearthn': '01 01 00 00 00 00 01 00 02 00 00 01 00 00 01 02 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 '
                 '01 01 01 07 00 01 01 00 08 23 05 95 20 44 32 53 01 01 00 00 00 00 01 00 02 00 00 01 00 00 01 02 '
                 '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 01 01 07 00 01 01 00 08 23 05 95 20 44 32 53 '
                 '01 ' + '00 ' * 31,
    'jojon': '00 00 01 00 01 01 00 00 00 00 01 01 00 00 00 00 00 00 00 00 01 07 00 00 01 00 01 01 00 00 00 01 '
             '00 00 00 00 00 00 00 00 00 00 00 00 02 4b 4a 4a 00 00 01 00 01 01 00 00 00 00 01 01 00 00 00 00 '
             '00 00 00 00 01 07 00 00 01 00 01 01 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 00 02 4b 4a 4a '
             + '00 ' * 32,
    'jojobanr2': '00 00 01 00 01 01 00 00 00 01 01 01 00 00 00 00 00 00 00 00 01 01 00 00 00 00 01 01 00 00 00 01 '
                 '00 00 00 00 00 00 00 00 00 00 00 00 01 4d 4a 4a 00 00 01 00 01 01 00 00 00 01 01 01 00 00 00 00 '
                 '00 00 00 00 01 01 00 00 00 00 01 01 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 00 01 4d 4a 4a '
                 + '00 ' * 32,
    'sfiii3nr1': '01 01 00 00 00 00 01 01 02 00 00 01 00 00 00 02 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 '
                 '01 01 02 00 01 00 00 11 00 15 04 99 20 53 33 33 01 01 00 00 00 00 01 01 02 00 00 01 00 00 00 02 '
                 '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 01 02 00 01 00 00 11 00 15 04 99 20 53 33 33 '
                 + '00 ' * 32,
    'sfiii3n': '01 01 00 00 00 00 01 01 02 00 00 01 00 00 00 02 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 '
               '01 01 02 00 01 00 00 11 00 15 04 99 20 53 33 33 01 01 00 00 00 00 01 01 02 00 00 01 00 00 00 02 '
               '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 01 02 00 01 00 00 11 00 15 04 99 20 53 33 33 '
               '01 ' + '00 ' * 31,
}

# One entry per patched game. mame/prefix/machine/key: the MAME set the game runs as with its own BIOS (bios =
# that BIOS's key family). Without its own BIOS a game runs as FALLBACK, the 3rd Strike machine with a 3rd Strike
# BIOS, which runs every bank (this is how all banks were tested). A BIOS can't be moved to another key: it copies
# a routine into the SH-2 cache RAM (C0000000) that is stored encrypted for its own key (MAME sh2cache_ram_w), so a
# re-keyed 3rd Strike BIOS crashes there. Warzard always uses FALLBACK: its widescreen code lives in SIMM 2, and
# the Red Earth machine has no SIMM 2 (Red Earth's inputs are 3rd Strike's, so only button names change).
GAMES = [
    dict(bank=0, slug='sfiii-new-generation', id='sfiiinw', title='Street Fighter III: New Generation',
         mame='sfiiina', prefix='sfiii', machine='sfiii', key='sfiii', bios='sfiii', eeprom='sfiiina',
         year=1997, buttons=BUTTONS6),
    dict(bank=1, slug='warzard', id='warzardw', title='Warzard / Red Earth', mame=None, bios=None,
         eeprom='redearthn', year=1996, buttons=BUTTONS6),
    dict(bank=3, slug='jojos-venture', id='jojow', title="JoJo's Venture", mame='jojonr2', prefix='jojo',
         machine='jojo', key='jojo', bios='jojo', eeprom='jojon', year=1998, buttons=BUTTONS_JOJO),
    dict(bank=4, slug='jojos-bizarre-adventure', id='jojobaw', title="JoJo's Bizarre Adventure: Heritage for the Future",
         mame='jojobanr2', prefix='jojoba', machine='jojoba', key='jojoba', bios='jojoba', eeprom='jojobanr2',
         year=1999, buttons=BUTTONS_JOJO),
    dict(bank=5, slug='sfiii-3rd-strike', id='sfiii3w', title='Street Fighter III 3rd Strike: Fight for the Future',
         mame='sfiii3nr1', prefix='sfiii3', machine='sfiii3', key='sfiii3', bios='sfiii3', eeprom='sfiii3nr1',
         year=1999, buttons=BUTTONS6),
    dict(bank=6, slug='sfiii-3rd-strike-makoto-fix', id='sfiii3mkw', title='Street Fighter III 3rd Strike: Makoto Fix',
         mame='sfiii3n', prefix='sfiii3', machine='sfiii3', key='sfiii3', bios='sfiii3', eeprom='sfiii3n',
         year=1999, buttons=BUTTONS6),
    dict(bank=7, slug='sfiii-4rd-strike', id='sfiii4rw', title='Street Fighter III 4rd Strike',
         mame='sfiii3n', prefix='sfiii3', machine='sfiii3', key='sfiii3', bios='sfiii3', eeprom='sfiii3n',
         year=1999, buttons=BUTTONS6),
]
FALLBACK = dict(mame='sfiii3n', prefix='sfiii3', machine='sfiii3', key='sfiii3', bios='sfiii3')
BIOS_NAME = {'sfiii': 'sfiii_asia_nocd.29f400.u2', 'jojo': 'jojo_asia_nocd.29f400.u2',
             'jojoba': 'jojoba_japan_nocd.29f400.u2', 'sfiii3': 'sfiii3_japan_nocd.29f400.u2'}
BIOS_SIZE = 0x80000


def word_masks(base, nbytes, key):
    """cps3_mask for every 32-bit word of base .. base + nbytes, as uint32."""
    m = mask_table(base, nbytes, *KEYS[key])[0::2].astype(np.uint32)
    return (m << 16) | m


def crypt_words(data, base, key):
    """Encrypt or decrypt (the same XOR) big-endian bytes at base with a key."""
    w = np.frombuffer(data, dtype='>u4')
    return (w ^ word_masks(base, len(data), key)).astype('>u4').tobytes()


def find_bioses(rom_dirs):
    """{key family: [(crc, plain BIOS bytes, where)]} for every NO CD BIOS chip in MAME set zips in rom_dirs."""
    import os
    found = {}
    for d in rom_dirs:
        for name in BIOS_ZIPS:
            path = os.path.join(d, name + '.zip')
            if not os.path.isfile(path):
                continue
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    crc = f'{info.CRC:08x}'
                    if crc in BIOSES and info.file_size == BIOS_SIZE:
                        fam = BIOSES[crc][0]
                        plain = crypt_words(z.read(info), 0, fam)
                        if all(c != crc for c, *_ in found.get(fam, [])):
                            found.setdefault(fam, []).append((crc, plain, f'{path}:{info.filename}'))
    return found


def pick_bios(game, found):
    """(the game with its set fields filled in, BIOS crc, plain BIOS, where): its own set and BIOS when that BIOS
    was found, else FALLBACK with a 3rd Strike BIOS; None when neither is there."""
    for conf in ([game] if game['bios'] else []) + [FALLBACK]:
        if found.get(conf['bios']):
            crc, plain, where = found[conf['bios']][0]
            g = dict(game)
            g.update({k: conf[k] for k in ('mame', 'prefix', 'machine', 'key', 'bios')})
            g['own'] = conf is game
            return g, crc, plain, where
    return None


def bios_plain_ok(plain):
    """A decrypted CPS3 BIOS starts with its reset vector (PC in the BIOS) and stack pointer (in main RAM)."""
    pc, sp = int.from_bytes(plain[0:4], 'big'), int.from_bytes(plain[4:8], 'big')
    return pc < BIOS_SIZE and 0x02000000 <= sp <= 0x02080000


def set_chips(game, simm12_dir, simm36_dir, bios_plain):
    """{MAME file name: bytes} for the game's set: BIOS and program encrypted with the set's key."""
    key, pre = game['key'], game['prefix']
    assert BIOSES and game['bios'] == key, 'a BIOS only runs with its own key (see GAMES)'
    out = {mame_bios_name(game): crypt_words(bios_plain, 0, key)}
    prog = read_program_bank(simm12_dir, game['bank'], 'Standard')
    gfx = gfx_chips(simm36_dir, game['bank'])
    for simm, n in MACHINES[game['machine']].items():
        if simm <= 2:
            base = 0x06000000 + (simm - 1) * 0x800000
            enc = np.frombuffer(crypt_words(prog[base - 0x06000000:base - 0x06000000 + 0x800000], base, key),
                                dtype=np.uint8).reshape(-1, 4)
            for i in range(4):
                out[f'{pre}-simm{simm}.{i}'] = enc[:, i].tobytes()
        else:
            for i in range(n):
                out[f'{pre}-simm{simm}.{i}'] = gfx[f'sfiii3-simm{simm}.{i}']
    return out, prog


def mame_bios_name(game):
    return BIOS_NAME[game['key']]


def write_zip(path, files):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name in sorted(files):
            z.writestr(zipfile.ZipInfo(name, (1996, 12, 24, 23, 32, 0)), files[name],
                       compress_type=zipfile.ZIP_DEFLATED)


# ---- MRA (MiSTer) ----

STREAM = [1, 3, 4, 5, 2, 6]  # SIMM order in the ROM stream after the BIOS; header offsets use this order


def header(game, bios_family, files):
    """The 32-byte jtcps3 header: start of SIMM 1, 3, 4, 5, 2, 6 after the header in 64 kB units, key, mode 4
    (normal decryption), BIOS region field (1 = Red Earth's place)."""
    pre, h = game['prefix'], bytearray(32)
    pos = BIOS_SIZE
    for i, simm in enumerate(STREAM):
        h[2 * i:2 * i + 2] = (pos >> 16).to_bytes(2, 'big')
        pos += sum(len(files[f'{pre}-simm{simm}.{c}']) for c in range(MACHINES[game['machine']].get(simm, 0)))
    k1, k2 = KEYS[game['key']]
    h[0x10:0x18] = k1.to_bytes(4, 'big') + k2.to_bytes(4, 'big')
    h[0x18] = 4
    h[0x19] = 1 if bios_family == 'redearth' else 0
    return bytes(h)


def hexrows(data, indent):
    return '\n'.join(indent + ' '.join(f'{b:02X}' for b in data[i:i + 8]) for i in range(0, len(data), 8))


def mra_text(game, zip_name, bios_family, files, asm_md5):
    pre, mach = game['prefix'], MACHINES[game['machine']]
    lines = [f'        <part>\n{hexrows(header(game, bios_family, files), " " * 12)}\n        </part>',
             f'        <part name="{mame_bios_name(game)}" crc="{crc(files[mame_bios_name(game)])}"/>']
    for simm in STREAM:
        n = mach.get(simm, 0)
        if not n:
            continue
        names = [f'{pre}-simm{simm}.{i}' for i in range(n)]
        if simm <= 2:
            lines.append('        <interleave output="32">')
            for i, m in ((1, '0001'), (0, '0010'), (3, '0100'), (2, '1000')):
                lines.append(f'            <part name="{names[i]}" crc="{crc(files[names[i]])}" map="{m}"/>')
            lines.append('        </interleave>')
        else:
            for i in range(0, n, 2):
                lines.append('        <interleave output="16">')
                lines.append(f'            <part name="{names[i + 1]}" crc="{crc(files[names[i + 1]])}" map="01"/>')
                lines.append(f'            <part name="{names[i]}" crc="{crc(files[names[i]])}" map="10"/>')
                lines.append('        </interleave>')
    ee = bytes.fromhex(EEPROM[game['eeprom']])
    assert len(ee) == 128
    body = '\n'.join(lines)
    eerows = '\n'.join(' '.join(f'{b:02x}' for b in ee[i:i + 16]) for i in range(0, 128, 16))
    return f'''<!-- Widescreen hack of {game["title"]} for Jotego's jtcps3 core, made by tools/export_sets.py from a
     Darksoft CPS-3 pack bank {game["bank"]} and your own BIOS. Needs {zip_name} in games/mame. -->
<misterromdescription>
    <about author="jotego" webpage="https://patreon.com/jotego" twitter="@topapate" source="https://jotego/jtcores"/>
    <rotation>horizontal</rotation>
    <name>{game["title"]} (widescreen)</name>
    <setname>{game["id"]}</setname>
    <mameversion>0282</mameversion>
    <year>{game["year"]}</year>
    <manufacturer>Capcom</manufacturer>
    <players>2</players>
    <rbf>jtcps3</rbf>
    <joystick>8</joystick>
    <region>World</region>
    <rom index="0" zip="{zip_name}" md5="None" address="0x30000000" asm_md5="{asm_md5}">
{body}
    </rom>
    <rom index="17" zip="jtbeta.zip" md5="None" asm_md5="7ecc1117032b37ba8a571c5a05db418c">
        <part name="beta.bin" crc="3df60dfd"/>
    </rom>
    <rom index="2">
        <part>
{eerows}
</part>
    </rom>
    <nvram index="2" size="128"/>
    <rom index="1">
        <part>00 80</part>
    </rom>
    <switches page_id="1" page_name="Switches" base="16" default="ff,ff">
        <dip name="BIOS region" ids="Japan,Asia,Europe,USA,Hispanic,Brazil,Oceania,Original" bits="0,2"/>
    </switches>
    {game["buttons"]}
</misterromdescription>
'''


def crc(data):
    import zlib
    return f'{zlib.crc32(data):08x}'


def assemble(mra, read):
    """ROM index 0 of an MRA as MiSTer builds it; read(name, zip) gives a part's bytes. Map strings are read right
    to left: the last character is the first byte of each output word (proven on sfiii3nr1's asm_md5)."""
    root = ET.fromstring(mra) if mra.lstrip().startswith('<') else ET.parse(mra).getroot()
    rom = [r for r in root.iter('rom') if r.get('index') == '0'][0]
    zips = rom.get('zip').split('|')

    def data(p):
        if p.get('name'):
            return read(p.get('name'), p.get('zip') or zips)
        return bytes.fromhex(''.join((p.text or '').split()))
    out = bytearray()
    for el in rom:
        if el.tag == 'part':
            out += data(el)
        elif el.tag == 'interleave':
            w = int(el.get('output')) // 8
            parts = [(data(p), p.get('map')) for p in el.findall('part')]
            per = sum(c != '0' for c in parts[0][1])
            buf = bytearray(len(parts[0][0]) // per * w)
            for d, m in parts:
                pos = sorted(w - 1 - i for i, c in enumerate(m) if c != '0')
                for j, ps in enumerate(pos):
                    buf[ps::w] = d[j::len(pos)]
            out += buf
    return bytes(out)


def md5(data):
    return hashlib.md5(data).hexdigest()
