#!/usr/bin/env python3
"""CPS3 Widescreen: make the widescreen files from a Darksoft CPS-3 pack (the part tools/make_pack.sh and the app share).

    cps3ws.py <Darksoft pack: .7z, .zip or folder> <out dir> [--format darksoft,mame,mister|all] [--roms DIR]...

Applies the prebuilt patches (patches/) to every bank, checks the Custom SH2 files, and writes the outputs asked for:
    darksoft  <out>/<pack name> - widescreen (...).zip   the patched pack, to flash
    mame      <out>/MAME/<game>/<set>.zip                 MAME NO CD sets (needs a NO CD BIOS from --roms)
    mister    <out>/MiSTer/...                            jtcps3 MRAs and zips (needs a NO CD BIOS from --roms)
Temporary files go in <out>/.cps3ws-work, removed at the end.

make() is what the app calls: it reports through log(line) and step(done, total, title), and raises Failed with a
message for the user when something is wrong.
"""
import argparse
import contextlib
import io
import os
import shutil
import sys
import zipfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import check_custom  # noqa: E402
import cps3sets  # noqa: E402
import export_sets  # noqa: E402
import patch_darksoft  # noqa: E402

# patches/: next to tools/ in the repository, or inside the app bundle (PyInstaller unpacks data to sys._MEIPASS)
ROOT = getattr(sys, '_MEIPASS', os.path.dirname(TOOLS))
PATCHES = os.path.join(ROOT, 'patches')

# (bank, patch, kinds patched, code ranges for the Custom check): the order make_pack.sh has always used
BANKS = [
    (0, 'bank0-sfiii-new-generation', 'both', 'bank0-sfiii-new-generation-code'),
    (5, 'bank5-sfiii-3rd-strike', 'both', 'bank5-sfiii-3rd-strike-code'),
    (6, 'bank6-sfiii-makoto-fix', 'both', 'bank6-sfiii-makoto-fix-code'),
    (7, 'bank7-sfiii-4rd-strike', 'both', 'bank7-sfiii-4rd-strike-code'),
    (4, 'bank4-jojos-bizarre-adventure', 'Standard', None),
    (3, 'bank3-jojos-venture', 'Standard', None),
    (1, 'bank1-warzard', 'both', 'bank1-warzard-code'),
]
GAMES_NOTE = 'SFIII NG, 3rd Strike, Makoto Fix, 4rd Strike, JoJo HFTF, JoJo Venture, Warzard'
FORMATS = ('darksoft', 'mame', 'mister')
WORK = '.cps3ws-work'
GB = 1024 ** 3


class Failed(Exception):
    """Something the user has to fix (wrong pack, no BIOS, no space): the message says what."""


def pack_name(src):
    base = os.path.basename(os.path.normpath(src))
    for ext in ('.7z', '.zip'):
        if base.lower().endswith(ext):
            return base[:-len(ext)]
    return base


def find_pack_root(d):
    """The folder under d that holds 'SIMM 1-2' and 'SIMM 3-6'."""
    for root, dirs, _ in os.walk(d):
        if 'SIMM 1-2' in dirs and 'SIMM 3-6' in dirs:
            return root
    raise Failed(f'No "SIMM 1-2" and "SIMM 3-6" folders in {d}. Choose the Darksoft CPS-3 pack '
                 '(the .7z you downloaded, or the folder you extracted it to).')


def extract(src, dest, log):
    """Unpack a .7z or .zip pack into dest."""
    os.makedirs(dest)
    if src.lower().endswith('.zip'):
        with zipfile.ZipFile(src) as z:
            z.extractall(dest)
        return
    try:
        import py7zr
    except ImportError:
        py7zr = None
    if py7zr:
        with py7zr.SevenZipFile(src, 'r') as z:
            z.extractall(dest)
        return
    seven = shutil.which('7z') or shutil.which('7zz') or shutil.which('7za')
    if not seven:
        raise Failed('Reading a .7z needs the Python module py7zr or the 7z program. Install one '
                     '(see README), or extract the pack yourself and choose the folder.')
    import subprocess
    r = subprocess.run([seven, 'x', '-bd', '-y', f'-o{dest}', src], capture_output=True, text=True)
    if r.returncode:
        raise Failed(f'7z could not extract {src}:\n{r.stdout[-2000:]}{r.stderr[-2000:]}')


def describe_pack(root):
    """A line saying which Darksoft release this looks like, from its file names."""
    s36 = os.listdir(os.path.join(root, 'SIMM 3-6'))
    s12 = [f for d in ('Standard SH2', 'Custom SH2') for f in os.listdir(os.path.join(root, 'SIMM 1-2', d))]
    notes = []
    if any('WarzardFIX' in f for f in s12):
        notes.append("Darksoft's Warzard no-CD fix")
    simm5 = sorted(f for f in s36 if f.startswith('SIMM5_Final'))
    if len(simm5) > 1:
        notes.append('two SIMM 5 files to choose from: ' + ', '.join(simm5))
    return 'Pack: ' + (', '.join(notes) if notes else 'single files per SIMM (the 2021-01-09 layout)')


class LineLog(io.TextIOBase):
    """stdout for the tools: whole lines go to log()."""

    def __init__(self, log):
        self.log, self.buf = log, ''

    def write(self, s):
        self.buf += s
        while '\n' in self.buf:
            line, self.buf = self.buf.split('\n', 1)
            self.log(line)
        return len(s)

    def flush(self):
        if self.buf:
            self.log(self.buf)
            self.buf = ''


def call(main, argv, log, what):
    """Run a tool's main(argv) with its output going to log; its sys.exit(message) becomes Failed."""
    out = LineLog(log)
    try:
        with contextlib.redirect_stdout(out):
            main(argv)
    except SystemExit as e:
        if e.code not in (None, 0):
            raise Failed(f'{what}: {e.code}') from None
    finally:
        out.flush()


def write_zip(src_dir, out_zip):
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for d, _, fs in sorted(os.walk(src_dir)):
            for f in sorted(fs):
                z.write(os.path.join(d, f), os.path.relpath(os.path.join(d, f), src_dir))
    with zipfile.ZipFile(out_zip) as z:
        if z.testzip() is not None:
            raise Failed(f'{out_zip} did not read back correctly')


def is_own_output(d):
    """A MAME or MiSTer folder this tool wrote earlier: its README.txt starts with export_sets' first line."""
    try:
        with open(os.path.join(d, 'README.txt'), encoding='utf-8') as f:
            return f.readline().startswith('Widescreen CPS3 games for ')
    except OSError:
        return False


def remove_own_output(d):
    """Replace an earlier run's folder; never delete a folder this tool did not write."""
    if not is_own_output(d):
        raise Failed(f'{d} already exists and was not made by this tool. Choose another output folder '
                     '(an empty one is best).')
    shutil.rmtree(d)


def make(pack_src, out, formats=('darksoft',), roms=(), log=None, step=None, patches=PATCHES):
    """Make the outputs; returns the list of paths written."""
    if log is None:
        console = sys.stdout  # the tools' output is redirected into log(): keep the real console here
        log = lambda s: print(s, file=console, flush=True)  # noqa: E731
    formats = [f for f in FORMATS if f in formats]
    if not formats:
        raise Failed('Choose at least one thing to make.')
    if not os.path.exists(pack_src):
        raise Failed(f'{pack_src} does not exist.')
    if not os.path.isfile(os.path.join(patches, 'bank5-sfiii-3rd-strike.json')):
        raise Failed(f'No prebuilt patches in {patches}.')
    steps = (['Unpacking the Darksoft pack'] + [f'Patching bank {b}' for b, *_ in BANKS] + ['Checking Custom SH2 files'] +
             (['Writing the Darksoft pack zip'] if 'darksoft' in formats else []) +
             (['Writing MAME / MiSTer files'] if {'mame', 'mister'} & set(formats) else []) + ['Cleaning up'])
    n = [0]

    def next_step():
        if step:
            step(n[0], len(steps), steps[n[0]])
        log(f'== {steps[n[0]]}')
        n[0] += 1

    found = None
    if {'mame', 'mister'} & set(formats):
        found = cps3sets.find_bioses([r for r in roms if r])
        if not found:
            raise Failed('MAME and MiSTer files need a CPS3 BIOS from your own MAME sets: choose the folder that '
                         'holds sfiii3nr1.zip or sfiii3n.zip (3rd Strike, NO CD). Only its BIOS chip is used.')
        for fam, lst in found.items():
            for crc, plain, where in lst:
                log(f'BIOS found: {cps3sets.BIOSES[crc][1]} in {where}')

    os.makedirs(out, exist_ok=True)
    need = (1.0 if os.path.isdir(pack_src) else 1.8) + 0.6 * ('darksoft' in formats) + \
        0.5 * ('mame' in formats) + 0.5 * ('mister' in formats)
    free = shutil.disk_usage(out).free / GB
    if free < need:
        raise Failed(f'Not enough free space in {out}: about {need:.1f} GB needed, {free:.1f} GB free.')

    for f, sub in (('mame', 'MAME'), ('mister', 'MiSTer')):
        d = os.path.join(out, sub)
        if f in formats and os.path.exists(d) and not is_own_output(d):
            raise Failed(f'{d} already exists and was not made by this tool. Choose another output folder '
                         '(an empty one is best).')

    work = os.path.join(out, WORK)
    if os.path.isdir(work):
        shutil.rmtree(work)  # this tool's own folder, left by a run that was stopped
    os.makedirs(work)
    written = []
    try:
        next_step()
        if os.path.isdir(pack_src):
            pack = find_pack_root(pack_src)
        else:
            extract(pack_src, os.path.join(work, 'pack'), log)
            pack = find_pack_root(os.path.join(work, 'pack'))
        log(describe_pack(pack))

        patched = os.path.join(work, 'patched')
        for i, (bank, name, kind, _) in enumerate(BANKS):
            next_step()
            argv = [pack, os.path.join(patches, name + '.json'), str(bank), patched]
            argv += (['--in-place'] if i else []) + (['--kind', kind] if kind != 'both' else [])
            call(patch_darksoft.main, argv, log, f'Bank {bank}')

        next_step()
        for bank, _, kind, code in BANKS:
            if code:
                call(check_custom.main, [pack, patched, str(bank), os.path.join(patches, code + '.json')], log,
                     f'Custom SH2 check, bank {bank}')

        if 'darksoft' in formats:
            next_step()
            z = os.path.join(out, f'{pack_name(pack_src)} - widescreen ({GAMES_NOTE}).zip')
            if os.path.exists(z):
                os.remove(z)
            write_zip(patched, z)
            log(f'{z}: {os.path.getsize(z) // 2 ** 20} MB')
            written.append(z)

        if {'mame', 'mister'} & set(formats):
            next_step()
            argv = [patched, '--stock', pack]
            for r in roms:
                if r:
                    argv += ['--roms', r]
            for f, sub in (('mame', 'MAME'), ('mister', 'MiSTer')):
                if f in formats:
                    d = os.path.join(out, sub)
                    if os.path.exists(d):
                        remove_own_output(d)
                    argv += [f'--{f}', d]
                    written.append(d)
            call(export_sets.main, argv, log, 'MAME / MiSTer files')
    finally:
        next_step()
        shutil.rmtree(work, ignore_errors=True)
    if step:
        step(len(steps), len(steps), 'Done')
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('pack')
    ap.add_argument('out')
    ap.add_argument('--format', default='darksoft')
    ap.add_argument('--roms', action='append', default=[])
    a = ap.parse_args(argv)
    formats = FORMATS if a.format == 'all' else a.format.split(',')
    bad = [f for f in formats if f not in FORMATS]
    if bad:
        sys.exit(f'unknown format {bad} (darksoft, mame, mister, all)')
    try:
        make(a.pack, a.out, formats, a.roms)
    except Failed as e:
        sys.exit(str(e))


if __name__ == '__main__':
    main()
