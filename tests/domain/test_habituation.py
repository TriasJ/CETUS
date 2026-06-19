from cravingcrave.domain import habituation as h
from cravingcrave.domain.models import EndReason


def test_count_trailing_low():
    assert h.count_trailing_low([8, 5, 2, 1], threshold=2) == 2
    assert h.count_trailing_low([1, 1, 1], threshold=2) == 3
    assert h.count_trailing_low([5, 5], threshold=2) == 0
    assert h.count_trailing_low([], threshold=2) == 0


def test_is_habituated_requires_enough_ratings():
    # A single low rating is not habituation.
    assert not h.is_habituated([1], threshold=2, consecutive=2)
    assert h.is_habituated([8, 2, 1], threshold=2, consecutive=2)
    assert not h.is_habituated([8, 5, 1], threshold=2, consecutive=2)  # only 1 trailing low


def test_compute_slope_negative_for_falling_craving():
    pts = [(0.0, 8.0), (30.0, 5.0), (60.0, 2.0)]
    slope = h.compute_slope(pts)
    assert slope is not None and slope < 0


def test_compute_slope_undefined_cases():
    assert h.compute_slope([]) is None
    assert h.compute_slope([(10.0, 5.0)]) is None
    # identical timestamps -> undefined
    assert h.compute_slope([(5.0, 1.0), (5.0, 9.0)]) is None


def test_evaluate_end_priorities():
    cfg = dict(threshold=2, consecutive=2, time_cap_sec=600)
    # habituated wins
    assert h.evaluate_end([2, 1], elapsed_sec=10, **cfg) is EndReason.HABITUATED
    # not habituated, under cap -> continue
    assert h.evaluate_end([8, 7], elapsed_sec=10, **cfg) is None
    # not habituated, over cap -> time cap
    assert h.evaluate_end([8, 7], elapsed_sec=600, **cfg) is EndReason.TIME_CAP
