"""Dev-only: build a labeled contact sheet of a media category, for grading.

Usage: python scripts/montage.py <category>
Prints an index->filename legend and writes docs/screenshots/montage_<category>.png
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

COLS = 5
THUMB = 360
PAD = 14
LABEL_H = 34


def main() -> None:
    category = sys.argv[1] if len(sys.argv) > 1 else "alcohol"
    app = QApplication(sys.argv)  # noqa: F841

    folder = ROOT / "media" / category
    files = sorted(p for p in folder.iterdir()
                   if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    if not files:
        print(f"No images in {folder}")
        return

    rows = (len(files) + COLS - 1) // COLS
    cell_w = THUMB + PAD
    cell_h = THUMB + LABEL_H + PAD
    sheet = QImage(COLS * cell_w + PAD, rows * cell_h + PAD, QImage.Format.Format_RGB32)
    sheet.fill(QColor("#222a30"))
    p = QPainter(sheet)
    p.setFont(QFont("Arial", 12, QFont.Weight.Bold))

    for i, path in enumerate(files):
        r, c = divmod(i, COLS)
        x = PAD + c * cell_w
        y = PAD + r * cell_h
        pix = QPixmap(str(path)).scaled(THUMB, THUMB, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap(x + (THUMB - pix.width()) // 2, y + (THUMB - pix.height()) // 2, pix)
        p.setPen(QColor("#ffffff"))
        p.drawText(x, y + THUMB + 4, THUMB, LABEL_H, Qt.AlignmentFlag.AlignCenter, f"#{i + 1}  {path.name}")
        print(f"#{i + 1}\t{path.name}")

    p.end()
    out = ROOT / "docs" / "screenshots" / f"montage_{category}.png"
    sheet.save(str(out))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
