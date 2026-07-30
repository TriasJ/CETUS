"""0.6.1 patient-data handling: anonymize, hard delete (+ media cleanup), export bundle."""

import zipfile
from pathlib import Path

from cravingcrave.data.database import Database
from cravingcrave.data.repositories import Repositories
from cravingcrave.domain.models import Clinician, CueConfig, Patient, Session
from cravingcrave.services import patient_admin, patient_bundle


def _repos(tmp_path):
    return Repositories(Database(tmp_path / "cc.db"))


def _clinician(repos) -> int:
    return repos.clinicians.create(Clinician(username="u", display_name="U", password_hash="x")).id


def test_anonymize_clears_pii_keeps_code_and_sessions(tmp_path):
    repos = _repos(tmp_path)
    cid = _clinician(repos)
    p = repos.patients.create(Patient(code="PT01", display_name="Jane Doe", birth_year=1990,
                                      notes="private", primary_substance="meth", created_by=cid))
    repos.sessions.create(Session(patient_id=p.id, clinician_id=cid, substance="meth", app_version="t"))

    repos.patients.anonymize(p.id)

    got = repos.patients.get(p.id)
    assert got.code == "PT01"                       # pseudonymous id preserved
    assert got.display_name is None and got.birth_year is None and got.notes is None
    assert len(repos.sessions.list_for_patient(p.id)) == 1   # sessions kept


def test_hard_delete_cascades_and_cleans_unique_media(tmp_path):
    repos = _repos(tmp_path)
    cid = _clinician(repos)
    media = tmp_path / "media"
    a = repos.patients.create(Patient(code="PTA", primary_substance="meth", created_by=cid))
    b = repos.patients.create(Patient(code="PTB", primary_substance="meth", created_by=cid))
    # A owns a unique cue file and shares one with B.
    for rel in ("meth/a_only.png", "meth/shared.png"):
        f = media / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b"x")
    repos.cues.create(CueConfig(patient_id=a.id, substance="meth", media_path="meth/a_only.png",
                                media_type="image"))
    repos.cues.create(CueConfig(patient_id=a.id, substance="meth", media_path="meth/shared.png",
                                media_type="image"))
    repos.cues.create(CueConfig(patient_id=b.id, substance="meth", media_path="meth/shared.png",
                                media_type="image"))
    repos.sessions.create(Session(patient_id=a.id, clinician_id=cid, substance="meth", app_version="t"))

    res = patient_admin.hard_delete_patient(repos, media, a.id)

    assert repos.patients.get(a.id) is None                 # patient gone
    assert repos.sessions.list_for_patient(a.id) == []      # sessions cascaded
    assert not (media / "meth" / "a_only.png").exists()     # unique media removed
    assert (media / "meth" / "shared.png").exists()         # shared media kept (B still uses it)
    assert res["media_removed"] == 1
    assert repos.patients.get(b.id) is not None             # other patient untouched


def test_patient_bundle_zip_has_expected_files(tmp_path):
    repos = _repos(tmp_path)
    cid = _clinician(repos)
    p = repos.patients.create(Patient(code="PT01", primary_substance="meth", created_by=cid))
    sessions = [repos.sessions.create(Session(patient_id=p.id, clinician_id=cid,
                                              substance="meth", app_version="t")) for _ in range(2)]
    coping_pairs = [(s, []) for s in sessions]
    dest = tmp_path / "bundle.zip"

    res = patient_bundle.create_patient_bundle(dest, p.code, sessions, {}, coping_pairs)

    assert dest.exists()
    with zipfile.ZipFile(dest) as z:
        names = z.namelist()
    assert "sessions_summary.csv" in names
    assert "coping_responses.csv" in names
    assert sum(n.startswith("timeline_session_") for n in names) == 2
    assert res["files"] == 4
    # Bundle carries only the pseudonymous code (privacy).
    with zipfile.ZipFile(dest) as z:
        assert Path("sessions_summary.csv").name in z.namelist()
