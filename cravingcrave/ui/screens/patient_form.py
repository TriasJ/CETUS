"""Create/edit patient dialog. Modal is fine here — no exposure is in progress."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox,
    QPlainTextEdit, QSpinBox, QWidget,
)

from ...domain.models import Patient
from ...services import substances as subs
from ...services.i18n import tr


class PatientFormDialog(QDialog):
    def __init__(self, context, parent: Optional[QWidget] = None, patient: Optional[Patient] = None) -> None:
        super().__init__(parent)
        self.context = context
        self.patient = patient
        self.setWindowTitle(tr("patient.edit_title") if patient else tr("patient.new_title"))
        self.setMinimumWidth(420)

        self.code = QLineEdit()
        self.code.setPlaceholderText(tr("patient.code_hint"))
        self.display_name = QLineEdit()
        self.birth_year = QSpinBox()
        self.birth_year.setRange(0, 2026)
        self.birth_year.setSpecialValueText("—")
        self.substance = QComboBox()
        for value, label in subs.available_substances(self.context.repos.settings):
            self.substance.addItem(label, value)
        # If editing a patient whose substance was later hidden, keep it selectable.
        if patient and patient.primary_substance and self.substance.findData(patient.primary_substance) < 0:
            self.substance.addItem(subs.display_name(self.context.repos.settings, patient.primary_substance),
                                   patient.primary_substance)
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(80)

        if patient:
            self.code.setText(patient.code)
            self.display_name.setText(patient.display_name or "")
            self.birth_year.setValue(patient.birth_year or 0)
            idx = self.substance.findData(patient.primary_substance)
            if idx >= 0:
                self.substance.setCurrentIndex(idx)
            self.notes.setPlainText(patient.notes or "")

        form = QFormLayout()
        form.addRow(tr("patient.code"), self.code)
        form.addRow(tr("patient.display_name"), self.display_name)
        form.addRow(tr("patient.birth_year"), self.birth_year)
        form.addRow(tr("patient.substance"), self.substance)
        form.addRow(tr("patient.notes"), self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        form.addRow(buttons)
        self.setLayout(form)

    def _save(self) -> None:
        code = self.code.text().strip()
        if not code:
            QMessageBox.warning(self, tr("app.title"), tr("patient.code_required"))
            return
        birth = self.birth_year.value() or None
        substance = self.substance.currentData()
        notes = self.notes.toPlainText().strip() or None
        name = self.display_name.text().strip() or None

        try:
            if self.patient is None:
                self.context.repos.patients.create(
                    Patient(code=code, display_name=name, birth_year=birth,
                            primary_substance=substance, notes=notes,
                            created_by=self.context.clinician.id)
                )
            else:
                self.patient.code = code
                self.patient.display_name = name
                self.patient.birth_year = birth
                self.patient.primary_substance = substance
                self.patient.notes = notes
                self.context.repos.patients.update(self.patient)
        except Exception:  # e.g. UNIQUE code collision
            QMessageBox.warning(self, tr("app.title"), tr("patient.code_taken"))
            return
        self.accept()
