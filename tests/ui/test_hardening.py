"""0.2.0 hardening: fullscreen toggle, empty-playlist guard, export write-failure handling."""

from pathlib import Path

import pytest

from cravingcrave.config import AppConfig
from cravingcrave.domain.models import (
    CravingRating,
    CueConfig,
    Patient,
    Session,
)
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.main_window import MainWindow
from cravingcrave.ui.screens import report_screen as rs_mod
from cravingcrave.ui.screens.report_screen import ReportScreen


@pytest.fixture
def ctx(tmp_path, qapp):
    cfg = AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                    db_path=tmp_path / "data" / "cc.db")
    c = AppContext.create(cfg)
    c.clinician = c.auth.register("u", "U", "p")
    return c


# ---------- fullscreen ------------------------------------------------------

def test_settings_logo_picker_wired(ctx, qtbot, tmp_path, monkeypatch):
    """Regression: SettingsScreen used QFileDialog without importing it (would crash on
    'Elegir logo…'). Exercise the picker end-to-end with a stubbed file dialog."""
    from PySide6.QtGui import QImage
    from PySide6.QtCore import Qt as _Qt
    from cravingcrave.ui.screens import settings_screen as ss_mod
    from cravingcrave.ui.screens.settings_screen import SettingsScreen

    logo = tmp_path / "logo.png"
    img = QImage(40, 20, QImage.Format.Format_RGB32); img.fill(_Qt.GlobalColor.blue); img.save(str(logo))
    monkeypatch.setattr(ss_mod, "QFileDialog",
                        type("QFD", (), {"getOpenFileName": staticmethod(lambda *a, **k: (str(logo), ""))}))
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = SettingsScreen(window, ctx)
    qtbot.addWidget(screen)
    screen._pick_logo()                                # would NameError before the fix
    assert ctx.repos.settings.get("clinic_logo_path")  # logo recorded


def test_f11_toggles_fullscreen(ctx, qtbot):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    window.show()
    assert window._fullscreen_shortcut.key().toString() == "F11"
    assert not window.isFullScreen()
    window._toggle_fullscreen()
    assert window.isFullScreen()
    window._toggle_fullscreen()
    assert not window.isFullScreen()


# ---------- empty-playlist guard -------------------------------------------

def test_start_exposure_blocks_empty_playlist(ctx, qtbot, monkeypatch):
    warned = []
    monkeypatch.setattr("cravingcrave.ui.main_window.QMessageBox",
                        type("MB", (), {"warning": staticmethod(lambda *a, **k: warned.append(a))}))
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    window.show()
    p = ctx.repos.patients.create(Patient(code="PTE", primary_substance="meth", created_by=ctx.clinician.id))
    window.start_exposure(p, "meth", [], [])          # no cues
    assert window._active_exposure is None             # never entered exposure
    assert len(warned) == 1                             # warned the clinician


# ---------- export write-failure --------------------------------------------

def _seed(ctx):
    p = ctx.repos.patients.create(Patient(code="PTX", primary_substance="meth", created_by=ctx.clinician.id))
    cue = ctx.repos.cues.create(CueConfig(patient_id=p.id, substance="meth", media_path="meth/x.png",
                                          media_type="image", appetitive_rank=0))
    s = ctx.repos.sessions.create(Session(patient_id=p.id, clinician_id=ctx.clinician.id,
                                          substance="meth", consent_given=True, app_version="t"))
    for el, v, k in [(0, 7, "baseline"), (30, 9, "peak"), (90, 1, "endpoint")]:
        ctx.repos.ratings.add(CravingRating(session_id=s.id, elapsed_sec=el, value=v, kind=k, cue_config_id=cue.id))
    s.baseline_vas, s.peak_vas, s.endpoint_vas, s.habituation_slope = 7, 9, 1, -0.05
    s.ended_at = "2026-06-18T00:02:00+00:00"; s.end_reason = "habituated"
    ctx.repos.sessions.finalize(s)
    return p


def test_pdf_export_failure_shows_error_not_success(ctx, qtbot, tmp_path, monkeypatch):
    calls = {"info": 0, "warn": 0}
    monkeypatch.setattr(rs_mod, "QMessageBox", type("MB", (), {
        "information": staticmethod(lambda *a, **k: calls.__setitem__("info", calls["info"] + 1)),
        "warning": staticmethod(lambda *a, **k: calls.__setitem__("warn", calls["warn"] + 1)),
    }))
    # A path whose parent directory does not exist: QPdfWriter cannot open it, so
    # doc.print_ writes no file and the exists()/size check reports failure.
    out = str(tmp_path / "no_such_dir" / "r.pdf")
    monkeypatch.setattr(rs_mod, "QFileDialog",
                        type("QFD", (), {"getSaveFileName": staticmethod(lambda *a, **k: (out, "PDF (*.pdf)"))}))
    p = _seed(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window); window.show()
    screen = ReportScreen(window, ctx, p); qtbot.addWidget(screen)

    screen._export_pdf()
    assert not Path(out).exists()                       # nothing written
    assert calls["warn"] == 1 and calls["info"] == 0    # error shown, no false success
