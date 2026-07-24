"""Within-session habituation detection and slope computation.

The research repository flags the *within-session habituation slope* as the key
mechanistic outcome (and warns about the "blocked habituation" pattern from
Ekhtiari 2022). The stopping rule mirrors the VR-CET protocol: end exposure once
craving stays low for N consecutive ratings, or a safety time cap is reached.

Pure functions only — no Qt, no DB.
"""

from __future__ import annotations

from collections.abc import Sequence

from .models import EndReason


def count_trailing_low(values: Sequence[int], threshold: int) -> int:
    """How many of the most recent ratings are <= ``threshold`` (consecutively)."""
    count = 0
    for v in reversed(values):
        if v <= threshold:
            count += 1
        else:
            break
    return count


def is_habituated(values: Sequence[int], threshold: int, consecutive: int) -> bool:
    """True when the last ``consecutive`` ratings are all <= ``threshold``.

    Requires at least ``consecutive`` ratings to fire (a single low baseline does
    not count as habituation).
    """
    if consecutive <= 0:
        return False
    if len(values) < consecutive:
        return False
    return count_trailing_low(values, threshold) >= consecutive


def compute_slope(points: Sequence[tuple[float, float]]) -> float | None:
    """Least-squares slope of craving over time (units: VAS points per second).

    ``points`` is a sequence of ``(elapsed_sec, value)``. A *negative* slope is the
    desired habituation pattern. Returns ``None`` if fewer than two distinct
    x-values are available (slope undefined).
    """
    n = len(points)
    if n < 2:
        return None
    sx = sum(x for x, _ in points)
    sy = sum(y for _, y in points)
    sxx = sum(x * x for x, _ in points)
    sxy = sum(x * y for x, y in points)
    denom = n * sxx - sx * sx
    if denom == 0:  # all timestamps identical -> slope undefined
        return None
    return (n * sxy - sx * sy) / denom


def evaluate_end(
    values: Sequence[int],
    elapsed_sec: float,
    *,
    threshold: int,
    consecutive: int,
    time_cap_sec: float,
) -> EndReason | None:
    """Decide whether the exposure should end on its own.

    Returns ``HABITUATED`` if the habituation criterion is met, else ``TIME_CAP``
    if the safety cap is reached, else ``None`` (continue). Panic and clinician
    stop are driven externally, not here.
    """
    if is_habituated(values, threshold, consecutive):
        return EndReason.HABITUATED
    if elapsed_sec >= time_cap_sec:
        return EndReason.TIME_CAP
    return None
