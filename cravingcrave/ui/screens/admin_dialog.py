"""Admin/debug recovery dialog, opened by Ctrl+Shift+A on the login screen.

Gated by an admin key (hashed in app_setting; a documented default applies until a
clinic sets its own). Lets an admin recover from a forgotten clinician password:
list accounts, reset a password, create a clinician, or change the admin key.
"""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...services import auth
from ...services.i18n import tr
from ..context import AppContext

_log = logging.getLogger(__name__)


class AdminDialog(QDialog):
    def __init__(self, context: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.setWindowTitle(tr("admin.title"))
        self.setMinimumWidth(600)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_key_page())
        self.stack.addWidget(self._build_recovery_page())

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

    # --- page 0: admin key ---------------------------------------------------
    def _build_key_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        title = QLabel(tr("admin.title")); title.setObjectName("H2")
        prompt = QLabel(tr("admin.key_prompt")); prompt.setWordWrap(True)
        self.key_input = QLineEdit(); self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        enter = QPushButton(tr("admin.enter")); enter.setObjectName("Primary")
        enter.clicked.connect(self._check_key)
        self.key_input.returnPressed.connect(self._check_key)
        v.addWidget(title); v.addWidget(prompt); v.addWidget(self.key_input); v.addWidget(enter)
        return page

    def _check_key(self) -> None:
        if auth.verify_admin_key(self.context.repos.settings, self.key_input.text()):
            self._refresh_clinicians()
            self.default_warning.setVisible(auth.admin_key_is_default(self.context.repos.settings))
            self.stack.setCurrentIndex(1)
        else:
            QMessageBox.warning(self, tr("admin.title"), tr("admin.wrong"))
            self.key_input.clear()

    # --- page 1: recovery ----------------------------------------------------
    def _build_recovery_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)

        self.default_warning = QLabel(tr("admin.default_warning"))
        self.default_warning.setWordWrap(True)
        self.default_warning.setStyleSheet("background:#fdecea; color:#922; border-radius:8px; padding:8px;")

        v.addWidget(QLabel(tr("admin.clinicians")))
        self.clinician_list = QListWidget()
        v.addWidget(self.default_warning)
        v.addWidget(self.clinician_list, 1)

        reset_btn = QPushButton(tr("admin.reset_pw")); reset_btn.setObjectName("Primary")
        reset_btn.clicked.connect(self._reset_password)
        create_btn = QPushButton(tr("admin.create")); create_btn.clicked.connect(self._create_clinician)
        key_btn = QPushButton(tr("admin.change_key")); key_btn.clicked.connect(self._change_key)
        close_btn = QPushButton(tr("common.close")); close_btn.clicked.connect(self.accept)

        row = QHBoxLayout()
        row.addWidget(reset_btn); row.addWidget(create_btn); row.addWidget(key_btn)
        row.addStretch(1); row.addWidget(close_btn)
        v.addLayout(row)
        return page

    def _refresh_clinicians(self) -> None:
        self.clinician_list.clear()
        for c in self.context.auth.list_clinicians():
            item = QListWidgetItem(f"{c.username}  —  {c.display_name}")
            item.setData(Qt.ItemDataRole.UserRole, c.id)
            self.clinician_list.addItem(item)

    def _selected_id(self):
        item = self.clinician_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _reset_password(self) -> None:
        cid = self._selected_id()
        item = self.clinician_list.currentItem()
        if cid is None:
            QMessageBox.information(self, tr("admin.title"), tr("admin.select_clinician"))
            return
        pw, ok = QInputDialog.getText(self, tr("admin.reset_pw"),
                                      tr("admin.new_password", user=item.text().split("  —")[0]),
                                      QLineEdit.EchoMode.Password)
        if ok and pw:
            self.context.auth.reset_password(cid, pw)
            QMessageBox.information(self, tr("admin.title"),
                                    tr("admin.done_reset", user=item.text().split("  —")[0]))

    def _create_clinician(self) -> None:
        user, ok = QInputDialog.getText(self, tr("admin.create"), tr("admin.new_username"))
        if not (ok and user.strip()):
            return
        name, ok = QInputDialog.getText(self, tr("admin.create"), tr("admin.new_name"))
        if not ok:
            return
        pw, ok = QInputDialog.getText(self, tr("admin.create"), tr("admin.new_clinician_pw"),
                                      QLineEdit.EchoMode.Password)
        if not (ok and pw):
            return
        try:
            self.context.auth.register(user, name, pw)
        except sqlite3.IntegrityError:  # UNIQUE username collision
            QMessageBox.warning(self, tr("admin.title"), tr("addclinician.duplicate"))
            return
        except Exception as exc:  # disk/DB/other — surface honestly, don't mislabel
            _log.exception("Clinician create failed: %s", exc)
            QMessageBox.warning(self, tr("admin.title"), tr("error.save_failed"))
            return
        self._refresh_clinicians()
        QMessageBox.information(self, tr("admin.title"), tr("admin.done_create", user=user.strip()))

    def _change_key(self) -> None:
        key, ok = QInputDialog.getText(self, tr("admin.change_key"), tr("admin.new_key"),
                                       QLineEdit.EchoMode.Password)
        if ok and key:
            auth.set_admin_key(self.context.repos.settings, key)
            self.default_warning.setVisible(False)
            QMessageBox.information(self, tr("admin.title"), tr("admin.done_key"))
