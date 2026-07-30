"""Admin-key gate — a small modal that guards the Admin Center and its tools.

Reuses the single global admin key (``services.auth.verify_admin_key``); there are no
per-clinician roles. Returns True only when the correct key is entered.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from ...services import auth
from ...services.i18n import tr


class _AdminGateDialog(QDialog):
    def __init__(self, parent, context) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle(tr("admin.title"))
        self.setMinimumWidth(440)

        prompt = QLabel(tr("admin.key_prompt")); prompt.setWordWrap(True)
        self.key_input = QLineEdit(); self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.returnPressed.connect(self._check)

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20); v.setSpacing(12)
        v.addWidget(prompt)
        if auth.admin_key_is_default(context.repos.settings):
            warn = QLabel(tr("admin.default_warning")); warn.setWordWrap(True)
            warn.setStyleSheet("background:#fdecea; color:#922; border-radius:8px; padding:8px;")
            v.addWidget(warn)
        v.addWidget(self.key_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("admin.enter"))
        buttons.accepted.connect(self._check)
        buttons.rejected.connect(self.reject)
        v.addWidget(buttons)

    def _check(self) -> None:
        if auth.verify_admin_key(self.context.repos.settings, self.key_input.text()):
            self.accept()
        else:
            QMessageBox.warning(self, tr("admin.title"), tr("admin.wrong"))
            self.key_input.clear()


def require_admin(parent, context) -> bool:
    """Prompt for the admin key; return True iff it verifies."""
    return _AdminGateDialog(parent, context).exec() == QDialog.DialogCode.Accepted
