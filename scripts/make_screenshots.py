"""Dev-only: render key screens to PNGs for visual verification. Not part of the app.

Usage: python scripts/make_screenshots.py [output_dir]
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QBrush, QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from cravingcrave.config import AppConfig  # noqa: E402
from cravingcrave.domain.models import CueConfig, Patient  # noqa: E402
from cravingcrave.ui.context import AppContext  # noqa: E402
from cravingcrave.ui.main_window import MainWindow  # noqa: E402
from cravingcrave.ui.theme import apply_theme  # noqa: E402


def _gradient_image(path: Path, top: str, bottom: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(900, 600, QImage.Format.Format_RGB32)
    p = QPainter(img)
    grad = QLinearGradient(QPointF(0, 0), QPointF(0, 600))
    grad.setColorAt(0, QColor(top))
    grad.setColorAt(1, QColor(bottom))
    p.fillRect(img.rect(), QBrush(grad))
    p.setPen(QColor("#ffffff"))
    p.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
    p.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter, label)
    p.end()
    img.save(str(path))


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "screenshots"
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    apply_theme(app)

    tmp = Path(tempfile.mkdtemp())
    config = AppConfig(data_dir=tmp / "data", media_root=tmp / "media",
                       db_path=tmp / "data" / "cc.db")
    ctx = AppContext.create(config)

    def grab(name: str) -> None:
        app.processEvents()
        ctx  # keep ref
        window.grab().save(str(out / f"{name}.png"))

    # 1) Login / first-run
    window = MainWindow(ctx)
    window.resize(1180, 760)
    window.show()
    grab("01_login")

    # Seed a clinician + patient + cue media.
    ctx.clinician = ctx.auth.register("dra.lopez", "Dra. López", "demo123456")
    patient = ctx.repos.patients.create(Patient(code="PT0001", primary_substance="meth",
                                                 created_by=ctx.clinician.id))
    _gradient_image(config.media_root / "meth" / "cue1.png", "#3a2a2a", "#7a3b2b", "Señal (ejemplo)")
    _gradient_image(config.media_root / "positive" / "nature.png", "#1f6f3a", "#9be7b0", "Naturaleza")
    ctx.repos.cues.create(CueConfig(patient_id=patient.id, substance="meth",
                                    media_path="meth/cue1.png", media_type="image", appetitive_rank=0))

    window.show_dashboard(); grab("02_dashboard")
    window.show_session_setup(patient)
    window._current.consent.setChecked(True)
    grab("03_setup_consent")

    # Exposure: baseline prompt, then mid-session view.
    positive = [str(config.media_root / "positive" / "nature.png")]
    window.start_exposure(patient, "meth", window._current._exposure_cues()
                          if hasattr(window._current, "_exposure_cues") else
                          ctx.repos.cues.list_for_patient(patient.id), positive)
    screen = window._active_exposure
    screen._ask_baseline()
    grab("04_exposure_baseline_vas")

    # Submit baseline -> cue shows; seed a falling craving curve + a shrink/blur.
    screen.vas_prompt.slider.slider.setValue(8)
    screen.vas_prompt._submit()
    for t, v in [(0, 8), (30, 7), (60, 4), (90, 2)]:
        screen.chart.add_point(t, v)
    screen._on_intensity(70, 25, 10, False, "shrink")
    grab("05_exposure_session")

    # Coping overlay + gallery.
    screen._open_coping(); grab("06_coping_uscs")
    screen.coping_panel._cancel()
    screen._open_gallery(); grab("07_positive_gallery")
    screen.gallery._close()

    window.show_calm(); grab("08_calm_panic")

    print(f"Screenshots written to {out}")


if __name__ == "__main__":
    main()
