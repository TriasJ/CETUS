"""Circles VAS display: 0..max as progressively larger clickable circles.

Each circle grows with the rating value it represents, giving a visceral sense
of escalating craving intensity. Filled circles mark the current rating and
below; outlined circles mark above.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...services.i18n import tr
from ..theme import PRIMARY
from .vas_input import AbstractVasInput


class CirclesVasInput(AbstractVasInput):
    """Eleven circles of increasing size. Tap/click one to rate 0..max."""

    def __init__(self, vas_max: int = 10, parent: QWidget | None = None) -> None:
        super().__init__(vas_max, parent)
        self._value = 0

        self._canvas = _CircleCanvas(vas_max, self)
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


class _CircleCanvas(QWidget):
    """Custom-painted row of circles with increasing diameters."""

    clicked = Signal(int)

    def __init__(self, vas_max: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vas_max = vas_max
        self._value = 0
        self.setMinimumHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_value(self, v: int) -> None:
        self._value = v
        self.update()

    def _circle_rects(self) -> list[tuple[QRectF, int]]:
        """Compute (bounding_rect, index) for each circle."""
        w = self.width()
        h = self.height()
        n = self.vas_max + 1
        min_d = 20
        max_d = min(h - 4, 64)

        diameters: list[float] = []
        for i in range(n):
            frac = i / max(1, self.vas_max)
            d = min_d + (max_d - min_d) * frac
            diameters.append(d)

        total_w = sum(diameters)
        spacing = max(4, (w - total_w) / max(1, n + 1))
        total_w += spacing * (n - 1)
        x = (w - total_w) / 2

        rects: list[tuple[QRectF, int]] = []
        for i, d in enumerate(diameters):
            y = (h - d) / 2
            rects.append((QRectF(x, y, d, d), i))
            x += d + spacing

        return rects

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        fill_color = QColor(PRIMARY)
        outline_color = QColor(PRIMARY)
        outline_color.setAlpha(120)

        for rect, i in self._circle_rects():
            if i <= self._value:
                painter.setBrush(fill_color)
                painter.setPen(QPen(fill_color.darker(110), 2))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(outline_color, 2))
            painter.drawEllipse(rect)

            # Number label inside each circle.
            painter.setPen(QColor("white") if i <= self._value else outline_color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(i))

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        for rect, i in self._circle_rects():
            # Expand touch target to at least 44×44.
            touch = rect.adjusted(-12, -12, 12, 12)
            if touch.contains(pos):
                self.clicked.emit(i)
                return
