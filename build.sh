#!/usr/bin/env bash
# Build CETUS on macOS / Linux: venv -> deps -> tests -> PyInstaller binary.
# PyInstaller cannot cross-compile, so run this on the OS you want to target.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

echo "==> Creating virtual environment (.venv)"
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements-dev.txt

echo "==> Running tests"
QT_QPA_PLATFORM=offscreen python -m pytest -q

echo "==> Building one-file binary with PyInstaller"
pyinstaller --noconfirm cravingcrave.spec

echo ""
echo "Done. Binary is in dist/  (ship it alongside the media/ folder)."
