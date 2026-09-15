"""End-of-session summary: VAS deltas, habituation slope, craving curve, export."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...services import export
from ...services.i18n import tr
from ..context import AppContext
from ..emoji_icon import emoji_icon
from ..widgets.craving_chart import CravingChart

_log = logging.getLogger(__name__)

_END_REASON_KEYS = {
    "habituated": "endreason.habituated", "time_cap": "endreason.time_cap",
    "panic": "endreason.panic", "clinician_stop": "endreason.clinician_stop",
}


def _duration(session) -> str:
    if not session.ended_at:
        return "—"
    try:
        start = datetime.fromisoformat(session.started_at)
        end = datetime.fromisoformat(session.ended_at)
        secs = int((end - start).total_seconds())
        return f"{secs // 60} min {secs % 60} s"
    except ValueError:
        return "—"


class SummaryScreen(QWidget):
    def __init__(self, window, context: AppContext, session, patient) -> None:
        super().__init__()
        self.window = window
        self.context = context
        self.session = session
        self.patient = patient

        title = QLabel(tr("summary.title"))
        title.setObjectName("H1")

        base = session.baseline_vas
        end = session.endpoint_vas
        change = "—" if (base is None or end is None) else f"{end - base:+d}"
        slope = "—" if session.habituation_slope is None else f"{session.habituation_slope:.4f}"

        card = QFrame(); card.setObjectName("Card")
        form = QFormLayout(card)
        form.setContentsMargins(24, 20, 24, 20)
        form.setSpacing(10)
        form.addRow(tr("summary.baseline"), QLabel(str(base if base is not None else "—")))
        form.addRow(tr("summary.peak"), QLabel(str(session.peak_vas if session.peak_vas is not None else "—")))
        form.addRow(tr("summary.endpoint"), QLabel(str(end if end is not None else "—")))
        form.addRow(tr("summary.change"), QLabel(change))
        form.addRow(tr("summary.slope"), QLabel(slope))
        form.addRow(tr("summary.duration"), QLabel(_duration(session)))
        reason = tr(_END_REASON_KEYS.get(session.end_reason, "")) if session.end_reason else "—"
        form.addRow(tr("summary.end_reason"), QLabel(reason))
        mode_key = {"intense": "mode.intense", "interspersed": "mode.interspersed",
                     "custom": "mode.custom"}.get(getattr(session, "mode", "intense"), "mode.intense")
        form.addRow(tr("mode.label"), QLabel(tr(mode_key)))

        slope_hint = QLabel(tr("summary.slope_hint"))
        slope_hint.setObjectName("Muted")
        slope_hint.setWordWrap(True)

        curve_label = QLabel(tr("summary.curve"))
        curve_label.setObjectName("H2")
        chart = CravingChart(context.config.vas_max)
        chart.setMinimumHeight(260)
        ratings = context.repos.ratings.list_for_session(session.id)
        chart.set_points([(float(r.elapsed_sec), float(r.value)) for r in ratings])

        saved = QLabel(tr("summary.saved"))
        saved.setObjectName("Muted")

        export_btn = QPushButton(tr("summary.export"))
        export_btn.setIcon(emoji_icon("\U0001F4CA"))
        export_btn.clicked.connect(self._export)
        finish_btn = QPushButton(tr("summary.finish"))
        finish_btn.setIcon(emoji_icon("✅"))
        finish_btn.setObjectName("Primary")
        finish_btn.clicked.connect(lambda: window.show_patient(patient.id))

        buttons = QHBoxLayout()
        buttons.addWidget(saved)
        buttons.addStretch(1)
        buttons.addWidget(export_btn)
        buttons.addWidget(finish_btn)

        left = QVBoxLayout()
        left.addWidget(card)
        left.addWidget(slope_hint)
        left.addStretch(1)

        right = QVBoxLayout()
        right.addWidget(curve_label)
        right.addWidget(chart, 1)

        body = QHBoxLayout()
        body.addLayout(left, 1)
        body.addLayout(right, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.addWidget(title)
        layout.addLayout(body, 1)
        layout.addLayout(buttons)

    def _export(self) -> None:
        repos = self.context.repos
        default = str(Path(self.context.config.data_dir) /
                      export.safe_filename(self.patient.code, f"session{self.session.id}"))
        path, _ = QFileDialog.getSaveFileName(self, tr("summary.export"), default, "CSV (*.csv)")
        if not path:
            return
        try:
            export.export_session_timeline(
                Path(path), self.patient.code, self.session,
                repos.ratings.list_for_session(self.session.id),
                repos.coping.list_for_session(self.session.id),
                repos.intensity.list_for_session(self.session.id),
            )
        except OSError as exc:
            _log.exception("CSV export failed: %s", exc)
            QMessageBox.warning(self, tr("app.title"), tr("report.export_failed"))
            return
        QMessageBox.information(self, tr("app.title"), tr("summary.saved"))
