"""End-to-end smoke test of the whole therapeutic loop, driven offscreen.

Builds a real MainWindow against a temp DB + temp media, then walks a session:
baseline -> peak -> periodic (until habituation) -> coping -> intensity -> gallery
-> endpoint, and asserts everything persisted. Also covers the panic path.
"""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from cravingcrave.config import AppConfig
from cravingcrave.domain.models import CueConfig, Patient
from cravingcrave.session.session_controller import SessionController
from cravingcrave.ui.context import AppContext
from cravingcrave.ui.main_window import MainWindow
from cravingcrave.ui.screens.exposure_screen import ExposureScreen


class FakeClock:
    """Advances 15 s per read so sessions span real time (for slope computation)."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 15.0
        return self.t


def _make_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(80, 80, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.darkRed)
    assert img.save(str(path))


def _make_wav(path: Path, seconds: float = 0.2, freq: int = 440, rate: int = 8000) -> None:
    import math
    import struct
    import wave
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for i in range(int(seconds * rate)):
            w.writeframes(struct.pack("<h", int(32767 * 0.2 * math.sin(2 * math.pi * freq * i / rate))))


@pytest.fixture
def context(tmp_path, qapp):
    config = AppConfig(data_dir=tmp_path / "data", media_root=tmp_path / "media",
                       db_path=tmp_path / "data" / "cc.db")
    ctx = AppContext.create(config)
    ctx.clinician = ctx.auth.register("dra", "Dra. Prueba", "pw123456")
    return ctx


def _patient_with_cue(ctx):
    patient = ctx.repos.patients.create(Patient(code="PT0001", primary_substance="meth",
                                                 created_by=ctx.clinician.id))
    _make_image(Path(ctx.config.media_root) / "meth" / "cue1.png")
    _make_image(Path(ctx.config.media_root) / "positive" / "puppy.png")
    cue = ctx.repos.cues.create(CueConfig(patient_id=patient.id, substance="meth",
                                          media_path="meth/cue1.png", media_type="image",
                                          appetitive_rank=0))
    return patient, [cue]


def _submit_vas(screen, value: int):
    screen.vas_prompt.slider.slider.setValue(value)
    screen.vas_prompt._submit()


def test_full_session_persists_everything(context, qtbot):
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()

    patient, cues = _patient_with_cue(context)
    positive = [str(Path(context.config.media_root) / "positive" / "puppy.png")]
    # Build directly with a fake clock so ratings get distinct elapsed times.
    controller = SessionController(context.repos, context.config, patient, context.clinician,
                                   "meth", cues, clock=FakeClock())
    screen = ExposureScreen(window, context, controller, positive)
    window._active_controller = controller
    window._active_exposure = screen

    # Baseline -> begins exposure and loads the cue.
    screen._ask_baseline()
    _submit_vas(screen, 7)
    assert controller.current_cue() is not None

    # Patient marks a peak.
    screen._mark_peak()
    _submit_vas(screen, 9)

    # Two consecutive low periodic ratings -> habituation criterion fires.
    with qtbot.waitSignal(controller.habituationReached, timeout=1000):
        screen._on_periodic(); _submit_vas(screen, 1)
        screen._on_periodic(); _submit_vas(screen, 1)
    assert screen._habituated is True

    # Run the four coping steps.
    screen._open_coping()
    for _ in range(4):
        screen.coping_panel._advance()

    # Down-regulate intensity, and use the positive gallery.
    screen._on_intensity(40, 30, 20, True, "shrink")
    screen._open_gallery()
    screen.gallery._close()

    # End the session (habituated) -> endpoint VAS -> summary.
    screen._end_clicked()
    _submit_vas(screen, 1)

    session = context.repos.sessions.list_for_patient(patient.id)[0]
    assert session.end_reason == "habituated"
    assert session.baseline_vas == 7 and session.peak_vas == 9 and session.endpoint_vas == 1
    assert session.habituation_slope is not None
    assert len(context.repos.ratings.list_for_session(session.id)) == 5  # baseline+peak+2 periodic+endpoint
    assert len(context.repos.coping.list_for_session(session.id)) == 4
    # shrink + gallery_open + gallery_close at least
    assert len(context.repos.intensity.list_for_session(session.id)) >= 3


def test_panic_finalizes_with_panic_reason(context, qtbot):
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()

    patient, cues = _patient_with_cue(context)
    window.start_exposure(patient, "meth", cues, [])
    screen = window._active_exposure
    screen._ask_baseline()
    _submit_vas(screen, 8)

    window._on_panic()

    session = context.repos.sessions.list_for_patient(patient.id)[0]
    assert session.end_reason == "panic"
    assert session.ended_at is not None


def test_ambient_bed_and_audio_cue(context, qtbot):
    window = MainWindow(context)
    qtbot.addWidget(window)
    window.show()

    patient = context.repos.patients.create(Patient(code="PT0007", primary_substance="meth",
                                                     created_by=context.clinician.id))
    root = Path(context.config.media_root)
    _make_image(root / "meth" / "cue1.png")
    _make_wav(root / "meth" / "cue_audio.wav")
    _make_wav(root / "sounds" / "ambience.wav")
    context.repos.cues.create(CueConfig(patient_id=patient.id, substance="meth",
                                        media_path="meth/cue1.png", media_type="image", appetitive_rank=0))
    context.repos.cues.create(CueConfig(patient_id=patient.id, substance="meth",
                                        media_path="meth/cue_audio.wav", media_type="audio", appetitive_rank=1))
    cues = context.repos.cues.list_for_patient(patient.id)

    controller = SessionController(context.repos, context.config, patient, context.clinician,
                                   "meth", cues, clock=FakeClock())
    ambient = str(root / "sounds" / "ambience.wav")
    screen = ExposureScreen(window, context, controller, [], ambient_path=ambient)
    window._active_controller = controller
    window._active_exposure = screen

    assert not screen.ambient_btn.isHidden()  # control is enabled when an ambient track is set
    screen._ask_baseline()
    _submit_vas(screen, 5)              # begins exposure, starts ambient bed, loads image cue
    screen.ambient_btn.setChecked(True)  # mute ambient -> logged
    screen._next_cue()                   # advance to the audio cue (show_audio path, no crash)
    screen._end_clicked()
    _submit_vas(screen, 1)

    session = context.repos.sessions.list_for_patient(patient.id)[0]
    intensity = context.repos.intensity.list_for_session(session.id)
    assert any(e.action == "ambient_mute" and e.muted is True for e in intensity)
