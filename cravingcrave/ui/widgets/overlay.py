"""Full-parent overlay base.

Overlays (VAS prompt, coping steps, positive gallery) are *children of the screen*
rather than modal dialogs, so the MainWindow panic button — a raised sibling of the
screen — always stays clickable on top of them.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QFrame, QWidget


class Overlay(QFrame):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Overlay")
        self._parent = parent
        parent.installEventFilter(self)
        self.hide()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        parent = getattr(self, "_parent", None)
        if parent is not None and obj is parent and event.type() == QEvent.Type.Resize:
            self.setGeometry(parent.rect())
        return super().eventFilter(obj, event)

    def show_overlay(self) -> None:
        self.setGeometry(self._parent.rect())
        self.show()
        self.raise_()

    def hide_overlay(self) -> None:
        self.hide()
