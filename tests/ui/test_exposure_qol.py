"""Exposure QoL: arrow-key cue navigation + periodic VAS suppressed during coping."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from cravingcrave.config import AppConfig
from cravingcrave.domain.models import CueConfig, Patient
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.main_window import MainWindow


def _img(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    im = QImage(20, 20, QImage.Format.Format_RGB32)
    im.fill(Qt.GlobalColor.darkGreen)
    im.save(str(p))


@pytest.fixture
def ctx(tmp_path, qapp):
    cfg = AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                    db_path=tmp_path / "data" / "cc.db")
    c = AppContext.create(cfg)
    c.clinician = c.auth.register("u", "U", "p")
    return c


def _start(ctx, qtbot):
    p = ctx.repos.patients.create(Patient(code="PTQ", primary_substance="meth", created_by=ctx.clinician.id))
    for i in range(3):
        _img(Path(ctx.config.media_root) / "meth" / f"c{i}.png")
        ctx.repos.cues.create(CueConfig(patient_id=p.id, substance="meth",
                                        media_path=f"meth/c{i}.png", media_type="image", appetitive_rank=i))
    cues = ctx.repos.cues.list_for_patient(p.id)
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    window.show()
    window.start_exposure(p, "meth", cues, [])
    screen = window._active_exposure
    qtbot.wait(50)              # let the screen's deferred baseline prompt fire once
    screen.vas_prompt.slider.slider.setValue(5)
    screen.vas_prompt._submit()  # baseline submitted -> exposure begins
    return window, screen


def test_arrow_shortcuts_registered(ctx, qtbot):
    _, screen = _start(ctx, qtbot)
    # Standard mode builds QShortcuts from the hotkey registry (default keys unchanged).
    keys = {sc.key().toString() for sc in screen._shortcuts}
    assert "Right" in keys and "Left" in keys
    assert "T" in keys and "Shift+T" in keys and "M" in keys


def test_cue_navigation_clamps(ctx, qtbot):
    _, screen = _start(ctx, qtbot)
    assert screen.controller.current_cue_index() == 0
    screen._next_cue(); screen._next_cue()
    assert screen.controller.current_cue_index() == 2
    screen._next_cue()                                   # clamped at last
    assert screen.controller.current_cue_index() == 2
    screen._prev_cue(); screen._prev_cue(); screen._prev_cue()
    assert screen.controller.current_cue_index() == 0    # clamped at first


def test_periodic_vas_suppressed_during_coping(ctx, qtbot):
    _, screen = _start(ctx, qtbot)
    screen._open_coping()
    qtbot.wait(10)
    assert screen.coping_panel.isVisible()
    screen._on_periodic()                                # should be a no-op while coping
    assert not screen._prompt_open
    assert not screen.vas_prompt.isVisible()


# ---------- loop + intensity shortcuts (new QoL) ---------------------------

def test_controller_loop_wraps_at_ends(ctx, qtbot):
    from cravingcrave.session.session_controller import SessionController
    p = ctx.repos.patients.create(Patient(code="PTL", primary_substance="meth", created_by=ctx.clinician.id))
    for i in range(3):
        _img(Path(ctx.config.media_root) / "meth" / f"c{i}.png")
        ctx.repos.cues.create(CueConfig(patient_id=p.id, substance="meth",
                                        media_path=f"meth/c{i}.png", media_type="image", appetitive_rank=i))
    cues = ctx.repos.cues.list_for_patient(p.id)
    # Without loop: stays at last on overflow.
    c = SessionController(ctx.repos, ctx.config, p, ctx.clinician, "meth", cues, loop=False)
    c.begin(); c.advance_cue(); c.advance_cue(); c.advance_cue()
    assert c.current_cue_index() == 2
    # With loop: wraps to 0 on overflow and to last on underflow.
    c = SessionController(ctx.repos, ctx.config, p, ctx.clinician, "meth", cues, loop=True)
    c.begin(); c.advance_cue(); c.advance_cue(); c.advance_cue()
    assert c.current_cue_index() == 0           # wrapped
    c.previous_cue()
    assert c.current_cue_index() == 2           # underflow wrap


def test_intensity_size_shortcut_steps_value(ctx, qtbot):
    _, screen = _start(ctx, qtbot)
    initial = screen.intensity._size.value()    # default 100
    screen.intensity.step_size(-30)
    assert screen.intensity._size.value() == initial - 30
    screen.intensity.step_size(+10)
    assert screen.intensity._size.value() == initial - 20


def test_reset_intensity_records_event(ctx, qtbot):
    _, screen = _start(ctx, qtbot)
    # Move some sliders first so reset has something to revert.
    screen.intensity.step_size(-40); screen.intensity.step_blur(+30)
    screen._reset_intensity()
    sid = screen.controller.session.id
    events = ctx.repos.intensity.list_for_session(sid)
    assert any(e.action == "reset" and e.scale_pct == 100 and e.blur_pct == 0 for e in events)


def test_runtime_loop_toggle_flips_controller(ctx, qtbot):
    _, screen = _start(ctx, qtbot)
    assert screen.controller.loop is False
    screen._toggle_loop()
    assert screen.controller.loop is True
    screen._toggle_loop()
    assert screen.controller.loop is False
