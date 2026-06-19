"""Dev-only: verify real video playback in the app (uses a fetched CC clip)."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cravingcrave.app  # noqa: F401,E402  (import runs _ensure_media_backend)
from PySide6.QtWidgets import QApplication  # noqa: E402

from cravingcrave.config import AppConfig  # noqa: E402
from cravingcrave.domain.models import CueConfig, Patient  # noqa: E402
from cravingcrave.ui.context import AppContext  # noqa: E402
from cravingcrave.ui.main_window import MainWindow  # noqa: E402
from cravingcrave.ui.theme import apply_theme  # noqa: E402


def main() -> None:
    out = ROOT / "docs" / "screenshots"
    app = QApplication(sys.argv)
    apply_theme(app)
    tmp = Path(tempfile.mkdtemp())
    config = AppConfig(data_dir=tmp / "data", media_root=ROOT / "media", db_path=tmp / "data" / "cc.db")
    ctx = AppContext.create(config)
    ctx.clinician = ctx.auth.register("dra", "Dra. López", "demo123456")
    patient = ctx.repos.patients.create(Patient(code="PT0001", primary_substance="alcohol", created_by=ctx.clinician.id))

    videos = [m for m in ctx.media.by_category("alcohol") if m.media_type == "video"]
    if not videos:
        print("No video found in media/alcohol"); return
    ctx.repos.cues.create(CueConfig(patient_id=patient.id, substance="alcohol",
                                    media_path=videos[0].path, media_type="video", appetitive_rank=0))
    cues = ctx.repos.cues.list_for_patient(patient.id)

    window = MainWindow(ctx); window.resize(1180, 760); window.show()
    window.start_exposure(patient, "alcohol", cues, [])
    screen = window._active_exposure
    app.processEvents()
    screen.vas_prompt.slider.slider.setValue(7)
    screen.vas_prompt._submit()      # loads the video cue

    deadline = time.time() + 5
    while time.time() < deadline:
        app.processEvents()
        if screen.cue_view._player and screen.cue_view._player.hasVideo():
            break
        time.sleep(0.05)

    player = screen.cue_view._player
    print("hasVideo:", player.hasVideo(), "duration(ms):", player.duration())
    # shrink + blur a little to prove the levers apply to video too
    screen._on_intensity(70, 20, 0, False, "shrink")
    for _ in range(20):
        app.processEvents(); time.sleep(0.05)
    window.grab().save(str(out / "13_exposure_video.png"))
    print("saved 13_exposure_video.png")


if __name__ == "__main__":
    main()
