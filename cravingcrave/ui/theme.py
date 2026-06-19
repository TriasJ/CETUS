"""Theme application and shared colour constants."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .. import paths

# Palette (kept in sync with app.qss for code that draws directly, e.g. charts).
PRIMARY = "#2a9d8f"
PRIMARY_DARK = "#21867a"
DANGER = "#e63946"
TEXT = "#1f2933"
MUTED = "#5f6b7a"
SURFACE = "#ffffff"
BG = "#f4f6f8"


def apply_theme(app: QApplication) -> None:
    app.setFont(QFont("Segoe UI", 10))
    qss_path = paths.resource_path("styles", "app.qss")
    try:
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
    except OSError:
        pass  # styling is non-essential; app still runs unstyled
