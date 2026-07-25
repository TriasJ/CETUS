"""Export tests — especially the privacy guarantee that no PII leaks."""

from pathlib import Path

from cravingcrave.domain.models import CopingEvent, CravingRating, Session
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
    assert "ts" in lines[0].split(",")  # absolute timestamp now included
    assert len(lines) == 3  # header + 2 ratings


def test_export_timeline_includes_coping_ts_and_detail(tmp_path: Path):
    s = Session(id=7, patient_id=1, clinician_id=1, substance="alcohol",
                started_at="2026-05-26T00:00:00+00:00", app_version="0.4.0")
    coping = [CopingEvent(session_id=7, ts="2026-05-26T00:01:00+00:00", elapsed_sec=60,
                          skill="name_feeling", detail="me siento ansioso")]
    out = export.export_session_timeline(tmp_path / "t.csv", "PT0001", s, [], coping, [])
    text = out.read_text(encoding="utf-8-sig")
    assert "me siento ansioso" in text and "2026-05-26T00:01:00+00:00" in text


def test_export_coping_responses_columns_and_content(tmp_path: Path):
    s = Session(id=3, patient_id=1, clinician_id=1, substance="meth",
                started_at="2026-05-26T00:00:00+00:00", app_version="0.4.0")
    events = [
        CopingEvent(session_id=3, ts="2026-05-26T00:02:00+00:00", elapsed_sec=120,
                    skill="recall_benefit", detail="dormir mejor"),
        CopingEvent(session_id=3, ts="2026-05-26T00:03:00+00:00", elapsed_sec=180,
                    skill="alternative_action", detail=""),  # used but blank
    ]
    labels = {"recall_benefit": "Recordar un beneficio",
              "alternative_action": "Elegir una alternativa"}
    out = export.export_coping_responses(tmp_path / "c.csv", "PT0001", [(s, events)], labels)
    lines = out.read_text(encoding="utf-8-sig").strip().splitlines()
    assert lines[0] == ",".join(export.COPING_COLUMNS)
    assert len(lines) == 3  # header + 2 responses
    body = "\n".join(lines[1:])
    assert "dormir mejor" in body and "Recordar un beneficio" in body
    assert "recall_benefit" in body  # stable language-neutral key retained
    assert "PT0001" in body and "meth" in body


def test_export_coping_no_pii_columns():
    forbidden = {"display_name", "birth_year", "notes", "name"}
    assert forbidden.isdisjoint(set(export.COPING_COLUMNS))


def test_password_hash_roundtrip():
    h = hash_password("s3cret")
    assert verify_password("s3cret", h)
    assert not verify_password("wrong", h)
    assert "s3cret" not in h  # never store plaintext
