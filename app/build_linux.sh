#!/usr/bin/env bash
# Build the Linux app (one file: build/app/CPS3-Widescreen-linux-x86_64) in a Debian 11 container, so it runs on
# older distributions too. Needs docker.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
docker build -q -f "$ROOT/app/linux.Dockerfile" -t cps3ws-linux-build "$ROOT/app" >/dev/null
mkdir -p "$ROOT/build/app"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$ROOT:/src:ro" -v "$ROOT/build/app:/out" \
    cps3ws-linux-build sh -c '
        set -e
        cd /tmp
        /opt/py/bin/pyinstaller --noconfirm --clean --onefile --windowed --name CPS3-Widescreen \
            --paths /src/tools --add-data /src/patches:patches --distpath /tmp/dist --workpath /tmp/work \
            --specpath /tmp/spec /src/app/cps3ws_app.py >/tmp/pyi.log 2>&1 || { tail -40 /tmp/pyi.log; exit 1; }
        cp /tmp/dist/CPS3-Widescreen /out/CPS3-Widescreen-linux-x86_64'
chmod +x "$ROOT/build/app/CPS3-Widescreen-linux-x86_64"
ls -la "$ROOT/build/app/CPS3-Widescreen-linux-x86_64"
