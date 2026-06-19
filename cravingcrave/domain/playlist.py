"""Graded cue-playlist construction.

The exposure escalates: cues are ordered by ``appetitive_rank`` (low -> high) so
craving builds within the session, matching the Mellentin design where "the
alcohol presented in the videos became increasingly appetitive."

Positive counter-stimuli (puppies/nature, plus the patient's own "reasons for
recovery") are *not* part of the escalation playlist — they are reserved for the
on-demand gallery — so they are separated out here.
"""

from __future__ import annotations

import random
from typing import Optional, Sequence

from .models import CueConfig


def build_exposure_playlist(cues: Sequence[CueConfig]) -> list[CueConfig]:
    """Enabled, non-positive cues ordered by ascending appetitive rank.

    Ties broken by ``id`` (then media_path) for a stable, deterministic order.
    """
    exposure = [c for c in cues if c.enabled and not c.is_personal_reason]
    return sorted(
        exposure,
        key=lambda c: (c.appetitive_rank, c.id if c.id is not None else 1 << 30, c.media_path),
    )


def positive_cues(cues: Sequence[CueConfig]) -> list[CueConfig]:
    """The patient's own positive counter-stimuli (reasons for recovery)."""
    return [c for c in cues if c.enabled and c.is_personal_reason]


def randomized(cues: Sequence[CueConfig], rng: Optional[random.Random] = None) -> list[CueConfig]:
    """A shuffled copy of the playlist (counterbalances order to isolate cue content
    from habituation effects, per the VR-CET literature). ``rng`` is injectable for
    deterministic tests."""
    items = list(cues)
    (rng or random).shuffle(items)
    return items
