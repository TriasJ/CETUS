"""Adaptive cue ordering service: cross-session ratings, per-patient scores, population + CSV."""

import csv

from cravingcrave.data.database import Database
from cravingcrave.data.repositories import Repositories
from cravingcrave.domain.models import Clinician, CravingRating, CueConfig, Patient, Session
from cravingcrave.services import cue_ranking, export


def _seed(tmp_path):
    repos = Repositories(Database(tmp_path / "cc.db"))
    cid = repos.clinicians.create(Clinician(username="u", display_name="U", password_hash="x")).id
    p = repos.patients.create(Patient(code="PT01", primary_substance="meth", created_by=cid))
    c1 = repos.cues.create(CueConfig(patient_id=p.id, substance="meth", media_path="meth/a.png",
                                     media_type="image", appetitive_rank=0))
    c2 = repos.cues.create(CueConfig(patient_id=p.id, substance="meth", media_path="meth/b.png",
                                     media_type="image", appetitive_rank=1))
    s = repos.sessions.create(Session(patient_id=p.id, clinician_id=cid, substance="meth",
                                      app_version="t"))
    # baseline 3; cue1 peaks at 7 (react 4), cue2 at 5 (react 2)
    repos.ratings.add(CravingRating(session_id=s.id, kind="baseline", value=3, cue_config_id=c1.id))
    repos.ratings.add(CravingRating(session_id=s.id, kind="peak", value=7, cue_config_id=c1.id))
    repos.ratings.add(CravingRating(session_id=s.id, kind="periodic", value=5, cue_config_id=c2.id))
    return repos, p, c1, c2


def test_ratings_list_for_patient_across_sessions(tmp_path):
    repos, p, _c1, _c2 = _seed(tmp_path)
    cid2 = repos.clinicians.list_all()[0].id
    s2 = repos.sessions.create(Session(patient_id=p.id, clinician_id=cid2, substance="meth",
                                       app_version="t"))
    repos.ratings.add(CravingRating(session_id=s2.id, kind="baseline", value=4))
    assert len(repos.ratings.list_for_patient(p.id)) == 4    # 3 from s1 + 1 from s2


def test_patient_cue_scores_and_suggested_ranks(tmp_path):
    repos, p, c1, c2 = _seed(tmp_path)
    scores = {row["cue_id"]: row for row in cue_ranking.patient_cue_scores(repos, p.id)}
    assert scores[c1.id]["n"] == 1 and scores[c1.id]["raw"] == 4.0
    assert scores[c2.id]["raw"] == 2.0
    assert scores[c1.id]["low_data"] is True                 # n < K
    # Lower-craving cue (c2) is suggested first.
    assert cue_ranking.suggested_ranks(repos, p.id) == [c2.id, c1.id]


def test_population_reactivity_groups_by_substance_modality(tmp_path):
    repos, _p, _c1, _c2 = _seed(tmp_path)
    rows = cue_ranking.population_reactivity(repos)
    assert len(rows) == 1
    r = rows[0]
    assert r["substance"] == "meth" and r["media_type"] == "image"
    assert r["mean_reactivity"] == 3.0        # (4 + 2) / 2
    assert r["n_cues"] == 2 and r["n_patients"] == 1


def test_cue_order_rows_and_export(tmp_path):
    repos, p, _c1, _c2 = _seed(tmp_path)
    rows = cue_ranking.cue_order_rows(repos, p.id)
    by_path = {r["media_path"]: r for r in rows}
    assert by_path["meth/a.png"]["current_rank"] == 0
    assert by_path["meth/a.png"]["patient_code"] == "PT01"
    # b (lower craving) is suggested first.
    assert by_path["meth/b.png"]["suggested_position"] == 0
    assert by_path["meth/a.png"]["suggested_position"] == 1

    path = tmp_path / "order.csv"
    export.export_cue_order(path, rows)
    with open(path, encoding="utf-8-sig", newline="") as fh:
        got = list(csv.DictReader(fh))
    assert len(got) == 2
    assert set(got[0].keys()) == set(export.CUE_ORDER_COLUMNS)   # no PII columns


def test_all_cue_order_rows_spans_patients(tmp_path):
    repos, _p, _c1, _c2 = _seed(tmp_path)
    assert len(cue_ranking.all_cue_order_rows(repos)) == 2   # one patient, two cues


def test_export_population_reactivity_csv(tmp_path):
    rows = [{"substance": "meth", "media_type": "image", "mean_reactivity": 3.0,
             "n_cues": 2, "n_patients": 1}]
    path = tmp_path / "pop.csv"
    export.export_population_reactivity(path, rows)
    with open(path, encoding="utf-8-sig", newline="") as fh:
        got = list(csv.DictReader(fh))
    assert got[0]["substance"] == "meth" and got[0]["mean_reactivity"] == "3.0"
    assert set(got[0].keys()) == set(export.POPULATION_REACTIVITY_COLUMNS)
