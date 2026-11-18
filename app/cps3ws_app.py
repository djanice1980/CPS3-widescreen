#!/usr/bin/env python3
"""CPS3 Widescreen app: the point-and-click front end of tools/cps3ws.py, for Linux and Windows (and Wine).

Run from the repository with python3 app/cps3ws_app.py, or as the single-file builds that app/build_linux.sh and
app/build_windows.sh make.
"""
import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import cps3ws  # noqa: E402

APP = 'CPS3 Widescreen'
VERSION = '1.4.0'
REPO = 'https://github.com/djanice1980/CPS3-widescreen'
ON_WINDOWS = sys.platform == 'win32'

INTRO = ('Adds a widescreen mode to seven CPS3 games on your own Darksoft CPS-3 pack. Each game gets a SCREEN MODE '
         'setting (NORMAL / WIDE) in its test menu. No game data comes with this app: it changes the pack you '
         'already have.')

FORMAT_TEXT = {
    'darksoft': ('Darksoft pack, ready to flash',
                 'The whole pack with the widescreen games, as one .zip. Flash it to your UltraSIMMs the same way '
                 'as the original pack.'),
    'mame': ('MAME ROM sets',
             'One folder per game, for MAME. Needs your MAME ROM folder (step 3).'),
    'mister': ('MiSTer FPGA files',
               "MRA files and ROM zips for Jotego's CPS3 core. Needs your MAME ROM folder (step 3)."),
}

INSTRUCTIONS = [
    ('What this does', f'''{INTRO}

Games: Street Fighter III: New Generation (bank 0), Warzard / Red Earth (bank 1), JoJo's Venture (bank 3), JoJo's \
Bizarre Adventure: Heritage for the Future (bank 4), Street Fighter III 3rd Strike (bank 5), 3rd Strike: Makoto Fix \
(bank 6) and 4rd Strike (bank 7). 2nd Impact (bank 2) already has a widescreen option of its own and is left as it is.

In widescreen, fights show more of each stage on both sides and the fight HUD is centered on the wider screen. \
With SCREEN MODE on NORMAL the games look the same as before.'''),
    ('What you need', '''- The Darksoft CPS-3 pack: "Darksoft CPS-3 2021-01-09.7z" or "Darksoft CPS-3 2021-04-02.7z" (the .7z \
file, or the folder you extracted it to). Other releases are checked byte by byte and refused if they differ.
- For MAME or MiSTer files only: your own MAME set of 3rd Strike, sfiii3nr1.zip or sfiii3n.zip (the NO CD \
versions). Only its BIOS chip is used, to start the games. If the same folder also has sfiiina.zip, jojonr2.zip or \
jojobanr2.zip (or their parents), New Generation and the JoJo games use their own BIOS.
- About 3 GB of free disk space for all three outputs (less for one).'''),
    ('Making the files', '''1. Pack: click "Choose .7z file..." and pick the Darksoft pack, or "Choose folder..." if you \
extracted it already.
2. What to make: tick any of the three.
3. MAME ROM folder: only for MAME or MiSTer. Pick the folder that holds sfiii3nr1.zip or sfiii3n.zip.
4. Save to: an empty folder is best. The app makes it if it does not exist.
5. Click "Make files". It takes a few minutes. Every patched byte is checked against what the patch expects, \
so a wrong or modified pack is refused and nothing is half-written.
When it is done, "Open output folder" shows the results.

Running under Wine: your Linux files are on drive Z: (Z:\\home\\<your user name>\\...).'''),
    ('Flashing the Darksoft pack', '''Unzip the "... - widescreen (...).zip" file. Flash it exactly as you would \
flash the original Darksoft pack, following Darksoft's instructions for your UltraSIMM kit:
- SIMM 1-2 (program): use the files in "Standard SH2" if your board has a standard SH2 CPU (the usual \
no-CD / Darksoft setup), or "Custom SH2" if it still has the original security-cart CPU.
- SIMM 3-6 (graphics): unchanged from the original pack.
- The 2021-04-02 pack has two SIMM 5 files: SIMM5_Final_MakotoFIX.bin (Makoto Fix graphics) and \
SIMM5_Final_reTHIRD.bin (the reTHIRD mod). Pick one, as with the original pack; widescreen works with both.

On a Custom SH2 board, JoJo's Venture and JoJo HFTF stay 4:3: Darksoft's Custom SH2 files for those two banks \
hold different revisions of the games, which this patch does not cover.'''),
    ('Turning widescreen on', '''1. Enter the test menu (the TEST button inside the cabinet; F2 in MAME).
2. Open the game's settings page (the one with difficulty, rounds and so on).
3. Set SCREEN MODE to WIDE. In Warzard's Japanese menu it is "スクリーンモード", ノーマル / ワイド.
4. Save and leave the test menu the way that game normally saves its settings (in New Generation: item 4, save \
and return).
Warzard switches as soon as you save. If another game is still 4:3 after you leave the test menu, reset it \
(F3 in MAME). The setting is kept like any other game setting.'''),
    ('MAME', '''The MAME folder has one folder per game, each holding the game as the MAME set named in MAME/README.txt \
(sfiii3n, sfiii3nr1 and so on). MAME reports wrong checksums for these files and then runs the game anyway.

Give each game its own ROM path AND its own nvram folder. MAME saves CPS3 program chips into nvram and boots from \
those copies afterwards, so a game sharing an nvram folder with the original game (or another folder here with the \
same set name) boots whichever program ran there first. From a terminal, for example:

  mame -rompath "<output>/MAME/sfiii-3rd-strike" -nvram_directory "<output>/MAME/sfiii-3rd-strike/nvram" sfiii3nr1

In a frontend, set the same two paths for that game. Warzard always runs as sfiii3n. New Generation and the JoJo \
games run as sfiii3n too unless your ROM folder had their own BIOS. On a 3rd Strike Japan BIOS, Warzard and the \
JoJo games show their Japanese versions.'''),
    ('MiSTer', '''For Jotego's CPS3 core (jtcps3). Copy to the root of the MiSTer SD card (/media/fat):
- MiSTer/_Arcade/_CPS3 Widescreen  ->  /media/fat/_Arcade/_CPS3 Widescreen
- MiSTer/games/mame/*.zip  ->  /media/fat/games/mame/
The CPS3 core must already be installed in _Arcade/cores. While the core is in beta it also needs Jotego's \
jtbeta.zip in games/mame, the same as his own CPS3 files. Each MRA uses only its own zip, so your other CPS3 files \
are not touched.'''),
    ('Known issues', '''- Tested in MAME 0.289 only so far; not yet confirmed on a real CPS3 board or a MiSTer. Please \
report results at the project page.
- Some screens outside the fights (continue, game over, results) are still drawn 4:3 wide.
- Stage objects at the edges of the wider view can appear a moment late.
- 3rd Strike, Makoto Fix and 4rd Strike in widescreen: near the left end of the savanna stage a black strip up \
to 4 pixels wide shows on the upper part of the left edge.'''),
]

ABOUT = f'''{APP} {VERSION}
{REPO}

Copyright (C) 2026 David Janice. Free software under the GNU Affero General Public License version 3 (AGPL-3.0), \
WITHOUT ANY WARRANTY. If you reuse or adapt it, keep the copyright notice, credit this project and share your \
version under the same license.

Built on gibletto's Street Fighter III 3rd Strike and New Generation decompilations (AGPL-3.0, parts from \
crowded-street/3s-decomp). MiSTer layout from Jotego's CPS3 core; keys and ROM layout from MAME's CPS3 driver; \
made for Darksoft's CPS-3 multi-game kit.

Street Fighter, JoJo's Venture, JoJo's Bizarre Adventure, Warzard and Red Earth are trademarks of Capcom. This \
project is not affiliated with Capcom, Darksoft or Jotego and contains none of their ROM data.'''


_helper_ok = {}
last_dialog = {}  # the last desktop chooser run: command, exit code, output (for the self-test and bug reports)


def helper_works(name):
    """True when a desktop helper program is installed and starts (asked once: `<name> --version`). A helper that
    is installed but cannot start must not be mistaken for one the user cancelled."""
    if name not in _helper_ok:
        ok = False
        if shutil.which(name):
            try:
                ok = subprocess.run([name, '--version'], capture_output=True, env=cps3ws.system_env(),
                                    timeout=15).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                ok = False
        _helper_ok[name] = ok
    return _helper_ok[name]


def native_dialog(kind, title, initial):
    """The desktop's own file chooser on Linux (KDE's kdialog or GNOME's zenity) when one works: the chosen path,
    '' when the user cancelled, None when there is no working helper (the caller then uses Tk's plain chooser)."""
    if ON_WINDOWS:
        return None
    start = initial if initial and os.path.exists(initial) else os.path.expanduser('~')
    if kind == 'dir' and not os.path.isdir(start):
        start = os.path.dirname(start)
    if helper_works('kdialog'):
        cmd = ['kdialog', '--title', title]
        cmd += (['--getexistingdirectory', start] if kind == 'dir' else
                ['--getopenfilename', start, 'Darksoft pack (*.7z *.zip)'])
    elif helper_works('zenity'):
        cmd = ['zenity', '--file-selection', '--title', title,
               '--filename', start if os.path.isfile(start) else start.rstrip('/') + '/']
        cmd += ['--directory'] if kind == 'dir' else ['--file-filter', 'Darksoft pack | *.7z *.zip']
    else:
        return None
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=cps3ws.system_env())
    except OSError:
        return None
    last_dialog.update(command=cmd[0], exit=r.returncode, stdout=r.stdout.strip(), stderr=r.stderr.strip()[-300:])
    if r.returncode == 0:
        return r.stdout.strip()
    # kdialog and zenity exit with 1 for Cancel; anything else is a failure: use Tk's chooser
    return '' if r.returncode == 1 else None


def open_folder(path):
    try:
        if ON_WINDOWS:
            os.startfile(path)  # noqa: S606 (a folder the user made)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path], env=cps3ws.system_env())
    except OSError as e:
        messagebox.showerror(APP, f'Could not open {path}:\n{e}')


def running_under_wine():
    if not ON_WINDOWS:
        return False
    try:
        import ctypes
        return hasattr(ctypes.windll.ntdll, 'wine_get_version')
    except (OSError, AttributeError):
        return False


def default_out():
    """Where to save unless the user chooses: 'CPS3 Widescreen' in the home folder. Under Wine the Windows home
    folder is hidden inside the Wine prefix, so the Linux home folder is used: Wine gives it to Windows programs
    as WINEHOMEDIR, written like \\??\\Z:\\home\\name (it does not pass HOME)."""
    home = os.path.expanduser('~')
    if running_under_wine():
        h = os.environ.get('WINEHOMEDIR', '')
        if h.startswith('\\??\\'):
            h = h[4:]
        if h and os.path.isdir(h):
            home = h
    return os.path.join(home, 'CPS3 Widescreen')


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.worker = None
        self.last_out = None
        root.title(f'{APP} {VERSION}')
        root.minsize(760, 600)
        style = ttk.Style()
        if not ON_WINDOWS and 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('Hint.TLabel', foreground='#555555')
        style.configure('Head.TLabel', font=('TkDefaultFont', 11, 'bold'))
        style.configure('Big.TButton', padding=(16, 6))
        style.configure('Horizontal.TProgressbar', background='#2f6fca')

        self.nb = nb = ttk.Notebook(root)
        nb.pack(fill='both', expand=True, padx=8, pady=8)
        nb.add(self.make_tab(nb), text='Make files')
        nb.add(self.text_tab(nb, INSTRUCTIONS), text='Instructions')
        nb.add(self.text_tab(nb, [('About', ABOUT)]), text='About')
        self.update_needs()
        root.after(100, self.poll)

    # ---- the Make files tab
    def make_tab(self, parent):
        f = ttk.Frame(parent, padding=12)
        f.columnconfigure(0, weight=1)
        wrap = 700
        ttk.Label(f, text=INTRO, wraplength=wrap, justify='left').grid(row=0, column=0, sticky='w', pady=(0, 8))

        # 1. pack
        self.pack_var = tk.StringVar()
        s = self.section(f, 1, '1.  Your Darksoft CPS-3 pack')
        row = ttk.Frame(s)
        row.pack(fill='x')
        ttk.Entry(row, textvariable=self.pack_var).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Choose .7z file...', command=self.pick_pack_file).pack(side='left', padx=(6, 0))
        ttk.Button(row, text='Choose folder...', command=self.pick_pack_dir).pack(side='left', padx=(6, 0))
        ttk.Label(s, text='The 2021-01-09 or 2021-04-02 release: the .7z file, or the folder you extracted it to.',
                  style='Hint.TLabel', wraplength=wrap).pack(anchor='w', pady=(2, 0))

        # 2. formats
        s = self.section(f, 2, '2.  What to make')
        self.fmt = {}
        for key, (name, desc) in FORMAT_TEXT.items():
            v = tk.BooleanVar(value=key == 'darksoft')
            self.fmt[key] = v
            ttk.Checkbutton(s, text=name, variable=v, command=self.update_needs).pack(anchor='w')
            ttk.Label(s, text=desc, style='Hint.TLabel', wraplength=wrap - 24).pack(anchor='w', padx=(24, 0),
                                                                                   pady=(0, 4))

        # 3. ROM folder
        self.roms_var = tk.StringVar()
        s = self.section(f, 3, '3.  Your MAME ROM folder (MAME and MiSTer only)')
        row = ttk.Frame(s)
        row.pack(fill='x')
        self.roms_entry = ttk.Entry(row, textvariable=self.roms_var)
        self.roms_entry.pack(side='left', fill='x', expand=True)
        self.roms_button = ttk.Button(row, text='Choose folder...', command=self.pick_roms)
        self.roms_button.pack(side='left', padx=(6, 0))
        ttk.Label(s, text='The folder that holds sfiii3nr1.zip or sfiii3n.zip (3rd Strike, NO CD). Only its BIOS '
                          'chip is used, to start the games.', style='Hint.TLabel', wraplength=wrap).pack(
            anchor='w', pady=(2, 0))

        # 4. output
        self.out_var = tk.StringVar(value=default_out())
        s = self.section(f, 4, '4.  Save to')
        row = ttk.Frame(s)
        row.pack(fill='x')
        ttk.Entry(row, textvariable=self.out_var).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Choose folder...', command=self.pick_out).pack(side='left', padx=(6, 0))

        # go
        row = ttk.Frame(f)
        row.grid(row=5, column=0, sticky='we', pady=(10, 4))
        self.go = ttk.Button(row, text='Make files', style='Big.TButton', command=self.start)
        self.go.pack(side='left')
        self.open_btn = ttk.Button(row, text='Open output folder', command=lambda: open_folder(self.last_out),
                                   state='disabled')
        self.open_btn.pack(side='left', padx=(8, 0))
        self.status = ttk.Label(row, text='', wraplength=420)
        self.status.pack(side='left', padx=(12, 0))
        self.bar = ttk.Progressbar(f, mode='determinate')
        self.bar.grid(row=6, column=0, sticky='we', pady=(2, 6))

        logf = ttk.Frame(f)
        logf.grid(row=7, column=0, sticky='nsew')
        f.rowconfigure(7, weight=1)
        self.log = tk.Text(logf, height=8, wrap='none', state='disabled', font=('TkFixedFont', 9))
        sb = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.log.pack(side='left', fill='both', expand=True)
        return f

    def section(self, parent, row, title):
        s = ttk.Frame(parent)
        s.grid(row=row, column=0, sticky='we', pady=(6, 0))
        ttk.Label(s, text=title, style='Head.TLabel').pack(anchor='w', pady=(0, 3))
        return s

    def text_tab(self, parent, sections):
        f = ttk.Frame(parent, padding=4)
        t = tk.Text(f, wrap='word', padx=12, pady=10, relief='flat', cursor='arrow')
        sb = ttk.Scrollbar(f, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        t.pack(side='left', fill='both', expand=True)
        t.tag_configure('h', font=('TkDefaultFont', 12, 'bold'), spacing1=10, spacing3=4)
        t.tag_configure('p', font=('TkDefaultFont', 10), spacing2=2, lmargin1=4, lmargin2=4)
        for head, body in sections:
            t.insert('end', head + '\n', 'h')
            t.insert('end', body + '\n', 'p')
        t.configure(state='disabled')
        return f

    # ---- pickers
    def pick_pack_file(self):
        p = native_dialog('file', 'Choose the Darksoft CPS-3 pack', self.pack_var.get())
        if p is None:
            p = filedialog.askopenfilename(title='Choose the Darksoft CPS-3 pack',
                                           filetypes=[('Darksoft pack', '*.7z *.zip'), ('All files', '*')])
        if p:
            self.pack_var.set(os.path.normpath(p))

    def pick_pack_dir(self):
        p = native_dialog('dir', 'Choose the extracted Darksoft pack folder', self.pack_var.get())
        if p is None:
            p = filedialog.askdirectory(title='Choose the extracted Darksoft pack folder')
        if p:
            self.pack_var.set(os.path.normpath(p))

    def pick_roms(self):
        p = native_dialog('dir', 'Choose your MAME ROM folder', self.roms_var.get())
        if p is None:
            p = filedialog.askdirectory(title='Choose your MAME ROM folder')
        if p:
            self.roms_var.set(os.path.normpath(p))

    def pick_out(self):
        p = native_dialog('dir', 'Choose where to save', self.out_var.get())
        if p is None:
            p = filedialog.askdirectory(title='Choose where to save')
        if p:
            self.out_var.set(os.path.normpath(p))

    def update_needs(self):
        need = self.fmt['mame'].get() or self.fmt['mister'].get()
        state = 'normal' if need else 'disabled'
        self.roms_entry.configure(state=state)
        self.roms_button.configure(state=state)

    # ---- running
    def write_log(self, line):
        self.log.configure(state='normal')
        self.log.insert('end', line + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def start(self):
        pack, out = self.pack_var.get().strip(), self.out_var.get().strip()
        formats = [k for k, v in self.fmt.items() if v.get()]
        roms = self.roms_var.get().strip()
        if not pack:
            return messagebox.showwarning(APP, 'Choose your Darksoft CPS-3 pack first (step 1).')
        if not formats:
            return messagebox.showwarning(APP, 'Tick at least one thing to make (step 2).')
        if {'mame', 'mister'} & set(formats) and not roms:
            return messagebox.showwarning(APP, 'MAME and MiSTer files need your MAME ROM folder (step 3).')
        if not out:
            return messagebox.showwarning(APP, 'Choose where to save (step 4).')
        self.go.configure(state='disabled')
        self.open_btn.configure(state='disabled')
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')
        self.bar['value'] = 0
        self.status.configure(text='Starting...')
        self.last_out = out

        def work():
            try:
                result = cps3ws.make(pack, out, formats, [roms] if roms else [],
                                     log=lambda s: self.events.put(('log', s)),
                                     step=lambda i, n, t: self.events.put(('step', i, n, t)))
                self.events.put(('done', result))
            except cps3ws.Failed as e:
                self.events.put(('failed', str(e)))
            except Exception:  # anything else is a bug: show all of it
                self.events.put(('crash', traceback.format_exc()))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                kind = ev[0]
                if kind == 'log':
                    self.write_log(ev[1])
                elif kind == 'step':
                    _, i, n, t = ev
                    self.bar['maximum'] = n
                    self.bar['value'] = i
                    self.status.configure(text=f'{t}...' if i < n else t)
                elif kind == 'done':
                    self.finish()
                    names = '\n'.join('  ' + os.path.basename(p) for p in ev[1]['written'])
                    skipped = ev[1]['skipped']
                    note = ''
                    if skipped:
                        note = ('\n\nNot made for MAME / MiSTer, because your ROM folder has no BIOS that can '
                                'start them (add sfiii3nr1.zip or sfiii3n.zip and run again):\n' +
                                '\n'.join('  ' + t for t in skipped))
                    self.status.configure(text='Done, with games left out.' if skipped else 'Done.')
                    messagebox.showinfo(APP, f'Done. In {self.last_out}:\n{names}{note}\n\nThe Instructions tab '
                                             'says what to do with them.')
                elif kind == 'failed':
                    self.finish()
                    self.status.configure(text='Stopped: nothing was made or changed.')
                    self.write_log('STOPPED: ' + ev[1])
                    messagebox.showerror(APP, ev[1])
                elif kind == 'crash':
                    self.finish()
                    self.status.configure(text='Stopped by an error: nothing was made or changed.')
                    self.write_log(ev[1])
                    messagebox.showerror(APP, 'Something went wrong (details in the log box). Please report it at '
                                              f'{REPO}/issues with the log text.')
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def finish(self):
        self.go.configure(state='normal')
        if self.last_out and os.path.isdir(self.last_out):
            self.open_btn.configure(state='normal')

    def closing(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(APP, 'Files are still being made. Stop and quit?'):
                return
        self.root.destroy()


def self_test(app, conf_path):
    """CPS3WS_SELFTEST=<json file>: fill the form from {pack, formats, roms, out, result, tab}, press Make files,
    write {"result": done|failed|crash, ...} to <result> when finished, then quit a few seconds later (time for a
    screenshot of the finished window). For automated tests of the built apps; not for users."""
    import json
    conf = json.load(open(conf_path, encoding='utf-8'))
    app.pack_var.set(conf.get('pack', ''))
    for k, v in app.fmt.items():
        v.set(k in conf.get('formats', ['darksoft']))
    app.update_needs()
    app.roms_var.set(conf.get('roms', ''))
    app.out_var.set(conf.get('out', ''))
    app.nb.select(int(conf.get('tab', 0)))
    picked = {}
    if conf.get('pick'):  # press a real "Choose..." button; the test drives or closes the chooser that opens
        def press():
            before = app.roms_var.get()
            app.pick_roms()
            picked.update(before=before, after=app.roms_var.get(), chooser=dict(last_dialog))
        app.root.after(1000, press)

    def report(kind):
        def show(title, text):
            with open(conf['result'], 'w', encoding='utf-8') as f:
                json.dump({'result': kind, 'message': text, 'log': app.log.get('1.0', 'end'),
                           'helpers': {h: helper_works(h) for h in ('kdialog', 'zenity', 'xdg-open')},
                           'default_out': default_out(), 'picked': picked}, f)
            app.root.after(int(conf.get('quit_after_ms', 4000)), app.root.destroy)
        return show
    messagebox.showinfo, messagebox.showerror = report('done'), report('failed')
    messagebox.showwarning = report('warning')  # a form problem: report it instead of waiting for a click
    if conf.get('run', True):
        app.root.after(800, app.start)
    else:
        app.root.after(1500, lambda: report('started')(APP, 'window shown'))


def main():
    root = tk.Tk()
    app = App(root)
    root.protocol('WM_DELETE_WINDOW', app.closing)
    if os.environ.get('CPS3WS_SELFTEST'):
        self_test(app, os.environ['CPS3WS_SELFTEST'])
    root.mainloop()


if __name__ == '__main__':
    main()
