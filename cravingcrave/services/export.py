"""CSV export of clinical data — privacy-conscious by construction.

Only the pseudonymous patient ``code`` ever appears in a filename or a CSV cell.
``display_name``, ``birth_year`` and ``notes`` are deliberately excluded via an
explicit column allowlist (enforced by tests), so an exported file cannot leak
identity if shared with a researcher.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from ..domain.models import CopingEvent, CravingRating, IntensityEvent, Session

# Explicit allowlist — PII columns (display_name/birth_year/notes) are NOT here.
SESSION_COLUMNS = [
    "session_id", "patient_code", "substance", "started_at", "ended_at",
    "end_reason", "consent_given", "baseline_vas", "peak_vas", "endpoint_vas",
    "habituation_slope", "app_version",
]

_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def safe_filename(patient_code: str, suffix: str) -> str:
    code = _SAFE.sub("_", patient_code or "anon")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"cetus_{code}_{suffix}_{stamp}.csv"


def export_sessions_summary(path: Path, patient_code: str, sessions: Sequence[Session]) -> Path:
    """One row per session (summary view)."""
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=SESSION_COLUMNS)
        writer.writeheader()
        for s in sessions:
            writer.writerow({
                "session_id": s.id,
                "patient_code": patient_code,
                "substance": s.substance,
                "started_at": s.started_at,
                "ended_at": s.ended_at or "",
                "end_reason": s.end_reason or "",
                "consent_given": int(s.consent_given),
                "baseline_vas": s.baseline_vas if s.baseline_vas is not None else "",
                "peak_vas": s.peak_vas if s.peak_vas is not None else "",
                "endpoint_vas": s.endpoint_vas if s.endpoint_vas is not None else "",
                "habituation_slope": "" if s.habituation_slope is None else round(s.habituation_slope, 5),
                "app_version": s.app_version,
            })
    return path


def export_session_timeline(
    path: Path,
    patient_code: str,
    session: Session,
    ratings: Sequence[CravingRating],
    coping: Sequence[CopingEvent],
    intensity: Sequence[IntensityEvent],
) -> Path:
    """Long-format event timeline for a single session (craving + coping + intensity).

    Carries the absolute ISO ``ts`` alongside ``elapsed_sec`` so the file is usable for
    qualitative coding (the coping ``detail`` is the patient's free-text response)."""
    rows = []
    for r in ratings:
        rows.append((r.elapsed_sec, r.ts, "craving", r.kind, str(r.value), ""))
    for e in coping:
        rows.append((e.elapsed_sec, e.ts, "coping", e.skill, "", e.detail or ""))
    for e in intensity:
        detail = f"scale={e.scale_pct} blur={e.blur_pct} dim={e.dim_pct} muted={e.muted}"
        rows.append((e.elapsed_sec, e.ts, "intensity", e.action, "", detail))
    rows.sort(key=lambda x: x[0])

    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["patient_code", "session_id", "elapsed_sec", "ts",
                         "event_type", "label", "value", "detail"])
        for elapsed, ts, etype, label, value, detail in rows:
            writer.writerow([patient_code, session.id, elapsed, ts, etype, label, value, detail])
    return path


# One row per USCS coping response. `skill` is the stable language-neutral key;
# `skill_label` is a localized human-readable label supplied by the caller.
COPING_COLUMNS = [
    "patient_code", "session_id", "substance", "session_started_at", "ts",
    "elapsed_sec", "skill", "skill_label", "response_text",
]


def export_coping_responses(
    path: Path,
    patient_code: str,
    sessions_coping: Sequence[tuple[Session, Sequence[CopingEvent]]],
    skill_labels: dict[str, str] | None = None,
) -> Path:
    """Analysis-ready export of the four USCS ("afrontamiento") free-text responses.

    One row per response across every session, timestamped and linked to the
    pseudonymous patient code — for qualitative study. No PII beyond ``code``."""
    labels = skill_labels or {}
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=COPING_COLUMNS)
        writer.writeheader()
        for session, events in sessions_coping:
            for e in events:
                writer.writerow({
                    "patient_code": patient_code,
                    "session_id": session.id,
                    "substance": session.substance,
                    "session_started_at": session.started_at,
                    "ts": e.ts,
                    "elapsed_sec": e.elapsed_sec,
                    "skill": e.skill,
                    "skill_label": labels.get(e.skill, e.skill),
                    "response_text": e.detail or "",
                })
    return path
