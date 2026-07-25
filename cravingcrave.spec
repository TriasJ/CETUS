# PyInstaller spec for CETUS — one-file exe (Windows/Linux) or .app bundle (macOS).
# Build:  pyinstaller cravingcrave.spec   (run on the OS you are targeting; no cross-compile)
#
# Notes:
# * collect_all('PySide6') pulls in the Qt multimedia + platform plugins that a
#   bare build often misses (cause of black video / "no Qt platform plugin" crashes).
# * resources/ (i18n, qss, icons) and data/schema.sql are bundled explicitly;
#   paths.resource_path() resolves them under sys._MEIPASS.
# * media/ and data/ are NOT bundled. Portable builds keep them next to the binary
#   (drop a portable.txt beside the exe); installed builds use the per-OS user data
#   dir (see cravingcrave/paths.py).

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

pyside_datas, pyside_bins, pyside_hidden = collect_all("PySide6")

# Bundle our resources explicitly (collect_data_files can miss them when running
# from source). Each tuple is (absolute source file, destination directory in the
# bundle) so paths.resource_path() finds them under _MEIPASS/cravingcrave/...
_ROOT = Path(SPECPATH)


def _collect(src_rel: str, dst_rel: str):
    base = _ROOT / src_rel
    items = []
    for path in base.rglob("*"):
        if path.is_file():
            rel_parent = path.relative_to(base).parent
            items.append((str(path), str(Path(dst_rel) / rel_parent)))
    return items


app_datas = (
    _collect("cravingcrave/resources", "cravingcrave/resources")
    + [(str(_ROOT / "cravingcrave" / "data" / "schema.sql"), "cravingcrave/data")]
)

# Per-OS app icon (falls back to None if the icon file is missing).
_ICON_DIR = _ROOT / "cravingcrave" / "resources" / "icons"
_icon_name = "cetus.icns" if sys.platform == "darwin" else "cetus.ico"
_icon_path = _ICON_DIR / _icon_name
APP_ICON = str(_icon_path) if _icon_path.exists() else None

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=pyside_bins,
    datas=app_datas + pyside_datas,
    hiddenimports=pyside_hidden + [
        "PySide6.QtCharts",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CETUS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,            # set True temporarily to debug codec issues
    disable_windowed_traceback=False,
    icon=APP_ICON,
)

# macOS: wrap the exe in a proper .app bundle (installer-friendly, dock icon).
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="CETUS.app",
        icon=APP_ICON,
        bundle_identifier="org.cetus.app",
        info_plist={
            "CFBundleName": "CETUS",
            "CFBundleDisplayName": "CETUS",
            "NSHighResolutionCapable": True,
        },
    )
