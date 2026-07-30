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


# Selectable themes. "light" (default) is the base app.qss on its own; the others append a
# small override on top of the base so they only restyle colours/sizes, not every rule.
THEME_OVERRIDES = {
    "light": None,
    "dark": "app_dark.qss",
    "high_contrast": "app_high_contrast.qss",
    "impaired": "app_impaired.qss",
    "classic": "app_classic.qss",
}


def available_themes() -> list[str]:
    return list(THEME_OVERRIDES.keys())


def _read_qss(name: str) -> str:
    try:
        return paths.resource_path("styles", name).read_text(encoding="utf-8")
    except OSError:
        return ""


def apply_theme(app: QApplication, theme: str = "light") -> None:
    app.setFont(QFont("Segoe UI", 10))
    qss = _read_qss("app.qss")
    override = THEME_OVERRIDES.get(theme)
    if override:
        qss = f"{qss}\n\n/* ---- theme: {theme} ---- */\n{_read_qss(override)}"
    app.setStyleSheet(qss)  # styling is non-essential; empty string just runs unstyled
