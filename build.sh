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

echo "==> Building binary with PyInstaller"
pyinstaller --noconfirm cravingcrave.spec

version="$(grep -m1 '^version = ' pyproject.toml | sed -E 's/version = "(.*)"/\1/')"
case "$(uname -s)" in
  Darwin)
    echo "==> Packaging macOS .dmg for v$version"
    bash packaging/macos/make_dmg.sh "$version" || echo "(dmg step skipped/failed; see packaging/README.md)"
    ;;
  Linux)
    echo "==> Packaging Linux AppImage for v$version"
    bash packaging/linux/make_appimage.sh "$version" || echo "(AppImage step needs appimagetool; see packaging/README.md)"
    ;;
esac

echo ""
echo "Done. See dist/ for the binary and any installer (.dmg / .AppImage)."
