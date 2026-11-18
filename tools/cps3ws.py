#!/usr/bin/env python3
"""CPS3 Widescreen: make the widescreen files from a Darksoft CPS-3 pack (the part tools/make_pack.sh and the app share).

    cps3ws.py <Darksoft pack: .7z, .zip or folder> <out dir> [--format darksoft,mame,mister|all] [--roms DIR]...

Applies the prebuilt patches (patches/) to every bank, checks the Custom SH2 files, and writes the outputs asked for:
    darksoft  <out>/<pack name> - widescreen (...).zip   the patched pack, to flash
    mame      <out>/MAME/<game>/<set>.zip                 MAME NO CD sets (needs a NO CD BIOS from --roms)
    mister    <out>/MiSTer/...                            jtcps3 MRAs and zips (needs a NO CD BIOS from --roms)
Everything is made in <out>/.cps3ws-work and moved into place only when all of it is complete, so a run that stops
part-way leaves <out> as it was. The work folder is removed at the end.

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
import darksoft  # noqa: E402
import darksoft_gfx  # noqa: E402
import export_sets  # noqa: E402
import patch_darksoft  # noqa: E402

# patches/: next to tools/ in the repository, or inside the app bundle (PyInstaller unpacks data to sys._MEIPASS)
ROOT = getattr(sys, '_MEIPASS', os.path.dirname(TOOLS))
PATCHES = os.path.join(ROOT, 'patches')

# (bank, patch, kinds patched, code ranges for the Custom check, custom map): the order make_pack.sh has always
# used. A custom map (tools/custom_map.py) is for a bank whose Custom file in the pack is another revision of the
# game: its Custom image is written anew from the Standard program.
BANKS = [
    (0, 'bank0-sfiii-new-generation', 'both', 'bank0-sfiii-new-generation-code', None),
    (5, 'bank5-sfiii-3rd-strike', 'both', 'bank5-sfiii-3rd-strike-code', None),
    (6, 'bank6-sfiii-makoto-fix', 'both', 'bank6-sfiii-makoto-fix-code', None),
    (7, 'bank7-sfiii-4rd-strike', 'both', 'bank7-sfiii-4rd-strike-code', None),
    (4, 'bank4-jojos-bizarre-adventure', 'both', 'bank4-jojos-bizarre-adventure-code',
     'bank4-jojos-bizarre-adventure-custom-map'),
    (3, 'bank3-jojos-venture', 'both', 'bank3-jojos-venture-code', 'bank3-jojos-venture-custom-map'),
    (1, 'bank1-warzard', 'both', 'bank1-warzard-code', None),
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


def system_env():
    """The environment for programs this tool starts. The single-file Linux app runs with LD_LIBRARY_PATH set to its
    own bundled libraries (PyInstaller does that), and a system program that inherits it fails to load (kdialog,
    zenity, even /bin/sh on Arch). PyInstaller keeps the user's own value in LD_LIBRARY_PATH_ORIG."""
    env = dict(os.environ)
    if getattr(sys, 'frozen', False) and sys.platform != 'win32':
        orig = env.pop('LD_LIBRARY_PATH_ORIG', None)
        if orig:
            env['LD_LIBRARY_PATH'] = orig
        else:
            env.pop('LD_LIBRARY_PATH', None)
    return env


def find_pack_root(d):
    """The folder that holds 'SIMM 1-2' and 'SIMM 3-6': d itself, or a folder one or two levels below it."""
    level = [d]
    for _ in range(3):
        below = []
        for root in level:
            try:
                dirs = sorted(e.name for e in os.scandir(root) if e.is_dir())
            except OSError:
                continue
            if 'SIMM 1-2' in dirs and 'SIMM 3-6' in dirs:
                return root
            below += [os.path.join(root, x) for x in dirs]
        level = below
    raise Failed(f'No "SIMM 1-2" and "SIMM 3-6" folders in {d}. Choose the Darksoft CPS-3 pack '
                 '(the .7z you downloaded, or the folder you extracted it to).')


def check_pack(root):
    """Stop with a plain message unless root holds one complete pack (each file once, at its full size)."""
    try:
        darksoft.check_program_files(os.path.join(root, 'SIMM 1-2'))
        darksoft_gfx.gfx_files(os.path.join(root, 'SIMM 3-6'))
    except darksoft.PackError as e:
        raise Failed(f'This is not one complete Darksoft CPS-3 pack: {e}. Extract the pack again into an empty '
                     'folder, or choose the .7z file itself.') from None


def extract(src, dest, log):
    """Unpack a .7z or .zip pack into dest."""
    os.makedirs(dest)
    broken = (f'{src} could not be unpacked ({{}}). It may be an incomplete download: download the pack again, '
              'or extract it yourself and choose the folder.')
    if src.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(src) as z:
                z.extractall(dest)
        except (zipfile.BadZipFile, EOFError) as e:
            raise Failed(broken.format(e)) from None
        return
    try:
        import py7zr
    except ImportError:
        py7zr = None
    if py7zr:
        try:
            with py7zr.SevenZipFile(src, 'r') as z:
                z.extractall(dest)
        except OSError:
            raise  # disk full, no permission: reported as a file error by make()
        except Exception as e:  # py7zr raises its own errors, lzma's and EOFError for a damaged archive
            raise Failed(broken.format(f'{type(e).__name__}: {e}')) from None
        return
    seven = shutil.which('7z') or shutil.which('7zz') or shutil.which('7za')
    if not seven:
        raise Failed('Reading a .7z needs the Python module py7zr or the 7z program. Install one '
                     '(see README), or extract the pack yourself and choose the folder.')
    import subprocess
    r = subprocess.run([seven, 'x', '-bd', '-y', f'-o{dest}', src], capture_output=True, text=True, env=system_env())
    if r.returncode:
        raise Failed(broken.format('7z: ' + (r.stderr.strip() or r.stdout.strip())[-600:]))


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
    except darksoft.PackError as e:
        raise Failed(f'{what}: {e}') from None
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


def inside(path, folder):
    """True when path is folder or lies in it (symbolic links resolved)."""
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    try:
        return os.path.commonpath([path, folder]) == folder
    except ValueError:  # different drives
        return False


def usable_games(found):
    """(titles that can be made, titles that cannot) with the BIOS chips found."""
    ok, no = [], []
    for g in cps3sets.GAMES:
        (ok if cps3sets.pick_bios(g, found) else no).append(g['title'])
    return ok, no


def make(pack_src, out, formats=('darksoft',), roms=(), log=None, step=None, patches=PATCHES):
    """Make the outputs. Returns {'written': [paths], 'skipped': [titles of games left out of MAME / MiSTer]}."""
    try:
        return _make(pack_src, out, formats, roms, log, step, patches)
    except OSError as e:  # disk full, no permission, a file in use: say which file
        where = f' ({e.filename})' if e.filename else ''
        raise Failed(f'File error: {e.strerror or e}{where}. Nothing was changed in the output folder.') from e


def _make(pack_src, out, formats, roms, log, step, patches):
    if log is None:
        console = sys.stdout  # the tools' output is redirected into log(): keep the real console here
        log = lambda s: print(s, file=console, flush=True)  # noqa: E731
    formats = [f for f in FORMATS if f in formats]
    export = [f for f in formats if f in ('mame', 'mister')]
    if not formats:
        raise Failed('Choose at least one thing to make.')
    if not os.path.exists(pack_src):
        raise Failed(f'{pack_src} does not exist.')
    if not os.path.isfile(os.path.join(patches, 'bank5-sfiii-3rd-strike.json')):
        raise Failed(f'No prebuilt patches in {patches}.')
    steps = (['Unpacking the Darksoft pack'] + [f'Patching bank {b}' for b, *_ in BANKS] + ['Checking Custom SH2 files'] +
             (['Writing the Darksoft pack zip'] if 'darksoft' in formats else []) +
             (['Writing MAME / MiSTer files'] if export else []) + ['Moving the files into place'])
    n = [0]

    def next_step():
        if step:
            step(n[0], len(steps), steps[n[0]])
        log(f'== {steps[n[0]]}')
        n[0] += 1

    skipped = []
    if export:
        found = cps3sets.find_bioses([r for r in roms if r])
        need_bios = ('choose the folder that holds sfiii3nr1.zip or sfiii3n.zip (3rd Strike, NO CD). Only its BIOS '
                     'chip is used.')
        if not found:
            raise Failed(f'MAME and MiSTer files need a CPS3 BIOS from your own MAME sets: {need_bios}')
        for fam, lst in found.items():
            for crc, plain, where in lst:
                log(f'BIOS found: {cps3sets.BIOSES[crc][1]} in {where}')
        ok, skipped = usable_games(found)
        if not ok:
            have = ', '.join(cps3sets.BIOSES[crc][1] for lst in found.values() for crc, *_ in lst)
            raise Failed(f'The CPS3 BIOS found ({have}) cannot start these games. For MAME and MiSTer files, '
                         f'{need_bios}')
        for title in skipped:
            log(f'NOT MADE for MAME / MiSTer: {title} (needs a 3rd Strike NO CD BIOS, or its own)')

    finals = {'mame': os.path.join(out, 'MAME'), 'mister': os.path.join(out, 'MiSTer')}
    for f in export:
        d = finals[f]
        if os.path.lexists(d) and not is_own_output(d):
            raise Failed(f'{d} already exists and was not made by this tool, so it will not be replaced. Choose '
                         'another output folder (an empty one is best). If that folder is left over from a run '
                         'that was stopped, delete it.')

    os.makedirs(out, exist_ok=True)
    need = (1.0 if os.path.isdir(pack_src) else 1.8) + 0.6 * ('darksoft' in formats) + 0.5 * len(export)
    free = shutil.disk_usage(out).free / GB
    if free < need:
        raise Failed(f'Not enough free space in {out}: about {need:.1f} GB needed, {free:.1f} GB free.')

    work = os.path.join(out, WORK)
    if os.path.isdir(work):
        shutil.rmtree(work)  # this tool's own folder, left by a run that was stopped
    os.makedirs(work)
    written = []
    try:
        next_step()
        if os.path.isdir(pack_src):
            pack = find_pack_root(pack_src)
            for sub in ('SIMM 1-2', 'SIMM 3-6'):
                if inside(out, os.path.join(pack, sub)):
                    raise Failed(f'The output folder is inside the pack\'s "{sub}" folder. Choose another one.')
        else:
            extract(pack_src, os.path.join(work, 'pack'), log)
            pack = find_pack_root(os.path.join(work, 'pack'))
        check_pack(pack)
        log(describe_pack(pack))

        patched = os.path.join(work, 'patched')
        for i, (bank, name, kind, _, cmap) in enumerate(BANKS):
            next_step()
            argv = [pack, os.path.join(patches, name + '.json'), str(bank), patched]
            argv += (['--in-place'] if i else []) + (['--kind', kind] if kind != 'both' else [])
            argv += ['--custom-map', os.path.join(patches, cmap + '.json')] if cmap else []
            call(patch_darksoft.main, argv, log, f'Bank {bank}')

        next_step()
        for bank, _, kind, code, cmap in BANKS:
            if code:
                argv = [pack, patched, str(bank), os.path.join(patches, code + '.json')]
                argv += [os.path.join(patches, cmap + '.json')] if cmap else []
                call(check_custom.main, argv, log, f'Custom SH2 check, bank {bank}')

        moves = []  # (made in the work folder, its place in out)
        if 'darksoft' in formats:
            next_step()
            name = f'{pack_name(pack_src)} - widescreen ({GAMES_NOTE}).zip'
            write_zip(patched, os.path.join(work, name))
            log(f'{name}: {os.path.getsize(os.path.join(work, name)) // 2 ** 20} MB')
            moves.append((os.path.join(work, name), os.path.join(out, name)))

        if export:
            next_step()
            argv = [patched, '--stock', pack]
            for r in roms:
                if r:
                    argv += ['--roms', r]
            for f in export:
                staged = os.path.join(work, os.path.basename(finals[f]))
                argv += [f'--{f}', staged]
                moves.append((staged, finals[f]))
            # the tools print the paths they write: show them where they will be
            call(export_sets.main, argv, lambda line: log(line.replace(work + os.sep, out + os.sep)),
                 'MAME / MiSTer files')

        # everything is complete: only now touch the output folder
        next_step()
        for staged, final in moves:
            if os.path.isdir(final):
                if not is_own_output(final):  # checked at the start; it must not have changed meanwhile
                    raise Failed(f'{final} was changed while the files were being made; nothing was replaced.')
                shutil.rmtree(final)
            os.replace(staged, final)
            written.append(final)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if step:
        step(len(steps), len(steps), 'Done')
    return {'written': written, 'skipped': skipped}


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
