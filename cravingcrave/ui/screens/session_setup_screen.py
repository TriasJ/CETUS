"""Pre-session setup: substance, graded playlist preview, and the consent gate.

Consent is a hard precondition — the "begin" button stays disabled until the
clinician confirms the patient consented and there is at least one active cue.
"""

from __future__ import annotations

import dataclasses
import json

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...domain import playlist as playlist_rules
from ...services import substances as subs
from ...services.i18n import tr
from ..context import AppContext
from ..widgets.session_params_dialog import SessionParamsDialog


class SessionSetupScreen(QWidget):
    def __init__(self, window, context: AppContext, patient) -> None:
        super().__init__()
        self.window = window
        self.context = context
        self.patient = patient
        # Per-session parameters: start from the last config this patient used, falling back
        # to the clinic-wide defaults from Ajustes. Populated by _load_last_params().
        self._param_overrides: dict | None = None
        self._random_order = False
        self._loop = False
        self._start_fullscreen = False
        self._params_customized = False
        self._load_last_params()

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

        # Quick run parameters live in the Parameters popup (random order, loop, auto-advance,
        # keyboard-only, time limit, start fullscreen) — all defaulted in Ajustes.
        self.params_btn = QPushButton(tr("setup.parameters"))
        self.params_btn.clicked.connect(self._open_params)
        self.params_status = QLabel(
            tr("setup.params_custom") if self._params_customized else tr("setup.params_default"))
        self.params_status.setObjectName("Muted")

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
        params_row = QHBoxLayout()
        params_row.addWidget(self.params_btn)
        params_row.addWidget(self.params_status, 1)
        inner.addLayout(params_row)
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

    def _params_key(self) -> str:
        return f"session_params:{self.patient.id}"

    def _load_last_params(self) -> None:
        """Seed the run parameters from this patient's last-used config, else the Ajustes
        defaults. The clinic-wide defaults are the fallback; the popup remembers the last use."""
        cfg = self.context.config
        raw = self.context.repos.settings.get(self._params_key())
        try:
            d = json.loads(raw) if raw else {}
        except (ValueError, TypeError):
            d = {}
        if d:
            self._param_overrides = {
                "autoscroll_on_grading": bool(d.get("autoscroll_on_grading", cfg.autoscroll_on_grading)),
                "autoscroll_timed_seconds": int(d.get("autoscroll_timed_seconds", cfg.autoscroll_timed_seconds)),
                "accessibility_kbmode": bool(d.get("accessibility_kbmode", cfg.accessibility_kbmode)),
                "session_time_cap_seconds": int(d.get("session_time_cap_seconds", cfg.session_time_cap_seconds)),
            }
            self._random_order = bool(d.get("random_order", cfg.default_random_order))
            self._loop = bool(d.get("loop", cfg.default_loop))
            self._start_fullscreen = bool(d.get("start_fullscreen", cfg.default_start_fullscreen))
            self._params_customized = True
        else:
            self._param_overrides = None
            self._random_order = cfg.default_random_order
            self._loop = cfg.default_loop
            self._start_fullscreen = cfg.default_start_fullscreen
            self._params_customized = False

    def _persist_last_params(self) -> None:
        d = dict(self._param_overrides or {})
        d.update(random_order=self._random_order, loop=self._loop,
                 start_fullscreen=self._start_fullscreen)
        self.context.repos.settings.set(self._params_key(), json.dumps(d))

    def _effective_config(self):
        """Current config with any chosen per-session overrides applied (for seeding)."""
        if self._param_overrides is None:
            return self.context.config
        return dataclasses.replace(self.context.config, **self._param_overrides)

    def _open_params(self) -> None:
        dlg = SessionParamsDialog(self, self._effective_config(),
                                  random_order=self._random_order, loop=self._loop)
        dlg.start_fullscreen.setChecked(self._start_fullscreen)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._param_overrides = dlg.overrides()
            self._start_fullscreen = dlg.wants_fullscreen()
            self._random_order = dlg.wants_random()
            self._loop = dlg.wants_loop()
            self._params_customized = True
            self._persist_last_params()   # remember this patient's last-used config
            self.params_status.setText(tr("setup.params_custom"))

    def _begin(self) -> None:
        cues = self._exposure_cues()
        if not cues or not self.consent.isChecked():
            return
        if self._random_order:
            cues = playlist_rules.randomized(cues)
        self.window.start_exposure(
            self.patient, self.substance.currentData(), cues, self._positive_paths(),
            self.ambient.currentData(),
            loop=self._loop,
            overrides=self._param_overrides,
            start_fullscreen=self._start_fullscreen,
        )
