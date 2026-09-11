"""Clinical report screen: per-session detail + cross-session progress + PDF/PNG export.

Built from the data the app already records (ratings, coping events, intensity events,
sessions). Pure aggregation lives in :mod:`cravingcrave.domain.reports`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from html import escape as _html_escape
from pathlib import Path

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QLineSeries,
    QScatterSeries,
    QValueAxis,
)
from PySide6.QtCore import QMarginsF, QSizeF, Qt, QUrl
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ... import paths
from ...domain import reports
from ...services import export
from ...services.i18n import tr
from ..context import AppContext
from ..emoji_icon import emoji_icon

_log = logging.getLogger(__name__)

# Stable colours for the 4 USCS skills (used in detail chart + bar charts).
SKILL_LABELS = {
    "name_feeling":       ("uscs.name_feeling.title",       QColor("#2a9d8f")),
    "recall_negative":    ("uscs.recall_negative.title",    QColor("#e76f51")),
    "recall_benefit":     ("uscs.recall_benefit.title",     QColor("#f4a261")),
    "alternative_action": ("uscs.alternative_action.title", QColor("#264653")),
}
END_REASON_KEYS = {
    "habituated": "endreason.habituated", "time_cap": "endreason.time_cap",
    "panic": "endreason.panic", "clinician_stop": "endreason.clinician_stop",
}


def _short(media_path: str) -> str:
    return media_path.split("/")[-1] if media_path else "—"


def _fmt(value, suffix: str = "", decimals: int | None = None) -> str:
    if value is None:
        return "—"
    if decimals is not None:           # decimals=0 must still round (e.g. "56%")
        return f"{value:.{decimals}f}{suffix}"
    return f"{value}{suffix}"


def _metrics_table_html(m: dict) -> str:
    """2-column HTML table of the session metrics (for the PDF)."""
    cells = "".join(
        f"<tr><td style='padding:4px 8px'><b>{label}</b></td>"
        f"<td style='padding:4px 8px;text-align:right'>{value}</td></tr>"
        for label, value in _metric_rows(m)
    )
    return (f"<table border='1' cellpadding='6' cellspacing='0' "
            f"style='font-size:11pt;border-collapse:collapse'>{cells}</table>")


def _metric_rows(m: dict) -> list[tuple[str, str]]:
    """(label, value) rows for the session-metrics table — shared by screen + PDF."""
    return [
        (tr("report.m_baseline"),   _fmt(m["baseline"])),
        (tr("report.m_peak"),       _fmt(m["peak"])),
        (tr("report.m_endpoint"),   _fmt(m["endpoint"])),
        (tr("report.m_mean_exp"),   _fmt(m["mean_exposure"], decimals=1)),
        (tr("report.m_reactivity"), _fmt(m["cue_reactivity"])),
        (tr("report.m_pct_red"),    _fmt(m["pct_reduction"], suffix="%", decimals=0)),
        (tr("report.m_time_peak"),  _fmt(m["time_to_peak_sec"], suffix=" s")),
        (tr("report.m_slope"),      _fmt(m["slope"], decimals=4)),
    ]


class ReportScreen(QWidget):
    def __init__(self, window, context: AppContext, patient) -> None:
        super().__init__()
        self.window = window
        self.context = context
        self.patient = patient
        # Width (px) for chart images embedded in the PDF; recomputed per export from
        # the writer's printable area so graphs fill the page and are never cropped.
        self._pdf_img_width = 1600

        back = QPushButton(tr("common.back"))
        back.setIcon(emoji_icon("←"))
        back.clicked.connect(lambda: window.show_patient(patient.id))
        title = QLabel(tr("report.title", code=patient.code))
        title.setObjectName("H1")
        header = QHBoxLayout()
        header.addWidget(back); header.addSpacing(10); header.addWidget(title); header.addStretch(1)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_session_tab(), tr("report.tab_session"))
        self.tabs.addTab(self._build_progress_tab(), tr("report.tab_progress"))

        self.include_notes = QCheckBox(tr("report.include_notes"))
        self.include_notes.setChecked(True)
        export_png = QPushButton(tr("report.export_png"))
        export_png.setIcon(emoji_icon("\U0001F4F8"))
        export_png.clicked.connect(self._export_png)
        export_coping = QPushButton(tr("report.export_coping"))
        export_coping.setIcon(emoji_icon("\U0001F4CA"))
        export_coping.clicked.connect(self._export_coping_csv)
        export_pdf = QPushButton(tr("report.export_pdf_session"))
        export_pdf.setIcon(emoji_icon("\U0001F4C4"))
        export_pdf.clicked.connect(self._export_pdf)
        export_pdf_full = QPushButton(tr("report.export_pdf_full"))
        export_pdf_full.setIcon(emoji_icon("\U0001F4C4"))
        export_pdf_full.setObjectName("Primary")
        export_pdf_full.clicked.connect(self._export_pdf_full)
        export_dwell = QPushButton(tr("report.export_dwell_csv"))
        export_dwell.setIcon(emoji_icon("\U0001F4CA"))
        export_dwell.clicked.connect(self._export_dwell_csv)
        actions = QHBoxLayout()
        actions.addWidget(self.include_notes); actions.addStretch(1)
        actions.addWidget(export_dwell); actions.addWidget(export_png)
        actions.addWidget(export_coping)
        actions.addWidget(export_pdf); actions.addWidget(export_pdf_full)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 24, 36, 24)
        layout.addLayout(header)
        layout.addWidget(self.tabs, 1)
        layout.addLayout(actions)

        self._populate()

    # ---- data helpers ------------------------------------------------------
    def _finished_sessions(self):
        return [s for s in self.context.repos.sessions.list_for_patient(self.patient.id)
                if s.baseline_vas is not None]

    def _patient_cue_index(self):
        return {c.id: c for c in self.context.repos.cues.list_for_patient(self.patient.id)}

    # ---- session-detail tab ------------------------------------------------
    @staticmethod
    def _card(title: str, *items) -> QFrame:
        """A titled 'Card' frame holding the given widgets/layouts (groups content
        so the two-column report reads cleanly instead of one long stack)."""
        card = QFrame(); card.setObjectName("Card")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(14, 12, 14, 12); cv.setSpacing(8)
        heading = QLabel(title); heading.setObjectName("H2")
        cv.addWidget(heading)
        for it in items:
            if isinstance(it, QLayout):
                cv.addLayout(it)
            else:
                cv.addWidget(it)
        return card

    def _build_session_tab(self) -> QWidget:
        outer = QWidget(); ov = QVBoxLayout(outer)
        ov.setSpacing(12)

        # Session selector drives both columns — keep it on top, full width.
        sel = QHBoxLayout()
        sel.addWidget(QLabel(tr("report.choose_session")))
        self.session_combo = QComboBox()
        self.session_combo.currentIndexChanged.connect(self._refresh_session)
        sel.addWidget(self.session_combo, 1)
        ov.addLayout(sel)

        # --- widgets (created here, arranged into cards below) ---
        self.detail_chart_view = QChartView()
        self.detail_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.detail_chart_view.setMinimumHeight(260)

        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(2)
        self.metrics_table.horizontalHeader().setVisible(False)
        self.metrics_table.verticalHeader().setVisible(False)
        self.metrics_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.metrics_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        caveat = QLabel(tr("report.exploratory_caveat")); caveat.setObjectName("Muted"); caveat.setWordWrap(True)

        self.cue_table = QTableWidget()
        self.cue_table.setColumnCount(6)
        self.cue_table.setHorizontalHeaderLabels(
            [tr("report.dwell_col_cue"), tr("report.dwell_col_dwell"),
             tr("report.dwell_col_views"), tr("report.dwell_col_mean"),
             tr("report.dwell_col_peak"), tr("report.dwell_col_reactivity")])
        self.cue_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cue_table.setMaximumHeight(160)

        self.dwell_summary = QLabel()
        self.dwell_summary.setWordWrap(True)
        self.dwell_summary.setStyleSheet("font-size: 13px; padding: 6px 0;")

        self.coping_table = QTableWidget()
        self.coping_table.setColumnCount(3)
        self.coping_table.setHorizontalHeaderLabels(
            [tr("report.col_time"), tr("report.col_skill"), tr("report.col_response")])
        self.coping_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.coping_table.verticalHeader().setVisible(False)
        self.coping_table.setWordWrap(True)
        self.coping_table.setTextElideMode(Qt.TextElideMode.ElideNone)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setMinimumHeight(90)
        save_notes = QPushButton(tr("report.save_notes"))
        save_notes.setIcon(emoji_icon("\U0001F4BE"))
        save_notes.clicked.connect(self._save_notes)
        notes_btn_row = QHBoxLayout(); notes_btn_row.addStretch(1); notes_btn_row.addWidget(save_notes)

        # --- two columns of grouped cards ---
        left = QVBoxLayout(); left.setSpacing(12)
        left.addWidget(self._card(tr("report.card_chart"), self.detail_chart_view), 3)
        left.addWidget(self._card(tr("report.metrics"), self.metrics_table, caveat), 2)

        right = QVBoxLayout(); right.setSpacing(12)
        right.addWidget(self._card(tr("report.dwell_title"), self.cue_table, self.dwell_summary), 3)
        right.addWidget(self._card(tr("report.coping_text"), self.coping_table), 2)
        right.addWidget(self._card(tr("report.clinician_notes"), self.notes_edit, notes_btn_row), 2)

        cols = QHBoxLayout(); cols.setSpacing(14)
        cols.addLayout(left, 1); cols.addLayout(right, 1)
        ov.addLayout(cols, 1)

        # Scroll wrapper keeps it usable when the window is short.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(outer)
        return scroll

    def _save_notes(self) -> None:
        sid = self.session_combo.currentData()
        if sid is None:
            return
        notes = self.notes_edit.toPlainText().strip() or None
        self.context.repos.sessions.update_notes(sid, notes)
        self._update_notes_badge(bool(notes))
        QMessageBox.information(self, tr("app.title"), tr("report.notes_saved"))

    def _update_dwell_summary(self, analysis: list[dict], cue_index: dict) -> None:
        """Build the text summary below the per-cue table."""
        if not analysis:
            self.dwell_summary.setText(tr("report.no_dwell_data"))
            return

        lines: list[str] = []
        # Highest craving cue
        with_craving = [a for a in analysis if a["mean_craving"] is not None]
        if with_craving:
            top = max(with_craving, key=lambda a: a["mean_craving"])
            cue = cue_index.get(top["cue_config_id"])
            name = _short(cue.media_path) if cue else "—"
            mean_str = f"{top['mean_craving']:.1f}"
            lines.append(
                f"🔴 <b>{tr('report.dwell_highest_craving')}</b>: {name} — "
                f"{tr('report.dwell_summary_craving', mean=mean_str, peak=top['peak_craving'])}"
            )

        # Longest dwell cue
        longest = reports.highest_dwell_cue(analysis)
        if longest:
            cue = cue_index.get(longest["cue_config_id"])
            name = _short(cue.media_path) if cue else "—"
            lines.append(
                f"⏱ <b>{tr('report.dwell_longest_viewing')}</b>: {name} — "
                f"{tr('report.dwell_summary_dwell', seconds=longest['total_dwell_sec'], views=longest['view_count'])}"
            )

        # Most challenging (combined)
        provocative = reports.most_provocative_cue(analysis)
        if provocative:
            cue = cue_index.get(provocative["cue_config_id"])
            name = _short(cue.media_path) if cue else "—"
            lines.append(
                f"⚠ <b>{tr('report.dwell_most_challenging')}</b>: {name} — "
                f"{tr('report.dwell_summary_combined')}"
            )

        self.dwell_summary.setText("<br>".join(lines) if lines else tr("report.no_dwell_data"))
        self.dwell_summary.setTextFormat(Qt.TextFormat.RichText)

    def _export_dwell_csv(self) -> None:
        """Export per-cue dwell + craving analysis for the selected session."""
        sid = self.session_combo.currentData()
        if sid is None:
            return
        session = self.context.repos.sessions.get(sid)
        ratings = self.context.repos.ratings.list_for_session(sid)
        dwell_events = self.context.repos.cue_dwell.list_for_session(sid)
        analysis = reports.per_cue_analysis(ratings, dwell_events)

        if not analysis:
            QMessageBox.information(self, tr("app.title"), tr("report.no_dwell_data"))
            return

        cue_index = self._patient_cue_index()
        cue_names = {cid: _short(c.media_path) for cid, c in cue_index.items()}

        default_name = export.safe_filename(self.patient.code, "per_cue_analysis")
        path, _ = QFileDialog.getSaveFileName(self, tr("report.export_dwell_csv"),
                                               default_name, "CSV (*.csv)")
        if not path:
            return
        export.export_session_dwell(Path(path), self.patient.code, session, analysis, cue_names)
        QMessageBox.information(self, tr("app.title"), tr("export.saved", path=path))

    def _refresh_session(self, _idx: int) -> None:
        sid = self.session_combo.currentData()
        if sid is None:
            return
        ratings = self.context.repos.ratings.list_for_session(sid)
        coping = self.context.repos.coping.list_for_session(sid)
        intensity = self.context.repos.intensity.list_for_session(sid)
        cue_index = self._patient_cue_index()

        sel = self.context.repos.sessions.get(sid)

        # --- detail chart (reused by the full-patient PDF too) ------------
        self.detail_chart_view.setChart(self._build_detail_chart(ratings, coping, intensity))

        # --- session metrics ----------------------------------------------
        self._fill_metrics_table(reports.session_metrics(sel, ratings))

        # --- per-cue table with dwell data -----------------------------------
        dwell_events = self.context.repos.cue_dwell.list_for_session(sid)
        analysis = reports.per_cue_analysis(ratings, dwell_events)
        top_id = reports.highest_reactivity_cue_id(ratings)
        self.cue_table.setRowCount(len(analysis))
        for row, info in enumerate(analysis):
            cue = cue_index.get(info["cue_config_id"])
            cells = [
                _short(cue.media_path) if cue else "—",
                str(info["total_dwell_sec"]),
                str(info["view_count"]),
                _fmt(info["mean_craving"], decimals=1),
                _fmt(info["peak_craving"]),
                _fmt(info["cue_reactivity"], decimals=0) if info["cue_reactivity"] is not None else "—",
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if info["cue_config_id"] == top_id:
                    f = item.font(); f.setBold(True); item.setFont(f)
                self.cue_table.setItem(row, col, item)

        # --- dwell summary text ----------------------------------------------
        self._update_dwell_summary(analysis, cue_index)

        # --- coping table (structured: time | skill | response) ------------
        self.coping_table.setRowCount(len(coping))
        for row, e in enumerate(coping):
            skill_label = tr(SKILL_LABELS[e.skill][0]) if e.skill in SKILL_LABELS else e.skill
            self.coping_table.setItem(row, 0, QTableWidgetItem(f"{e.elapsed_sec}s"))
            self.coping_table.setItem(row, 1, QTableWidgetItem(skill_label))
            self.coping_table.setItem(row, 2, QTableWidgetItem(e.detail or "—"))
        self.coping_table.resizeRowsToContents()

        # --- clinician notes ----------------------------------------------
        self.notes_edit.setPlainText((sel.clinician_notes if sel else "") or "")

    def _fill_metrics_table(self, m: dict) -> None:
        rows = _metric_rows(m)
        self.metrics_table.setRowCount(len(rows))
        for r, (label, value) in enumerate(rows):
            k = QTableWidgetItem(label); f = k.font(); f.setBold(True); k.setFont(f)
            self.metrics_table.setItem(r, 0, k)
            self.metrics_table.setItem(r, 1, QTableWidgetItem(value))

    # ---- cross-session tab -------------------------------------------------
    def _build_progress_tab(self) -> QWidget:
        w = QWidget(); v = QVBoxLayout(w)

        v.addWidget(QLabel(tr("patient.progress")))
        self.trends_view = QChartView(); self.trends_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.trends_view.setMinimumHeight(220)
        v.addWidget(self.trends_view, 1)

        v.addWidget(QLabel(tr("report.slope_trend")))
        self.slope_view = QChartView(); self.slope_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.slope_view.setMinimumHeight(160)
        v.addWidget(self.slope_view, 1)

        v.addWidget(QLabel(tr("report.recovery_trend")))
        self.recovery_view = QChartView(); self.recovery_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.recovery_view.setMinimumHeight(160)
        v.addWidget(self.recovery_view, 1)

        bottom = QHBoxLayout()
        self.skills_view = QChartView(); self.skills_view.setMinimumHeight(180)
        self.skills_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.reasons_view = QChartView(); self.reasons_view.setMinimumHeight(180)
        self.reasons_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        left = QVBoxLayout(); left.addWidget(QLabel(tr("report.coping_mix"))); left.addWidget(self.skills_view, 1)
        right = QVBoxLayout(); right.addWidget(QLabel(tr("report.end_reasons"))); right.addWidget(self.reasons_view, 1)
        bottom.addLayout(left, 1); bottom.addLayout(right, 1)
        v.addLayout(bottom, 1)
        return w

    def _populate(self) -> None:
        sessions = self._finished_sessions()
        self.session_combo.blockSignals(True)
        self.session_combo.clear()
        for s in sessions:
            reason = tr(END_REASON_KEYS.get(s.end_reason, "")) if s.end_reason else "—"
            label = f"{s.started_at[:16].replace('T', ' ')}   ·   {reason}"
            if s.clinician_notes:
                label += f"   · {tr('report.notes_badge')}"
            self.session_combo.addItem(label, s.id)
        self.session_combo.blockSignals(False)
        if sessions:
            self._refresh_session(0)
        self._populate_progress(sessions)

    def _update_notes_badge(self, has_notes: bool) -> None:
        """Toggle the 'Notas' badge on the currently-selected session label."""
        idx = self.session_combo.currentIndex()
        if idx < 0:
            return
        badge = f"   · {tr('report.notes_badge')}"
        label = self.session_combo.itemText(idx)
        if has_notes and badge not in label:
            self.session_combo.setItemText(idx, label + badge)
        elif not has_notes and badge in label:
            self.session_combo.setItemText(idx, label.replace(badge, ""))

    def _populate_progress(self, sessions) -> None:
        self.trends_view.setChart(self._build_trends_chart(sessions))
        self.slope_view.setChart(self._build_slope_chart(sessions))
        self.recovery_view.setChart(self._build_recovery_chart(sessions))
        self.skills_view.setChart(self._build_skills_chart(sessions))
        self.reasons_view.setChart(self._build_reasons_chart(sessions))

    def _build_trends_chart(self, sessions) -> QChart:
        """Baseline / peak / endpoint / mean-exposure craving vs session index."""
        max_y = self.context.config.vas_max
        chart = QChart(); chart.setTitle(tr("patient.progress"))
        ax_x = QValueAxis(); ax_y = QValueAxis()
        ax_x.setTitleText(tr("chart.session")); ax_x.setLabelFormat("%d")
        ax_y.setRange(0, max_y); ax_y.setTitleText(tr("chart.craving"))
        chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom); chart.addAxis(ax_y, Qt.AlignmentFlag.AlignLeft)
        trends = reports.metric_trends(sessions)
        defs = [
            (tr("summary.baseline"), [(i, s.baseline_vas) for i, s in enumerate(sessions, 1)]),
            (tr("summary.peak"),     [(i, s.peak_vas) for i, s in enumerate(sessions, 1)]),
            (tr("summary.endpoint"), [(i, s.endpoint_vas) for i, s in enumerate(sessions, 1)]),
            (tr("report.m_mean_exp"), trends["mean_exposure"]),
        ]
        for name, pts in defs:
            series = QLineSeries(); series.setName(name)
            for i, v in pts:
                if v is not None:
                    series.append(i, v)
            chart.addSeries(series); series.attachAxis(ax_x); series.attachAxis(ax_y)
        n = max(2, len(sessions))
        ax_x.setRange(1, n); ax_x.setTickCount(n); ax_x.setLabelFormat("%d")
        return chart

    def _build_slope_chart(self, sessions) -> QChart:
        chart = QChart(); chart.setTitle(tr("report.slope_trend"))
        sx = QValueAxis(); sy = QValueAxis()
        sx.setTitleText(tr("chart.session")); sx.setLabelFormat("%d")
        sy.setTitleText(tr("summary.slope"))
        chart.addAxis(sx, Qt.AlignmentFlag.AlignBottom); chart.addAxis(sy, Qt.AlignmentFlag.AlignLeft)
        series = QLineSeries(); series.setName(tr("summary.slope"))
        pts = reports.session_slopes(sessions)
        for i, v in pts:
            series.append(i, v)
        chart.addSeries(series); series.attachAxis(sx); series.attachAxis(sy)
        if pts:
            n = max(2, len(pts))
            sx.setRange(1, n); sx.setTickCount(n); sx.setLabelFormat("%d")
            ys = [v for _, v in pts]
            sy.setRange(min(0.0, min(ys)) - 0.05, max(0.0, max(ys)) + 0.05)
        return chart

    def _build_recovery_chart(self, sessions) -> QChart:
        """Between-session spontaneous recovery (baseline − prev endpoint)."""
        chart = QChart(); chart.setTitle(tr("report.recovery_trend"))
        rx = QValueAxis(); ry = QValueAxis()
        rx.setTitleText(tr("chart.session")); rx.setLabelFormat("%d")
        ry.setTitleText(tr("report.m_recovery"))
        chart.addAxis(rx, Qt.AlignmentFlag.AlignBottom); chart.addAxis(ry, Qt.AlignmentFlag.AlignLeft)
        series = QLineSeries(); series.setName(tr("report.m_recovery"))
        pts = [(i, v) for i, v in reports.spontaneous_recovery(sessions) if v is not None]
        for i, v in pts:
            series.append(i, v)
        chart.addSeries(series); series.attachAxis(rx); series.attachAxis(ry)
        if pts:
            n = max(2, len(sessions))
            rx.setRange(1, n); rx.setTickCount(n); rx.setLabelFormat("%d")
            ys = [v for _, v in pts]
            ry.setRange(min(0.0, min(ys)) - 0.5, max(0.0, max(ys)) + 0.5)
        return chart

    def _build_skills_chart(self, sessions) -> QChart:
        all_coping = []
        for s in sessions:
            all_coping.extend(self.context.repos.coping.list_for_session(s.id))
        return _bar_chart(
            reports.coping_skill_counts(all_coping),
            label_fn=lambda k: tr(SKILL_LABELS.get(k, (k, None))[0]) if k in SKILL_LABELS else k,
            title=tr("report.coping_mix"),
        )

    def _build_reasons_chart(self, sessions) -> QChart:
        return _bar_chart(
            reports.end_reason_counts(sessions),
            label_fn=lambda k: tr(END_REASON_KEYS.get(k, "")) or k,
            title=tr("report.end_reasons"),
        )

    # ---- exports -----------------------------------------------------------
    def _current_chart_view(self) -> QChartView | None:
        return self.detail_chart_view if self.tabs.currentIndex() == 0 else self.trends_view

    def _export_png(self) -> None:
        view = self._current_chart_view()
        if view is None or view.chart() is None:
            return
        default = str(Path(self.context.config.data_dir) /
                      export.safe_filename(self.patient.code, "chart").replace(".csv", ".png"))
        path, _ = QFileDialog.getSaveFileName(self, tr("report.export_png"), default, "PNG (*.png)")
        if not path:
            return
        try:
            ok = view.grab().save(path)
        except OSError as exc:
            ok = False
            _log.exception("PNG export failed: %s", exc)
        self._notify_export(ok)

    @staticmethod
    def _skill_label_map() -> dict[str, str]:
        """skill key -> localized label, from the shared SKILL_LABELS table."""
        return {skill: tr(label_key) for skill, (label_key, _color) in SKILL_LABELS.items()}

    def _export_coping_csv(self) -> None:
        """Analysis-ready CSV of every USCS coping free-text response, for qualitative study."""
        default = str(Path(self.context.config.data_dir) /
                      export.safe_filename(self.patient.code, "coping"))
        path, _ = QFileDialog.getSaveFileName(self, tr("report.export_coping"), default, "CSV (*.csv)")
        if not path:
            return
        sessions = self._finished_sessions()
        sessions_coping = [(s, self.context.repos.coping.list_for_session(s.id)) for s in sessions]
        try:
            export.export_coping_responses(Path(path), self.patient.code, sessions_coping,
                                           self._skill_label_map())
            ok = Path(path).exists() and Path(path).stat().st_size > 0
        except OSError as exc:
            ok = False
            _log.exception("Coping CSV export failed: %s", exc)
        self._notify_export(ok)

    def _notify_export(self, ok: bool) -> None:
        """Show a success or failure dialog for an export instead of always claiming success."""
        if ok:
            QMessageBox.information(self, tr("app.title"), tr("summary.saved"))
        else:
            QMessageBox.warning(self, tr("app.title"), tr("report.export_failed"))

    def _new_landscape_doc(self, path: str):
        """A4-landscape QPdfWriter + QTextDocument laid out to the printable area.

        Returns (writer, doc). Sets ``self._pdf_img_width`` to the printable width in
        px so embedded charts fill the page exactly and are never clipped (QTextDocument
        clips overflow rather than scaling, so the width must match the content area)."""
        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Landscape)
        writer.setResolution(200)
        writer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)
        paint = writer.pageLayout().paintRectPixels(writer.resolution())
        self._pdf_img_width = int(paint.width())          # charts fill the printable width
        doc = QTextDocument()
        doc.setPageSize(QSizeF(paint.width(), paint.height()))
        doc.setDocumentMargin(0)
        return writer, doc

    def _export_pdf(self) -> None:
        default = str(Path(self.context.config.data_dir) /
                      export.safe_filename(self.patient.code, "report").replace(".csv", ".pdf"))
        path, _ = QFileDialog.getSaveFileName(self, tr("report.export_pdf_session"), default, "PDF (*.pdf)")
        if not path:
            return

        sessions = self._finished_sessions()
        sid = self.session_combo.currentData()
        sel = next((s for s in sessions if s.id == sid), None)

        writer, doc = self._new_landscape_doc(path)
        self._add_logo_resource(doc)
        if sel is not None:
            ratings = self.context.repos.ratings.list_for_session(sel.id)
            coping = self.context.repos.coping.list_for_session(sel.id)
            intensity = self.context.repos.intensity.list_for_session(sel.id)
            doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("img://detail"),
                            _print_chart_pixmap(self._build_detail_chart(ratings, coping, intensity)))
        doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("img://trends"),
                        _print_chart_pixmap(self._build_trends_chart(sessions)))
        doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("img://slope"),
                        _print_chart_pixmap(self._build_slope_chart(sessions)))
        doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("img://recovery"),
                        _print_chart_pixmap(self._build_recovery_chart(sessions)))
        doc.setHtml(self._build_html())
        try:
            doc.print_(writer)
            ok = Path(path).exists() and Path(path).stat().st_size > 0
        except OSError as exc:
            ok = False
            _log.exception("Session PDF export failed: %s", exc)
        self._notify_export(ok)

    # ---- full per-patient PDF (every session, with changes-between view) ---
    def _export_pdf_full(self) -> None:
        default = str(Path(self.context.config.data_dir) /
                      export.safe_filename(self.patient.code, "report_full").replace(".csv", ".pdf"))
        path, _ = QFileDialog.getSaveFileName(self, tr("report.export_pdf_full"), default, "PDF (*.pdf)")
        if not path:
            return

        sessions = self._finished_sessions()
        cue_index = self._patient_cue_index()

        writer, doc = self._new_landscape_doc(path)
        self._add_logo_resource(doc)
        # Cross-session charts via the print theme.
        doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("img://trends"),
                        _print_chart_pixmap(self._build_trends_chart(sessions)))
        doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("img://slope"),
                        _print_chart_pixmap(self._build_slope_chart(sessions)))
        doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("img://recovery"),
                        _print_chart_pixmap(self._build_recovery_chart(sessions)))
        # One freshly-rendered annotated chart per session.
        for s in sessions:
            ratings = self.context.repos.ratings.list_for_session(s.id)
            coping = self.context.repos.coping.list_for_session(s.id)
            intensity = self.context.repos.intensity.list_for_session(s.id)
            chart = self._build_detail_chart(ratings, coping, intensity)
            doc.addResource(QTextDocument.ResourceType.ImageResource,
                            QUrl(f"img://session-{s.id}"), _print_chart_pixmap(chart))

        doc.setHtml(self._build_full_html(sessions, cue_index))
        try:
            doc.print_(writer)
            ok = Path(path).exists() and Path(path).stat().st_size > 0
        except OSError as exc:
            ok = False
            _log.exception("Full-patient PDF export failed: %s", exc)
        self._notify_export(ok)

    # ---- PDF header (clinic logo + name) -----------------------------------
    def _resolve_logo_path(self) -> str | None:
        """The clinic's configured logo if set and valid, otherwise the bundled CETUS
        brand mark (so reports carry CETUS branding by default, overridable per clinic)."""
        path = self.context.repos.settings.get("clinic_logo_path")
        if path and Path(path).is_file():
            return path
        default = paths.resource_path("icons", "cetus.png")
        return str(default) if default.is_file() else None

    def _add_logo_resource(self, doc: QTextDocument) -> bool:
        """Load the header logo (clinic logo or bundled CETUS mark) as ``img://logo``.
        Returns True if a usable logo was found."""
        path = self._resolve_logo_path()
        if not path:
            return False
        img = QImage(path)
        if img.isNull():
            return False
        if img.width() > 320:   # keep header logo a sane size
            img = img.scaledToWidth(320, Qt.TransformationMode.SmoothTransformation)
        doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("img://logo"), img)
        return True

    def _header_html(self, title: str, has_logo: bool) -> str:
        s = self.context.repos.settings
        clinic = (s.get("clinic_name") or "").strip()
        # Optional clinic contact line (address · email · phone), set in the Admin Center.
        contact = "  ·  ".join(
            x for x in ((s.get("clinic_address") or "").strip(),
                        (s.get("clinic_email") or "").strip(),
                        (s.get("clinic_phone") or "").strip()) if x)
        logo_cell = "<td><img src='img://logo' height='64'></td>" if has_logo else ""
        clinic_html = f"<div style='color:#555;font-size:12pt'>{_html_escape(clinic)}</div>" if clinic else ""
        contact_html = (f"<div style='color:#777;font-size:9pt'>{_html_escape(contact)}</div>"
                        if contact else "")
        return (
            "<table width='100%'><tr>"
            f"{logo_cell}"
            f"<td align='right' valign='middle'><h1 style='margin:0'>{title}</h1>"
            f"{clinic_html}{contact_html}</td>"
            "</tr></table><hr>"
        )

    # ---- chart builder (extracted so the full PDF can re-render it) -------
    def _build_detail_chart(self, ratings, coping, intensity) -> QChart:
        max_y = self.context.config.vas_max
        chart = QChart(); chart.setTitle(tr("chart.craving"))
        ax_x = QValueAxis(); ax_x.setTitleText(tr("chart.time")); ax_x.setLabelFormat("%d")
        ax_y = QValueAxis(); ax_y.setRange(0, max_y); ax_y.setTitleText(tr("chart.craving"))
        ax_y.setTickCount(max_y + 1)
        chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(ax_y, Qt.AlignmentFlag.AlignLeft)

        craving = QLineSeries(); craving.setName(tr("chart.craving"))
        pen = craving.pen(); pen.setWidth(3); craving.setPen(pen)
        max_t = 60
        for r in ratings:
            craving.append(r.elapsed_sec, r.value)
            max_t = max(max_t, r.elapsed_sec)
        chart.addSeries(craving); craving.attachAxis(ax_x); craving.attachAxis(ax_y)

        coping_y = max_y - 0.5
        for skill, (lbl_key, color) in SKILL_LABELS.items():
            pts = [e for e in coping if e.skill == skill]
            if not pts:
                continue
            s = QScatterSeries(); s.setName(tr(lbl_key))
            s.setColor(color); s.setMarkerSize(11)
            for e in pts:
                s.append(e.elapsed_sec, coping_y)
            chart.addSeries(s); s.attachAxis(ax_x); s.attachAxis(ax_y)
        if intensity:
            s = QScatterSeries(); s.setName(tr("intensity.title"))
            s.setColor(QColor("#7a7a7a")); s.setMarkerSize(8)
            for e in intensity:
                s.append(e.elapsed_sec, max(0, max_y - 1.5))
            chart.addSeries(s); s.attachAxis(ax_x); s.attachAxis(ax_y)
        ax_x.setRange(0, max_t + 10)
        return chart

    def _build_full_html(self, sessions, cue_index) -> str:
        include_notes = self.include_notes.isChecked()
        has_logo = bool(self._resolve_logo_path())
        gen = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        # ----- summary table (changes between sessions) -----
        rows = []
        for i, s in enumerate(sessions, start=1):
            change = "—" if (s.baseline_vas is None or s.endpoint_vas is None) else f"{s.endpoint_vas - s.baseline_vas:+d}"
            slope = "—" if s.habituation_slope is None else f"{s.habituation_slope:.4f}"
            notes_flag = "✓" if s.clinician_notes else ""
            reason = tr(END_REASON_KEYS.get(s.end_reason, "")) if s.end_reason else "—"
            rows.append(
                f"<tr><td>{i}</td><td>{s.started_at[:16]}</td><td>{reason}</td>"
                f"<td>{s.baseline_vas}</td><td>{s.peak_vas}</td><td>{s.endpoint_vas}</td>"
                f"<td>{change}</td><td>{slope}</td><td>{notes_flag}</td></tr>"
            )
        summary_table = (
            f"<h2>{tr('report.summary_table')}</h2>"
            f"<table border='1' cellpadding='4' cellspacing='0'>"
            f"<tr><th>#</th><th>{tr('report.col_date')}</th><th>{tr('report.col_endreason')}</th>"
            f"<th>{tr('summary.baseline')}</th><th>{tr('summary.peak')}</th>"
            f"<th>{tr('summary.endpoint')}</th><th>{tr('report.col_change')}</th>"
            f"<th>{tr('report.col_slope')}</th><th>{tr('report.col_notes')}</th></tr>"
            f"{''.join(rows)}</table>"
        )

        # ----- per-session detail blocks -----
        blocks = []
        for i, s in enumerate(sessions, start=1):
            ratings = self.context.repos.ratings.list_for_session(s.id)
            dwell_events = self.context.repos.cue_dwell.list_for_session(s.id)
            analysis = reports.per_cue_analysis(ratings, dwell_events)
            top_id = reports.highest_reactivity_cue_id(ratings)
            per_cue_rows = ""
            for info in analysis:
                cue = cue_index.get(info["cue_config_id"])
                name = _short(cue.media_path) if cue else "—"
                if info["cue_config_id"] == top_id:
                    name = f"<b>{name}</b>"
                mean_c = f"{info['mean_craving']:.1f}" if info["mean_craving"] is not None else "—"
                peak_c = str(info["peak_craving"]) if info["peak_craving"] is not None else "—"
                react = f"+{info['cue_reactivity']}" if info["cue_reactivity"] is not None else "—"
                per_cue_rows += (
                    f"<tr><td>{name}</td>"
                    f"<td>{info['total_dwell_sec']}</td><td>{info['view_count']}</td>"
                    f"<td>{mean_c}</td><td>{peak_c}</td>"
                    f"<td>{react}</td></tr>"
                )
            metrics_html = _metrics_table_html(reports.session_metrics(s, ratings))
            notes_html = ""
            if include_notes and s.clinician_notes:
                notes_html = (
                    f"<h4>{tr('report.clinician_notes')}</h4>"
                    f"<p style='white-space:pre-wrap'>{_html_escape(s.clinician_notes)}</p>"
                )
            page_break = "style='page-break-before: always'" if i > 1 else ""
            blocks.append(
                f"<h3 {page_break}>{tr('report.session_section')} {i} — {s.started_at[:16]}</h3>"
                f"<p><img src='img://session-{s.id}' width='{self._pdf_img_width}'></p>"
                f"<h4>{tr('report.metrics')}</h4>{metrics_html}"
                f"<h4>{tr('report.dwell_title')}</h4>"
                f"<table border='1' cellpadding='4' cellspacing='0'>"
                f"<tr><th>{tr('report.dwell_col_cue')}</th>"
                f"<th>{tr('report.dwell_col_dwell')}</th>"
                f"<th>{tr('report.dwell_col_views')}</th>"
                f"<th>{tr('report.dwell_col_mean')}</th>"
                f"<th>{tr('report.dwell_col_peak')}</th>"
                f"<th>{tr('report.dwell_col_reactivity')}</th></tr>"
                f"{per_cue_rows}</table>"
                f"{self._coping_html(s.id)}"
                f"{notes_html}"
            )

        return (
            f"{self._header_html(tr('report.full_title', code=self.patient.code), has_logo)}"
            f"<p style='color:#666'>{tr('report.generated', when=gen)} — "
            f"{tr('report.sessions_total', n=len(sessions))}</p>"
            f"<p style='color:#922'><b>{tr('report.disclaimer')}</b></p>"
            f"<p style='color:#666'><i>{tr('report.exploratory_caveat')}</i></p>"
            f"<h2>{tr('report.progress_section')}</h2>"
            f"<p><img src='img://trends' width='{self._pdf_img_width}'></p>"
            f"<p><img src='img://slope'  width='{self._pdf_img_width}'></p>"
            f"<p><img src='img://recovery' width='{self._pdf_img_width}'></p>"
            f"{summary_table}"
            f"<h2>{tr('report.full_per_session')}</h2>"
            f"{''.join(blocks)}"
        )

    def _coping_html(self, session_id: int) -> str:
        """A table of the session's USCS coping free-text responses for the PDF.

        Returns '' when the session has no coping events."""
        events = self.context.repos.coping.list_for_session(session_id)
        if not events:
            return ""
        labels = self._skill_label_map()
        rows = ""
        for e in events:
            skill = labels.get(e.skill, e.skill)
            text = _html_escape(e.detail) if e.detail else "—"
            rows += (
                f"<tr>"
                f"<td style='white-space:nowrap;text-align:right'>{e.elapsed_sec}s</td>"
                f"<td style='white-space:nowrap'>{skill}</td>"
                f"<td style='white-space:pre-wrap;word-break:break-word'>{text}</td>"
                f"</tr>"
            )
        return (
            f"<h4>{tr('report.coping_text')}</h4>"
            f"<table border='1' cellpadding='6' cellspacing='0' "
            f"style='font-size:11pt;border-collapse:collapse;width:100%'>"
            f"<tr style='background:#f0f4f5'>"
            f"<th style='width:8%'>{tr('report.col_time')}</th>"
            f"<th style='width:28%'>{tr('report.col_skill')}</th>"
            f"<th style='width:64%'>{tr('report.col_response')}</th></tr>"
            f"{rows}</table>"
        )

    def _build_html(self) -> str:
        include_notes = self.include_notes.isChecked()
        has_logo = bool(self._resolve_logo_path())
        sessions = self._finished_sessions()
        sid = self.session_combo.currentData()
        sel = next((s for s in sessions if s.id == sid), None)
        gen = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        sel_block = ""
        if sel:
            ratings = self.context.repos.ratings.list_for_session(sel.id)
            dwell_events = self.context.repos.cue_dwell.list_for_session(sel.id)
            analysis = reports.per_cue_analysis(ratings, dwell_events)
            cue_index = self._patient_cue_index()
            top_id = reports.highest_reactivity_cue_id(ratings)
            rows_per_cue = ""
            for info in analysis:
                cue = cue_index.get(info["cue_config_id"])
                name = _short(cue.media_path) if cue else "—"
                if info["cue_config_id"] == top_id:
                    name = f"<b>{name}</b>"
                mean_c = f"{info['mean_craving']:.1f}" if info["mean_craving"] is not None else "—"
                peak_c = str(info["peak_craving"]) if info["peak_craving"] is not None else "—"
                react = f"+{info['cue_reactivity']}" if info["cue_reactivity"] is not None else "—"
                rows_per_cue += (
                    f"<tr><td>{name}</td>"
                    f"<td>{info['total_dwell_sec']}</td><td>{info['view_count']}</td>"
                    f"<td>{mean_c}</td><td>{peak_c}</td>"
                    f"<td>{react}</td></tr>"
                )
            notes_html = ""
            if include_notes and sel.clinician_notes:
                notes_html = (
                    f"<h3>{tr('report.clinician_notes')}</h3>"
                    f"<p style='white-space:pre-wrap'>{_html_escape(sel.clinician_notes)}</p>"
                )
            sel_block = (
                f"<h2>{tr('report.session_section')}</h2>"
                f"<p><b>{sel.started_at}</b> · {tr(END_REASON_KEYS.get(sel.end_reason, '')) or '—'}</p>"
                f"<p><img src='img://detail' width='{self._pdf_img_width}'></p>"
                f"<h3>{tr('report.metrics')}</h3>"
                f"{_metrics_table_html(reports.session_metrics(sel, ratings))}"
                f"<h3>{tr('report.dwell_title')}</h3>"
                f"<table border='1' cellpadding='4' cellspacing='0'>"
                f"<tr><th>{tr('report.dwell_col_cue')}</th>"
                f"<th>{tr('report.dwell_col_dwell')}</th>"
                f"<th>{tr('report.dwell_col_views')}</th>"
                f"<th>{tr('report.dwell_col_mean')}</th>"
                f"<th>{tr('report.dwell_col_peak')}</th>"
                f"<th>{tr('report.dwell_col_reactivity')}</th></tr>"
                f"{rows_per_cue}</table>"
                f"{self._coping_html(sel.id)}"
                f"{notes_html}"
            )
        return (
            f"{self._header_html(tr('report.title', code=self.patient.code), has_logo)}"
            f"<p style='color:#666'>{tr('report.generated', when=gen)} — "
            f"{tr('report.sessions_total', n=len(sessions))}</p>"
            f"<p style='color:#922'><b>{tr('report.disclaimer')}</b></p>"
            f"<p style='color:#666'><i>{tr('report.exploratory_caveat')}</i></p>"
            f"{sel_block}"
            f"<h2>{tr('report.progress_section')}</h2>"
            f"<p><img src='img://trends' width='{self._pdf_img_width}'></p>"
            f"<p><img src='img://slope'  width='{self._pdf_img_width}'></p>"
            f"<p><img src='img://recovery' width='{self._pdf_img_width}'></p>"
        )


def _print_chart_pixmap(chart: QChart, width: int = 1200, height: int = 540):
    """Render a chart for PDF/print: large fonts, thick series, 2× pixel ratio.

    The on-screen QtCharts defaults are ~8pt and look tiny once embedded in an A4
    PDF; this applies a legible 'print theme' before grabbing at high resolution.
    """
    title_font = QFont(); title_font.setPointSize(18); title_font.setBold(True)
    axis_title = QFont(); axis_title.setPointSize(14)
    axis_labels = QFont(); axis_labels.setPointSize(12)
    legend_font = QFont(); legend_font.setPointSize(13)

    chart.setTitleFont(title_font)
    for axis in chart.axes():
        axis.setTitleFont(axis_title)
        axis.setLabelsFont(axis_labels)
    chart.legend().setFont(legend_font)
    for s in chart.series():
        if isinstance(s, QLineSeries):
            pen = s.pen(); pen.setWidth(4); s.setPen(pen)
            s.setPointsVisible(True)
        if isinstance(s, QScatterSeries):
            s.setMarkerSize(max(14.0, s.markerSize()))

    from PySide6.QtCharts import QChartView as _CV
    dpr = 2.0
    view = _CV(chart)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    view.resize(int(width * dpr), int(height * dpr))   # render at 2× for crispness
    pix = view.grab()
    pix.setDevicePixelRatio(dpr)                        # lay out at logical width in the PDF
    return pix


# Back-compat name used elsewhere; route through the print theme.
def _render_chart_pixmap(chart: QChart, width: int = 1200, height: int = 540):
    return _print_chart_pixmap(chart, width, height)


def _bar_chart(counts: dict, label_fn, title: str) -> QChart:
    chart = QChart(); chart.setTitle(title)
    keys = list(counts.keys())
    bar_set = QBarSet("n")
    for k in keys:
        bar_set.append(counts[k])
    series = QBarSeries()
    series.append(bar_set)
    chart.addSeries(series)
    cats = QBarCategoryAxis()
    cats.append([label_fn(k) for k in keys])
    chart.addAxis(cats, Qt.AlignmentFlag.AlignBottom); series.attachAxis(cats)
    y = QValueAxis(); y.setLabelFormat("%d")
    y.setRange(0, max(counts.values()) + 1 if counts else 1)
    chart.addAxis(y, Qt.AlignmentFlag.AlignLeft); series.attachAxis(y)
    chart.legend().hide()
    return chart
