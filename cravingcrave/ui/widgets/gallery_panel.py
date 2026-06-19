"""Positive counter-stimuli gallery overlay (puppies/nature/reasons for recovery).

Counterconditioning: on demand the patient replaces the cue with something that
does them good. Images come from ``media/positive`` plus any cues the clinician
flagged as the patient's personal "reasons for recovery".
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ...services.i18n import tr
from .overlay import Overlay


class GalleryPanel(Overlay):
    closed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._paths: list[str] = []
        self._index = 0

        card = QWidget(self)
        card.setObjectName("OverlayCard")
        card.setMinimumSize(640, 520)

        title = QLabel(tr("gallery.title"))
        title.setObjectName("H2")
        intro = QLabel(tr("gallery.intro"))
        intro.setWordWrap(True)
        intro.setObjectName("Muted")

        self._image = QLabel("")
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setMinimumSize(580, 360)
        self._image.setStyleSheet("background:#0e1418; border-radius:10px; color:#eef2f5;")

        prev = QPushButton(tr("gallery.prev"))
        prev.clicked.connect(self._prev)
        nxt = QPushButton(tr("gallery.next"))
        nxt.clicked.connect(self._next)
        back = QPushButton(tr("gallery.back_to_cue"))
        back.setObjectName("Primary")
        back.clicked.connect(self._close)

        nav = QHBoxLayout()
        nav.addWidget(prev)
        nav.addWidget(nxt)
        nav.addStretch(1)
        nav.addWidget(back)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(28, 24, 28, 24)
        inner.setSpacing(12)
        inner.addWidget(title)
        inner.addWidget(intro)
        inner.addWidget(self._image, 1)
        inner.addLayout(nav)

        outer = QVBoxLayout(self)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1); row.addWidget(card); row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def open_with(self, image_paths: list[str]) -> None:
        self._paths = image_paths
        self._index = 0
        self._render()
        self.show_overlay()

    def _render(self) -> None:
        if not self._paths:
            self._image.setText(tr("gallery.empty"))
            self._image.setPixmap(QPixmap())
            return
        path = self._paths[self._index % len(self._paths)]
        pix = QPixmap(path)
        if pix.isNull():
            self._image.setText(tr("gallery.empty"))
            return
        self._image.setPixmap(
            pix.scaled(self._image.size(), Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        )

    def _prev(self) -> None:
        if self._paths:
            self._index = (self._index - 1) % len(self._paths)
            self._render()

    def _next(self) -> None:
        if self._paths:
            self._index = (self._index + 1) % len(self._paths)
            self._render()

    def _close(self) -> None:
        self.hide_overlay()
        self.closed.emit()
