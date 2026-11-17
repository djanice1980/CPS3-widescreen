#!/usr/bin/env bash
# Build the Windows app (one file: build/app/CPS3-Widescreen-windows-x64.exe) on Linux with Wine.
#
# Needs wine and curl. The first run sets up its own Wine prefix (build/wine-app) with the official Windows Python
# 3.12.10 from python.org (MD5 checked) and PyInstaller, numpy and py7zr from PyPI. Wine needs a display: set
# DISPLAY to any X server (app/test_windows.sh shows how to use a private Xvfb in a container).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export WINEPREFIX="$ROOT/build/wine-app" WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml="
PY='C:\Python312\python.exe'
if ! wine "$PY" -c "import PyInstaller, numpy, py7zr" >/dev/null 2>&1; then
    mkdir -p "$ROOT/build/wine-dl"
    exe="$ROOT/build/wine-dl/python-3.12.10-amd64.exe"
    [ -f "$exe" ] || curl -fsSL -o "$exe" https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
    echo "5eddb0b6f12c852725de071ae681dde4  $exe" | md5sum -c --quiet
    wineboot -i >/dev/null 2>&1
    wine "$exe" /quiet InstallAllUsers=0 'TargetDir=C:\Python312' Include_test=0 Include_launcher=0 Shortcuts=0 \
        AssociateFiles=0 >/dev/null 2>&1
    wine "$PY" -m pip install -q --disable-pip-version-check pyinstaller==6.11.1 numpy==2.0.2 py7zr==0.22.0
fi
src=$(winepath -w "$ROOT")
work="$ROOT/build/wine-pyi"
rm -rf "$work" && mkdir -p "$work" "$ROOT/build/app"
w=$(winepath -w "$work")
wine "$PY" -m PyInstaller --noconfirm --clean --onefile --windowed --name CPS3-Widescreen \
    --paths "$src\\tools" --add-data "$src\\patches;patches" --distpath "$w\\dist" --workpath "$w\\work" \
    --specpath "$w" "$src\\app\\cps3ws_app.py" >"$work/pyi.log" 2>&1 || { tail -40 "$work/pyi.log"; exit 1; }
cp "$work/dist/CPS3-Widescreen.exe" "$ROOT/build/app/CPS3-Widescreen-windows-x64.exe"
ls -la "$ROOT/build/app/CPS3-Widescreen-windows-x64.exe"
