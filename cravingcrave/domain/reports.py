"""Pure aggregations for the clinical report (per-cue, coping mix, slopes, end-reasons).

No Qt, no DB — easy to unit-test. The UI layer calls these to populate charts/tables.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from collections.abc import Sequence


def per_cue_craving(ratings) -> list[dict]:
    """Group craving ratings by ``cue_config_id`` (preserving first-appearance order).

    Returns one dict per cue with mean/peak/count/cue_reactivity — what the per-cue
    table needs. ``cue_reactivity`` is peak − first-rating-on-this-cue (induction
    magnitude for that cue; Lütt 2026). Ratings with no associated cue are skipped.
    """
    by_cue: OrderedDict[int, list[int]] = OrderedDict()
    for r in ratings:
        cid = r.cue_config_id
        if cid is None:
            continue
        by_cue.setdefault(cid, []).append(int(r.value))
    out = []
    for cid, vs in by_cue.items():
        out.append({
            "cue_config_id": cid, "mean": sum(vs) / len(vs), "peak": max(vs),
            "count": len(vs), "cue_reactivity": max(vs) - vs[0],
        })
    return out


def highest_reactivity_cue_id(ratings) -> int | None:
    """cue_config_id with the greatest cue-reactivity this session (relapse-risk
    context; Schröder 2024). None if no cued ratings."""
    per_cue = per_cue_craving(ratings)
    if not per_cue:
        return None
    return max(per_cue, key=lambda c: c["cue_reactivity"])["cue_config_id"]


def coping_skill_counts(coping_events) -> dict[str, int]:
    """How many times each USCS skill was used."""
    return dict(Counter(e.skill for e in coping_events))


def end_reason_counts(sessions) -> dict[str, int]:
    """Distribution of session end-reasons (habituated/time_cap/panic/clinician_stop)."""
    return dict(Counter(s.end_reason for s in sessions if s.end_reason))


def session_slopes(sessions: Sequence) -> list[tuple[int, float]]:
    """Habituation slope per (1-indexed) finished session, in chronological order."""
    out = []
    idx = 0
    for s in sessions:
        if s.habituation_slope is not None:
            idx += 1
            out.append((idx, float(s.habituation_slope)))
    return out


# --- within-session metrics (evidence-based, exploratory) -------------------
# mean_exposure: mean craving DURING exposure (periodic+peak+endpoint) — lower
#   predicted abstinence (Schröder 2024). cue_reactivity = peak-baseline (Lütt
#   2026). pct_reduction = (peak-endpoint)/peak (within-session habituation;
#   Powell 1993). slope from the stored habituation_slope (Ekhtiari 2022).
_EXPOSURE_KINDS = ("periodic", "peak", "endpoint")


def session_metrics(session, ratings) -> dict:
    """Per-session descriptive craving metrics (no inference; small-n)."""
    exposure_vals = [int(r.value) for r in ratings if r.kind in _EXPOSURE_KINDS]
    baseline = session.baseline_vas
    peak = session.peak_vas
    endpoint = session.endpoint_vas

    mean_exposure = (sum(exposure_vals) / len(exposure_vals)) if exposure_vals else None
    cue_reactivity = (peak - baseline) if (peak is not None and baseline is not None) else None
    pct_reduction = None
    if peak is not None and endpoint is not None and peak > 0:
        pct_reduction = (peak - endpoint) / peak * 100.0

    time_to_peak = None
    if peak is not None:
        peak_ratings = [r for r in ratings if int(r.value) == peak]
        if peak_ratings:
            time_to_peak = min(int(r.elapsed_sec) for r in peak_ratings)

    return {
        "baseline": baseline, "peak": peak, "endpoint": endpoint,
        "mean_exposure": mean_exposure, "cue_reactivity": cue_reactivity,
        "pct_reduction": pct_reduction, "time_to_peak_sec": time_to_peak,
        "slope": session.habituation_slope,
    }


def spontaneous_recovery(sessions: Sequence) -> list[tuple[int, float | None]]:
    """Per (1-indexed) finished session: baseline − previous session's endpoint.

    Positive = craving returned toward baseline between sessions (recovery; less
    carry-over). First session and any with missing values yield None. Price 2010
    explicitly tracked between-session spontaneous recovery in meth cue extinction.
    """
    finished = [s for s in sessions if s.baseline_vas is not None]
    out: list[tuple[int, float | None]] = []
    prev_endpoint = None
    for idx, s in enumerate(finished, start=1):
        if prev_endpoint is None or s.baseline_vas is None:
            out.append((idx, None))
        else:
            out.append((idx, float(s.baseline_vas - prev_endpoint)))
        prev_endpoint = s.endpoint_vas
    return out


def metric_trends(sessions: Sequence) -> dict:
    """Cross-session series (1-indexed) for the progress view.

    Returns {'mean_exposure': [(idx, val|None)], 'cue_reactivity': [(idx, val|None)]}.
    mean_exposure here uses the denormalized peak/endpoint as a proxy when raw
    ratings aren't loaded (callers that have ratings should prefer session_metrics)."""
    finished = [s for s in sessions if s.baseline_vas is not None]
    mean_exp, reactivity = [], []
    for idx, s in enumerate(finished, start=1):
        react = (s.peak_vas - s.baseline_vas) if (s.peak_vas is not None and s.baseline_vas is not None) else None
        reactivity.append((idx, float(react) if react is not None else None))
        # proxy mean of peak+endpoint when present (raw ratings not passed here)
        vals = [v for v in (s.peak_vas, s.endpoint_vas) if v is not None]
        mean_exp.append((idx, sum(vals) / len(vals) if vals else None))
    return {"mean_exposure": mean_exp, "cue_reactivity": reactivity}
