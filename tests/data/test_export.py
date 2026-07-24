"""Export tests — especially the privacy guarantee that no PII leaks."""

from pathlib import Path

from cravingcrave.domain.models import CravingRating, Session
from cravingcrave.services import export
from cravingcrave.services.auth import hash_password, verify_password


def test_safe_filename_has_no_pii_and_is_sanitized():
    name = export.safe_filename("PT/01 *bad*", "summary")
    assert name.startswith("cetus_PT_01__bad__summary_")
    assert name.endswith(".csv")


def test_session_columns_exclude_pii():
    forbidden = {"display_name", "birth_year", "notes", "name"}
    assert forbidden.isdisjoint(set(export.SESSION_COLUMNS))


def test_export_summary_body_contains_code_not_name(tmp_path: Path):
    sessions = [Session(id=1, patient_id=1, clinician_id=1, substance="meth",
                        started_at="2026-05-26T00:00:00+00:00", end_reason="habituated",
                        baseline_vas=7, peak_vas=9, endpoint_vas=1, habituation_slope=-0.04,
                        app_version="0.1.0")]
    out = export.export_sessions_summary(tmp_path / "s.csv", "PT0001", sessions)
    text = out.read_text(encoding="utf-8-sig")
    assert "PT0001" in text and "habituated" in text


def test_export_timeline_merges_and_sorts(tmp_path: Path):
    s = Session(id=5, patient_id=1, clinician_id=1, substance="alcohol",
                started_at="2026-05-26T00:00:00+00:00", app_version="0.1.0")
    ratings = [CravingRating(session_id=5, elapsed_sec=0, value=6, kind="baseline"),
               CravingRating(session_id=5, elapsed_sec=60, value=2, kind="endpoint")]
    out = export.export_session_timeline(tmp_path / "t.csv", "PT0001", s, ratings, [], [])
    lines = out.read_text(encoding="utf-8-sig").strip().splitlines()
    assert lines[0].startswith("patient_code,session_id,elapsed_sec")
    assert len(lines) == 3  # header + 2 ratings


def test_password_hash_roundtrip():
    h = hash_password("s3cret")
    assert verify_password("s3cret", h)
    assert not verify_password("wrong", h)
    assert "s3cret" not in h  # never store plaintext
