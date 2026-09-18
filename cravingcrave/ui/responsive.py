"""Responsive layout helpers — adapt margins, fonts, and sizes to the current screen.

Every screen should call :func:`adaptive_margins` for its outer ``setContentsMargins``
and :func:`adaptive_nav_width` for master-detail navigation panels.  This ensures the
UI stays usable from 800×600 netbooks up to 4K displays, regardless of OS.

Usage::

    from ..responsive import adaptive_margins, screen_category

    layout.setContentsMargins(*adaptive_margins())

    if screen_category() == "compact":
        card.setMaximumWidth(480)
    else:
        card.setMaximumWidth(620)
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication


def screen_size() -> tuple[int, int]:
    """Return the primary screen's available size (width, height) in pixels."""
    app = QApplication.instance()
    if app is None:
        return (1920, 1080)
    screen = app.primaryScreen()
    if screen is None:
        return (1920, 1080)
    geo = screen.availableGeometry()
    return (geo.width(), geo.height())


def screen_category() -> str:
    """Classify the screen into a size bucket.

    * ``"compact"`` — width < 1100 (800×600, 1024×768, netbooks)
    * ``"normal"``  — 1100 ≤ width < 1600 (1366×768, 1440×900, most laptops)
    * ``"wide"``    — width ≥ 1600 (1080p, 1440p, 4K)
    """
    w, _ = screen_size()
    if w < 1100:
        return "compact"
    if w < 1600:
        return "normal"
    return "wide"


def adaptive_margins() -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) content margins scaled to screen size.

    At 800×600 this gives 12px side margins; at 1920×1080 it gives 36px.
    """
    cat = screen_category()
    if cat == "compact":
        return (12, 10, 12, 10)
    if cat == "normal":
        return (24, 18, 24, 18)
    return (36, 24, 36, 24)


def adaptive_card_margins() -> tuple[int, int, int, int]:
    """Margins inside a card/groupbox, scaled to screen."""
    cat = screen_category()
    if cat == "compact":
        return (14, 12, 14, 12)
    if cat == "normal":
        return (22, 18, 22, 18)
    return (28, 24, 28, 24)


def adaptive_nav_width() -> int:
    """Width for a master-detail navigation list (settings, admin center)."""
    cat = screen_category()
    if cat == "compact":
        return 140
    if cat == "normal":
        return 170
    return 200


def adaptive_card_max_width() -> int:
    """Max width for centered cards (login, session setup)."""
    cat = screen_category()
    if cat == "compact":
        return 440
    if cat == "normal":
        return 540
    return 620


def adaptive_right_panel_width() -> int:
    """Max width for the exposure screen's right panel (chart + controls)."""
    cat = screen_category()
    if cat == "compact":
        return 260
    if cat == "normal":
        return 320
    return 380


def adaptive_dialog_width() -> int:
    """Minimum width for dialogs (params, help, wizard)."""
    cat = screen_category()
    if cat == "compact":
        return 400
    if cat == "normal":
        return 480
    return 540


def adaptive_font_scale() -> float:
    """Scale factor for font sizes at low resolution (1.0 = default)."""
    cat = screen_category()
    if cat == "compact":
        return 0.85
    return 1.0


def adaptive_min_window() -> tuple[int, int]:
    """Minimum window size based on screen resolution."""
    w, h = screen_size()
    # Never require more than 80% of the available screen
    min_w = min(960, int(w * 0.9))
    min_h = min(640, int(h * 0.9))
    # Absolute floor
    return (max(640, min_w), max(480, min_h))
