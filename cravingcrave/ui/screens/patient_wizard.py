"""Evidence-based patient setup wizard.

Auto-launches on a patient's first session (0 prior sessions) and is accessible
from the patient detail screen via a "Setup Wizard" button.  Each page provides
tailored recommendations backed by numbered citations from the bundled
``wizard_citations.json``.  The clinician can accept or override every suggestion.
"""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from ... import paths
from ...services.i18n import tr
from ..context import AppContext
from ..responsive import screen_size

# ---------------------------------------------------------------------------
# Citation helpers
# ---------------------------------------------------------------------------

def _load_citations() -> list[dict]:
    p = paths.resource_path("wizard_citations.json")
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("citations", [])


def _cite_short(citations: list[dict], *ids: int) -> str:
    """Return a compact '[1][2]' reference string for the given citation ids."""
    return "".join(f"[{i}]" for i in ids)


def _evidence_label(text: str, parent: QWidget | None = None) -> QLabel:
    """A styled evidence-recommendation label (italic, teal left-border)."""
    lbl = QLabel(text, parent)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        "font-style:italic; color:#2f5d63; padding:6px 10px; "
        "border-left:3px solid #2a9d8f; margin:4px 0;"
    )
    return lbl


# ---------------------------------------------------------------------------
# Page 1 — Patient Profile
# ---------------------------------------------------------------------------

class _ProfilePage(QWizardPage):
    def __init__(self, context: AppContext, patient, parent=None) -> None:
        super().__init__(parent)
        self.setTitle(tr("wizard.page1_title"))
        self.setSubTitle(tr("wizard.first_time"))

        box = QGroupBox(tr("wizard.page1_title"))
        form = QFormLayout(box)
        form.setSpacing(10)

        code = QLabel(f"<b>{patient.code}</b>")
        substance = QLabel(f"<b>{patient.primary_substance or '—'}</b>")
        birth = QLabel(str(patient.birth_year) if patient.birth_year else "—")
        form.addRow(tr("patient.code"), code)
        form.addRow(tr("patient.substance"), substance)
        form.addRow(tr("patient.birth_year"), birth)

        # Clinician inputs
        self.duration = QComboBox()
        for data, key in [("lt1", "wizard.duration_lt1"), ("1to5", "wizard.duration_1to5"),
                          ("5to10", "wizard.duration_5to10"), ("10plus", "wizard.duration_10plus")]:
            self.duration.addItem(tr(key), data)

        self.frequency = QComboBox()
        for data, key in [("daily", "wizard.freq_daily"), ("several", "wizard.freq_several"),
                          ("weekly", "wizard.freq_weekly"), ("less", "wizard.freq_less")]:
            self.frequency.addItem(tr(key), data)

        self.status = QComboBox()
        for data, key in [("active", "wizard.status_active"), ("early", "wizard.status_early"),
                          ("sustained", "wizard.status_sustained"), ("treatment", "wizard.status_treatment")]:
            self.status.addItem(tr(key), data)

        self.prev_cet = QCheckBox(tr("wizard.previous_cet"))

        form.addRow(tr("wizard.usage_duration"), self.duration)
        form.addRow(tr("wizard.usage_frequency"), self.frequency)
        form.addRow(tr("wizard.current_status"), self.status)
        form.addRow(self.prev_cet)

        v = QVBoxLayout(self)
        v.addWidget(box)
        v.addStretch(1)


# ---------------------------------------------------------------------------
# Page 2 — Session Mode
# ---------------------------------------------------------------------------

class _ModePage(QWizardPage):
    def __init__(self, context: AppContext, citations: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setTitle(tr("wizard.page2_title"))
        self.setSubTitle(tr("wizard.recommendation_reason"))
        self._citations = citations

        self.radio_intense = QRadioButton(tr("mode.intense"))
        self.radio_interspersed = QRadioButton(tr("mode.interspersed"))
        self.radio_custom = QRadioButton(tr("mode.custom"))

        self.evidence_intense = _evidence_label(
            tr("wizard.mode_intense_reason") + " " + _cite_short(citations, 1, 2))
        self.evidence_interspersed = _evidence_label(
            tr("wizard.mode_interspersed_reason") + " " + _cite_short(citations, 3, 6, 10, 11, 8))
        evidence_custom = _evidence_label(tr("mode.custom_desc"))

        self.recommendation_label = QLabel()
        self.recommendation_label.setWordWrap(True)
        self.recommendation_label.setStyleSheet(
            "background:#e0f2ef; color:#14303a; border-radius:8px; padding:10px; font-weight:bold;"
        )

        v = QVBoxLayout(self)
        v.addWidget(self.recommendation_label)
        v.addSpacing(10)
        v.addWidget(self.radio_intense)
        v.addWidget(self.evidence_intense)
        v.addSpacing(6)
        v.addWidget(self.radio_interspersed)
        v.addWidget(self.evidence_interspersed)
        v.addSpacing(6)
        v.addWidget(self.radio_custom)
        v.addWidget(evidence_custom)
        v.addStretch(1)

    def initializePage(self) -> None:
        """Called when this page becomes visible — read the profile page's values."""
        wizard = self.wizard()
        profile: _ProfilePage = wizard.page(0)
        status = profile.status.currentData()
        duration = profile.duration.currentData()

        if status == "active" or duration == "lt1":
            self.radio_interspersed.setChecked(True)
            self.recommendation_label.setText(
                "★ " + tr("wizard.recommended") + ": " + tr("mode.interspersed")
                + "\n" + tr("wizard.mode_interspersed_reason"))
        elif status == "sustained" and duration in ("5to10", "10plus"):
            self.radio_intense.setChecked(True)
            self.recommendation_label.setText(
                "★ " + tr("wizard.recommended") + ": " + tr("mode.intense")
                + "\n" + tr("wizard.mode_intense_reason"))
        else:
            self.radio_interspersed.setChecked(True)
            self.recommendation_label.setText(
                "★ " + tr("wizard.recommended") + ": " + tr("mode.interspersed")
                + "\n" + tr("wizard.mode_interspersed_reason"))

    def selected_mode(self) -> str:
        if self.radio_intense.isChecked():
            return "intense"
        if self.radio_custom.isChecked():
            return "custom"
        return "interspersed"


# ---------------------------------------------------------------------------
# Page 3 — Cue Selection
# ---------------------------------------------------------------------------

class _CuePage(QWizardPage):
    def __init__(self, context: AppContext, patient, citations: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setTitle(tr("wizard.page3_title"))
        self.context = context
        self.patient = patient

        self.cue_count_label = QLabel()
        self.cue_count_label.setStyleSheet("font-size:14px;")
        self.neutral_count_label = QLabel()
        self.neutral_count_label.setObjectName("Muted")

        self.evidence = _evidence_label(
            tr("wizard.cue_recommendation") + " " + _cite_short(citations, 1, 4, 11))

        self.interspersed_box = QGroupBox(tr("mode.interspersed"))
        inter_form = QFormLayout(self.interspersed_box)
        self.craving_pct = QSpinBox()
        self.craving_pct.setRange(1, 50); self.craving_pct.setSuffix(" %")
        self.craving_pct.setValue(context.config.interspersed_craving_pct)
        inter_form.addRow(tr("setup.interspersed_pct"), self.craving_pct)
        inter_evidence = _evidence_label(
            "Standard cue-reactivity paradigms use 5–10% craving cues among neutrals "
            + _cite_short(citations, 10, 11)
            + ". Clinical exposure typically uses fewer craving cues than research protocols.")
        inter_form.addRow(inter_evidence)

        self.warning = QLabel(tr("wizard.no_cues_warning"))
        self.warning.setStyleSheet("color:#e63946; font-weight:bold;")
        self.warning.setWordWrap(True)

        v = QVBoxLayout(self)
        v.addWidget(self.cue_count_label)
        v.addWidget(self.neutral_count_label)
        v.addSpacing(6)
        v.addWidget(self.evidence)
        v.addSpacing(6)
        v.addWidget(self.interspersed_box)
        v.addWidget(self.warning)
        v.addStretch(1)

    def initializePage(self) -> None:
        substance = self.patient.primary_substance or "alcohol"
        cues = [c for c in self.context.repos.cues.list_for_patient(self.patient.id)
                if c.substance == substance and c.enabled and not c.is_personal_reason]
        n_neutral = len(self.context.media.by_category("neutral"))
        self.cue_count_label.setText(
            f"<b>{len(cues)}</b> {tr('setup.cues_count', n=len(cues)).lower()}"
            f" ({substance})")
        self.neutral_count_label.setText(tr("setup.neutral_count", n=n_neutral))
        self.warning.setVisible(len(cues) == 0)

        mode_page: _ModePage = self.wizard().page(1)
        mode = mode_page.selected_mode()
        self.interspersed_box.setVisible(mode in ("interspersed", "custom"))


# ---------------------------------------------------------------------------
# Page 4 — VAS & Timing
# ---------------------------------------------------------------------------

class _TimingPage(QWizardPage):
    def __init__(self, context: AppContext, citations: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setTitle(tr("wizard.page4_title"))

        # VAS display
        vas_box = QGroupBox(tr("vas.display_label"))
        vas_form = QFormLayout(vas_box)
        self.vas_mode = QComboBox()
        for code, key in [("slider", "vas.display_slider"),
                          ("circles", "vas.display_circles"),
                          ("stars", "vas.display_stars")]:
            self.vas_mode.addItem(tr(key), code)
        vas_form.addRow(tr("vas.display_label"), self.vas_mode)
        vas_form.addRow(_evidence_label(
            tr("wizard.vas_recommendation") + " " + _cite_short(citations, 9, 4, 5)))

        # Periodic VAS
        timing_box = QGroupBox(tr("wizard.page4_title"))
        timing_form = QFormLayout(timing_box)
        self.periodic_sec = QSpinBox()
        self.periodic_sec.setRange(10, 120); self.periodic_sec.setSuffix(" s")
        self.periodic_sec.setValue(30)
        timing_form.addRow(tr("settings.periodic_sec"), self.periodic_sec)

        # Video settings
        self.pause_video = QCheckBox(tr("settings.pause_video_on_rating"))
        self.pause_video.setChecked(True)
        timing_form.addRow(self.pause_video)

        # Habituation
        hab_box = QGroupBox(tr("habituacion" if tr("habituacion") != "habituacion" else "wizard.page4_title"))
        hab_form = QFormLayout(hab_box)
        self.threshold = QSpinBox()
        self.threshold.setRange(0, 10)
        self.threshold.setValue(2)
        self.consecutive = QSpinBox()
        self.consecutive.setRange(1, 10)
        self.consecutive.setValue(2)
        hab_form.addRow(tr("settings.habituation_threshold"), self.threshold)
        hab_form.addRow(tr("settings.habituation_consecutive"), self.consecutive)
        hab_form.addRow(_evidence_label(
            tr("wizard.habituation_recommendation") + " " + _cite_short(citations, 3)))

        # Min exposure (for interspersed)
        self.min_exposure = QSpinBox()
        self.min_exposure.setRange(1, 30); self.min_exposure.setSuffix(" s")
        self.min_exposure.setValue(5)
        timing_form.addRow(tr("setup.min_exposure_sec"), self.min_exposure)

        scroll_inner = QWidget()
        inner = QVBoxLayout(scroll_inner)
        inner.addWidget(vas_box)
        inner.addWidget(timing_box)
        inner.addWidget(hab_box)
        inner.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(scroll_inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        v = QVBoxLayout(self)
        v.addWidget(scroll)


# ---------------------------------------------------------------------------
# Page 5 — Safety & Coping
# ---------------------------------------------------------------------------

class _SafetyPage(QWizardPage):
    def __init__(self, context: AppContext, citations: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setTitle(tr("wizard.page5_title"))

        info = context.crisis.get()

        contacts_box = QGroupBox(tr("settings.contacts_title"))
        contacts_form = QFormLayout(contacts_box)
        self.therapist = QLineEdit(info.therapist_phone)
        self.crisis_line = QLineEdit(info.crisis_line)
        self.emergency = QLineEdit(info.emergency_number)
        contacts_form.addRow(tr("settings.therapist_phone"), self.therapist)
        contacts_form.addRow(tr("settings.crisis_line"), self.crisis_line)
        contacts_form.addRow(tr("settings.emergency"), self.emergency)

        coping_box = QGroupBox(tr("uscs.title") if tr("uscs.title") != "uscs.title" else "USCS")
        coping_form = QFormLayout(coping_box)
        self.auto_coping = QCheckBox(tr("settings.auto_coping_enabled"))
        self.auto_coping.setChecked(True)
        self.coping_threshold = QSpinBox()
        self.coping_threshold.setRange(1, 10)
        self.coping_threshold.setValue(7)
        self.coping_consecutive = QSpinBox()
        self.coping_consecutive.setRange(1, 10)
        self.coping_consecutive.setValue(3)
        coping_form.addRow(self.auto_coping)
        coping_form.addRow(tr("settings.auto_coping_threshold") if tr("settings.auto_coping_threshold") != "settings.auto_coping_threshold" else "Threshold", self.coping_threshold)
        coping_form.addRow("Consecutive", self.coping_consecutive)
        coping_form.addRow(_evidence_label(
            tr("wizard.coping_recommendation") + " " + _cite_short(citations, 1, 2)))

        neutral_box = QGroupBox(tr("setup.dynamic_neutral"))
        neutral_form = QFormLayout(neutral_box)
        self.dynamic_neutral = QCheckBox(tr("setup.dynamic_neutral"))
        self.dynamic_neutral.setChecked(False)
        self.dynamic_threshold = QSpinBox()
        self.dynamic_threshold.setRange(1, 10)
        self.dynamic_threshold.setValue(4)
        neutral_form.addRow(self.dynamic_neutral)
        neutral_form.addRow(tr("setup.dynamic_neutral_threshold"), self.dynamic_threshold)
        neutral_form.addRow(_evidence_label(
            "When craving remains elevated, extending neutral cue runs provides a "
            "natural cooling-off period before the next craving cue "
            + _cite_short(citations, 8) + "."))

        v = QVBoxLayout(self)
        v.addWidget(contacts_box)
        v.addWidget(coping_box)
        v.addWidget(neutral_box)
        v.addStretch(1)

    def initializePage(self) -> None:
        mode_page: _ModePage = self.wizard().page(1)
        mode = mode_page.selected_mode()
        self.dynamic_neutral.setChecked(mode in ("interspersed", "custom"))


# ---------------------------------------------------------------------------
# Page 6 — Summary
# ---------------------------------------------------------------------------

class _SummaryPage(QWizardPage):
    def __init__(self, context: AppContext, citations: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setTitle(tr("wizard.page6_title"))
        self._context = context
        self._citations = citations

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)
        self.summary_label.setStyleSheet("padding:8px;")

        self.apply_check = QCheckBox(tr("wizard.apply_defaults"))
        self.apply_check.setChecked(True)

        refs_btn = QPushButton(tr("wizard.view_references"))
        refs_btn.clicked.connect(self._show_references)

        v = QVBoxLayout(self)
        scroll_inner = QWidget()
        inner = QVBoxLayout(scroll_inner)
        inner.addWidget(self.summary_label)
        inner.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(scroll_inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        v.addWidget(scroll, 1)
        bottom = QHBoxLayout()
        bottom.addWidget(self.apply_check)
        bottom.addStretch(1)
        bottom.addWidget(refs_btn)
        v.addLayout(bottom)

    def initializePage(self) -> None:
        w = self.wizard()
        profile: _ProfilePage = w.page(0)
        mode_p: _ModePage = w.page(1)
        cue_p: _CuePage = w.page(2)
        timing_p: _TimingPage = w.page(3)
        safety_p: _SafetyPage = w.page(4)

        mode = mode_p.selected_mode()
        mode_label = {"intense": tr("mode.intense"),
                      "interspersed": tr("mode.interspersed"),
                      "custom": tr("mode.custom")}.get(mode, mode)

        rows = [
            (tr("wizard.current_status"), profile.status.currentText()),
            (tr("wizard.usage_duration"), profile.duration.currentText()),
            (tr("wizard.page2_title"), f"<b>{mode_label}</b>"),
            (tr("vas.display_label"), timing_p.vas_mode.currentText()),
            (tr("settings.periodic_sec"), f"{timing_p.periodic_sec.value()} s"),
            (tr("settings.habituation_threshold"), str(timing_p.threshold.value())),
            (tr("settings.habituation_consecutive"), str(timing_p.consecutive.value())),
            (tr("settings.pause_video_on_rating"), "✓" if timing_p.pause_video.isChecked() else "✗"),
            (tr("setup.min_exposure_sec"), f"{timing_p.min_exposure.value()} s"),
            (tr("settings.auto_coping_enabled"), "✓" if safety_p.auto_coping.isChecked() else "✗"),
            (tr("setup.dynamic_neutral"), "✓" if safety_p.dynamic_neutral.isChecked() else "✗"),
        ]

        if mode in ("interspersed", "custom"):
            rows.insert(3, (tr("setup.interspersed_pct"), f"{cue_p.craving_pct.value()} %"))

        html = "<table style='border-collapse:collapse; width:100%;'>"
        for i, (label, value) in enumerate(rows):
            bg = "#f7fafa" if i % 2 == 0 else "#ffffff"
            html += (f"<tr style='background:{bg};'>"
                     f"<td style='padding:6px 10px;'>{label}</td>"
                     f"<td style='padding:6px 10px; text-align:right;'>{value}</td></tr>")
        html += "</table>"
        self.summary_label.setText(html)

    def _show_references(self) -> None:
        from .help_dialog import HelpDialog
        dlg = HelpDialog(self)
        dlg.show_topic("references")
        dlg.exec()

    def should_apply(self) -> bool:
        return self.apply_check.isChecked()


# ---------------------------------------------------------------------------
# Main Wizard
# ---------------------------------------------------------------------------

class PatientWizard(QWizard):
    """Six-page evidence-based setup wizard for a patient's CET configuration."""

    def __init__(self, context: AppContext, patient, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.patient = patient
        self._citations = _load_citations()

        self.setWindowTitle(tr("wizard.title"))
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        sw, sh = screen_size()
        self.setMinimumSize(min(680, sw - 40), min(560, sh - 40))
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)

        self._profile = _ProfilePage(context, patient)
        self._mode = _ModePage(context, self._citations)
        self._cue = _CuePage(context, patient, self._citations)
        self._timing = _TimingPage(context, self._citations)
        self._safety = _SafetyPage(context, self._citations)
        self._summary = _SummaryPage(context, self._citations)

        self.addPage(self._profile)
        self.addPage(self._mode)
        self.addPage(self._cue)
        self.addPage(self._timing)
        self.addPage(self._safety)
        self.addPage(self._summary)

    def apply_settings(self) -> None:
        """Persist the wizard choices as the patient's default session params."""
        if not self._summary.should_apply():
            return
        mode = self._mode.selected_mode()
        d = {
            "mode": mode,
            "autoscroll_on_grading": False,
            "autoscroll_timed_seconds": 0,
            "accessibility_kbmode": False,
            "session_time_cap_seconds": self.context.config.session_time_cap_seconds,
            "random_order": False,
            "loop": False,
            "start_fullscreen": False,
        }
        s = self.context.repos.settings
        params_key = f"session_params:{self.patient.id}"
        s.set(params_key, json.dumps(d))

        # Persist individual overridable settings.
        cfg = self.context.config
        cfg.periodic_vas_seconds = self._timing.periodic_sec.value()
        s.set("periodic_vas_seconds", str(cfg.periodic_vas_seconds))
        cfg.habituation_threshold = self._timing.threshold.value()
        s.set("habituation_threshold", str(cfg.habituation_threshold))
        cfg.habituation_consecutive = self._timing.consecutive.value()
        s.set("habituation_consecutive", str(cfg.habituation_consecutive))
        cfg.vas_display_mode = self._timing.vas_mode.currentData()
        s.set("vas_display_mode", cfg.vas_display_mode)
        cfg.pause_video_on_rating = self._timing.pause_video.isChecked()
        s.set("pause_video_on_rating", "1" if cfg.pause_video_on_rating else "0")
        cfg.interspersed_min_exposure_sec = self._timing.min_exposure.value()
        s.set("interspersed_min_exposure_sec", str(cfg.interspersed_min_exposure_sec))
        cfg.default_session_mode = mode
        s.set("default_session_mode", mode)

        if mode in ("interspersed", "custom"):
            cfg.interspersed_craving_pct = self._cue.craving_pct.value()
            s.set("interspersed_craving_pct", str(cfg.interspersed_craving_pct))

        cfg.auto_coping_enabled = self._safety.auto_coping.isChecked()
        s.set("auto_coping_enabled", "1" if cfg.auto_coping_enabled else "0")
        cfg.auto_coping_threshold = self._safety.coping_threshold.value()
        s.set("auto_coping_threshold", str(cfg.auto_coping_threshold))
        cfg.auto_coping_consecutive = self._safety.coping_consecutive.value()
        s.set("auto_coping_consecutive", str(cfg.auto_coping_consecutive))

        cfg.dynamic_neutral_enabled = self._safety.dynamic_neutral.isChecked()
        s.set("dynamic_neutral_enabled", "1" if cfg.dynamic_neutral_enabled else "0")
        cfg.dynamic_neutral_threshold = self._safety.dynamic_threshold.value()
        s.set("dynamic_neutral_threshold", str(cfg.dynamic_neutral_threshold))

        # Save crisis contacts if changed.
        from ...services.crisis import CrisisInfo
        self.context.crisis.save(CrisisInfo(
            therapist_phone=self._safety.therapist.text().strip(),
            crisis_line=self._safety.crisis_line.text().strip(),
            emergency_number=self._safety.emergency.text().strip(),
        ))

        # Mark wizard as complete for this patient.
        s.set(f"wizard_complete:{self.patient.id}", "1")
