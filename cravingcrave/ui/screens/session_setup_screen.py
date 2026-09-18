"""Pre-session setup: substance, graded playlist preview, and the consent gate.

Consent is a hard precondition — the "begin" button stays disabled until the
clinician confirms the patient consented and there is at least one active cue.
"""

from __future__ import annotations

import dataclasses
import json

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...domain import playlist as playlist_rules
from ...services import substances as subs
from ...services.i18n import tr
from ..context import AppContext
from ..emoji_icon import emoji_icon
from ..responsive import adaptive_card_margins, adaptive_card_max_width, adaptive_margins
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
        self._selected_mode = context.config.default_session_mode
        self._params_customized = False
        self._load_last_params()

        back = QPushButton(tr("common.back"))
        back.setIcon(emoji_icon("←")); back.setIconSize(QSize(20, 20))
        back.clicked.connect(lambda: window.show_patient(patient.id))
        title = QLabel(tr("setup.title"))
        title.setObjectName("H1")
        header = QHBoxLayout()
        header.addWidget(back); header.addSpacing(10); header.addWidget(title); header.addStretch(1)

        card = QFrame(); card.setObjectName("Card")
        card.setMaximumWidth(adaptive_card_max_width())

        # Session mode selector: Intense / Interspersed / Custom.
        self.mode_selector = QComboBox()
        self.mode_selector.addItem(tr("mode.intense"), "intense")
        self.mode_selector.addItem(tr("mode.interspersed"), "interspersed")
        self.mode_selector.addItem(tr("mode.custom"), "custom")
        idx = self.mode_selector.findData(self._selected_mode)
        if idx >= 0:
            self.mode_selector.setCurrentIndex(idx)
        self.mode_selector.currentIndexChanged.connect(self._on_mode_changed)

        # Interspersed-mode parameters (shown for interspersed and custom modes).
        self._inter_frame = QFrame()
        inter_layout = QVBoxLayout(self._inter_frame)
        inter_layout.setContentsMargins(0, 0, 0, 0); inter_layout.setSpacing(8)
        self.craving_pct_spin = QSpinBox()
        self.craving_pct_spin.setRange(1, 50); self.craving_pct_spin.setSuffix(" %")
        self.craving_pct_spin.setValue(context.config.interspersed_craving_pct)
        self.craving_count_spin = QSpinBox()
        self.craving_count_spin.setRange(0, 500)
        self.craving_count_spin.setValue(context.config.interspersed_craving_count)
        self.min_exposure_spin = QSpinBox()
        self.min_exposure_spin.setRange(1, 60); self.min_exposure_spin.setSuffix(" s")
        self.min_exposure_spin.setValue(context.config.interspersed_min_exposure_sec)
        self.neutral_label = QLabel("")
        self.neutral_label.setObjectName("Muted")
        pct_row = QHBoxLayout()
        pct_row.addWidget(QLabel(tr("setup.interspersed_pct"))); pct_row.addWidget(self.craving_pct_spin)
        count_row = QHBoxLayout()
        count_row.addWidget(QLabel(tr("setup.interspersed_count"))); count_row.addWidget(self.craving_count_spin)
        min_row = QHBoxLayout()
        min_row.addWidget(QLabel(tr("setup.min_exposure_sec"))); min_row.addWidget(self.min_exposure_spin)
        inter_layout.addLayout(pct_row)
        inter_layout.addLayout(count_row)
        inter_layout.addLayout(min_row)
        inter_layout.addWidget(self.neutral_label)
        self._inter_frame.setVisible(self._selected_mode in ("interspersed", "custom"))

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
        self.params_btn.setIcon(emoji_icon("⚙")); self.params_btn.setIconSize(QSize(20, 20))
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
        self.begin.setIcon(emoji_icon("▶")); self.begin.setIconSize(QSize(20, 20))
        self.begin.clicked.connect(self._begin)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(*adaptive_card_margins())
        inner.setSpacing(14)
        inner.addWidget(QLabel(tr("setup.mode_label")))
        inner.addWidget(self.mode_selector)
        inner.addWidget(self._inter_frame)
        inner.addSpacing(4)
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

        scroll_inner = QWidget()
        scroll_layout = QVBoxLayout(scroll_inner)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addStretch(1); row.addWidget(card); row.addStretch(1)
        scroll_layout.addLayout(row)
        scroll_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(scroll_inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*adaptive_margins())
        layout.addLayout(header)
        layout.addWidget(scroll, 1)

        self._update()

        # Auto-launch wizard for first-time patients (0 prior sessions).
        session_count = len(self.context.repos.sessions.list_for_patient(self.patient.id))
        wizard_done = self.context.repos.settings.get(f"wizard_complete:{self.patient.id}")
        if session_count == 0 and not wizard_done:
            from .patient_wizard import PatientWizard
            wizard = PatientWizard(self.context, self.patient, self)
            if wizard.exec() == QDialog.DialogCode.Accepted:
                wizard.apply_settings()
                self._load_last_params()
                # Re-sync mode selector with wizard choice.
                idx = self.mode_selector.findData(self._selected_mode)
                if idx >= 0:
                    self.mode_selector.setCurrentIndex(idx)
                self._update()

    def _exposure_cues(self):
        substance = self.substance.currentData()
        cues = [c for c in self.context.repos.cues.list_for_patient(self.patient.id)
                if c.substance == substance]
        # Pass per-cue reactivity data for reactivity-gated backlog.
        reactivity = None
        if self.context.config.max_cue_repeats > 0:
            from ...domain.cue_ranking import cue_reactivity
            ratings = self.context.repos.ratings.list_for_patient(self.patient.id)
            reactivity = cue_reactivity(ratings) if ratings else None
        return playlist_rules.build_exposure_playlist(
            cues, max_repeats=self.context.config.max_cue_repeats,
            cue_reactivity=reactivity)

    def _positive_paths(self) -> list[str]:
        paths = [m.absolute_path for m in self.context.media.by_category("positive")]
        for c in self.context.repos.cues.list_for_patient(self.patient.id):
            if c.is_personal_reason:
                paths.append(str(self.context.media.absolute(c.media_path)))
        return paths

    def _on_mode_changed(self) -> None:
        mode = self.mode_selector.currentData()
        self._inter_frame.setVisible(mode in ("interspersed", "custom"))
        self._update()

    def _update(self) -> None:
        cues = self._exposure_cues()
        if cues:
            missing = sum(1 for c in cues
                          if not self.context.media.absolute(c.media_path).exists())
            if missing:
                self.count_label.setText(tr("cueconfig.files_missing", n=missing))
                self.count_label.setStyleSheet("color:#e63946;")
            else:
                self.count_label.setText(tr("setup.cues_count", n=len(cues)))
                self.count_label.setStyleSheet("")
        else:
            self.count_label.setText(tr("setup.no_cues"))
            self.count_label.setStyleSheet("")
        # Show neutral cue availability when an interspersed/custom mode is selected.
        mode = self.mode_selector.currentData()
        if mode in ("interspersed", "custom"):
            n_neutral = len(self.context.media.by_category("neutral"))
            self.neutral_label.setText(
                tr("setup.neutral_count", n=n_neutral) if n_neutral else tr("setup.no_neutral"))
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
            self._selected_mode = str(d.get("mode", cfg.default_session_mode))
            self._params_customized = True
        else:
            self._param_overrides = None
            self._random_order = cfg.default_random_order
            self._loop = cfg.default_loop
            self._start_fullscreen = cfg.default_start_fullscreen
            self._selected_mode = cfg.default_session_mode
            self._params_customized = False

    def _persist_last_params(self) -> None:
        d = dict(self._param_overrides or {})
        d.update(random_order=self._random_order, loop=self._loop,
                 start_fullscreen=self._start_fullscreen,
                 mode=self.mode_selector.currentData())
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
        mode = self.mode_selector.currentData()
        if mode in ("interspersed", "custom"):
            neutral_media = self.context.media.by_category("neutral")
            neutral_pool = playlist_rules.media_to_neutral_cues(neutral_media)
            # Pass per-cue reactivity for reactivity-gated backlog.
            reactivity = None
            if self.context.config.max_cue_repeats > 0:
                from ...domain.cue_ranking import cue_reactivity as _cr
                ratings = self.context.repos.ratings.list_for_patient(self.patient.id)
                reactivity = _cr(ratings) if ratings else None
            cues = playlist_rules.build_playlist_for_mode(
                mode, cues, neutral_pool=neutral_pool,
                craving_pct=self.craving_pct_spin.value(),
                craving_count=self.craving_count_spin.value(),
                max_repeats=self.context.config.max_cue_repeats,
                cue_reactivity=reactivity,
            )
        elif self._random_order:
            cues = playlist_rules.randomized(cues)
        self._persist_last_params()
        self.window.start_exposure(
            self.patient, self.substance.currentData(), cues, self._positive_paths(),
            self.ambient.currentData(),
            loop=self._loop,
            overrides=self._param_overrides,
            start_fullscreen=self._start_fullscreen,
            mode=mode,
        )
