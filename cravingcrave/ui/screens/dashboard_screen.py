"""Clinician home: patient roster, add patient, settings, logout."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...services import substances as subs
from ...services.i18n import tr
from ..context import AppContext
from .add_clinician_dialog import AddClinicianDialog
from .patient_form import PatientFormDialog


class DashboardScreen(QWidget):
    def __init__(self, window, context: AppContext) -> None:
        super().__init__()
        self.window = window
        self.context = context

        title = QLabel(tr("dashboard.title"))
        title.setObjectName("H1")
        welcome = QLabel(tr("dashboard.welcome", name=context.clinician.display_name))
        welcome.setObjectName("Muted")

        add_clinician_btn = QPushButton(tr("dashboard.add_clinician"))
        add_clinician_btn.clicked.connect(self._add_clinician)
        admin_btn = QPushButton(tr("dashboard.admin"))
        admin_btn.clicked.connect(window.show_admin_center)
        help_btn = QPushButton(tr("dashboard.help"))
        help_btn.clicked.connect(window.show_help)
        settings_btn = QPushButton(tr("dashboard.settings"))
        settings_btn.clicked.connect(window.show_settings)
        logout_btn = QPushButton(tr("dashboard.logout"))
        logout_btn.clicked.connect(window.show_login)

        header = QHBoxLayout()
        head_text = QVBoxLayout()
        head_text.addWidget(title)
        head_text.addWidget(welcome)
        header.addLayout(head_text)
        header.addStretch(1)
        header.addWidget(add_clinician_btn)
        header.addWidget(admin_btn)
        header.addWidget(help_btn)
        header.addWidget(settings_btn)
        header.addWidget(logout_btn)

        section = QLabel(tr("dashboard.patients"))
        section.setObjectName("H2")
        add_btn = QPushButton(tr("dashboard.add_patient"))
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self._add_patient)

        section_row = QHBoxLayout()
        section_row.addWidget(section)
        section_row.addStretch(1)
        section_row.addWidget(add_btn)

        self.empty = QLabel(tr("dashboard.no_patients"))
        self.empty.setObjectName("Muted")
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._open_selected)

        open_btn = QPushButton(tr("dashboard.open"))
        open_btn.clicked.connect(self._open_selected)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.addLayout(header)
        layout.addSpacing(12)
        layout.addLayout(section_row)
        layout.addWidget(self.empty)
        layout.addWidget(self.list, 1)
        layout.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignRight)

        self._refresh()

    def _refresh(self) -> None:
        self.list.clear()
        patients = self.context.repos.patients.list_active()
        self.empty.setVisible(not patients)
        self.list.setVisible(bool(patients))
        for p in patients:
            label = p.code
            if p.primary_substance:
                label += f"  ·  {subs.display_name(self.context.repos.settings, p.primary_substance)}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            self.list.addItem(item)

    def _add_patient(self) -> None:
        dialog = PatientFormDialog(self.context, self)
        if dialog.exec():
            self._refresh()

    def _add_clinician(self) -> None:
        AddClinicianDialog(self.context, self).exec()

    def _open_selected(self) -> None:
        item = self.list.currentItem()
        if item is not None:
            self.window.show_patient(item.data(Qt.ItemDataRole.UserRole))
