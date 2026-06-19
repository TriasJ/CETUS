from cravingcrave.domain import vas


def test_clamp_rating():
    assert vas.clamp_rating(-3, 10) == 0
    assert vas.clamp_rating(15, 10) == 10
    assert vas.clamp_rating(7, 10) == 7


def test_is_periodic_due():
    assert vas.is_periodic_due(elapsed_sec=30, last_prompt_sec=0, interval_sec=30)
    assert not vas.is_periodic_due(elapsed_sec=29, last_prompt_sec=0, interval_sec=30)
    assert not vas.is_periodic_due(elapsed_sec=100, last_prompt_sec=100, interval_sec=0)
