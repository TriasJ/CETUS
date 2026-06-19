"""Add-clinician dialog opened from the dashboard.

Lets any *already-logged-in* clinician register a new clinician account directly,
without going through the admin recovery dialog (which is reserved for the
locked-out / reset case). Validates that the password is confirmed and that the
username is unique (the underlying UNIQUE constraint also enforces this).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox, QWidget,
)

from ...services.i18n import tr


class AddClinicianDialog(QDialog):
    def __init__(self, context, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle(tr("addclinician.title"))
        self.setMinimumWidth(420)

        self.username = QLineEdit()
        self.display_name = QLineEdit()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm = QLineEdit(); self.confirm.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout(self)
        form.addRow(tr("login.username"), self.username)
        form.addRow(tr("login.display_name"), self.display_name)
        form.addRow(tr("login.password"), self.password)
        form.addRow(tr("login.confirm_password"), self.confirm)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _save(self) -> None:
        username = self.username.text().strip()
        password = self.password.text()
        if not username or not password:
            QMessageBox.warning(self, tr("app.title"), tr("login.empty"))
            return
        if password != self.confirm.text():
            QMessageBox.warning(self, tr("app.title"), tr("login.mismatch"))
            return
        # Block duplicates explicitly so the message is friendly (the UNIQUE
        # constraint on clinician.username is the ultimate guard).
        if self.context.auth.clinicians.get_by_username(username) is not None:
            QMessageBox.warning(self, tr("app.title"), tr("addclinician.duplicate"))
            return
        self.context.auth.register(username, self.display_name.text().strip(), password)
        self.accept()
