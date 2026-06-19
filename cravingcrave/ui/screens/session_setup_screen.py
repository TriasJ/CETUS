"""Pre-session setup: substance, graded playlist preview, and the consent gate.

Consent is a hard precondition — the "begin" button stays disabled until the
clinician confirms the patient consented and there is at least one active cue.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ...domain import playlist as playlist_rules
from ...services import substances as subs
from ...services.i18n import tr
from ..context import AppContext


class SessionSetupScreen(QWidget):
    def __init__(self, window, context: AppContext, patient) -> None:
        super().__init__()
        self.window = window
        self.context = context
        self.patient = patient

        back = QPushButton(tr("common.back"))
        back.clicked.connect(lambda: window.show_patient(patient.id))
        title = QLabel(tr("setup.title"))
        title.setObjectName("H1")
        header = QHBoxLayout()
        header.addWidget(back); header.addSpacing(10); header.addWidget(title); header.addStretch(1)

        card = QFrame(); card.setObjectName("Card")
        card.setMaximumWidth(620)

        self.substance = QComboBox()
        for value, label in subs.available_substances(self.context.repos.settings):
            self.substance.addItem(label, value)
        if patient.primary_substance and self.substance.findData(patient.primary_substance) < 0:
            self.substance.addItem(subs.display_name(self.context.repos.settings, patient.primary_substance),
                                   patient.primary_substance)
        idx = self.substance.findData(patient.primary_substance)
        if idx >= 0:
            self.substance.setCurrentIndex(idx)
        self.substance.currentIndexChanged.connect(self._update)

        self.count_label = QLabel("")
        self.count_label.setObjectName("Muted")

        # Optional ambient sound bed (layered under the visual cue, boosts presence).
        self.ambient = QComboBox()
        self.ambient.addItem(tr("setup.ambient_none"), None)
        for m in self.context.media.by_category("sounds"):
            self.ambient.addItem(m.filename, m.absolute_path)

        # Randomize cue order (counterbalances order vs. the graded escalation).
        self.random_order = QCheckBox(tr("setup.random_order"))
        # Loop the cue list (wrap at the ends so quick skimming doesn't dead-end).
        self.loop_cues = QCheckBox(tr("setup.loop_cues"))

        # Disclaimer + consent gate.
        disclaimer = QLabel(tr("disclaimer.body"))
        disclaimer.setWordWrap(True)
        self.consent = QCheckBox(tr("consent.checkbox"))
        self.consent.toggled.connect(self._update)

        self.begin = QPushButton(tr("setup.begin"))
        self.begin.setObjectName("Primary")
        self.begin.clicked.connect(self._begin)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(28, 24, 28, 24)
        inner.setSpacing(14)
        inner.addWidget(QLabel(tr("setup.choose_substance")))
        inner.addWidget(self.substance)
        inner.addWidget(self.count_label)
        inner.addSpacing(4)
        inner.addWidget(QLabel(tr("setup.ambient")))
        inner.addWidget(self.ambient)
        inner.addWidget(self.random_order)
        inner.addWidget(self.loop_cues)
        inner.addSpacing(8)
        inner.addWidget(disclaimer)
        inner.addWidget(self.consent)
        inner.addWidget(self.begin)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.addLayout(header)
        row = QHBoxLayout()
        row.addStretch(1); row.addWidget(card); row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)

        self._update()

    def _exposure_cues(self):
        substance = self.substance.currentData()
        cues = [c for c in self.context.repos.cues.list_for_patient(self.patient.id)
                if c.substance == substance]
        return playlist_rules.build_exposure_playlist(cues)

    def _positive_paths(self) -> list[str]:
        paths = [m.absolute_path for m in self.context.media.by_category("positive")]
        for c in self.context.repos.cues.list_for_patient(self.patient.id):
            if c.is_personal_reason:
                paths.append(str(self.context.media.absolute(c.media_path)))
        return paths

    def _update(self) -> None:
        cues = self._exposure_cues()
        if cues:
            self.count_label.setText(tr("setup.cues_count", n=len(cues)))
        else:
            self.count_label.setText(tr("setup.no_cues"))
        self.begin.setEnabled(bool(cues) and self.consent.isChecked())

    def _begin(self) -> None:
        cues = self._exposure_cues()
        if not cues or not self.consent.isChecked():
            return
        if self.random_order.isChecked():
            cues = playlist_rules.randomized(cues)
        self.window.start_exposure(
            self.patient, self.substance.currentData(), cues, self._positive_paths(),
            self.ambient.currentData(),
            loop=self.loop_cues.isChecked(),
        )
