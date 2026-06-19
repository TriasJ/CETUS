"""Guided Urge-Specific Coping Skills overlay (the 4 evidence-based steps)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from ...domain.uscs import USCS_STEPS
from ...services.i18n import tr
from .overlay import Overlay


class UscsPanel(Overlay):
    # skill, detail
    copingRecorded = Signal(str, str)
    finished = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._index = 0

        card = QWidget(self)
        card.setObjectName("OverlayCard")
        card.setMinimumWidth(560)

        self._step_label = QLabel("")
        self._step_label.setObjectName("Muted")
        self._title = QLabel("")
        self._title.setObjectName("H2")
        self._title.setWordWrap(True)
        self._prompt = QLabel("")
        self._prompt.setWordWrap(True)
        self._input = QPlainTextEdit()
        self._input.setPlaceholderText(tr("uscs.detail_placeholder"))
        self._input.setFixedHeight(110)

        self._next_btn = QPushButton(tr("common.next"))
        self._next_btn.setObjectName("Primary")
        self._next_btn.clicked.connect(self._advance)
        close_btn = QPushButton(tr("gallery.back_to_cue"))
        close_btn.clicked.connect(self._cancel)

        buttons = QHBoxLayout()
        buttons.addWidget(close_btn)
        buttons.addStretch(1)
        buttons.addWidget(self._next_btn)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(34, 28, 34, 28)
        inner.setSpacing(14)
        inner.addWidget(self._step_label)
        inner.addWidget(self._title)
        inner.addWidget(self._prompt)
        inner.addWidget(self._input)
        inner.addLayout(buttons)

        outer = QVBoxLayout(self)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1); row.addWidget(card); row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def start(self) -> None:
        self._index = 0
        self._render()
        self.show_overlay()

    def _render(self) -> None:
        step = USCS_STEPS[self._index]
        self._step_label.setText(f"{self._index + 1} / {len(USCS_STEPS)}")
        self._title.setText(tr(step.title_key))
        self._prompt.setText(tr(step.prompt_key))
        self._input.clear()
        last = self._index == len(USCS_STEPS) - 1
        self._next_btn.setText(tr("uscs.done") if last else tr("common.next"))

    def _advance(self) -> None:
        step = USCS_STEPS[self._index]
        self.copingRecorded.emit(step.skill.value, self._input.toPlainText().strip())
        if self._index < len(USCS_STEPS) - 1:
            self._index += 1
            self._render()
        else:
            self.hide_overlay()
            self.finished.emit()

    def _cancel(self) -> None:
        self.hide_overlay()
        self.finished.emit()
