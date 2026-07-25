"""Generate the CETUS app icon (placeholder) in PNG / ICO / ICNS from one drawing.

Run with the project venv:  python scripts/make_icons.py
Replace with real brand art any time — keep the same filenames so the spec/installers
pick it up. Requires a Qt platform; on CI use QT_QPA_PLATFORM=offscreen.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

OUT = Path(__file__).resolve().parent.parent / "cravingcrave" / "resources" / "icons"
PRIMARY = QColor("#2a9d8f")
PRIMARY_DARK = QColor("#21867a")


def _render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Rounded-square background.
    margin = size * 0.06
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(PRIMARY))
    p.drawRoundedRect(rect, size * 0.22, size * 0.22)
    # A stylized "C" for CETUS.
    p.setBrush(Qt.BrushStyle.NoBrush)
    pen = QPen(QColor("#ffffff"))
    pen.setWidthF(size * 0.11)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    arc = QRectF(size * 0.30, size * 0.26, size * 0.42, size * 0.48)
    p.drawArc(arc, 55 * 16, 250 * 16)
    # Small dot (cue) accent.
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(PRIMARY_DARK.lighter(160)))
    r = size * 0.055
    p.drawEllipse(QRectF(size * 0.63, size * 0.60, r * 2, r * 2))
    p.end()
    return img


def main() -> int:
    QApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    master = _render(256)
    (OUT / "cetus.png").write_bytes(b"")  # ensure file exists/truncate
    assert master.save(str(OUT / "cetus.png"), "PNG")
    # ICO (Windows) and ICNS (macOS) — Qt writes both.
    assert master.save(str(OUT / "cetus.ico"), "ICO")
    assert master.save(str(OUT / "cetus.icns"), "ICNS")
    print(f"Wrote cetus.png / cetus.ico / cetus.icns to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
