"""Craving VAS slider (0..max) and the prompt overlay that collects a rating."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ...services.i18n import tr
from .overlay import Overlay
from .vas_input import AbstractVasInput, create_vas_input


class SliderVasInput(AbstractVasInput):
    """A large, touch-friendly 0..max slider with a prominent value readout."""

    def __init__(self, vas_max: int = 10, parent: QWidget | None = None) -> None:
        super().__init__(vas_max, parent)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, vas_max)
        self.slider.setPageStep(1)
        self.slider.setMinimumHeight(64)
        self.slider.valueChanged.connect(self._on_change)

        ends = QHBoxLayout()
        low = QLabel(tr("vas.none")); low.setObjectName("Muted")
        high = QLabel(tr("vas.extreme")); high.setObjectName("Muted")
        high.setAlignment(Qt.AlignmentFlag.AlignRight)
        ends.addWidget(low)
        ends.addStretch(1)
        ends.addWidget(high)

        layout = QVBoxLayout(self)
        layout.addWidget(self.value_label)
        layout.addWidget(self.slider)
        layout.addLayout(ends)

    def _on_change(self, value: int) -> None:
        self.value_label.setText(str(value))
        self.valueChanged.emit(value)

    def value(self) -> int:
        return self.slider.value()

    def set_value(self, v: int) -> None:
        """Set the rating, clamped to 0..max (used by keyboard-only entry)."""
        self.slider.setValue(self._clamp(v))

    def nudge(self, delta: int) -> None:
        self.set_value(self.slider.value() + delta)

    def reset(self) -> None:
        self.slider.setValue(0)
        self.value_label.setText("0")


# Backward-compatible alias — existing callers import VasSlider.
VasSlider = SliderVasInput


class VasPrompt(Overlay):
    """Overlay asking the patient to rate craving. Emits the submitted value."""

    submitted = Signal(int)

    def __init__(self, parent: QWidget, vas_max: int = 10,
                 mode: str = "slider") -> None:
        super().__init__(parent)

        card = QWidget(self)
        card.setObjectName("OverlayCard")
        min_w = 460 if mode in ("stars", "circles") else 380
        card.setMinimumWidth(min_w)

        self.title = QLabel("")
        self.title.setObjectName("H2")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        question = QLabel(tr("vas.question"))
        question.setWordWrap(True)
        question.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.slider = create_vas_input(mode, vas_max)
        submit = QPushButton(tr("vas.submit"))
        submit.setObjectName("Primary")
        submit.clicked.connect(self._submit)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(20, 18, 20, 18)
        inner.setSpacing(18)
        inner.addWidget(self.title)
        inner.addWidget(question)
        inner.addWidget(self.slider)
        inner.addWidget(submit)

        outer = QVBoxLayout(self)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def ask(self, title: str) -> None:
        self.title.setText(title)
        self.slider.reset()
        self.show_overlay()

    def set_value(self, v: int) -> None:
        """Keyboard-only entry: set the rating directly (digit keys / max)."""
        self.slider.set_value(v)

    def nudge(self, delta: int) -> None:
        self.slider.nudge(delta)

    def submit(self) -> None:
        """Public submit (keyboard Enter) — same path as the button."""
        self._submit()

    def _submit(self) -> None:
        value = self.slider.value()
        self.hide_overlay()
        self.submitted.emit(value)
