# Packaging CETUS (Windows · macOS · Linux)

CETUS ships as per-OS installers plus a portable build. PyInstaller **cannot
cross-compile**, so each installer is built on its own OS (the `Release` GitHub
Actions workflow does all three on a tag; see below).

## Where patient data lives

Installed builds place the executable in a read-only location (Program Files, a macOS
`.app`), so patient **data and media move to the standard per-user directory**
(`cravingcrave/paths.py`):

| OS | Data + media directory |
|----|------------------------|
| Windows | `%APPDATA%\CETUS` |
| macOS | `~/Library/Application Support/CETUS` |
| Linux | `$XDG_DATA_HOME/CETUS` or `~/.local/share/CETUS` |

**Portable override:** drop an empty `portable.txt` (or a `data/` folder) next to the
executable and CETUS keeps everything beside the binary instead — this is the old
portable-exe workflow, and it also means every existing deployment keeps working
untouched. First run creates the folders automatically.

## Icons

`cravingcrave/resources/icons/cetus.{png,ico,icns}` are generated placeholders. Replace
them with real brand art (keep the filenames) or regenerate:
`python scripts/make_icons.py`.

## Build per OS

Prereq everywhere: `pyinstaller --noconfirm cravingcrave.spec` (or run `build.ps1` /
`build.sh`, which also invoke the installer step when the tooling is present).

### Windows — Inno Setup installer
1. Build `dist\CETUS.exe`.
2. Install [Inno Setup](https://jrsoftware.org/isinfo.php) (provides `iscc`).
3. `iscc /DAppVersion=0.4.0 packaging\windows\cetus.iss`
   → `packaging\windows\Output\CETUS-Setup-0.4.0.exe` (Start-menu shortcut, uninstaller).
   The portable `dist\CETUS.exe` still works on its own.

### macOS — .dmg
1. Build `dist/CETUS.app` (the spec emits a bundle on macOS).
2. `bash packaging/macos/make_dmg.sh 0.4.0` → `dist/CETUS-0.4.0.dmg`
   (uses `create-dmg` if installed, else `hdiutil`).

### Linux — AppImage
1. Build `dist/CETUS`.
2. Install [`appimagetool`](https://github.com/AppImage/AppImageKit/releases).
3. `bash packaging/linux/make_appimage.sh 0.4.0` → `dist/CETUS-0.4.0-x86_64.AppImage`.

## Signing / notarization (important)

The default builds are **unsigned**. Without a certificate:
- **macOS**: Gatekeeper shows "unidentified developer" — users right-click → **Open** once.
  With an Apple Developer ID you can `codesign` + `notarytool` + `stapler staple`
  (see comments in `make_dmg.sh`).
- **Windows**: SmartScreen may warn on first run. An EV/OV code-signing certificate
  removes the warning (sign `CETUS.exe` and the setup exe with `signtool`).

Provide certificates via CI secrets and add the signing steps to `release.yml` if/when
available.

## CI release

Push a tag `vX.Y.Z` → `.github/workflows/release.yml` builds Windows/macOS/Linux in
parallel and attaches the installers to the GitHub Release. `workflow_dispatch` lets you
dry-run it without tagging.
