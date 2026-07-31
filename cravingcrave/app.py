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

from PySide6.QtCore import QRect, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QSplashScreen  # noqa: E402

from . import paths  # noqa: E402
from .config import AppConfig  # noqa: E402
from .logging_setup import configure_logging  # noqa: E402
from .services import i18n  # noqa: E402
from .ui.context import AppContext  # noqa: E402
from .ui.main_window import MainWindow  # noqa: E402
from .ui.theme import apply_theme  # noqa: E402


def _build_splash() -> QSplashScreen | None:
    """A small branded launch screen (logo on the CETUS navy) shown while the DB loads."""
    width, height = 520, 340
    pm = QPixmap(width, height)
    pm.fill(QColor("#0d1b2a"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    logo_path = paths.resource_path("icons", "cetus.png")
    if logo_path.is_file():
        logo = QPixmap(str(logo_path)).scaled(
            160, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((width - logo.width()) // 2, 46, logo)
    p.setPen(QColor("#e6edf3"))
    p.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
    p.drawText(QRect(0, 222, width, 46), Qt.AlignmentFlag.AlignHCenter, "CETUS")
    p.setPen(QColor("#9fb0bd"))
    p.setFont(QFont("Segoe UI", 11))
    p.drawText(QRect(0, 272, width, 28), Qt.AlignmentFlag.AlignHCenter,
               "Cue Exposure Therapy · CET-USCS")
    p.end()
    return QSplashScreen(pm)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CETUS")
    _icon = paths.resource_path("icons", "cetus.png")
    if _icon.is_file():
        app.setWindowIcon(QIcon(str(_icon)))

    config = AppConfig()
    configure_logging(config.data_dir)
    apply_theme(app)   # base light theme immediately; re-applied with the saved theme below

    splash = _build_splash()
    if splash is not None:
        splash.show()
        app.processEvents()

    # Build the context first: AppContext.create() reads the clinic's saved UI language and
    # theme from the DB into config, so applying them afterwards lets the persisted choices
    # win over the bootstrap defaults.
    context = AppContext.create(config)
    _log.info("Starting CETUS (locale=%s, theme=%s).", config.locale, config.theme)
    apply_theme(app, config.theme)
    i18n.set_locale(config.locale)
    window = MainWindow(context)
    window.show()
    if splash is not None:
        # Keep the splash up briefly for a smooth launch even when the DB loads instantly.
        QTimer.singleShot(800, lambda: splash.finish(window))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
