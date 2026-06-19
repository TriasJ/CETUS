"""Patient-controlled intensity panel: shrink, blur, dim, mute.

Gives the patient agency to down-regulate the cue. Each change emits ``changed``
with the full state plus the action label, so the exposure screen can log an
``intensity_event`` (down-regulation is a clinically meaningful behaviour).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout, QFrame, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from ...domain.models import IntensityAction
from ...services.i18n import tr


class IntensityControls(QFrame):
    # scale_pct, blur_pct, dim_pct, muted, action
    changed = Signal(int, int, int, bool, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")

        title = QLabel(tr("intensity.title"))
        title.setObjectName("H2")

        self._size = self._make_slider(10, 100, 100)
        self._blur = self._make_slider(0, 100, 0)
        self._dim = self._make_slider(0, 100, 0)
        self._muted = False

        self._mute_btn = QPushButton(tr("intensity.mute"))
        self._mute_btn.setCheckable(True)
        self._mute_btn.toggled.connect(self._on_mute)

        form = QFormLayout()
        form.setSpacing(12)
        form.addRow(tr("intensity.size"), self._size)
        form.addRow(tr("intensity.blur"), self._blur)
        form.addRow(tr("intensity.dim"), self._dim)
        form.addRow("", self._mute_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(form)

        self._size.valueChanged.connect(lambda _: self._emit(IntensityAction.SHRINK.value))
        self._blur.valueChanged.connect(lambda _: self._emit(IntensityAction.BLUR.value))
        self._dim.valueChanged.connect(lambda _: self._emit(IntensityAction.DIM.value))

    def _make_slider(self, lo: int, hi: int, val: int) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        return s

    def _on_mute(self, checked: bool) -> None:
        self._muted = checked
        self._mute_btn.setText(tr("intensity.unmute") if checked else tr("intensity.mute"))
        self._emit(IntensityAction.MUTE.value)

    def _emit(self, action: str) -> None:
        self.changed.emit(self._size.value(), self._blur.value(), self._dim.value(),
                          self._muted, action)

    def state(self) -> tuple[int, int, int, bool]:
        return self._size.value(), self._blur.value(), self._dim.value(), self._muted

    def reset(self) -> None:
        for s in (self._size, self._blur, self._dim):
            s.blockSignals(True)
        self._size.setValue(100)
        self._blur.setValue(0)
        self._dim.setValue(0)
        for s in (self._size, self._blur, self._dim):
            s.blockSignals(False)
        self._mute_btn.setChecked(False)
        self._muted = False

    # --- public API for keyboard shortcuts ----------------------------------
    @staticmethod
    def _step(slider: QSlider, delta: int) -> None:
        slider.setValue(max(slider.minimum(), min(slider.maximum(), slider.value() + delta)))

    def step_size(self, delta: int) -> None: self._step(self._size, delta)
    def step_blur(self, delta: int) -> None: self._step(self._blur, delta)
    def step_dim(self,  delta: int) -> None: self._step(self._dim,  delta)
    def toggle_mute(self) -> None: self._mute_btn.setChecked(not self._muted)
