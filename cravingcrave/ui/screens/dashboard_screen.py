"""Clinician home: patient roster, add patient, settings, logout."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
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
from ..emoji_icon import emoji_icon
from ..responsive import adaptive_margins
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
        add_clinician_btn.setIcon(emoji_icon("✏")); add_clinician_btn.setIconSize(QSize(20, 20))
        add_clinician_btn.clicked.connect(self._add_clinician)
        admin_btn = QPushButton(tr("dashboard.admin"))
        admin_btn.setIcon(emoji_icon("\U0001F6E1")); admin_btn.setIconSize(QSize(20, 20))
        admin_btn.clicked.connect(window.show_admin_center)
        help_btn = QPushButton(tr("dashboard.help"))
        help_btn.setIcon(emoji_icon("❓")); help_btn.setIconSize(QSize(20, 20))
        help_btn.clicked.connect(window.show_help)
        settings_btn = QPushButton(tr("dashboard.settings"))
        settings_btn.setIcon(emoji_icon("⚙")); settings_btn.setIconSize(QSize(20, 20))
        settings_btn.clicked.connect(window.show_settings)
        logout_btn = QPushButton(tr("dashboard.logout"))
        logout_btn.setIcon(emoji_icon("\U0001F513")); logout_btn.setIconSize(QSize(20, 20))
        logout_btn.clicked.connect(window.show_login)

        header = QHBoxLayout()
        head_text = QVBoxLayout()
        head_text.addWidget(title)
        head_text.addWidget(welcome)
        header.addLayout(head_text)
        header.addStretch(1)

        # Toolbar row — separated from header to avoid clipping at low res.
        toolbar = QHBoxLayout()
        toolbar.addWidget(add_clinician_btn)
        toolbar.addWidget(admin_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(help_btn)
        toolbar.addWidget(settings_btn)
        toolbar.addWidget(logout_btn)

        section = QLabel(tr("dashboard.patients"))
        section.setObjectName("H2")
        add_btn = QPushButton(tr("dashboard.add_patient"))
        add_btn.setObjectName("Primary")
        add_btn.setIcon(emoji_icon("\U0001F464")); add_btn.setIconSize(QSize(20, 20))
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
        open_btn.setIcon(emoji_icon("\U0001F4C2")); open_btn.setIconSize(QSize(20, 20))
        open_btn.clicked.connect(self._open_selected)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*adaptive_margins())
        layout.addLayout(header)
        layout.addLayout(toolbar)
        layout.addSpacing(8)
        layout.addLayout(section_row)
        layout.addWidget(self.empty)
        layout.addWidget(self.list, 1)
        layout.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignRight)

        self._refresh()

        # Auto-launch the Import Wizard on first run or if no neutral images exist.
        QTimer.singleShot(500, self._check_import_wizard)

    def _check_import_wizard(self) -> None:
        """Auto-launch the Import Wizard on first run only.

        Once the flag is set (whether the wizard was completed or cancelled),
        it never auto-launches again. The clinician can always open it manually
        from the cue library or Settings.
        """
        done = self.context.repos.settings.get("import_wizard_complete")
        if not done:
            from .import_wizard import ImportWizard
            w = ImportWizard(self.context, self)
            w.exec()
            # Set flag even if cancelled so it doesn't re-launch on every login.
            self.context.repos.settings.set("import_wizard_complete", "1")

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
