"""Auto-scroll: cues advance after a grading prompt and/or on a timer, both gated."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from cravingcrave.config import AppConfig
from cravingcrave.domain.models import CueConfig, Patient
from cravingcrave.session.session_controller import SessionController
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.main_window import MainWindow
from cravingcrave.ui.screens.exposure_screen import ExposureScreen


def _make_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(60, 60, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.darkGreen)
    assert img.save(str(path))


def _ctx(tmp_path, **cfg_kwargs) -> AppContext:
    config = AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                       db_path=tmp_path / "data" / "cc.db", **cfg_kwargs)
    ctx = AppContext.create(config)
    ctx.clinician = ctx.auth.register("dra", "Dra", "pw123456")
    return ctx


def _patient_with_cues(ctx, n=3):
    patient = ctx.repos.patients.create(Patient(code="PT0002", primary_substance="meth",
                                                created_by=ctx.clinician.id))
    cues = []
    for i in range(n):
        _make_image(Path(ctx.config.media_root) / "meth" / f"cue{i}.png")
        cues.append(ctx.repos.cues.create(CueConfig(
            patient_id=patient.id, substance="meth", media_path=f"meth/cue{i}.png",
            media_type="image", appetitive_rank=i)))
    return patient, cues


def _submit_vas(screen, value: int):
    screen.vas_prompt.slider.slider.setValue(value)
    screen.vas_prompt._submit()


def _build(ctx, qtbot):
    window = MainWindow(ctx)
    qtbot.addWidget(window)
    patient, cues = _patient_with_cues(ctx)
    controller = SessionController(ctx.repos, ctx.config, patient, ctx.clinician, "meth", cues)
    screen = ExposureScreen(window, ctx, controller, [])
    qtbot.addWidget(screen)
    screen._ask_baseline()
    _submit_vas(screen, 6)  # baseline -> begins exposure at cue index 0
    return screen, controller


def test_advance_after_grading_when_enabled(tmp_path, qtbot):
    ctx = _ctx(tmp_path, autoscroll_on_grading=True)
    screen, controller = _build(ctx, qtbot)
    assert controller.current_cue_index() == 0
    screen._on_periodic()          # opens periodic VAS
    _submit_vas(screen, 2)         # submit -> should auto-advance
    assert controller.current_cue_index() == 1
    screen._mark_peak()
    _submit_vas(screen, 4)         # peak submit -> advance again
    assert controller.current_cue_index() == 2


def test_no_advance_after_grading_when_disabled(tmp_path, qtbot):
    ctx = _ctx(tmp_path, autoscroll_on_grading=False)
    screen, controller = _build(ctx, qtbot)
    assert controller.current_cue_index() == 0
    screen._on_periodic()
    _submit_vas(screen, 2)
    assert controller.current_cue_index() == 0   # unchanged


def test_timed_tick_advances_and_is_gated(tmp_path, qtbot):
    ctx = _ctx(tmp_path, autoscroll_timed_seconds=5)
    screen, controller = _build(ctx, qtbot)
    assert controller.current_cue_index() == 0
    screen._on_autoscroll_tick()
    assert controller.current_cue_index() == 1
    # Gated while a prompt is open: no advance.
    screen._prompt_open = True
    screen._on_autoscroll_tick()
    assert controller.current_cue_index() == 1


def test_timed_timer_only_active_when_configured(tmp_path, qtbot):
    off = _ctx(tmp_path / "off", autoscroll_timed_seconds=0)
    screen_off, _ = _build(off, qtbot)
    assert not screen_off._autoscroll_timer.isActive()

    on = _ctx(tmp_path / "on", autoscroll_timed_seconds=5)
    screen_on, _ = _build(on, qtbot)
    assert screen_on._autoscroll_timer.isActive()
