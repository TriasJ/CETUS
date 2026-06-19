"""Archiving a patient hides it from the active roster but keeps the data."""

from cravingcrave.data.database import Database
from cravingcrave.data.repositories import Repositories
from cravingcrave.domain.models import Clinician, Patient


def test_archive_excludes_from_active():
    r = Repositories(Database(":memory:"))
    c = r.clinicians.create(Clinician(username="u", display_name="U", password_hash="x"))
    p = r.patients.create(Patient(code="PT9", created_by=c.id))
    assert [x.code for x in r.patients.list_active()] == ["PT9"]

    p.archived = True
    r.patients.update(p)
    assert r.patients.list_active() == []          # hidden from roster
    assert r.patients.get(p.id).archived is True     # but still in the DB
