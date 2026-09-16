"""Graded cue-playlist construction.

The exposure escalates: cues are ordered by ``appetitive_rank`` (low -> high) so
craving builds within the session, matching the Mellentin design where "the
alcohol presented in the videos became increasingly appetitive."

Positive counter-stimuli (puppies/nature, plus the patient's own "reasons for
recovery") are *not* part of the escalation playlist — they are reserved for the
on-demand gallery — so they are separated out here.

Playlist builders
-----------------
* ``build_exposure_playlist`` — classic graded escalation (Intense mode).
* ``build_interspersed_playlist`` — craving cues interspersed among neutrals.
* ``build_weighted_playlist`` — sort by research-backed ``craving_weight``.
* ``build_playlist_for_mode`` — dispatcher that picks the right builder.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from .models import CueConfig, MediaItem


def build_exposure_playlist(
    cues: Sequence[CueConfig],
    max_repeats: int = 0,
) -> list[CueConfig]:
    """Enabled, non-positive cues ordered by ascending appetitive rank.

    Ties broken by ``id`` (then media_path) for a stable, deterministic order.

    If *max_repeats* > 0, cues shown more than that many times across sessions
    are moved to the end of the playlist (backlog rotation), preserving their
    relative order within the backlog.
    """
    exposure = [c for c in cues if c.enabled and not c.is_personal_reason]
    sorted_cues = sorted(
        exposure,
        key=lambda c: (c.appetitive_rank, c.id if c.id is not None else 1 << 30, c.media_path),
    )
    if max_repeats <= 0:
        return sorted_cues
    fresh = [c for c in sorted_cues if c.exposure_count <= max_repeats]
    backlog = [c for c in sorted_cues if c.exposure_count > max_repeats]
    return fresh + backlog


def positive_cues(cues: Sequence[CueConfig]) -> list[CueConfig]:
    """The patient's own positive counter-stimuli (reasons for recovery)."""
    return [c for c in cues if c.enabled and c.is_personal_reason]


def randomized(cues: Sequence[CueConfig], rng: random.Random | None = None) -> list[CueConfig]:
    """A shuffled copy of the playlist (counterbalances order to isolate cue content
    from habituation effects, per the VR-CET literature). ``rng`` is injectable for
    deterministic tests."""
    items = list(cues)
    (rng or random).shuffle(items)
    return items


# ---------------------------------------------------------------------------
# Neutral-cue helpers
# ---------------------------------------------------------------------------

def neutral_cues(cues: Sequence[CueConfig]) -> list[CueConfig]:
    """Neutral (non-craving) cues from a patient's cue library."""
    return [c for c in cues if c.enabled and c.is_neutral]


def media_to_neutral_cues(items: Sequence[MediaItem]) -> list[CueConfig]:
    """Wrap ``MediaItem`` objects from the neutral media folder as temporary
    ``CueConfig`` instances for use in interspersed playlists.

    The returned cues have ``id=None`` (not persisted) and ``is_neutral=True``.
    """
    return [
        CueConfig(
            substance="neutral",
            media_path=item.path,
            media_type=item.media_type,
            is_neutral=True,
        )
        for item in items
    ]


# ---------------------------------------------------------------------------
# Interspersed playlist (neutral + craving mix)
# ---------------------------------------------------------------------------

def build_interspersed_playlist(
    craving_cues: Sequence[CueConfig],
    neutral_pool: Sequence[CueConfig],
    craving_pct: int = 5,
    craving_count: int = 0,
    rng: random.Random | None = None,
) -> list[CueConfig]:
    """Build a mixed playlist of craving and neutral cues.

    Craving cues are interspersed among neutral cues.  The craving cues
    maintain their graded order (ascending appetitive rank) but are placed at
    random positions in the neutral stream.

    Parameters
    ----------
    craving_cues : sequence of CueConfig
        The patient's enabled, non-positive substance cues.
    neutral_pool : sequence of CueConfig
        Neutral (non-craving) cues — patient-assigned neutrals **or** media
        library neutrals wrapped via :func:`media_to_neutral_cues`.
    craving_pct : int
        Target percentage of craving cues in the total playlist (e.g. 5 means
        5 % are craving, 95 % are neutral).  Ignored if *craving_count* > 0.
    craving_count : int
        If > 0, the exact number of craving cues to include (overrides *pct*).
    rng : random.Random, optional
        Injectable RNG for deterministic tests.
    """
    _rng = rng or random.Random()

    # 1. Prepare the graded craving cues (ascending appetitive rank).
    graded = build_exposure_playlist(list(craving_cues))
    if not graded:
        # No craving cues — return shuffled neutrals only.
        neutrals = list(neutral_pool)
        _rng.shuffle(neutrals)
        return neutrals

    # 2. Determine how many craving cues to use.
    if craving_count > 0:
        n_craving = min(craving_count, len(graded))
    else:
        n_neutral = len(neutral_pool)
        if n_neutral == 0:
            return graded[:]  # no neutrals, fall back to pure exposure
        pct = max(1, min(50, craving_pct))
        # n_craving / (n_craving + n_neutral) ≈ pct / 100
        n_craving = max(1, round(pct * n_neutral / (100 - pct)))
        n_craving = min(n_craving, len(graded))

    selected_craving = graded[:n_craving]

    # 3. Build the neutral stream (shuffled).
    neutrals = list(neutral_pool)
    _rng.shuffle(neutrals)

    # 4. Interleave: place craving cues at random positions in the first
    #    two thirds of the playlist.  The last third is neutral-only so the
    #    session winds down without further craving provocation.
    total = len(neutrals) + len(selected_craving)
    cutoff = max(1, (total * 2) // 3)  # first 2/3 boundary
    eligible = list(range(cutoff))
    if len(selected_craving) > len(eligible):
        # Rare edge case: more craving cues than eligible slots.
        positions = sorted(eligible)
    else:
        positions = sorted(_rng.sample(eligible, len(selected_craving)))

    result: list[CueConfig] = []
    ci = 0  # craving index
    ni = 0  # neutral index
    for i in range(total):
        if ci < len(selected_craving) and ci < len(positions) and i == positions[ci]:
            result.append(selected_craving[ci])
            ci += 1
        elif ni < len(neutrals):
            result.append(neutrals[ni])
            ni += 1

    # Append any remaining (guards against rounding / edge-case mismatches).
    while ci < len(selected_craving):
        result.append(selected_craving[ci])
        ci += 1
    while ni < len(neutrals):
        result.append(neutrals[ni])
        ni += 1

    return result


# ---------------------------------------------------------------------------
# Weighted playlist (research-backed ordering)
# ---------------------------------------------------------------------------

def build_weighted_playlist(cues: Sequence[CueConfig]) -> list[CueConfig]:
    """Like :func:`build_exposure_playlist` but uses ``craving_weight`` as the
    primary sort key when available, falling back to ``appetitive_rank``.

    Research-based weights provide a data-driven alternative to manual
    clinician ranking.  Cues without weights sort by their appetitive_rank.
    """
    exposure = [c for c in cues if c.enabled and not c.is_personal_reason]
    return sorted(
        exposure,
        key=lambda c: (
            c.craving_weight if c.craving_weight is not None else float(c.appetitive_rank),
            c.appetitive_rank,
            c.id if c.id is not None else 1 << 30,
            c.media_path,
        ),
    )


# ---------------------------------------------------------------------------
# Mode dispatcher
# ---------------------------------------------------------------------------

def build_playlist_for_mode(
    mode: str,
    craving_cues: Sequence[CueConfig],
    neutral_pool: Sequence[CueConfig] | None = None,
    craving_pct: int = 5,
    craving_count: int = 0,
    use_weights: bool = False,
    rng: random.Random | None = None,
) -> list[CueConfig]:
    """Build the exposure playlist for the given session mode.

    Parameters
    ----------
    mode : str
        One of ``'intense'``, ``'interspersed'``, ``'custom'``.
    craving_cues : sequence
        Patient's enabled substance cues.
    neutral_pool : sequence, optional
        Available neutral cues (for interspersed / custom modes).
    craving_pct / craving_count : int
        Interspersed-mode mixing parameters.
    use_weights : bool
        If *True*, sort by ``craving_weight`` instead of ``appetitive_rank``.
    rng : Random, optional
        Injectable RNG for deterministic tests.
    """
    if mode == "interspersed":
        return build_interspersed_playlist(
            craving_cues, neutral_pool or [], craving_pct, craving_count, rng,
        )
    # intense and custom both start from the standard graded playlist
    if use_weights:
        return build_weighted_playlist(craving_cues)
    return build_exposure_playlist(craving_cues)
