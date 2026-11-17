# CPS3 Widescreen

Widescreen (495 x 224) for seven Capcom CPS3 games, switched on and off from each game's own service menu with a
new SCREEN MODE setting. With the setting on NORMAL the games draw the same picture as before (checked frame by
frame in MAME against the unpatched games for the four Street Fighter III games and Warzard).

The patch is applied to your own **Darksoft CPS-3 multi-game pack** (the 2021-01-09 release). From that one
pack it can make any of three things:

| Output   | What you get                                                                   |
|----------|--------------------------------------------------------------------------------|
| darksoft | The patched pack, ready to flash to Darksoft UltraSIMM program and graphics SIMMs |
| mame     | MAME NO CD ROM sets, one folder per game                                       |
| mister   | MRA files and ROM zips for Jotego's CPS3 core (jtcps3) on MiSTer              |

No ROM data is included in this repository or its releases. You need the Darksoft pack, and for the MAME and
MiSTer outputs one MAME set of your own (see [What you need](#what-you-need)).

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

- **The Darksoft CPS-3 pack**, `Darksoft CPS-3 2021-01-09.7z` (or the folder you extracted it to: the one that
  holds `SIMM 1-2` and `SIMM 3-6`).
- **For the MAME and MiSTer outputs:** your MAME `sfiii3nr1.zip` or `sfiii3n.zip` (3rd Strike, NO CD). Only its
  BIOS chip is used. If you also have `sfiiina`/`sfiiin`, `jojon`/`jojonr1`/`jojonr2` or
  `jojoban`/`jojobanr1`/`jojobanr2`, New Generation and the JoJo games use their own BIOS and their own MAME
  sets instead (see [MAME](#mame)).
- **Python 3 with numpy, git, and 7-Zip.** Install them:

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

## Making the files

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
couple of minutes and needs about 3 GB of free space for `all` (temporary files go in `build/` inside the
`CPS3-widescreen` folder).

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

## Darksoft

Unzip the patched pack and flash it the same way you flash the original Darksoft pack, following Darksoft's
instructions for your UltraSIMM kit. Use the `Standard SH2` program files on a board with a standard
(HD6417095) SH2, and the `Custom SH2` files on a board that still uses the original security-cart CPU. Only the
program SIMM files (`SIMM 1-2`) differ from the original pack; `SIMM 3-6` are copied unchanged.

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
- The MAME sets made with a game's own BIOS (New Generation, JoJo) follow MAME's own layout for those sets but
  were not run here.
- Some non-fight screens (continue, game over, results, a few intro scenes) are still drawn at 4:3 width, with
  black side bars or an offset picture.
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
