"""Darksoft CPS-3 UltraSIMM image layout (verified 2026-11-16 against the 2021-01-09 pack, and the
2021-04-02 pack, which has the same layout).

Program SIMMs 1 and 2 are dual-flash: two files per SIMM (jumper U9 and U10), each 32 MB, 8 banks of 4 MB.
A big-endian program word is bswap16(U9 halfword) << 16 | bswap16(U10 halfword). SIMM1 is 06000000-067FFFFF and
SIMM2 06800000-06FFFFFF of a game's program. "Standard SH2" files hold plain code; "Custom SH2" files (dead
security cart) hold the same data with instruction words XORed by cps3_mask(address, 0, 0).
"""
import glob
import os

import numpy as np

NBANK = 8
BANK_BYTES = 8 * 1024 * 1024  # program bytes per SIMM per bank
PROGRAM_FILE_BYTES = NBANK * BANK_BYTES // 2  # each of a SIMM's two files (U9, U10) holds half of every word
GFX_FILE_BYTES = NBANK * 16 * 1024 * 1024


class PackError(Exception):
    """The folder is not one complete Darksoft pack (a file missing, doubled or of the wrong size)."""


def one_file(d, stem):
    """The single file d/<stem>*.bin. Packs after 2021-01-09 add suffixes to changed files (2021-04-02:
    SIMM1_Jumper_U9_StandardSH2_WarzardFIX.bin), so files are found by their name up to the suffix."""
    fs = sorted(glob.glob(f'{glob.escape(d)}/{stem}*.bin'))
    if len(fs) != 1:
        names = ', '.join(os.path.basename(f) for f in fs) or 'none'
        raise PackError(f'{d} should hold one {stem}*.bin file; found {len(fs)} ({names})')
    if os.path.getsize(fs[0]) != PROGRAM_FILE_BYTES:
        raise PackError(f'{fs[0]} is {os.path.getsize(fs[0])} bytes; a Darksoft program SIMM file is '
                        f'{PROGRAM_FILE_BYTES}')
    return fs[0]


def simm_paths(root, simm, kind):
    d = f'{root}/{kind} SH2'
    return one_file(d, f'SIMM{simm}_Jumper_U9_{kind}SH2'), one_file(d, f'SIMM{simm}_Jumper_U10_{kind}SH2')


def check_program_files(root):
    """Raise PackError unless root ("SIMM 1-2") has each program file once, at its full size, for both CPU kinds."""
    for kind in ('Standard', 'Custom'):
        if not os.path.isdir(f'{root}/{kind} SH2'):
            raise PackError(f'{root} has no "{kind} SH2" folder')
        for simm in (1, 2):
            simm_paths(root, simm, kind)


def read_simm_words(u9_path, u10_path):
    a = np.frombuffer(open(u9_path, 'rb').read(), dtype='<u2').astype(np.uint32)
    b = np.frombuffer(open(u10_path, 'rb').read(), dtype='<u2').astype(np.uint32)
    return (a << 16) | b


def split_simm_words(words):
    """Inverse of read_simm_words: returns (u9 bytes, u10 bytes)."""
    w = words.astype(np.uint32)
    u9 = (w >> 16).astype('<u2').tobytes()
    u10 = (w & 0xFFFF).astype('<u2').tobytes()
    return u9, u10


def read_program_bank(root, bank, kind='Standard'):
    """The bank's 16 MB program image (06000000-06FFFFFF) as big-endian bytes, as the files hold it."""
    out = []
    for simm in (1, 2):
        words = read_simm_words(*simm_paths(root, simm, kind))
        per = len(words) // NBANK
        out.append(words[bank * per:(bank + 1) * per].astype('>u4').tobytes())
    return b''.join(out)
