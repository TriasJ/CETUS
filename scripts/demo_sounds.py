"""Dev-only: screenshots of the sound features (ambient selector + audio-cue placeholder)."""

from __future__ import annotations

import math
import os
import struct
import sys
import tempfile
import wave
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from cravingcrave.config import AppConfig  # noqa: E402
from cravingcrave.domain.models import CueConfig, Patient  # noqa: E402
from cravingcrave.ui.context import AppContext  # noqa: E402
from cravingcrave.ui.main_window import MainWindow  # noqa: E402
from cravingcrave.ui.theme import apply_theme  # noqa: E402


def _img(path: Path, color) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im = QImage(400, 300, QImage.Format.Format_RGB32)
    im.fill(color)
    im.save(str(path))


def _wav(path: Path, seconds=0.3, freq=440, rate=8000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        for i in range(int(seconds * rate)):
            w.writeframes(struct.pack("<h", int(32767 * 0.2 * math.sin(2 * math.pi * freq * i / rate))))


def main() -> None:
    out = ROOT / "docs" / "screenshots"
    app = QApplication(sys.argv)
    apply_theme(app)
    tmp = Path(tempfile.mkdtemp())
    config = AppConfig(data_dir=tmp / "data", media_root=tmp / "media", db_path=tmp / "data" / "cc.db")
    ctx = AppContext.create(config)
    ctx.clinician = ctx.auth.register("dra", "Dra. López", "demo123456")
    patient = ctx.repos.patients.create(Patient(code="PT0001", primary_substance="meth", created_by=ctx.clinician.id))

    _img(config.media_root / "meth" / "cue1.png", Qt.GlobalColor.darkRed)
    _wav(config.media_root / "meth" / "sonido_consumo.wav")
    _wav(config.media_root / "sounds" / "ambiente_calle.wav")
    ctx.repos.cues.create(CueConfig(patient_id=patient.id, substance="meth", media_path="meth/cue1.png", media_type="image", appetitive_rank=0))
    ctx.repos.cues.create(CueConfig(patient_id=patient.id, substance="meth", media_path="meth/sonido_consumo.wav", media_type="audio", appetitive_rank=1))
    cues = ctx.repos.cues.list_for_patient(patient.id)

    window = MainWindow(ctx); window.resize(1180, 760); window.show()
    window.show_session_setup(patient)
    window._current.consent.setChecked(True)
    app.processEvents()
    window.grab().save(str(out / "11_setup_with_sound.png"))

    ambient = str(config.media_root / "sounds" / "ambiente_calle.wav")
    window.start_exposure(patient, "meth", cues, [], ambient)
    screen = window._active_exposure
    app.processEvents()
    screen.vas_prompt.slider.slider.setValue(6); screen.vas_prompt._submit()
    screen._next_cue()  # advance to the audio cue -> shows the music-note placeholder
    app.processEvents()
    window.grab().save(str(out / "12_audio_cue.png"))
    print(f"Wrote sound-feature screenshots to {out}")


if __name__ == "__main__":
    main()
