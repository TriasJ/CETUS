"""Test that backlog rotation works across simulated sessions."""
from cravingcrave.domain.models import CueConfig
from cravingcrave.domain.playlist import build_exposure_playlist


def _cue(rank, exposure=0, weight=None, cid=None):
    return CueConfig(
        id=cid or rank, patient_id=1, substance="meth",
        media_path=f"meth/cue_{rank:02d}.jpg", media_type="image",
        appetitive_rank=rank, exposure_count=exposure,
        craving_weight=weight,
    )


def test_session1_all_fresh():
    """Session 1: all cues at exposure_count=0, normal order."""
    cues = [_cue(0, exposure=0), _cue(1, exposure=0), _cue(2, exposure=0)]
    result = build_exposure_playlist(cues, max_repeats=2)
    assert [c.appetitive_rank for c in result] == [0, 1, 2]


def test_session2_after_increment():
    """After 3 sessions (exposure=3 > max_repeats=2), habituated cues deprioritized."""
    cues = [
        _cue(0, exposure=3, weight=1.0),  # over-exposed, low weight → backlog
        _cue(1, exposure=3, weight=1.0),  # over-exposed, low weight → backlog
        _cue(2, exposure=1, weight=5.0),  # fresh
    ]
    result = build_exposure_playlist(cues, max_repeats=2)
    # rank 2 (fresh) should come before ranks 0,1 (backlogged)
    assert result[0].appetitive_rank == 2


def test_high_reactivity_stays():
    """Over-exposed but high-reactivity cues stay in position."""
    cues = [
        _cue(0, exposure=10, weight=9.0),  # over-exposed, HIGH weight
        _cue(1, exposure=1, weight=3.0),
    ]
    reactivity = {0: {"raw": 8.0, "n": 5}}
    result = build_exposure_playlist(cues, max_repeats=2, cue_reactivity=reactivity)
    assert result[0].appetitive_rank == 0  # stays because high reactivity


def test_backlog_disabled_when_zero():
    """max_repeats=0 means no backlog — all cues in normal order."""
    cues = [_cue(0, exposure=100), _cue(1, exposure=0)]
    result = build_exposure_playlist(cues, max_repeats=0)
    assert [c.appetitive_rank for c in result] == [0, 1]
