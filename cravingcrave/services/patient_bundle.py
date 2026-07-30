"""Compose one patient's CSV exports into a single zip bundle.

Reuses the privacy-conscious writers in ``services.export`` (only the pseudonymous ``code`` ever
appears), so the bundle carries no PII beyond what a single-report export already would.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from . import export


def create_patient_bundle(dest_zip, patient_code: str, sessions, per_session,
                          coping_pairs, skill_labels=None) -> dict:
    """Write a zip of this patient's data.

    ``sessions``: the patient's sessions. ``per_session``: dict[session_id] -> (ratings, coping,
    intensity). ``coping_pairs``: list of (session, coping_events). Returns a small summary dict.
    """
    dest_zip = Path(dest_zip)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        summary = tmp / "sessions_summary.csv"
        export.export_sessions_summary(summary, patient_code, sessions)
        coping = tmp / "coping_responses.csv"
        export.export_coping_responses(coping, patient_code, coping_pairs, skill_labels)
        timelines = []
        for s in sessions:
            ratings, cop, intensity = per_session.get(s.id, ([], [], []))
            tl = tmp / f"timeline_session_{s.id}.csv"
            export.export_session_timeline(tl, patient_code, s, ratings, cop, intensity)
            timelines.append(tl)
        with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(summary, summary.name); written += 1
            z.write(coping, coping.name); written += 1
            for tl in timelines:
                z.write(tl, tl.name); written += 1
    return {"files": written, "sessions": len(sessions)}
