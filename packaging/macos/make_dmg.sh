#!/usr/bin/env bash
# Package the PyInstaller .app bundle into a distributable .dmg (macOS only).
# Prereqs: run `pyinstaller cravingcrave.spec` first (produces dist/CETUS.app).
# Usage:   packaging/macos/make_dmg.sh 0.4.0
#
# The build is UNSIGNED unless you provide an Apple Developer ID certificate and
# notarize it. Without that, users must right-click -> Open the first time to bypass
# Gatekeeper ("unidentified developer"). Signing/notarization steps (optional):
#   codesign --deep --force --options runtime --sign "Developer ID Application: NAME" dist/CETUS.app
#   xcrun notarytool submit ... && xcrun stapler staple dist/CETUS.app
set -euo pipefail

VERSION="${1:-0.0.0}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/dist/CETUS.app"
OUT="$ROOT/dist/CETUS-$VERSION.dmg"

[ -d "$APP" ] || { echo "error: $APP not found — run pyinstaller cravingcrave.spec first" >&2; exit 1; }

rm -f "$OUT"
if command -v create-dmg >/dev/null 2>&1; then
  create-dmg --volname "CETUS $VERSION" --app-drop-link 450 160 \
    --icon "CETUS.app" 150 160 --window-size 600 320 "$OUT" "$APP"
else
  # Fallback: plain read-only dmg containing the .app + an Applications symlink.
  STAGE="$(mktemp -d)"
  cp -R "$APP" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  hdiutil create -volname "CETUS $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
  rm -rf "$STAGE"
fi
echo "Wrote $OUT"
