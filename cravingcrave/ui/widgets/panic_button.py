"""The always-on STOP button.

Lives as a raised child of the MainWindow (not of any screen) so no screen state or
overlay can hide or cover it. Esc also triggers it via a shortcut wired in MainWindow.
"""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QWidget

from ...services.i18n import tr


class PanicButton(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(tr("exposure.panic"), parent)
        self.setObjectName("Panic")
        self.setCursor(self.cursor())
        self.setFixedHeight(56)
        self.setMinimumWidth(120)
        self.hide()
