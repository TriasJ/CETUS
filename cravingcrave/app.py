"""Application bootstrap."""

from __future__ import annotations

import logging
import sys

_log = logging.getLogger(__name__)


def _ensure_media_backend() -> None:
    """Make the QtMultimedia ffmpeg backend loadable on Windows.

    Windows *Store* Python (and some locked-down setups) don't add the PySide6
    directory to the DLL search path, so the multimedia plugin can't find its
    ``av*.dll`` dependencies and audio/video silently fail with "No QtMultimedia
    backends found". Adding the directory and pre-loading the DLLs (in dependency
    order) fixes it. Must run before the first QMediaPlayer is created. No-op when
    frozen (PyInstaller co-locates everything) or on non-Windows.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import os

        import PySide6

        pyside_dir = os.path.dirname(PySide6.__file__)
        if hasattr(os, "add_dll_directory") and os.path.isdir(pyside_dir):
            os.add_dll_directory(pyside_dir)
        # NOTE: discovered via QtMultimedia "No backends found" on Store Python.
        # Pre-load in dependency order so the plugin's deps are already resolved.
        for prefix in ("avutil", "swresample", "swscale", "avcodec", "avformat"):
            for dll in sorted(p for p in os.listdir(pyside_dir)
                              if p.lower().startswith(prefix) and p.lower().endswith(".dll")):
                try:
                    ctypes.WinDLL(os.path.join(pyside_dir, dll))
                except OSError:
                    pass
    except Exception:  # best-effort; the app still runs (media just may not play)
        _log.exception("Media backend preload failed; audio/video may not play.")


_ensure_media_backend()

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from . import paths  # noqa: E402
from .config import AppConfig  # noqa: E402
from .logging_setup import configure_logging  # noqa: E402
from .services import i18n  # noqa: E402
from .ui.context import AppContext  # noqa: E402
from .ui.main_window import MainWindow  # noqa: E402
from .ui.theme import apply_theme  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CETUS")
    _icon = paths.resource_path("icons", "cetus.png")
    if _icon.is_file():
        app.setWindowIcon(QIcon(str(_icon)))

    config = AppConfig()
    configure_logging(config.data_dir)
    apply_theme(app)   # base light theme immediately; re-applied with the saved theme below

    # Build the context first: AppContext.create() reads the clinic's saved UI language and
    # theme from the DB into config, so applying them afterwards lets the persisted choices
    # win over the bootstrap defaults.
    context = AppContext.create(config)
    _log.info("Starting CETUS (locale=%s, theme=%s).", config.locale, config.theme)
    apply_theme(app, config.theme)
    i18n.set_locale(config.locale)
    window = MainWindow(context)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
