"""Render an emoji glyph as a QIcon for use on QPushButtons.

The emoji is drawn 1–2 pt larger than the surrounding button text so it reads
as a distinct pictograph rather than inline text.  No icon file is needed;
Segoe UI Emoji (Windows) or Apple Color Emoji (macOS) supplies the glyphs.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap

# Default icon size — 20 px gives a comfortable ~2 pt uplift over the 15 px
# base widget font.
_DEFAULT_SIZE = 20
_FONT_FAMILY = "Segoe UI Emoji" if sys.platform == "win32" else "Apple Color Emoji"


def emoji_icon(emoji: str, size: int = _DEFAULT_SIZE) -> QIcon:
    """Return a *QIcon* that paints *emoji* centred on a transparent square."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setFont(QFont(_FONT_FAMILY, int(size * 0.68)))
    p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, emoji)
    p.end()
    return QIcon(pm)
