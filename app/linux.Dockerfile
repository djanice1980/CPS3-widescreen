# Build image for the Linux app: Debian 11 (glibc 2.31), so the single-file app runs on Debian 11, Ubuntu 20.04 and
# anything newer. Used by app/build_linux.sh.
FROM debian:bullseye
# Debian 11 left LTS in 2026: its packages live on archive.debian.org now
RUN printf "deb http://archive.debian.org/debian bullseye main\ndeb http://archive.debian.org/debian-security bullseye-security main\n" \
        > /etc/apt/sources.list && apt-get update && apt-get install -y --no-install-recommends python3 python3-dev python3-tk python3-venv python3-pip \
        binutils ca-certificates && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/py && /opt/py/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/py/bin/pip install --no-cache-dir pyinstaller==6.11.1 numpy==2.0.2 py7zr==0.22.0
