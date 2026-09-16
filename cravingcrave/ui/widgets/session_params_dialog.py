"""Per-session run parameters popup.

Lets the clinician tweak run-time exposure behaviour for a single session without
touching the global (clinic-wide) defaults: automatic cue advancement, keyboard-only
mode, the safety time limit, and whether to start in fullscreen. Every control is seeded
from the current ``AppConfig`` so leaving it untouched reproduces the global behaviour.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...services.i18n import tr


class SessionParamsDialog(QDialog):
    def __init__(self, parent, config, random_order: bool = False, loop: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("setup.params_title"))
        self.setModal(True)
        self.setMinimumWidth(540)   # wide enough for the full-length toggle labels

        # Cue-ordering flags (per-session, not AppConfig fields).
        self.random_order = QCheckBox(tr("setup.random_order"))
        self.random_order.setChecked(random_order)
        self.loop_cues = QCheckBox(tr("setup.loop_cues"))
        self.loop_cues.setChecked(loop)
        # When adaptive ordering is enabled, warn that random shuffling overrides the learned
        # graded order for this session (learning itself is unaffected).
        self._random_note = QLabel(tr("setup.random_overrides_adaptive"))
        self._random_note.setWordWrap(True)
        self._random_note.setStyleSheet("color:#8a5a00; font-size:13px;")
        self._random_note.setVisible(getattr(config, "adaptive_ordering", False))

        self.autoscroll_on_grading = QCheckBox(tr("settings.autoscroll_on_grading"))
        self.autoscroll_on_grading.setChecked(config.autoscroll_on_grading)
        self.autoscroll_timed = QSpinBox(); self.autoscroll_timed.setRange(0, 600)
        self.autoscroll_timed.setSuffix(" s"); self.autoscroll_timed.setMinimumWidth(120)
        self.autoscroll_timed.setValue(config.autoscroll_timed_seconds)
        self.accessibility = QCheckBox(tr("settings.accessibility_kbmode"))
        self.accessibility.setChecked(config.accessibility_kbmode)
        self.time_cap = QSpinBox(); self.time_cap.setRange(1, 120)
        self.time_cap.setSuffix(" min"); self.time_cap.setMinimumWidth(120)
        self.time_cap.setValue(config.session_time_cap_seconds // 60)
        self.start_fullscreen = QCheckBox(tr("setup.start_fullscreen"))

        # Per-cue craving prompt
        self.vas_per_cue = QSpinBox(); self.vas_per_cue.setRange(0, 600)
        self.vas_per_cue.setSuffix(" s"); self.vas_per_cue.setMinimumWidth(120)
        self.vas_per_cue.setValue(config.vas_prompt_per_cue_seconds)

        # Interspersed-mode: measure craving on neutral cues too?
        self.vas_on_neutral = QCheckBox(tr("setup.vas_on_neutral"))
        self.vas_on_neutral.setChecked(config.interspersed_vas_on_neutral)

        # Dynamic neutral increase: extend neutral runs when craving is high.
        self.dynamic_neutral = QCheckBox(tr("setup.dynamic_neutral"))
        self.dynamic_neutral.setChecked(config.dynamic_neutral_enabled)
        self.dynamic_neutral.setToolTip(tr("setup.dynamic_neutral_hint"))
        self.dynamic_threshold = QSpinBox(); self.dynamic_threshold.setRange(1, 10)
        self.dynamic_threshold.setMinimumWidth(120)
        self.dynamic_threshold.setValue(config.dynamic_neutral_threshold)

        # Progressive down-regulation
        self.progressive_enabled = QCheckBox(tr("settings.progressive_enabled"))
        self.progressive_enabled.setChecked(config.progressive_downreg_enabled)
        self.progressive_target = QSpinBox(); self.progressive_target.setRange(1, 100)
        self.progressive_target.setSuffix(" %"); self.progressive_target.setMinimumWidth(120)
        self.progressive_target.setValue(config.progressive_downreg_target_pct)

        # Auto-coping
        self.auto_coping = QCheckBox(tr("settings.auto_coping_enabled"))
        self.auto_coping.setChecked(config.auto_coping_enabled)

        # Cue audio mode
        self.cue_audio_mode = QComboBox()
        for code, label_key in [("auto", "settings.cue_audio_auto"),
                                ("always", "settings.cue_audio_always"),
                                ("muted", "settings.cue_audio_muted"),
                                ("audio_only", "settings.cue_audio_only")]:
            self.cue_audio_mode.addItem(tr(label_key), code)
        idx = self.cue_audio_mode.findData(config.cue_audio_mode)
        if idx >= 0:
            self.cue_audio_mode.setCurrentIndex(idx)

        # Full-width rows for the checkboxes so their (long) labels never clip; the two
        # spinboxes keep a right-aligned label column.
        form = QFormLayout(); form.setSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.addRow(self.random_order)
        form.addRow(self._random_note)
        form.addRow(self.loop_cues)
        form.addRow(self.autoscroll_on_grading)
        form.addRow(tr("settings.autoscroll_timed"), self.autoscroll_timed)
        form.addRow(self.accessibility)
        form.addRow(tr("settings.time_cap_min"), self.time_cap)
        form.addRow(self.start_fullscreen)
        form.addRow(tr("settings.vas_per_cue_seconds"), self.vas_per_cue)
        form.addRow(self.vas_on_neutral)
        form.addRow(self.dynamic_neutral)
        form.addRow(tr("setup.dynamic_neutral_threshold"), self.dynamic_threshold)
        form.addRow(self.progressive_enabled)
        form.addRow(tr("settings.progressive_target"), self.progressive_target)
        form.addRow(self.auto_coping)
        form.addRow(tr("settings.cue_audio_label"), self.cue_audio_mode)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Help)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.helpRequested.connect(self._open_help)
        buttons.button(QDialogButtonBox.StandardButton.Help).setText(tr("common.help"))

        intro = QLabel(tr("setup.params_intro")); intro.setWordWrap(True)

        # Wrap the form in a scroll area so it remains usable on small screens.
        form_widget = QWidget()
        form_widget.setLayout(form)
        scroll = QScrollArea()
        scroll.setWidget(form_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20); v.setSpacing(14)
        v.addWidget(intro)
        v.addWidget(scroll, 1)
        v.addWidget(buttons)

    def _open_help(self) -> None:
        # Opened on top of this modal dialog; explains how each parameter changes the session.
        from ..screens.help_dialog import HelpDialog
        dlg = HelpDialog(self)
        dlg.show_topic("settings_help")
        dlg.exec()

    def overrides(self) -> dict:
        """The chosen values as an ``AppConfig`` field override map (per-run only)."""
        return {
            "autoscroll_on_grading": self.autoscroll_on_grading.isChecked(),
            "autoscroll_timed_seconds": self.autoscroll_timed.value(),
            "accessibility_kbmode": self.accessibility.isChecked(),
            "session_time_cap_seconds": self.time_cap.value() * 60,
            "vas_prompt_per_cue_seconds": self.vas_per_cue.value(),
            "progressive_downreg_enabled": self.progressive_enabled.isChecked(),
            "progressive_downreg_target_pct": self.progressive_target.value(),
            "auto_coping_enabled": self.auto_coping.isChecked(),
            "cue_audio_mode": self.cue_audio_mode.currentData(),
            "interspersed_vas_on_neutral": self.vas_on_neutral.isChecked(),
            "dynamic_neutral_enabled": self.dynamic_neutral.isChecked(),
            "dynamic_neutral_threshold": self.dynamic_threshold.value(),
        }

    def wants_fullscreen(self) -> bool:
        return self.start_fullscreen.isChecked()

    def wants_random(self) -> bool:
        return self.random_order.isChecked()

    def wants_loop(self) -> bool:
        return self.loop_cues.isChecked()
