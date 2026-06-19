"""Dev-only: render the exposure + gallery screens using the REAL downloaded media."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from cravingcrave.config import AppConfig  # noqa: E402
from cravingcrave.domain.models import CueConfig, Patient  # noqa: E402
from cravingcrave.ui.context import AppContext  # noqa: E402
from cravingcrave.ui.main_window import MainWindow  # noqa: E402
from cravingcrave.ui.theme import apply_theme  # noqa: E402


def main() -> None:
    out = ROOT / "docs" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    apply_theme(app)

    tmp = Path(tempfile.mkdtemp())
    config = AppConfig(data_dir=tmp / "data", media_root=ROOT / "media",
                       db_path=tmp / "data" / "cc.db")
    ctx = AppContext.create(config)
    ctx.clinician = ctx.auth.register("dra", "Dra. López", "demo123456")
    patient = ctx.repos.patients.create(Patient(code="PT0001", primary_substance="alcohol",
                                                 created_by=ctx.clinician.id))

    alcohol = ctx.media.by_category("alcohol")
    for rank, m in enumerate(alcohol):
        ctx.repos.cues.create(CueConfig(patient_id=patient.id, substance="alcohol",
                                        media_path=m.path, media_type=m.media_type,
                                        appetitive_rank=rank))
    positive = [m.absolute_path for m in ctx.media.by_category("positive")]
    cues = ctx.repos.cues.list_for_patient(patient.id)

    window = MainWindow(ctx)
    window.resize(1180, 760)
    window.show()
    window.start_exposure(patient, "alcohol", cues, positive)
    screen = window._active_exposure
    app.processEvents()  # let the screen's deferred baseline prompt fire once
    screen.vas_prompt.slider.slider.setValue(8)
    screen.vas_prompt._submit()
    for t, v in [(0, 8), (30, 6), (60, 3)]:
        screen.chart.add_point(t, v)
    app.processEvents()
    window.grab().save(str(out / "09_exposure_real_media.png"))

    screen._open_gallery()
    app.processEvents()
    window.grab().save(str(out / "10_gallery_real_media.png"))
    print(f"Discovered alcohol={len(alcohol)} positive={len(positive)}. Screenshots in {out}")


if __name__ == "__main__":
    main()
