"""Per-patient detail: actions, session history, cross-session progress, export."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizard,
)

from ...services import export
from ...services.i18n import tr
from ..context import AppContext
from ..emoji_icon import emoji_icon
from .patient_form import PatientFormDialog

_log = logging.getLogger(__name__)

_END_REASON_KEYS = {
    "habituated": "endreason.habituated",
    "time_cap": "endreason.time_cap",
    "panic": "endreason.panic",
    "clinician_stop": "endreason.clinician_stop",
}


class PatientScreen(QWidget):
    def __init__(self, window, context: AppContext, patient_id: int) -> None:
        super().__init__()
        self.window = window
        self.context = context
        self.patient = context.repos.patients.get(patient_id)

        back = QPushButton(tr("common.back"))
        back.setIcon(emoji_icon("←")); back.setIconSize(QSize(20, 20))
        back.clicked.connect(window.show_dashboard)
        self.title = QLabel(tr("patient.detail_title", code=self.patient.code))
        self.title.setObjectName("H1")
        edit_btn = QPushButton(tr("patient.edit"))
        edit_btn.setIcon(emoji_icon("✏")); edit_btn.setIconSize(QSize(20, 20))
        edit_btn.clicked.connect(self._edit)

        header = QHBoxLayout()
        header.addWidget(back)
        header.addSpacing(10)
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(edit_btn)

        cfg_btn = QPushButton(tr("patient.configure_cues"))
        cfg_btn.setIcon(emoji_icon("\U0001F3AF")); cfg_btn.setIconSize(QSize(20, 20))
        cfg_btn.clicked.connect(lambda: window.show_cue_config(self.patient))
        start_btn = QPushButton(tr("patient.start_session"))
        start_btn.setObjectName("Primary")
        start_btn.setIcon(emoji_icon("▶")); start_btn.setIconSize(QSize(20, 20))
        start_btn.clicked.connect(lambda: window.show_session_setup(self.patient))
        export_btn = QPushButton(tr("patient.export"))
        export_btn.setIcon(emoji_icon("\U0001F4CA")); export_btn.setIconSize(QSize(20, 20))
        export_btn.clicked.connect(self._export)
        report_btn = QPushButton(tr("patient.report"))
        report_btn.setIcon(emoji_icon("\U0001F4CB")); report_btn.setIconSize(QSize(20, 20))
        report_btn.clicked.connect(lambda: window.show_report(self.patient))
        archive_btn = QPushButton(tr("patient.archive"))
        archive_btn.setObjectName("Danger")
        archive_btn.setIcon(emoji_icon("\U0001F4E6")); archive_btn.setIconSize(QSize(20, 20))
        archive_btn.clicked.connect(self._archive)

        wizard_btn = QPushButton(tr("wizard.button"))
        wizard_btn.setIcon(emoji_icon("🧙")); wizard_btn.setIconSize(QSize(20, 20))
        wizard_btn.clicked.connect(self._run_wizard)

        actions = QHBoxLayout()
        actions.addWidget(cfg_btn)
        actions.addWidget(wizard_btn)
        actions.addWidget(start_btn)
        actions.addStretch(1)
        actions.addWidget(report_btn)
        actions.addWidget(export_btn)
        actions.addWidget(archive_btn)

        history_label = QLabel(tr("patient.history"))
        history_label.setObjectName("H2")
        self.history = QListWidget()
        self.empty = QLabel(tr("patient.no_sessions"))
        self.empty.setObjectName("Muted")

        progress_label = QLabel(tr("patient.progress"))
        progress_label.setObjectName("H2")
        self.chart_view = self._build_progress_chart()

        left = QVBoxLayout()
        left.addWidget(history_label)
        left.addWidget(self.empty)
        left.addWidget(self.history, 1)

        right = QVBoxLayout()
        right.addWidget(progress_label)
        right.addWidget(self.chart_view, 1)

        body = QHBoxLayout()
        body.addLayout(left, 1)
        body.addLayout(right, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.addLayout(header)
        layout.addLayout(actions)
        layout.addSpacing(8)
        layout.addLayout(body, 1)

        self._refresh()

    # --- data ---------------------------------------------------------------
    def _sessions(self):
        return self.context.repos.sessions.list_for_patient(self.patient.id)

    def _refresh(self) -> None:
        sessions = self._sessions()
        self.history.clear()
        self.empty.setVisible(not sessions)
        for s in sessions:
            reason = tr(_END_REASON_KEYS.get(s.end_reason, "")) if s.end_reason else "—"
            base = s.baseline_vas if s.baseline_vas is not None else "—"
            end = s.endpoint_vas if s.endpoint_vas is not None else "—"
            item = QListWidgetItem(f"{s.started_at[:16].replace('T', ' ')}   {base} → {end}   ·   {reason}")
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            self.history.addItem(item)
        self._populate_chart(sessions)

    def _build_progress_chart(self) -> QChartView:
        self._chart = QChart()
        self._chart.setTitle(tr("patient.progress"))
        view = QChartView(self._chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._axis_x = QValueAxis()
        self._axis_x.setTitleText(tr("chart.session"))
        self._axis_x.setLabelFormat("%d")
        self._axis_y = QValueAxis()
        self._axis_y.setRange(0, self.context.config.vas_max)
        self._axis_y.setTitleText(tr("chart.craving"))
        self._chart.addAxis(self._axis_x, Qt.AlignmentFlag.AlignBottom)
        self._chart.addAxis(self._axis_y, Qt.AlignmentFlag.AlignLeft)
        return view

    def _populate_chart(self, sessions) -> None:
        self._chart.removeAllSeries()
        finished = [s for s in sessions if s.baseline_vas is not None]
        self._axis_x.setRange(1, max(2, len(finished)))
        series_defs = [
            (tr("summary.baseline"), lambda s: s.baseline_vas),
            (tr("summary.peak"), lambda s: s.peak_vas),
            (tr("summary.endpoint"), lambda s: s.endpoint_vas),
        ]
        for name, getter in series_defs:
            series = QLineSeries()
            series.setName(name)
            for idx, s in enumerate(finished, start=1):
                val = getter(s)
                if val is not None:
                    series.append(idx, val)
            self._chart.addSeries(series)
            series.attachAxis(self._axis_x)
            series.attachAxis(self._axis_y)

    def _run_wizard(self) -> None:
        from .patient_wizard import PatientWizard
        wizard = PatientWizard(self.context, self.patient, self)
        if wizard.exec() == QWizard.DialogCode.Accepted:
            wizard.apply_settings()
            self._refresh()

    # --- export -------------------------------------------------------------
    def _export(self) -> None:
        sessions = self._sessions()
        if not sessions:
            QMessageBox.information(self, tr("app.title"), tr("patient.no_sessions"))
            return
        default = str(Path(self.context.config.data_dir) / export.safe_filename(self.patient.code, "summary"))
        path, _ = QFileDialog.getSaveFileName(self, tr("patient.export"), default, "CSV (*.csv)")
        if not path:
            return
        try:
            export.export_sessions_summary(Path(path), self.patient.code, sessions)
        except OSError as exc:
            _log.exception("CSV summary export failed: %s", exc)
            QMessageBox.warning(self, tr("app.title"), tr("report.export_failed"))
            return
        QMessageBox.information(self, tr("app.title"), tr("summary.saved"))

    def _edit(self) -> None:
        dialog = PatientFormDialog(self.context, self, self.patient)
        if dialog.exec():
            self.patient = self.context.repos.patients.get(self.patient.id)
            self.title.setText(tr("patient.detail_title", code=self.patient.code))
            self._refresh()

    def _archive(self) -> None:
        confirm = QMessageBox.question(
            self, tr("app.title"), tr("patient.archive_confirm", code=self.patient.code))
        if confirm == QMessageBox.StandardButton.Yes:
            self.patient.archived = True
            self.context.repos.patients.update(self.patient)
            self.window.show_dashboard()
