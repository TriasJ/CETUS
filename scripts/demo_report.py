"""Dev-only: screenshot the clinical Report (session-detail tab + progress tab)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from cravingcrave.config import AppConfig  # noqa: E402
from cravingcrave.domain.models import (  # noqa: E402
    CopingEvent, CravingRating, CueConfig, IntensityEvent, Patient, Session,
)
from cravingcrave.ui.context import AppContext  # noqa: E402
from cravingcrave.ui.screens.report_screen import ReportScreen  # noqa: E402
from cravingcrave.ui.theme import apply_theme  # noqa: E402


def _img(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    QImage(20, 20, QImage.Format.Format_RGB32).save(str(p))


def main() -> None:
    app = QApplication(sys.argv)
    apply_theme(app)
    tmp = Path(tempfile.mkdtemp())
    cfg = AppConfig(data_dir=tmp / "data", media_root=tmp / "media", db_path=tmp / "data" / "cc.db")
    ctx = AppContext.create(cfg)
    ctx.clinician = ctx.auth.register("dra", "Dra. López", "x")
    patient = ctx.repos.patients.create(Patient(code="PT0007", primary_substance="alcohol",
                                                 created_by=ctx.clinician.id))
    cues = []
    for rank, name in enumerate(["bar/distal.jpg", "bar/medio.jpg", "bar/cerveza_closeup.jpg"]):
        _img(cfg.media_root / name)
        cues.append(ctx.repos.cues.create(CueConfig(
            patient_id=patient.id, substance="alcohol", media_path=name, media_type="image",
            appetitive_rank=rank)))

    # Seed three sessions with a realistic profile: peak around middle cue, slope going negative.
    for sess_i, (b, p_, e, slope) in enumerate(
        [(8, 9, 4, -0.02), (8, 9, 2, -0.04), (7, 8, 1, -0.06)], start=1
    ):
        s = ctx.repos.sessions.create(Session(
            patient_id=patient.id, clinician_id=ctx.clinician.id,
            substance="alcohol", consent_given=True, app_version="t"))
        seq = [(0, b, "baseline", cues[0].id), (30, p_, "peak", cues[1].id),
               (60, max(0, p_ - 3), "periodic", cues[1].id),
               (90, max(0, p_ - 5), "periodic", cues[2].id), (120, e, "endpoint", cues[2].id)]
        for elapsed, value, kind, cid in seq:
            ctx.repos.ratings.add(CravingRating(session_id=s.id, elapsed_sec=elapsed,
                                                value=value, kind=kind, cue_config_id=cid))
        for elapsed, skill, detail in [
            (40, "name_feeling", "Ansiedad, opresión en el pecho."),
            (55, "recall_negative", "Perdí una promoción por beber el viernes."),
            (80, "recall_benefit", "Estoy presente con mis hijos los fines de semana."),
            (95, "alternative_action", "Llamé a mi padrino y salí a caminar."),
        ]:
            ctx.repos.coping.add(CopingEvent(session_id=s.id, elapsed_sec=elapsed,
                                             skill=skill, detail=detail))
        ctx.repos.intensity.add(IntensityEvent(session_id=s.id, elapsed_sec=70,
                                               action="shrink", scale_pct=60))
        ctx.repos.intensity.add(IntensityEvent(session_id=s.id, elapsed_sec=85,
                                               action="blur", blur_pct=40))
        s.started_at = f"2026-05-2{sess_i}T18:00:00+00:00"
        s.ended_at   = f"2026-05-2{sess_i}T18:02:30+00:00"
        s.end_reason = "habituated"
        s.baseline_vas, s.peak_vas, s.endpoint_vas, s.habituation_slope = b, p_, e, slope
        ctx.repos.sessions.finalize(s)
        ctx.repos.sessions.update_notes(s.id, (
            f"Sesión {sess_i}: paciente más cómodo afrontando la señal del bar. "
            "Habituación marcada al cierre. Revisar señales 2 y 3 (mayor reactividad)."
        ))

    out = ROOT / "docs" / "screenshots"
    screen = ReportScreen(window=None, context=ctx, patient=patient)
    screen.resize(1180, 760)
    screen.show()
    app.processEvents()
    screen.tabs.setCurrentIndex(0)
    app.processEvents()
    screen.grab().save(str(out / "18_report_session.png"))
    screen.tabs.setCurrentIndex(1)
    app.processEvents()
    screen.grab().save(str(out / "19_report_progress.png"))
    print("wrote report screenshots")


if __name__ == "__main__":
    main()
