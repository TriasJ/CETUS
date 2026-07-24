"""Clinician login, with first-run account creation when no clinician exists yet."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...services.i18n import tr
from ..context import AppContext
from .admin_dialog import AdminDialog


class LoginScreen(QWidget):
    def __init__(self, window, context: AppContext) -> None:
        super().__init__()
        self.window = window
        self.context = context
        self._first_run = not context.auth.has_any_clinician()

        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(460)

        title = QLabel(tr("app.title"))
        title.setObjectName("H1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel(tr("app.subtitle"))
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        heading = QLabel(tr("login.first_run_title") if self._first_run else tr("login.title"))
        heading.setObjectName("H2")

        self.username = QLineEdit()
        self.username.setPlaceholderText(tr("login.username"))
        self.password = QLineEdit()
        self.password.setPlaceholderText(tr("login.password"))
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        form = QVBoxLayout()
        form.setSpacing(10)
        form.addWidget(self.username)

        if self._first_run:
            self.display_name = QLineEdit()
            self.display_name.setPlaceholderText(tr("login.display_name"))
            self.confirm = QLineEdit()
            self.confirm.setPlaceholderText(tr("login.confirm_password"))
            self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
            form.addWidget(self.display_name)
            form.addWidget(self.password)
            form.addWidget(self.confirm)
            submit = QPushButton(tr("login.create"))
        else:
            form.addWidget(self.password)
            submit = QPushButton(tr("login.submit"))

        submit.setObjectName("Primary")
        submit.clicked.connect(self._submit)
        self.password.returnPressed.connect(self._submit)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(34, 30, 34, 30)
        inner.setSpacing(16)
        inner.addWidget(title)
        inner.addWidget(subtitle)
        inner.addWidget(heading)
        inner.addLayout(form)
        inner.addWidget(submit)

        hint = QLabel(tr("login.admin_hint"))
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fs_hint = QLabel(tr("app.fullscreen_hint"))
        fs_hint.setObjectName("Muted")
        fs_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1); row.addWidget(card); row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)
        layout.addWidget(hint)
        layout.addWidget(fs_hint)

        # Admin/debug recovery shortcut (gated by the admin key inside the dialog).
        self._admin_shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), self)
        self._admin_shortcut.activated.connect(self._open_admin)

    def _open_admin(self) -> None:
        AdminDialog(self.context, self).exec()

    def _submit(self) -> None:
        username = self.username.text().strip()
        password = self.password.text()
        if not username or not password:
            QMessageBox.warning(self, tr("app.title"), tr("login.empty"))
            return

        if self._first_run:
            if password != self.confirm.text():
                QMessageBox.warning(self, tr("app.title"), tr("login.mismatch"))
                return
            clinician = self.context.auth.register(username, self.display_name.text(), password)
        else:
            clinician = self.context.auth.login(username, password)
            if clinician is None:
                QMessageBox.warning(self, tr("app.title"), tr("login.error"))
                return

        self.context.clinician = clinician
        self.window.show_dashboard()
