from cravingcrave.data.database import Database
from cravingcrave.data.repositories import Repositories
from cravingcrave.domain.models import (
    Clinician, CopingEvent, CravingRating, CueConfig, IntensityEvent, Patient, Session,
)


def make_repos():
    return Repositories(Database(":memory:"))


def test_schema_version_set():
    db = Database(":memory:")
    ver = db.conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert ver == 2
    # v2 column present (and migration is idempotent on fresh DBs).
    cols = [r[1] for r in db.conn.execute("PRAGMA table_info(session)").fetchall()]
    assert "clinician_notes" in cols


def test_update_clinician_notes_roundtrip():
    r = make_repos()
    c = r.clinicians.create(Clinician(username="u", display_name="U", password_hash="x"))
    p = r.patients.create(Patient(code="PT-N1", created_by=c.id))
    s = r.sessions.create(Session(patient_id=p.id, clinician_id=c.id, substance="alcohol", app_version="t"))
    assert r.sessions.get(s.id).clinician_notes is None
    r.sessions.update_notes(s.id, "Habituación rápida; revisar señales 2 y 3.")
    assert r.sessions.get(s.id).clinician_notes == "Habituación rápida; revisar señales 2 y 3."
    r.sessions.update_notes(s.id, None)                       # clearing works
    assert r.sessions.get(s.id).clinician_notes is None


def test_clinician_and_patient_roundtrip():
    r = make_repos()
    c = r.clinicians.create(Clinician(username="dra.lopez", display_name="Dra. López", password_hash="x"))
    assert c.id is not None
    assert r.clinicians.get_by_username("dra.lopez").display_name == "Dra. López"
    assert r.clinicians.count() == 1

    p = r.patients.create(Patient(code="PT0001", display_name="Secret Name", primary_substance="meth", created_by=c.id))
    assert p.id is not None
    assert [pp.code for pp in r.patients.list_active()] == ["PT0001"]


def test_full_session_logging_roundtrip():
    r = make_repos()
    c = r.clinicians.create(Clinician(username="u", display_name="U", password_hash="x"))
    p = r.patients.create(Patient(code="PT0002", created_by=c.id))
    cue = r.cues.create(CueConfig(patient_id=p.id, substance="meth", media_path="meth/1.jpg", media_type="image", appetitive_rank=10))

    s = r.sessions.create(Session(patient_id=p.id, clinician_id=c.id, substance="meth", consent_given=True, app_version="0.1.0"))
    r.ratings.add(CravingRating(session_id=s.id, elapsed_sec=0, value=3, kind="baseline", cue_config_id=cue.id))
    r.ratings.add(CravingRating(session_id=s.id, elapsed_sec=30, value=8, kind="peak", cue_config_id=cue.id))
    r.ratings.add(CravingRating(session_id=s.id, elapsed_sec=120, value=1, kind="endpoint", cue_config_id=cue.id))
    r.coping.add(CopingEvent(session_id=s.id, elapsed_sec=40, skill="recall_negative", detail="perdí mi trabajo"))
    r.intensity.add(IntensityEvent(session_id=s.id, elapsed_sec=45, action="shrink", scale_pct=40, muted=True))

    s.ended_at = "2026-05-26T00:02:00+00:00"
    s.end_reason = "habituated"
    s.baseline_vas, s.peak_vas, s.endpoint_vas = 3, 8, 1
    s.habituation_slope = -0.05
    r.sessions.finalize(s)

    got = r.sessions.get(s.id)
    assert got.end_reason == "habituated" and got.peak_vas == 8
    assert len(r.ratings.list_for_session(s.id)) == 3
    assert r.coping.list_for_session(s.id)[0].detail == "perdí mi trabajo"
    ie = r.intensity.list_for_session(s.id)[0]
    assert ie.action == "shrink" and ie.scale_pct == 40 and ie.muted is True


def test_cascade_delete_patient_removes_sessions():
    r = make_repos()
    c = r.clinicians.create(Clinician(username="u", display_name="U", password_hash="x"))
    p = r.patients.create(Patient(code="PT0003", created_by=c.id))
    s = r.sessions.create(Session(patient_id=p.id, clinician_id=c.id, substance="alcohol", app_version="0.1.0"))
    r.ratings.add(CravingRating(session_id=s.id, elapsed_sec=0, value=5, kind="baseline"))
    with r.db.transaction() as conn:
        conn.execute("DELETE FROM patient WHERE id = ?", (p.id,))
    assert r.sessions.get(s.id) is None
    assert r.ratings.list_for_session(s.id) == []


def test_settings_upsert():
    r = make_repos()
    assert r.settings.get("therapist_phone", "none") == "none"
    r.settings.set("therapist_phone", "33-1111-2222")
    r.settings.set("therapist_phone", "33-3333-4444")
    assert r.settings.get("therapist_phone") == "33-3333-4444"
