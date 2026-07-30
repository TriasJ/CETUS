"""Adaptive ordering UI: Suggest-order button gated by the toggle; Apply rewrites ranks."""

from cravingcrave.config import AppConfig
from cravingcrave.domain.models import CravingRating, CueConfig, Patient, Session
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.main_window import MainWindow
from cravingcrave.ui.screens.cue_config_screen import CueConfigScreen


def _ctx(tmp_path, **cfg):
    c = AppContext.create(AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                                    db_path=tmp_path / "data" / "cc.db", **cfg))
    c.clinician = c.auth.register("dra", "Dra", "pw123456")
    return c


def _seed(ctx):
    p = ctx.repos.patients.create(Patient(code="PT01", primary_substance="meth",
                                          created_by=ctx.clinician.id))
    a = ctx.repos.cues.create(CueConfig(patient_id=p.id, substance="meth", media_path="meth/a.png",
                                        media_type="image", appetitive_rank=0))   # higher craving
    b = ctx.repos.cues.create(CueConfig(patient_id=p.id, substance="meth", media_path="meth/b.png",
                                        media_type="image", appetitive_rank=1))   # lower craving
    s = ctx.repos.sessions.create(Session(patient_id=p.id, clinician_id=ctx.clinician.id,
                                          substance="meth", app_version="t"))
    ctx.repos.ratings.add(CravingRating(session_id=s.id, kind="baseline", value=3, cue_config_id=a.id))
    ctx.repos.ratings.add(CravingRating(session_id=s.id, kind="peak", value=8, cue_config_id=a.id))
    ctx.repos.ratings.add(CravingRating(session_id=s.id, kind="periodic", value=5, cue_config_id=b.id))
    return p


def test_suggest_button_hidden_when_toggle_off(tmp_path, qtbot):
    ctx = _ctx(tmp_path)                      # adaptive_ordering defaults False
    p = _seed(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window)
    screen = CueConfigScreen(window, ctx, p); qtbot.addWidget(screen)
    assert not hasattr(screen, "_suggest_button_present") or True  # no assertion on private
    # The button text should not be anywhere among the screen's QPushButtons.
    from PySide6.QtWidgets import QPushButton
    texts = {b.text() for b in screen.findChildren(QPushButton)}
    from cravingcrave.services.i18n import tr
    assert tr("cueconfig.suggest_order") not in texts


def test_suggest_apply_rewrites_ranks_low_first(tmp_path, qtbot, monkeypatch):
    import cravingcrave.ui.screens.cue_config_screen as ccs
    ctx = _ctx(tmp_path, adaptive_ordering=True)
    p = _seed(ctx)
    window = MainWindow(ctx); qtbot.addWidget(window)
    screen = CueConfigScreen(window, ctx, p); qtbot.addWidget(screen)
    # Accept the preview dialog and swallow the info box.
    monkeypatch.setattr(ccs.QDialog, "exec", lambda self: ccs.QDialog.DialogCode.Accepted)
    monkeypatch.setattr(ccs, "QMessageBox",
                        type("MB", (), {"information": staticmethod(lambda *a, **k: None)}))
    screen._suggest_order()
    ranks = {c.media_path: c.appetitive_rank for c in ctx.repos.cues.list_for_patient(p.id)}
    assert ranks["meth/b.png"] == 0    # lower-craving cue suggested first
    assert ranks["meth/a.png"] == 1
