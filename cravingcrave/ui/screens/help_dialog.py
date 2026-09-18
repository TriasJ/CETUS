"""CHM-like help viewer: a table of contents (left) + an HTML topic browser (right)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ...services.help import load_help
from ...services.i18n import current_locale, tr
from ..responsive import adaptive_nav_width, screen_size


class HelpDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, locale: str | None = None) -> None:
        super().__init__(parent)
        data = load_help(locale or current_locale())
        self._sections = data.get("sections", [])
        self.setWindowTitle(data.get("title", tr("dashboard.help")))
        sw, sh = screen_size()
        self.resize(min(940, sw - 40), min(660, sh - 40))

        self.toc = QListWidget()
        self.toc.setMaximumWidth(min(290, adaptive_nav_width() + 80))
        for s in self._sections:
            self.toc.addItem(QListWidgetItem(s.get("title", "")))
        self.toc.currentRowChanged.connect(self._show)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)

        close = QPushButton(tr("common.close"))
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)

        right = QVBoxLayout()
        right.addWidget(self.browser, 1)
        right.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)

        layout = QHBoxLayout(self)
        layout.addWidget(self.toc)
        layout.addLayout(right, 1)

        if self._sections:
            self.toc.setCurrentRow(0)

    def _show(self, row: int) -> None:
        if 0 <= row < len(self._sections):
            self.browser.setHtml(self._sections[row].get("html", ""))

    def show_topic(self, section_id: str) -> None:
        """Jump to a section by id (e.g. opened contextually)."""
        for i, s in enumerate(self._sections):
            if s.get("id") == section_id:
                self.toc.setCurrentRow(i)
                return
