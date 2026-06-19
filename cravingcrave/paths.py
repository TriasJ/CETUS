"""Path resolution that works identically in development and when frozen by PyInstaller.

Two distinct concepts:

* **Bundled resources** (i18n strings, QSS, icons) live *inside* the package and
  are read-only. When frozen they are unpacked to ``sys._MEIPASS``.
* **External runtime folders** (``media/`` and ``data/``) live *next to the
  executable* (or the project root in dev) so a clinician can drop in
  patient-specific cues and so the SQLite database persists between runs without
  rebuilding the ``.exe``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent


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


def app_base_dir() -> Path:
    """Directory that holds the external ``media/`` and ``data/`` folders.

    Frozen: the folder containing the executable. Dev: the project root (parent
    of the ``cravingcrave`` package).
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return _PACKAGE_DIR.parent


def media_root() -> Path:
    return app_base_dir() / "media"


def data_dir() -> Path:
    return app_base_dir() / "data"


def db_path() -> Path:
    return data_dir() / "cravingcrave.db"
