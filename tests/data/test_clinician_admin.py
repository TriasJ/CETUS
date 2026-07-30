"""0.6.2 clinician management: disable-blocks-login, rename, delete guard, transfer ownership."""

from cravingcrave.data.database import Database
from cravingcrave.data.repositories import Repositories
from cravingcrave.domain.models import Patient, Session
from cravingcrave.services.auth import AuthService


def _setup(tmp_path):
    repos = Repositories(Database(tmp_path / "cc.db"))
    auth = AuthService(repos.clinicians)
    return repos, auth


def test_disabled_clinician_cannot_log_in(tmp_path):
    repos, auth = _setup(tmp_path)
    c = auth.register("dra", "Dra", "pw123456")
    assert auth.login("dra", "pw123456") is not None      # enabled: ok
    repos.clinicians.set_disabled(c.id, True)
    assert auth.login("dra", "pw123456") is None          # disabled: blocked
    repos.clinicians.set_disabled(c.id, False)
    assert auth.login("dra", "pw123456") is not None      # re-enabled: ok


def test_rename_and_delete_guard(tmp_path):
    repos, auth = _setup(tmp_path)
    a = auth.register("a", "Alpha", "pw123456")
    repos.clinicians.set_display_name(a.id, "Renamed")
    assert repos.clinicians.get_by_username("a").display_name == "Renamed"
    # Owns a patient → owns_counts non-zero (delete should be refused by the UI).
    repos.patients.create(Patient(code="PT01", primary_substance="meth", created_by=a.id))
    assert repos.clinicians.owns_counts(a.id)[0] == 1
    # A clinician owning nothing can be deleted.
    b = auth.register("b", "Beta", "pw123456")
    assert repos.clinicians.owns_counts(b.id) == (0, 0)
    repos.clinicians.delete(b.id)
    assert repos.clinicians.get_by_username("b") is None


def test_transfer_patient_ownership_keeps_session_clinician(tmp_path):
    repos, auth = _setup(tmp_path)
    a = auth.register("a", "Alpha", "pw123456")
    b = auth.register("b", "Beta", "pw123456")
    p = repos.patients.create(Patient(code="PT01", primary_substance="meth", created_by=a.id))
    sess = repos.sessions.create(Session(patient_id=p.id, clinician_id=a.id,
                                         substance="meth", app_version="t"))

    moved = repos.patients.reassign_owner(a.id, b.id)

    assert moved == 1
    assert repos.patients.get(p.id).created_by == b.id            # ownership transferred
    assert repos.sessions.get(sess.id).clinician_id == a.id       # history preserved
    assert repos.patients.count_for_owner(a.id) == 0
