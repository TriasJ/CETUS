"""Stars VAS display: 0..max as a row of clickable five-pointed star shapes.

Stars up to the current value are filled amber/gold; higher stars are outlined.
All stars are the same size for a familiar rating-row UX.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...services.i18n import tr
from .vas_input import AbstractVasInput

# Star fill: amber/gold — universally recognised as "active star" in rating UIs.
_STAR_FILL = "#f0a500"
_STAR_OUTLINE = "#c0c0c0"


class StarsVasInput(AbstractVasInput):
    """Row of five-pointed stars. Tap/click to rate 0..max."""

    def __init__(self, vas_max: int = 10, parent: QWidget | None = None) -> None:
        super().__init__(vas_max, parent)
        self._value = 0

        self._canvas = _StarCanvas(vas_max, self)
        self._canvas.clicked.connect(self._on_click)

        ends = QHBoxLayout()
        low = QLabel(tr("vas.none")); low.setObjectName("Muted")
        high = QLabel(tr("vas.extreme")); high.setObjectName("Muted")
        high.setAlignment(Qt.AlignmentFlag.AlignRight)
        ends.addWidget(low); ends.addStretch(1); ends.addWidget(high)

        layout = QVBoxLayout(self)
        layout.addWidget(self.value_label)
        layout.addWidget(self._canvas)
        layout.addLayout(ends)

    def value(self) -> int:
        return self._value

    def set_value(self, v: int) -> None:
        v = self._clamp(v)
        if v != self._value:
            self._value = v
            self.value_label.setText(str(v))
            self._canvas.set_value(v)
            self.valueChanged.emit(v)

    def reset(self) -> None:
        self._value = 0
        self.value_label.setText("0")
        self._canvas.set_value(0)

    def _on_click(self, v: int) -> None:
        self.set_value(v)


def _star_polygon(
    cx: float, cy: float, outer_r: float, inner_r: float, points: int = 5,
) -> QPolygonF:
    """Generate a five-pointed star polygon centred at (*cx*, *cy*)."""
    poly = QPolygonF()
    for i in range(points * 2):
        r = outer_r if i % 2 == 0 else inner_r
        angle = math.pi / 2 + i * math.pi / points  # start from the top
        poly.append(QPointF(cx + r * math.cos(angle), cy - r * math.sin(angle)))
    return poly


class _StarCanvas(QWidget):
    """Custom-painted row of star shapes."""

    clicked = Signal(int)

    def __init__(self, vas_max: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vas_max = vas_max
        self._value = 0
        n = vas_max + 1
        min_star = 24
        self.setMinimumSize(n * min_star + (n - 1) * 3 + 8, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_value(self, v: int) -> None:
        self._value = v
        self.update()

    def _star_centers(self) -> list[tuple[float, float, float, int]]:
        """Return (cx, cy, radius, index) for each star."""
        w = self.width()
        h = self.height()
        n = self.vas_max + 1
        gap = 3
        star_size = min(40, max(20, (w - 8) / n - gap))
        r = star_size / 2
        total = n * star_size + (n - 1) * gap
        x0 = (w - total) / 2 + r
        cy = h / 2
        centers: list[tuple[float, float, float, int]] = []
        for i in range(n):
            cx = x0 + i * (star_size + gap)
            centers.append((cx, cy, r, i))
        return centers

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        fill_color = QColor(_STAR_FILL)
        outline_color = QColor(_STAR_OUTLINE)

        for cx, cy, r, i in self._star_centers():
            poly = _star_polygon(cx, cy, r, r * 0.4)
            if i <= self._value:
                painter.setBrush(fill_color)
                painter.setPen(QPen(fill_color.darker(120), 1.5))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(outline_color, 1.5))
            painter.drawPolygon(poly)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        for cx, cy, r, i in self._star_centers():
            touch = QRectF(cx - r - 6, cy - r - 6, (r + 6) * 2, (r + 6) * 2)
            if touch.contains(pos):
                self.clicked.emit(i)
                return
