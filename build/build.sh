#!/bin/sh
# Build both GodModeWii channel WADs from scratch and check them.
# Needs devkitPPC + libogc, wine (for Benzin), Python 3 and the donor files in donor/ (see BUILDING.md).
set -eu
cd "$(dirname "$0")/.."

if [ ! -x build/.venv/bin/python ]; then
    python3 -m venv build/.venv
    build/.venv/bin/pip install -q Pillow pycryptodome numpy
fi

make -C forwarder
cd build/tools
../.venv/bin/python sound.py
../.venv/bin/python banner.py
../.venv/bin/python icon.py
../.venv/bin/python build_wad.py
../.venv/bin/python verify.py
../.venv/bin/python preview.py
