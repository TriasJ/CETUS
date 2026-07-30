"""Admin patient-data operations that go beyond a single repo call.

Hard delete removes the patient (the DB ``ON DELETE CASCADE`` handles cues/sessions/events) and
then cleans up the patient's media files on disk — but only files that no *other* patient's cue
still references, so a shared library image is never deleted out from under another patient.
"""

from __future__ import annotations

from pathlib import Path


def hard_delete_patient(repos, media_root, patient_id: int) -> dict:
    """Delete a patient + all their data, and remove their now-orphaned media files."""
    mine = {c.media_path for c in repos.cues.list_for_patient(patient_id)}
    others: set[str] = set()
    for p in repos.patients.list_all():
        if p.id != patient_id:
            others.update(c.media_path for c in repos.cues.list_for_patient(p.id))

    repos.patients.delete(patient_id)   # cascades cues/sessions/ratings/coping/intensity

    removed = 0
    root = Path(media_root)
    for rel in mine - others:           # only files unique to this patient
        f = root / rel
        try:
            if f.is_file():
                f.unlink()
                removed += 1
        except OSError:
            pass
    return {"media_removed": removed}
