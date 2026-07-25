"""Path resolution that works identically in development, portable, and installed builds.

Two distinct concepts:

* **Bundled resources** (i18n strings, QSS, icons) live *inside* the package and
  are read-only. When frozen they are unpacked to ``sys._MEIPASS``.
* **External runtime folders** (``media/`` and ``data/``) hold patient-specific cues and
  the SQLite database. Where they live depends on how the app is running:

  - *Development*: the project root (next to the package), so the repo stays self-contained.
  - *Portable build*: next to the executable — used when a ``portable.txt`` marker or an
    existing ``data/`` folder sits beside the ``.exe`` (this also preserves every existing
    deployment, whose data already lives next to the binary).
  - *Installed build*: the standard per-OS, per-user data directory, because an installer
    puts the executable in a read-only location (Program Files, a macOS ``.app`` bundle)
    where writing next to it is not possible.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
APP_DIRNAME = "CETUS"   # per-OS user-data folder name


def is_frozen() -> bool:
    """True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def resource_path(*parts: str) -> Path:
    """Absolute path to a read-only bundled resource under ``resources/``.

    Always access bundled files through this helper — never ``open("resources/...")``
    directly — so paths resolve correctly once frozen.
    """
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS", _PACKAGE_DIR)) / "cravingcrave"
    else:
        base = _PACKAGE_DIR
    return base / "resources" / Path(*parts)


def user_data_root() -> Path:
    """The standard writable per-user data directory for this OS (installed builds)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_DIRNAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIRNAME
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else (Path.home() / ".local" / "share")
    return base / APP_DIRNAME


def app_base_dir() -> Path:
    """Directory that holds the external ``media/`` and ``data/`` folders.

    Dev: the project root. Frozen + portable (``portable.txt`` marker or an existing
    ``data/`` beside the exe): next to the executable. Frozen + installed: the per-OS
    user-data directory.
    """
    if not is_frozen():
        return _PACKAGE_DIR.parent
    exe_dir = Path(sys.executable).resolve().parent
    if (exe_dir / "portable.txt").exists() or (exe_dir / "data").exists():
        return exe_dir
    return user_data_root()


def media_root() -> Path:
    return app_base_dir() / "media"


def data_dir() -> Path:
    return app_base_dir() / "data"


def db_path() -> Path:
    return data_dir() / "cravingcrave.db"
