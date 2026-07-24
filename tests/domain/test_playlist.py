from cravingcrave.domain import playlist
from cravingcrave.domain.models import CueConfig


def _cue(cid, rank, enabled=True, personal=False):
    return CueConfig(
        id=cid, patient_id=1, substance="alcohol", media_path=f"a/{cid}.jpg",
        media_type="image", appetitive_rank=rank, enabled=enabled,
        is_personal_reason=personal,
    )


def test_exposure_playlist_is_graded_ascending():
    cues = [_cue(1, 30), _cue(2, 10), _cue(3, 20)]
    ordered = playlist.build_exposure_playlist(cues)
    assert [c.id for c in ordered] == [2, 3, 1]


def test_exposure_playlist_excludes_disabled_and_personal():
    cues = [_cue(1, 10), _cue(2, 20, enabled=False), _cue(3, 5, personal=True)]
    ordered = playlist.build_exposure_playlist(cues)
    assert [c.id for c in ordered] == [1]


def test_positive_cues_returns_only_personal_reasons():
    cues = [_cue(1, 10), _cue(3, 5, personal=True)]
    assert [c.id for c in playlist.positive_cues(cues)] == [3]


def test_randomized_is_permutation_and_pure():
    import random
    cues = [_cue(i, i) for i in range(6)]
    original = [c.id for c in cues]
    out = playlist.randomized(cues, random.Random(123))
    assert sorted(c.id for c in out) == sorted(original)   # same items, shuffled
    assert [c.id for c in cues] == original                # input not mutated

