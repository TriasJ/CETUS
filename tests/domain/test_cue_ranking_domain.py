"""Adaptive cue ordering domain: reactivity, population prior, shrinkage, suggested order."""

from cravingcrave.domain import cue_ranking
from cravingcrave.domain.models import CravingRating


def _r(session_id, kind, value, cue):
    return CravingRating(session_id=session_id, kind=kind, value=value, cue_config_id=cue)


def test_cue_reactivity_excludes_baseline_and_averages():
    ratings = [
        # session 1: baseline 3 (stamped to cue 1); peak on cue1=7, on cue2=5
        _r(1, "baseline", 3, 1), _r(1, "peak", 7, 1), _r(1, "periodic", 5, 2),
        # session 2: baseline 4; peak on cue1=6
        _r(2, "baseline", 4, 1), _r(2, "peak", 6, 1),
    ]
    react = cue_ranking.cue_reactivity(ratings)
    # cue1: (7-3)=4 and (6-4)=2 -> mean 3, n 2 ; the baseline value 3 is NOT used as an on-cue peak
    assert react[1] == {"raw": 3.0, "n": 2}
    assert react[2] == {"raw": 2.0, "n": 1}


def test_cue_reactivity_baseline_only_session_yields_nothing():
    react = cue_ranking.cue_reactivity([_r(1, "baseline", 5, 1)])
    assert react == {}


def test_population_prior_by_media_cat_global():
    entries = [
        ("meth", "image", "meth/a.png", 4.0, 2),
        ("meth", "image", "meth/a.png", 6.0, 1),   # same file, other patient
        ("meth", "video", "meth/v.mp4", 8.0, 3),
        ("alcohol", "image", "alc/x.png", 0.0, 0),  # n=0 ignored
    ]
    priors = cue_ranking.population_prior(entries)
    assert priors["by_media"]["meth/a.png"] == 5.0            # (4+6)/2
    assert priors["by_cat"][("meth", "image")] == 5.0
    assert priors["by_cat"][("meth", "video")] == 8.0
    assert priors["global"] == (4.0 + 6.0 + 8.0) / 3


def test_shrunk_scores_and_prior_fallback():
    meta = {
        1: {"media_path": "meth/a.png", "substance": "meth", "media_type": "image"},
        2: {"media_path": "meth/z.png", "substance": "meth", "media_type": "image"},  # no media prior
        3: {"media_path": "x", "substance": "?", "media_type": "?"},                   # global only
    }
    raw = {1: {"raw": 3.0, "n": 2}}   # cues 2,3 unseen (n=0)
    priors = {"by_media": {"meth/a.png": 9.0}, "by_cat": {("meth", "image"): 5.0}, "global": 6.0}
    scores = cue_ranking.shrunk_scores(meta, raw, priors, k=3)
    assert scores[1]["score"] == (2 * 3.0 + 3 * 9.0) / 5    # media prior wins
    assert scores[2]["score"] == 5.0                        # n=0 -> category prior
    assert scores[3]["score"] == 6.0                        # n=0 -> global fallback


def test_suggested_order_low_craving_first():
    class Cue:
        def __init__(self, cid, rank):
            self.id, self.appetitive_rank = cid, rank
    cues = [Cue(1, 0), Cue(2, 1), Cue(3, 2)]
    scores = {1: {"score": 8.0}, 2: {"score": 2.0}, 3: {"score": 5.0}}
    assert cue_ranking.suggested_order(cues, scores) == [2, 3, 1]   # ascending score
