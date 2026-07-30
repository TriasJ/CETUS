"""0.6.3 cohort & per-clinician reporting: aggregation, CSV exports, per-clinician queries."""

import csv

from cravingcrave.data.database import Database
from cravingcrave.data.repositories import Repositories
from cravingcrave.domain import reports
from cravingcrave.domain.models import Clinician, Patient, Session
from cravingcrave.services import export


def _repos(tmp_path):
    return Repositories(Database(tmp_path / "cc.db"))


def test_cohort_summary_and_totals():
    # Two finished sessions: peak 8→endpoint 2 (75% reduction) and peak 10→5 (50%).
    s1 = Session(baseline_vas=5, peak_vas=8, endpoint_vas=2, habituation_slope=-0.4,
                 started_at="2026-07-01")
    s2 = Session(baseline_vas=6, peak_vas=10, endpoint_vas=5, habituation_slope=-0.2,
                 started_at="2026-07-10")
    unfinished = Session(baseline_vas=None, started_at="2026-07-20")
    rows = reports.cohort_summary([("PT01", "meth", [s1, s2, unfinished])])
    r = rows[0]
    assert r["patient_code"] == "PT01" and r["n_sessions"] == 2   # unfinished excluded
    assert r["mean_pct_reduction"] == 62.5                        # (75 + 50) / 2
    assert r["last_session_at"] == "2026-07-10"
    totals = reports.cohort_totals(rows)
    assert totals["patients"] == 1 and totals["sessions"] == 2


def test_export_cohort_summary_csv(tmp_path):
    rows = [{"patient_code": "PT01", "primary_substance": "meth", "n_sessions": 2,
             "mean_pct_reduction": 62.5, "mean_slope": -0.3, "last_session_at": "2026-07-10"},
            {"patient_code": "PT02", "primary_substance": "alcohol", "n_sessions": 0,
             "mean_pct_reduction": None, "mean_slope": None, "last_session_at": ""}]
    path = tmp_path / "cohort.csv"
    export.export_cohort_summary(path, rows)
    with open(path, encoding="utf-8-sig", newline="") as fh:
        got = list(csv.DictReader(fh))
    assert got[0]["patient_code"] == "PT01" and got[0]["mean_pct_reduction"] == "62.5"
    assert got[1]["mean_pct_reduction"] == ""          # None -> blank cell
    # No PII columns leaked.
    assert set(got[0].keys()) == set(export.COHORT_COLUMNS)


def test_export_clinician_activity_csv(tmp_path):
    rows = [{"clinician": "dra", "patients": 3, "sessions": 12}]
    path = tmp_path / "activity.csv"
    export.export_clinician_activity(path, rows)
    with open(path, encoding="utf-8-sig", newline="") as fh:
        got = list(csv.DictReader(fh))
    assert got[0]["clinician"] == "dra" and got[0]["sessions"] == "12"


def test_per_clinician_queries(tmp_path):
    repos = _repos(tmp_path)
    a = repos.clinicians.create(Clinician(username="a", display_name="A", password_hash="x"))
    b = repos.clinicians.create(Clinician(username="b", display_name="B", password_hash="x"))
    pa = repos.patients.create(Patient(code="PA", primary_substance="meth", created_by=a.id))
    repos.patients.create(Patient(code="PB", primary_substance="meth", created_by=b.id))
    repos.sessions.create(Session(patient_id=pa.id, clinician_id=a.id, substance="meth", app_version="t"))

    assert [p.code for p in repos.patients.list_for_clinician(a.id)] == ["PA"]
    assert len(repos.sessions.list_for_clinician(a.id)) == 1
    assert repos.sessions.list_for_clinician(b.id) == []
