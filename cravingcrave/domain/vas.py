"""VAS (Visual Analog Scale) craving-rating scheduling rules.

The clinical protocol samples craving at: baseline (before exposure), periodically
during exposure (~every 30 s), at the patient-reported peak, and at endpoint.
This module only decides *when* a periodic prompt is due; the Qt timer in the UI
acts on that decision.
"""

from __future__ import annotations


def clamp_rating(value: int, vas_max: int) -> int:
    """Constrain a raw rating into the valid 0..vas_max range."""
    return max(0, min(vas_max, int(value)))


def is_periodic_due(elapsed_sec: float, last_prompt_sec: float, interval_sec: float) -> bool:
    """True when at least ``interval_sec`` has passed since the last periodic prompt."""
    if interval_sec <= 0:
        return False
    return (elapsed_sec - last_prompt_sec) >= interval_sec
