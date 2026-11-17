# CPS3 Widescreen

Widescreen (495 x 224) for seven Capcom CPS3 games, switched on and off from each game's own service menu with a
new SCREEN MODE setting. With the setting on NORMAL the Street Fighter III and JoJo games draw the same picture
as before (checked frame by frame in MAME against the unpatched games; 3rd Strike and both JoJo games also through
scripted fights). Warzard on NORMAL matches in attract mode but not frame for frame during play: see
[Status and known issues](#status-and-known-issues).

The patch is applied to your own **Darksoft CPS-3 multi-game pack** (the 2021-01-09 or 2021-04-02 release).
From that one pack it can make any of three things:

| Output   | What you get                                                                   |
|----------|--------------------------------------------------------------------------------|
| darksoft | The patched pack, ready to flash to Darksoft UltraSIMM program and graphics SIMMs |
| mame     | MAME NO CD ROM sets, one folder per game                                       |
| mister   | MRA files and ROM zips for Jotego's CPS3 core (jtcps3) on MiSTer              |

No ROM data is included in this repository or its releases. You need the Darksoft pack, and for the MAME and
MiSTer outputs one MAME set of your own (see [What you need](#what-you-need)).

The easiest way is the app: download it, double-click it, choose your pack, click **Make files**. It runs on
Linux and on Windows, including under Wine, and has the instructions built in. See [The app](#the-app).

## Games

| Darksoft bank | Game                                              | Darksoft files patched          |
|---------------|---------------------------------------------------|---------------------------------|
| 0             | Street Fighter III: New Generation                | Standard SH2 and Custom SH2     |
| 1             | Warzard (Red Earth)                               | Standard SH2 and Custom SH2     |
| 3             | JoJo's Venture                                    | Standard SH2 only               |
| 4             | JoJo's Bizarre Adventure: Heritage for the Future | Standard SH2 only               |
| 5             | Street Fighter III 3rd Strike                     | Standard SH2 and Custom SH2     |
| 6             | Street Fighter III 3rd Strike: Makoto Fix         | Standard SH2 and Custom SH2     |
| 7             | Street Fighter III 4rd Strike                     | Standard SH2 and Custom SH2     |

Bank 2 (2nd Impact) is left as it is: it already has a widescreen option of its own. Darksoft's bank 3 and 4
Custom SH2 files hold different revisions of the two JoJo games, so those stay unpatched; on a Custom SH2
(security cart) board the JoJo games run in 4:3 as before.

What widescreen does:

- Fights show more of each stage on both sides.
- The fight HUD (life bars, timer, meters, score) is centered on the wider screen.
- In 3rd Strike, Makoto Fix and 4rd Strike, life and damage stay the same as in 4:3. (The game's own unfinished
  wide mode raises the life total, which also changes damage; the patch keeps the 4:3 value.)

## What you need

- **The Darksoft CPS-3 pack**, `Darksoft CPS-3 2021-01-09.7z` or `Darksoft CPS-3 2021-04-02.7z` (or the folder
  you extracted it to: the one that holds `SIMM 1-2` and `SIMM 3-6`). See
  [The two Darksoft releases](#the-two-darksoft-releases) for how they differ.
- **For the MAME and MiSTer outputs:** your MAME `sfiii3nr1.zip` or `sfiii3n.zip` (3rd Strike, NO CD). Only its
  BIOS chip is used. If you also have `sfiiina`/`sfiiin`, `jojon`/`jojonr1`/`jojonr2` or
  `jojoban`/`jojobanr1`/`jojobanr2`, New Generation and the JoJo games use their own BIOS and their own MAME
  sets instead (see [MAME](#mame)).
- **About 3 GB of free disk space** for all three outputs (less for one).

## The app

Download from the [latest release](https://github.com/djanice1980/CPS3-widescreen/releases/latest):

| Your system | File |
|---|---|
| Linux (64-bit PC: Ubuntu 20.04, Debian 11, Fedora, Arch and newer) | `CPS3-Widescreen-linux-x86_64` |
| Windows 10 or 11 (64-bit), or Wine on Linux | `CPS3-Widescreen-windows-x64.exe` |

Nothing to install: each is a single file.

**Linux:** downloaded files are not allowed to run until you say so. In your file manager, right-click the file,
choose Properties, and on the Permissions tab tick "Allow executing file as program" (KDE: "Is executable"). Then
double-click it. (In a terminal: `chmod +x CPS3-Widescreen-linux-x86_64` and `./CPS3-Widescreen-linux-x86_64`.)

**Windows:** double-click the .exe. The app is not code-signed, so Windows may show "Windows protected your PC":
click **More info**, then **Run anyway**.

**Wine:** double-click the .exe if your desktop opens .exe files with Wine, or run
`wine CPS3-Widescreen-windows-x64.exe`. Your Linux files are on drive Z: in its file dialogs.

Then, in the app:

1. **Your Darksoft CPS-3 pack:** choose the .7z you downloaded (or the folder you extracted it to; only its
   `SIMM 1-2` and `SIMM 3-6` folders are read).
2. **What to make:** tick the Darksoft pack, MAME sets, MiSTer files, or any mix.
3. **Your MAME ROM folder** (MAME and MiSTer only): the folder that holds `sfiii3nr1.zip` or `sfiii3n.zip`.
4. **Save to:** an empty folder is best.
5. Click **Make files**. It takes a few minutes; **Open output folder** shows the results.

Everything is made in a work folder and moved into the output folder only when all of it is complete. If the app
stops for any reason (a wrong pack, no BIOS, a full disk, closing the window), the output folder is left as it
was and the message says what to fix.

The Instructions tab in the app covers flashing, turning widescreen on, MAME and MiSTer, the same as the sections
below.

## Command line (optional)

The app and `tools/make_pack.sh` do the same work with the same code (`tools/cps3ws.py`). To use the command line
you need **Python 3 with numpy, git, and 7-Zip**. Install them:

  Arch / CachyOS / Manjaro:
  ```bash
  sudo pacman -S --needed python python-numpy 7zip git
  ```
  Debian / Ubuntu / Mint:
  ```bash
  sudo apt install python3 python3-numpy p7zip-full git
  ```
  Fedora:
  ```bash
  sudo dnf install python3 python3-numpy p7zip p7zip-plugins git
  ```
  Windows: use WSL. In PowerShell run `wsl --install`, restart, open "Ubuntu" from the Start menu, and use the
  Debian / Ubuntu line above inside it. Your Windows drives are under `/mnt/c`, `/mnt/d` and so on, so a pack in
  your Downloads folder is `/mnt/c/Users/<your Windows user name>/Downloads/Darksoft CPS-3 2021-01-09.7z`.

  macOS has not been tried (the script uses GNU `realpath`); use Linux, WSL or a Linux VM.

  To check what you already have: `python3 -c "import numpy"` prints nothing when numpy is installed, and
  `7z` prints its version banner when 7-Zip is installed.

You do not need a compiler: the patches are prebuilt in `patches/`. (To build them yourself, see
[Building the patches from source](#building-the-patches-from-source).)

### Running make_pack.sh

Get the code, either with git:

```bash
git clone https://github.com/djanice1980/CPS3-widescreen.git
```

or by downloading the source zip from the [latest release](https://github.com/djanice1980/CPS3-widescreen/releases/latest)
and unzipping it. Then, from inside the `CPS3-widescreen` folder:

```bash
cd CPS3-widescreen
```

Run `tools/make_pack.sh <Darksoft pack> <output folder> --format <formats> [--roms <folder with your MAME sets>]`.
Replace the two paths in these examples with your own:

All three outputs:
```bash
tools/make_pack.sh ~/Downloads/"Darksoft CPS-3 2021-01-09.7z" out --format all --roms ~/mame/roms
```
Only the Darksoft pack (no MAME set needed):
```bash
tools/make_pack.sh ~/Downloads/"Darksoft CPS-3 2021-01-09.7z" out --format darksoft
```
Only MAME, or only MiSTer:
```bash
tools/make_pack.sh ~/Downloads/"Darksoft CPS-3 2021-01-09.7z" out --format mame --roms ~/mame/roms
```
```bash
tools/make_pack.sh ~/Downloads/"Darksoft CPS-3 2021-01-09.7z" out --format mister --roms ~/mame/roms
```

`--format` takes `darksoft`, `mame`, `mister` (several separated by commas) or `all`; without it you get
`darksoft`. `--roms` is the folder that holds your MAME zips (it can be given more than once). The run takes a
couple of minutes and needs about 3 GB of free space for `all`. Everything is made in `.cps3ws-work` inside the
output folder and moved into place when complete; a run that stops leaves the output folder as it was.

The tool checks every patched address against the bytes the patch expects and stops if any differ, so a
different or modified pack is refused. It also checks that the Custom
SH2 files decrypt back to the Standard ones and that every MAME set and MRA decodes back to the patched program.

You get, in the output folder:

```
Darksoft CPS-3 2021-01-09 - widescreen (...).zip   the patched Darksoft pack
MAME/                                               one folder per game, plus README.txt
MiSTer/_Arcade/_CPS3 Widescreen/*.mra               MiSTer MRA files
MiSTer/games/mame/*.zip                             their ROM zips, plus MiSTer/README.txt
```

## Turning widescreen on

Each game gets a SCREEN MODE item (NORMAL / WIDE) in its settings page of the test menu:

1. Enter the test menu (the TEST button on the board; F2 in MAME).
2. Open the game's settings page (the one with difficulty, rounds and so on).
3. Set SCREEN MODE to WIDE. In Warzard's Japanese menu it is スクリーンモード, ノーマル / ワイド.
4. Save and leave the test menu the way that game normally saves its settings (for New Generation that is item
   4, save and return). Warzard switches as soon as you save. If another game is still 4:3 after you leave the
   test menu, reset the machine (F3 in MAME).

The setting is stored in the game's EEPROM settings like any other option, so it survives power-off.

## The two Darksoft releases

Both work, and the tool tells you which one it was given. The 2021-04-02 release differs from 2021-01-09 in two
places, found by comparing the two packs bank by bank (everything else is byte-identical):

- **Warzard (bank 1):** `SIMM1_Jumper_U9_..._WarzardFIX.bin` changes one instruction, at 060024C0: a call to
  0600E864 becomes a no-op. That routine writes to 05140000, which is the CPS3's SCSI controller (the WD33C93 in
  MAME's CPS3 driver), so the call sends a command to the CD-ROM drive. A board running from Darksoft SIMMs has
  no CD-ROM drive; forum reports from the time call this release's change the Warzard no-CD fix. The widescreen
  patch does not touch that code and works with either release.
- **Makoto Fix (bank 6) graphics:** `SIMM 3-6` now has two SIMM 5 files instead of one:
  `SIMM5_Final_MakotoFIX.bin` (the Makoto Fix graphics, with a fix of its own) and `SIMM5_Final_reTHIRD.bin` (the
  reTHIRD mod). Both differ from 2021-01-09 only in bank 6, and the bank 6 program is the same for both. You
  flash one of them. The MAME and MiSTer outputs make both, as "Makoto Fix" and "Makoto Fix (reTHIRD)".

## Darksoft

Unzip the patched pack and flash it the same way you flash the original Darksoft pack, following Darksoft's
instructions for your UltraSIMM kit. Use the `Standard SH2` program files on a board with a standard
(HD6417095) SH2, and the `Custom SH2` files on a board that still uses the original security-cart CPU. Only the
program SIMM files (`SIMM 1-2`) differ from the original pack; `SIMM 3-6` are copied unchanged. With the
2021-04-02 pack, flash one of the two SIMM 5 files, as you would with the original.

## MAME

Each folder under `MAME/` is one game, stored as the MAME NO CD set named inside it. The files differ from
MAME's own sets, so MAME reports wrong checksums and then runs the game anyway.

Run a game with its folder as the ROM path **and its own nvram folder**:

```bash
mame -rompath "out/MAME/sfiii-3rd-strike" -nvram_directory "out/MAME/sfiii-3rd-strike/nvram" sfiii3nr1
```

The nvram folder matters. MAME saves CPS3 program SIMMs into `nvram/<set name>/` and boots from those copies
afterwards, so a game that shares an nvram folder with the unpatched game, or with another folder here that uses
the same set name, boots whichever program ran there first. `MAME/README.txt` lists the set name of each folder.

Set names:

- 3rd Strike is `sfiii3nr1`. Makoto Fix and 4rd Strike are `sfiii3n` (they are 3rd Strike hacks).
- Warzard is always `sfiii3n`. MAME's Red Earth machine has no second program SIMM, and that is where Warzard's
  widescreen code lives. Red Earth's inputs are the same as 3rd Strike's, so only the button names differ.
- New Generation and the JoJo games are `sfiiina`, `jojonr2` and `jojobanr2` when your `--roms` folder has a
  BIOS for that game. Without one they run as `sfiii3n` on the 3rd Strike BIOS. A CPS3 BIOS only works on its
  own game's MAME machine, so it cannot be moved to another set.
- The BIOS sets the region. On the 3rd Strike Japan BIOS, Warzard and the JoJo games show their Japanese
  versions.

## MiSTer

This is for Jotego's CPS3 core (`jtcps3`). Copy the output to the root of the MiSTer SD card (`/media/fat`):

- `MiSTer/_Arcade/_CPS3 Widescreen/` to `/media/fat/_Arcade/_CPS3 Widescreen/`
- `MiSTer/games/mame/*.zip` to `/media/fat/games/mame/`

The core itself must already be installed in `/media/fat/_Arcade/cores/`. While the core is in beta it also
needs Jotego's `jtbeta.zip` in `games/mame`, the same as his own CPS3 MRAs. Each MRA uses only its own zip
(`sfiii3w.zip`, `warzardw.zip` and so on), so your normal CPS3 zips are untouched, and its own setname, so the
saved settings are kept apart from the unpatched games.

The MRAs use the same header, ROM order and interleave as Jotego's published CPS3 MRAs. Given an unmodified
`sfiii3nr1` set, the generator reproduces the checksum Jotego publishes for it exactly.

## Status and known issues

- Tested in MAME 0.289: all seven games boot from all three outputs' data, and run in both modes. Not yet
  confirmed on a real CPS3 board or on a MiSTer. Reports are welcome in
  [Issues](https://github.com/djanice1980/CPS3-widescreen/issues).
- The apps: the Linux app ran end to end (all three outputs from the 2021-04-02 .7z) on Ubuntu 20.04 and opens on
  Ubuntu 24.04, Fedora 42 and Arch; its "Choose..." buttons were tested with the real desktop choosers (zenity on
  Ubuntu 24.04, kdialog on Arch). The Windows app ran end to end under Wine 11.22. Both gave the same files as
  the command line (the zips hold identical files; only their compression differs slightly). The Windows app has
  not been run on real Windows yet.
- The MAME sets made with a game's own BIOS (New Generation, JoJo) follow MAME's own layout for those sets but
  were not run here.
- Some non-fight screens (continue, game over, results, a few intro scenes) are still drawn at 4:3 width, with
  black side bars or an offset picture.
- 3rd Strike, Makoto Fix and 4rd Strike in WIDE: the label of a timed super art (such as Yun's Genei-Jin) now
  moves with the gauge, but this fix was not replayed in MAME (it needs that character with a full gauge). The
  bonus stage's score digits may still sit at their 4:3 column (seen in the source, not tried).
- **JoJo's Venture and JoJo HFTF on a real Darksoft board:** up to v1.1.1 the patch kept its variables on the RAM
  bytes the Darksoft versions of the games read at boot (region at 0207F000, no-CD flag at 0207F004), so the
  game ran the CD-ROM drive scan the flag exists to skip. Fixed in v1.2.0: the variables moved to 0207C000, and
  with the two bytes set as a Darksoft board has them the patched boot is identical to the unpatched one in
  MAME. It is still not confirmed on hardware.
- Warzard (both modes): all text is drawn through a copy in RAM that reaches the screen once per frame.
  - The test menu's memory check shows no progress for 25 to 50 seconds and then every result at once.
  - The copy takes CPU time every frame. The game has plenty to spare (its scheduler still idles through about
    330 of its usual 350 passes a frame; no slowdown), but a few effects advance with those passes, so on NORMAL
    some frames differ from the unpatched game (measured: 57 of 121 frames around one scene transition) and, as
    the game's random numbers follow, the same scripted inputs lead to different fights. This cannot be brought
    to zero with this design; v1.2.0 cut the copy to a third.
- JoJo games in WIDE: the last rows of the test menu's memory check never appear ("FLASH SIMM6 CHECKING..." stays
  on screen).
- At the edges of the wider view, some stage objects can appear a moment late.

## Building the patches from source

`patches/` is generated; you only need this to change the patches. `--build` compiles everything from source
and refreshes `patches/` before making the outputs:

```bash
tools/make_pack.sh ~/Downloads/"Darksoft CPS-3 2021-01-09.7z" out --format all --build
```

On top of the requirements above it needs:

- **wine and make**, for the original Hitachi SHC compiler that builds 3rd Strike and New Generation code:
  Arch `sudo pacman -S --needed wine make`, Debian/Ubuntu `sudo apt install wine make`.
- **The two decompilation projects** by gibletto, in `vendor/`, at the commits this was built against:
  ```bash
  git clone https://github.com/gibletto/sfIII3-cps3-decomp vendor/sfIII3-cps3-decomp
  ```
  ```bash
  git -C vendor/sfIII3-cps3-decomp checkout d440837003292a6521f85f0c57752c7b5f30255b
  ```
  ```bash
  git clone https://github.com/gibletto/sfIII-cps3-decomp vendor/sfIII-cps3-decomp
  ```
  ```bash
  git -C vendor/sfIII-cps3-decomp checkout f9b0553a44bd15bf82b71290f29e3aebf3e33edd
  ```
- **Your MAME `sfiii3nr1.zip`** in `rom/` (the 3rd Strike build takes its graphics data from it).

## Building the apps

The release files are built from this repository, on Linux, with Docker (Linux app) and Wine (Windows app):

```bash
app/build_linux.sh
```
```bash
DISPLAY=:0 app/build_windows.sh
```

`build_linux.sh` builds in a Debian 11 container (so the app runs on glibc 2.31 and newer). `build_windows.sh`
sets up its own Wine prefix in `build/wine-app` with the official Windows Python 3.12.10 from python.org (MD5
checked) and PyInstaller, numpy and py7zr from PyPI. Both write to `build/app/`. `app/test_linux.sh` and
`app/test_windows.sh` run the built apps on a virtual display (Xvfb in a container), fill in the form, make the
files and save a screenshot, without opening windows on your desktop. `PICK=zenity` or `PICK=kdialog` with
`app/test_linux.sh` also presses a real "Choose folder..." button and accepts the desktop chooser that opens. To run the app from source instead:
`python3 app/cps3ws_app.py` (needs python3-tk and numpy, plus py7zr or 7z for .7z packs).

## How it works (short version)

- **3rd Strike, Makoto Fix, 4rd Strike:** 3rd Strike has a leftover, unfinished wide mode. This turns it on and
  adds wide versions of the fight HUD routines, compiled from gibletto's byte-matching decompilation with the
  original compiler. Makoto Fix and 4rd Strike are built from the same code, relinked to the addresses of their
  own programs.
- **New Generation:** it keeps its complete original wide mode; the patch adds the SCREEN MODE menu item.
- **JoJo's Venture, JoJo's Bizarre Adventure, Warzard:** these have no wide mode at all. The patch widens the
  display, shifts the camera, sprites and backgrounds, and draws the whole text layer into RAM so it can be
  centered on the wider screen. The code was written against the games' machine code directly (there is no
  decompilation of these games).
- **Darksoft Custom SH2 files:** new instructions are stored encrypted the way Darksoft stores the rest of each
  bank, and the checksum byte of each SIMM is kept unchanged so the board's memory test still passes.

## License

Copyright (C) 2026 David Janice

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero
General Public License as published by the Free Software Foundation, version 3. It is distributed WITHOUT ANY
WARRANTY; see [LICENSE](LICENSE) for the full terms.

If you reuse or adapt this code, keep this copyright notice and credit this project, and release your version
under the same license with its source.

The license covers this project's own code and patches only. It grants no rights to Capcom's games, ROM data or
trademarks. The 3rd Strike family and New Generation code is built on gibletto's decompilations, which are
themselves AGPL-3.0.

## Credits

- [gibletto](https://github.com/gibletto)'s 3rd Strike and New Generation decompilations and rebuilt SHC
  toolchain, which the 3rd Strike family and New Generation patches are built from (AGPL-3.0). Parts of those
  were ported from [crowded-street/3s-decomp](https://github.com/crowded-street/3s-decomp).
- [Jotego](https://github.com/jotego/jtcores)'s CPS3 core, whose published MRAs define the MiSTer layout.
- MAME's CPS3 driver, for the decryption keys and ROM layout.
- Darksoft, for the multi-game kit and pack these patches target.

Street Fighter, JoJo's Venture, JoJo's Bizarre Adventure, Warzard and Red Earth are trademarks of Capcom (JoJo's
Bizarre Adventure under license from Hirohiko Araki / Shueisha). This project is not affiliated with Capcom,
Darksoft or Jotego and contains none of their ROM data.
