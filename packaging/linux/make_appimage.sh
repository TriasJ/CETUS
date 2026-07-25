#!/usr/bin/env bash
# Package the PyInstaller one-dir/one-file build into a portable AppImage (Linux only).
# Prereqs: run `pyinstaller cravingcrave.spec` first (produces dist/CETUS).
# Usage:   packaging/linux/make_appimage.sh 0.4.0
#
# AppImages are portable: one file runs on most modern distros with no install step.
# Needs `appimagetool` on PATH (https://github.com/AppImage/AppImageKit/releases).
set -euo pipefail

VERSION="${1:-0.0.0}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BIN="$ROOT/dist/CETUS"
ICON="$ROOT/cravingcrave/resources/icons/cetus.png"
APPDIR="$ROOT/dist/CETUS.AppDir"
OUT="$ROOT/dist/CETUS-$VERSION-x86_64.AppImage"

[ -f "$BIN" ] || { echo "error: $BIN not found — run pyinstaller cravingcrave.spec first" >&2; exit 1; }

rm -rf "$APPDIR"; mkdir -p "$APPDIR/usr/bin"
cp "$BIN" "$APPDIR/usr/bin/CETUS"
cp "$ICON" "$APPDIR/cetus.png"

cat > "$APPDIR/cetus.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=CETUS
Exec=CETUS
Icon=cetus
Categories=Science;MedicalSoftware;
Terminal=false
DESKTOP

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/CETUS" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

if command -v appimagetool >/dev/null 2>&1; then
  appimagetool "$APPDIR" "$OUT"
  echo "Wrote $OUT"
else
  echo "appimagetool not found; AppDir prepared at $APPDIR" >&2
  echo "Install appimagetool and run: appimagetool \"$APPDIR\" \"$OUT\"" >&2
  exit 1
fi
