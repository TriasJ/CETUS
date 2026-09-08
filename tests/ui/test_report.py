"""Clinical report screen: builds with real session data + PDF export produces a file."""

from pathlib import Path

import pytest

from cravingcrave.config import AppConfig
from cravingcrave.domain.models import (
    CopingEvent,
    CravingRating,
    CueConfig,
    IntensityEvent,
    Patient,
    Session,
)
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.main_window import MainWindow
from cravingcrave.ui.screens import report_screen as rs_mod
from cravingcrave.ui.screens.report_screen import ReportScreen


class _FakeMessageBox:
    @staticmethod
    def information(*a, **k):
        return None


@pytest.fixture
def ctx(tmp_path, qapp):
    cfg = AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                    db_path=tmp_path / "data" / "cc.db")
    c = AppContext.create(cfg)
    c.clinician = c.auth.register("u", "U", "p")
    return c


def _seed(ctx) -> Patient:
    p = ctx.repos.patients.create(Patient(code="PT-R1", primary_substance="meth",
                                          created_by=ctx.clinician.id))
    cue = ctx.repos.cues.create(CueConfig(patient_id=p.id, substance="meth",
                                          media_path="meth/x.png", media_type="image",
                                          appetitive_rank=0))
    s = ctx.repos.sessions.create(Session(patient_id=p.id, clinician_id=ctx.clinician.id,
                                          substance="meth", consent_given=True, app_version="t"))
    for elapsed, value, kind in [(0, 7, "baseline"), (30, 9, "peak"), (60, 5, "periodic"), (90, 1, "endpoint")]:
        ctx.repos.ratings.add(CravingRating(session_id=s.id, elapsed_sec=elapsed,
                                            value=value, kind=kind, cue_config_id=cue.id))
    for elapsed, skill in [(45, "recall_negative"), (70, "alternative_action")]:
        ctx.repos.coping.add(CopingEvent(session_id=s.id, elapsed_sec=elapsed, skill=skill, detail="ejemplo"))
    ctx.repos.intensity.add(IntensityEvent(session_id=s.id, elapsed_sec=50, action="shrink", scale_pct=50))
    s.ended_at = "2026-05-27T00:02:00+00:00"
    s.end_reason = "habituated"
    s.baseline_vas, s.peak_vas, s.endpoint_vas, s.habituation_slope = 7, 9, 1, -0.05
    ctx.repos.sessions.finalize(s)
    return p


def test_report_screen_populates_from_data(ctx, qtbot, monkeypatch):
    monkeypatch.setattr(rs_mod, "QMessageBox", _FakeMessageBox)
    p = _seed(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)
    assert screen.session_combo.count() == 1
    assert screen.cue_table.rowCount() == 1
    assert screen.coping_list.count() == 2
    assert screen.detail_chart_view.chart() is not None
    assert screen.trends_view.chart() is not None
    assert screen.slope_view.chart() is not None


def test_export_pdf_writes_a_real_file(ctx, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(rs_mod, "QMessageBox", _FakeMessageBox)
    out = str(tmp_path / "rep.pdf")
    monkeypatch.setattr(rs_mod, "QFileDialog",
                        type("QFD", (),
                             {"getSaveFileName": staticmethod(lambda *a, **k: (out, "PDF (*.pdf)"))}))
    p = _seed(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)
    screen._export_pdf()
    f = Path(out)
    assert f.exists() and f.stat().st_size > 1000   # non-trivial PDF
    assert f.read_bytes()[:4] == b"%PDF"             # valid PDF magic


def test_default_cetus_logo_used_when_no_clinic_logo(ctx, qtbot):
    p = _seed(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)
    # With no clinic logo set, the bundled CETUS mark is the default report logo.
    resolved = screen._resolve_logo_path()
    assert resolved is not None and resolved.endswith("cetus.png")
    assert "img://logo" in screen._build_html()


def test_coping_responses_appear_in_pdf_html(ctx, qtbot):
    p = _seed(ctx)  # seeds two coping events with detail="ejemplo"
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)
    # Single-session PDF HTML now carries the coping responses (was dropped before 0.4.0).
    assert "ejemplo" in screen._build_html()
    # Localized skill label present too.
    assert "afronta" in screen._build_html().lower() or "coping" in screen._build_html().lower()
    # Full-patient PDF HTML also includes them.
    sessions = [s for s in ctx.repos.sessions.list_for_patient(p.id) if s.baseline_vas is not None]
    assert "ejemplo" in screen._build_full_html(sessions, screen._patient_cue_index())


def test_export_coping_csv_writes_file(ctx, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(rs_mod, "QMessageBox", _FakeMessageBox)
    out = str(tmp_path / "coping.csv")
    monkeypatch.setattr(rs_mod, "QFileDialog",
                        type("QFD", (),
                             {"getSaveFileName": staticmethod(lambda *a, **k: (out, "CSV (*.csv)"))}))
    p = _seed(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)
    screen._export_coping_csv()
    f = Path(out)
    assert f.exists()
    text = f.read_text(encoding="utf-8-sig")
    assert "response_text" in text and "ejemplo" in text and "PT-R1" in text


def test_coping_repo_list_for_patient(ctx):
    p = _seed(ctx)
    _seed_extra(ctx, p, n=1)  # extra session has no coping
    events = ctx.repos.coping.list_for_patient(p.id)
    assert len(events) == 2  # only the seeded session had coping
    assert {e.skill for e in events} == {"recall_negative", "alternative_action"}


def test_clinician_notes_save_reload_and_appear_in_pdf(ctx, qtbot, monkeypatch):
    monkeypatch.setattr(rs_mod, "QMessageBox", _FakeMessageBox)
    p = _seed(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)

    note = "Sesion productiva: el paciente verbalizo razones de cambio."
    screen.notes_edit.setPlainText(note)
    screen._save_notes()
    sid = screen.session_combo.currentData()
    assert ctx.repos.sessions.get(sid).clinician_notes == note

    # Re-rendering reloads notes from the DB (drops any local override).
    screen.notes_edit.setPlainText("(override)")
    screen._refresh_session(0)
    assert screen.notes_edit.toPlainText() == note

    # PDF source HTML includes the (escaped) note text.
    assert note in screen._build_html()


def test_notes_badge_toggles_on_save_and_clear(ctx, qtbot, monkeypatch):
    monkeypatch.setattr(rs_mod, "QMessageBox", _FakeMessageBox)
    p = _seed(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)
    assert "Notas" not in screen.session_combo.itemText(0)
    screen.notes_edit.setPlainText("recordar revisar la señal 3")
    screen._save_notes()
    assert "Notas" in screen.session_combo.itemText(0)        # badge appears
    screen.notes_edit.setPlainText("")
    screen._save_notes()
    assert "Notas" not in screen.session_combo.itemText(0)    # badge cleared


def test_notes_badge_present_on_initial_population(ctx, qtbot):
    p = _seed(ctx)
    sid = ctx.repos.sessions.list_for_patient(p.id)[0].id
    ctx.repos.sessions.update_notes(sid, "nota previa")
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)
    assert "Notas" in screen.session_combo.itemText(0)


def _seed_extra(ctx, patient, n=2):
    """Add `n` more finished sessions after the one created by _seed."""
    cue = ctx.repos.cues.list_for_patient(patient.id)[0]
    for i in range(n):
        s = ctx.repos.sessions.create(Session(patient_id=patient.id, clinician_id=ctx.clinician.id,
                                              substance="meth", consent_given=True, app_version="t"))
        ctx.repos.ratings.add(CravingRating(session_id=s.id, elapsed_sec=0, value=6, kind="baseline",
                                            cue_config_id=cue.id))
        ctx.repos.ratings.add(CravingRating(session_id=s.id, elapsed_sec=60, value=1, kind="endpoint",
                                            cue_config_id=cue.id))
        s.ended_at = "2026-05-27T00:02:00+00:00"
        s.end_reason = "habituated"
        s.baseline_vas, s.peak_vas, s.endpoint_vas = 6, 7, 1
        s.habituation_slope = -0.04 - 0.01 * i
        ctx.repos.sessions.finalize(s)


def test_full_patient_pdf_includes_every_session(ctx, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(rs_mod, "QMessageBox", _FakeMessageBox)
    out = str(tmp_path / "full.pdf")
    monkeypatch.setattr(rs_mod, "QFileDialog",
                        type("QFD", (),
                             {"getSaveFileName": staticmethod(lambda *a, **k: (out, "PDF (*.pdf)"))}))
    p = _seed(ctx)
    _seed_extra(ctx, p, n=2)
    # Add a note to the middle session (and re-fetch so in-memory objects see it).
    mid = ctx.repos.sessions.list_for_patient(p.id)[1]
    ctx.repos.sessions.update_notes(mid.id, "Observación clínica para la sesión 2.")
    sessions = [s for s in ctx.repos.sessions.list_for_patient(p.id) if s.baseline_vas is not None]

    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)

    # HTML references all sessions and the summary table.
    html = screen._build_full_html(sessions, screen._patient_cue_index())
    for s in sessions:
        assert f"img://session-{s.id}" in html
    assert "Cambios entre sesiones" in html
    assert "Observación clínica para la sesión 2." in html

    # Real PDF file gets written.
    screen._export_pdf_full()
    f = Path(out)
    assert f.exists() and f.stat().st_size > 1000
    assert f.read_bytes()[:4] == b"%PDF"


# ---------- new: metrics table, comments toggle, logo, recovery ------------

def test_fmt_rounds_zero_decimals():
    # pct_reduction is formatted with decimals=0 and must round, not dump a long float.
    assert rs_mod._fmt(55.55555, suffix="%", decimals=0) == "56%"
    assert rs_mod._fmt(5.83, decimals=1) == "5.8"
    assert rs_mod._fmt(8) == "8"          # raw
    assert rs_mod._fmt(None) == "—"


def test_metrics_table_and_reactivity_column(ctx, qtbot):
    p = _seed(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)
    assert screen.metrics_table.rowCount() == 8         # 8 metric rows
    assert screen.cue_table.columnCount() == 7          # expanded with dwell columns
    assert screen.recovery_view.chart() is not None     # spontaneous-recovery chart built
    # metrics appear in the PDF HTML
    html = screen._build_html()
    assert "Deseo medio durante la exposición" in html
    assert "Reactividad" in html


def test_comments_toggle_excludes_notes(ctx, qtbot):
    p = _seed(ctx)
    sid = ctx.repos.sessions.list_for_patient(p.id)[0].id
    ctx.repos.sessions.update_notes(sid, "NOTA-SECRETA-123")
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)

    screen.include_notes.setChecked(True)
    assert "NOTA-SECRETA-123" in screen._build_html()
    assert "NOTA-SECRETA-123" in screen._build_full_html(
        [s for s in ctx.repos.sessions.list_for_patient(p.id) if s.baseline_vas is not None],
        screen._patient_cue_index())

    screen.include_notes.setChecked(False)
    assert "NOTA-SECRETA-123" not in screen._build_html()
    assert "NOTA-SECRETA-123" not in screen._build_full_html(
        [s for s in ctx.repos.sessions.list_for_patient(p.id) if s.baseline_vas is not None],
        screen._patient_cue_index())


def test_clinic_logo_embedded_in_pdf(ctx, qtbot, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QTextDocument
    logo = tmp_path / "logo.png"
    img = QImage(120, 60, QImage.Format.Format_RGB32); img.fill(Qt.GlobalColor.blue); img.save(str(logo))
    ctx.repos.settings.set("clinic_logo_path", str(logo))
    ctx.repos.settings.set("clinic_name", "Clínica Demo")
    p = _seed(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)

    doc = QTextDocument()
    assert screen._add_logo_resource(doc) is True       # logo loaded
    assert "img://logo" in screen._build_html()         # header references it
    assert "Clínica Demo" in screen._build_html()

    # No clinic logo -> the bundled CETUS brand mark is used as the default header logo.
    ctx.repos.settings.set("clinic_logo_path", "")
    assert screen._add_logo_resource(QTextDocument()) is True
    assert "img://logo" in screen._build_html()
