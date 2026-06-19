"""Craving charts built on QtCharts.

Two uses: a *live* line that grows during the session, and a static plot for the
summary / cross-session progress views. Wrapped here so the charting backend stays
swappable.
"""

from __future__ import annotations

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from ...services.i18n import tr
from ..theme import PRIMARY


class CravingChart(QChartView):
    def __init__(self, vas_max: int = 10, parent: QWidget | None = None) -> None:
        self._chart = QChart()
        super().__init__(self._chart, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.vas_max = vas_max

        self._series = QLineSeries()
        self._series.setName(tr("chart.craving"))
        pen = self._series.pen()
        pen.setColor(Qt.GlobalColor.darkCyan)
        pen.setWidth(3)
        self._series.setPen(pen)
        self._chart.addSeries(self._series)

        self._axis_x = QValueAxis()
        self._axis_x.setTitleText(tr("chart.time"))
        self._axis_x.setLabelFormat("%d")
        self._axis_x.setRange(0, 60)
        self._axis_y = QValueAxis()
        self._axis_y.setTitleText(tr("chart.craving"))
        self._axis_y.setRange(0, vas_max)
        self._axis_y.setTickCount(vas_max + 1)
        self._axis_y.setLabelFormat("%d")

        self._chart.addAxis(self._axis_x, Qt.AlignmentFlag.AlignBottom)
        self._chart.addAxis(self._axis_y, Qt.AlignmentFlag.AlignLeft)
        self._series.attachAxis(self._axis_x)
        self._series.attachAxis(self._axis_y)
        self._chart.legend().hide()

    def clear(self) -> None:
        self._series.clear()
        self._axis_x.setRange(0, 60)

    def add_point(self, elapsed_sec: int, value: int) -> None:
        self._series.append(elapsed_sec, value)
        if elapsed_sec > self._axis_x.max():
            self._axis_x.setRange(0, elapsed_sec + 30)

    def set_points(self, points: list[tuple[float, float]]) -> None:
        self._series.clear()
        max_x = 60.0
        for x, y in points:
            self._series.append(x, y)
            max_x = max(max_x, x)
        self._axis_x.setRange(0, max_x + 10)
