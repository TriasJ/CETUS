"""Adaptive cue ordering — learn a per-patient low→high craving hierarchy from recorded ratings.

Pure functions (no Qt, no DB). A cue's reactivity in one session is the **peak craving recorded
while that cue was on screen, minus the session's baseline**. Baseline-kind ratings are excluded
from the on-cue peaks: the baseline row is stamped with the first cue's id but it is the
pre-exposure anchor, not a reaction to that cue. Small samples are shrunk toward a cross-patient
population prior so a single noisy reading (or a never-rated cue) doesn't drive the order.

Everything here is **suggested / exploratory** — the clinician reviews and applies the order.
"""

from __future__ import annotations

from collections import defaultdict

EXPOSURE_KINDS = ("periodic", "peak", "endpoint")
BASELINE_KIND = "baseline"
DEFAULT_K = 3   # shrinkage pseudo-count (weight given to the population prior)


def cue_reactivity(ratings) -> dict[int, dict]:
    """Per-cue reactivity for one patient across sessions: {cue_id: {"raw": mean, "n": sessions}}.

    ``ratings`` = all of a patient's ratings (any session). For each session with a baseline,
    each cue's reactivity = max(on-cue periodic/peak/endpoint value) − session baseline.
    """
    by_session: dict[int, list] = defaultdict(list)
    for r in ratings:
        by_session[r.session_id].append(r)

    per_cue: dict[int, list[float]] = defaultdict(list)
    for rs in by_session.values():
        baselines = [int(r.value) for r in rs if r.kind == BASELINE_KIND]
        if not baselines:
            continue
        base = baselines[0]
        peaks: dict[int, list[int]] = defaultdict(list)
        for r in rs:
            if r.kind in EXPOSURE_KINDS and r.cue_config_id is not None:
                peaks[r.cue_config_id].append(int(r.value))
        for cid, vals in peaks.items():
            per_cue[cid].append(max(vals) - base)
    return {cid: {"raw": sum(v) / len(v), "n": len(v)} for cid, v in per_cue.items()}


def population_prior(entries) -> dict:
    """Build the cross-patient prior from ``(substance, media_type, media_path, raw, n)`` rows.

    Returns priors keyed by shared ``media_path``, by ``(substance, media_type)``, and a global
    fallback mean — consulted in that order by :func:`shrunk_scores`."""
    by_media: dict[str, list[float]] = defaultdict(list)
    by_cat: dict[tuple, list[float]] = defaultdict(list)
    allv: list[float] = []
    for substance, media_type, media_path, raw, n in entries:
        if n <= 0:
            continue
        by_media[media_path].append(raw)
        by_cat[(substance, media_type)].append(raw)
        allv.append(raw)

    def mean(xs):
        return sum(xs) / len(xs)

    return {
        "by_media": {k: mean(v) for k, v in by_media.items()},
        "by_cat": {k: mean(v) for k, v in by_cat.items()},
        "global": mean(allv) if allv else None,
    }


def _prior_for(meta: dict, priors: dict) -> float | None:
    """Resolve the best prior in priority order: same-media cross-patient → same-category
    cross-patient → global cross-patient → research craving_weight (from validated dataset)."""
    p = priors.get("by_media", {}).get(meta.get("media_path"))
    if p is not None:
        return p
    p = priors.get("by_cat", {}).get((meta.get("substance"), meta.get("media_type")))
    if p is not None:
        return p
    g = priors.get("global")
    if g is not None:
        return g
    # Fallback: research-derived craving weight (bundled from MOCIS / Tobacco datasets).
    return meta.get("craving_weight")


def shrunk_scores(cue_meta_by_id: dict[int, dict], raw_map: dict[int, dict],
                  priors: dict, k: int = DEFAULT_K) -> dict[int, dict]:
    """Shrink each cue's raw reactivity toward its prior: score = (n·raw + k·prior)/(n+k).

    n=0 → the prior alone; no prior available → the raw value (or 0). ``cue_meta_by_id`` maps
    cue id → {media_path, substance, media_type}."""
    out: dict[int, dict] = {}
    for cid, meta in cue_meta_by_id.items():
        entry = raw_map.get(cid, {"raw": 0.0, "n": 0})
        n, raw = entry["n"], entry["raw"]
        prior = _prior_for(meta, priors)
        if n <= 0:
            score = prior if prior is not None else 0.0
        elif prior is None:
            score = raw
        else:
            score = (n * raw + k * prior) / (n + k)
        out[cid] = {"score": score, "n": n, "raw": raw if n else None, "prior": prior}
    return out


def suggested_order(cues, scores: dict[int, dict]) -> list[int]:
    """Cue ids ascending by score (low craving first), tie-broken by current rank then id."""
    def key(c):
        s = scores.get(c.id, {}).get("score", 0.0)
        return (s, c.appetitive_rank, c.id if c.id is not None else 0)

    return [c.id for c in sorted(cues, key=key)]
