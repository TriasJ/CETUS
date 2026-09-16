"""Orchestration for adaptive cue ordering: pull ratings/cues from repos, run the pure domain
functions, and produce per-patient scores, a suggested order, and the cross-patient population view.
"""

from __future__ import annotations

from collections import defaultdict

from ..domain import cue_ranking as dom


def _population_entries(repos):
    """(substance, media_type, media_path, raw, n) for every rated cue across all patients."""
    entries = []
    for p in repos.patients.list_all():
        cues = {c.id: c for c in repos.cues.list_for_patient(p.id)}
        react = dom.cue_reactivity(repos.ratings.list_for_patient(p.id))
        for cid, r in react.items():
            c = cues.get(cid)
            if c is not None:
                entries.append((c.substance, c.media_type, c.media_path, r["raw"], r["n"]))
    return entries


def _priors(repos):
    return dom.population_prior(_population_entries(repos))


def _meta(cues):
    return {c.id: {"media_path": c.media_path, "substance": c.substance,
                   "media_type": c.media_type,
                   "craving_weight": c.craving_weight} for c in cues}


def patient_cue_scores(repos, patient_id) -> list[dict]:
    """This patient's cues with learned reactivity, shrunk score, n and a low-data flag."""
    cues = repos.cues.list_for_patient(patient_id)
    react = dom.cue_reactivity(repos.ratings.list_for_patient(patient_id))
    scores = dom.shrunk_scores(_meta(cues), react, _priors(repos))
    out = []
    for c in cues:
        s = scores.get(c.id, {})
        out.append({
            "cue_id": c.id, "media_path": c.media_path, "media_type": c.media_type,
            "substance": c.substance, "raw": s.get("raw"), "n": s.get("n", 0),
            "score": s.get("score", 0.0), "low_data": s.get("n", 0) < dom.DEFAULT_K,
        })
    return out


def suggested_ranks(repos, patient_id) -> list[int]:
    """Cue ids in the suggested low→high order (to become the new appetitive_rank sequence)."""
    cues = repos.cues.list_for_patient(patient_id)
    react = dom.cue_reactivity(repos.ratings.list_for_patient(patient_id))
    scores = dom.shrunk_scores(_meta(cues), react, _priors(repos))
    return dom.suggested_order(cues, scores)


def cue_order_rows(repos, patient_id) -> list[dict]:
    """The 'signal order database' for one patient: each cue's learned reactivity, current rank
    and suggested position. Pseudonymous (patient code only)."""
    patient = repos.patients.get(patient_id)
    code = patient.code if patient else str(patient_id)
    cues = repos.cues.list_for_patient(patient_id)
    scores = {r["cue_id"]: r for r in patient_cue_scores(repos, patient_id)}
    pos = {cid: i for i, cid in enumerate(suggested_ranks(repos, patient_id))}
    rows = []
    for c in cues:
        s = scores.get(c.id, {})
        rows.append({
            "patient_code": code, "media_path": c.media_path, "media_type": c.media_type,
            "substance": c.substance, "current_rank": c.appetitive_rank,
            "suggested_position": pos.get(c.id, ""),
            "score": round(s.get("score", 0.0), 2), "n": s.get("n", 0),
            "low_data": int(bool(s.get("low_data", True))),
        })
    return rows


def all_cue_order_rows(repos) -> list[dict]:
    """The full cue-reactivity database across every patient (one row per patient×cue)."""
    rows = []
    for p in repos.patients.list_all():
        rows.extend(cue_order_rows(repos, p.id))
    return rows


def population_reactivity(repos) -> list[dict]:
    """Cross-patient mean reactivity by (substance, media_type) — the prior + admin report."""
    groups: dict[tuple, dict] = defaultdict(lambda: {"vals": [], "patients": set(), "cues": 0})
    for p in repos.patients.list_all():
        cues = {c.id: c for c in repos.cues.list_for_patient(p.id)}
        react = dom.cue_reactivity(repos.ratings.list_for_patient(p.id))
        for cid, r in react.items():
            c = cues.get(cid)
            if c is None:
                continue
            g = groups[(c.substance, c.media_type)]
            g["vals"].append(r["raw"]); g["patients"].add(p.id); g["cues"] += 1
    rows = []
    for (substance, media_type), g in sorted(groups.items()):
        rows.append({
            "substance": substance, "media_type": media_type,
            "mean_reactivity": round(sum(g["vals"]) / len(g["vals"]), 2),
            "n_cues": g["cues"], "n_patients": len(g["patients"]),
        })
    return rows
