"""Calm screen — the panic destination. Soothing, with safety contacts always visible."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...services.i18n import tr
from ..context import AppContext

_BREATH_CYCLE = [
    ("calm.breathe_in", 4000),
    ("calm.breathe_hold", 4000),
    ("calm.breathe_out", 6000),
]


class CalmScreen(QWidget):
    def __init__(self, window, context: AppContext) -> None:
        super().__init__()
        self.window = window
        self.context = context
        self.setStyleSheet("background:#0f3a44;")

        info = context.crisis.get()

        title = QLabel(tr("calm.title"))
        title.setStyleSheet("color:#ffffff; font-size:30px; font-weight:700;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body = QLabel(tr("calm.body"))
        body.setStyleSheet("color:#d7eef0; font-size:17px;")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.breath = QLabel(tr("calm.breathe_in"))
        self.breath.setStyleSheet("color:#9be7d8; font-size:40px; font-weight:800;")
        self.breath.setAlignment(Qt.AlignmentFlag.AlignCenter)

        contacts = QFrame()
        contacts.setStyleSheet("background:#ffffff; border-radius:16px;")
        c = QVBoxLayout(contacts)
        c.setContentsMargins(28, 22, 28, 22)
        for label_key, value in (
            ("calm.therapist", info.therapist_phone),
            ("calm.crisis", info.crisis_line),
            ("calm.emergency", info.emergency_number),
        ):
            row = QLabel(f"<b>{tr(label_key)}:</b>&nbsp;&nbsp;{value}")
            row.setTextFormat(Qt.TextFormat.RichText)
            row.setStyleSheet("font-size:18px; color:#14303a; background:transparent;")
            c.addWidget(row)

        ret = QPushButton(tr("calm.return"))
        ret.setObjectName("Primary")
        ret.clicked.connect(window.show_dashboard)

        layout = QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addSpacing(10)
        layout.addWidget(self.breath)
        layout.addSpacing(10)
        row = QHBoxLayout(); row.addStretch(1); row.addWidget(contacts); row.addStretch(1)
        layout.addLayout(row)
        layout.addSpacing(16)
        row2 = QHBoxLayout(); row2.addStretch(1); row2.addWidget(ret); row2.addStretch(1)
        layout.addLayout(row2)
        layout.addStretch(1)

        self._step = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._tick()

    def _tick(self) -> None:
        key, duration = _BREATH_CYCLE[self._step % len(_BREATH_CYCLE)]
        self.breath.setText(tr(key))
        self._step += 1
        self._timer.start(duration)
