from cravingcrave.domain import reports
from cravingcrave.domain.models import CopingEvent, CravingRating, Session


def test_per_cue_craving_groups_in_first_seen_order():
    rs = [
        CravingRating(session_id=1, elapsed_sec=0, value=8, kind="baseline", cue_config_id=10),
        CravingRating(session_id=1, elapsed_sec=30, value=6, kind="periodic", cue_config_id=10),
        CravingRating(session_id=1, elapsed_sec=60, value=9, kind="peak", cue_config_id=20),
        CravingRating(session_id=1, elapsed_sec=90, value=2, kind="endpoint", cue_config_id=20),
        CravingRating(session_id=1, elapsed_sec=120, value=1, kind="periodic", cue_config_id=None),  # skipped
    ]
    out = reports.per_cue_craving(rs)
    assert [r["cue_config_id"] for r in out] == [10, 20]
    assert out[0]["mean"] == 7 and out[0]["peak"] == 8 and out[0]["count"] == 2
    assert out[1]["mean"] == 5.5 and out[1]["peak"] == 9 and out[1]["count"] == 2


def test_coping_skill_counts():
    evs = [CopingEvent(session_id=1, skill="recall_negative"),
           CopingEvent(session_id=1, skill="recall_negative"),
           CopingEvent(session_id=1, skill="alternative_action")]
    assert reports.coping_skill_counts(evs) == {"recall_negative": 2, "alternative_action": 1}


def test_end_reason_counts_skips_open():
    ss = [Session(end_reason="habituated"), Session(end_reason="panic"),
          Session(end_reason="habituated"), Session(end_reason=None)]
    assert reports.end_reason_counts(ss) == {"habituated": 2, "panic": 1}


def test_session_slopes_indexes_only_finished():
    ss = [Session(habituation_slope=-0.02), Session(habituation_slope=None),
          Session(habituation_slope=-0.05), Session(habituation_slope=-0.1)]
    assert reports.session_slopes(ss) == [(1, -0.02), (2, -0.05), (3, -0.1)]


def test_per_cue_reactivity_and_highest():
    rs = [
        CravingRating(session_id=1, elapsed_sec=0, value=3, kind="baseline", cue_config_id=10),
        CravingRating(session_id=1, elapsed_sec=30, value=7, kind="periodic", cue_config_id=10),  # react 4
        CravingRating(session_id=1, elapsed_sec=60, value=4, kind="peak", cue_config_id=20),
        CravingRating(session_id=1, elapsed_sec=90, value=9, kind="periodic", cue_config_id=20),  # react 5
    ]
    out = reports.per_cue_craving(rs)
    assert out[0]["cue_reactivity"] == 4 and out[1]["cue_reactivity"] == 5
    assert reports.highest_reactivity_cue_id(rs) == 20
    assert reports.highest_reactivity_cue_id([]) is None


def test_session_metrics():
    s = Session(baseline_vas=4, peak_vas=9, endpoint_vas=2, habituation_slope=-0.05)
    rs = [
        CravingRating(session_id=1, elapsed_sec=0, value=4, kind="baseline"),
        CravingRating(session_id=1, elapsed_sec=30, value=9, kind="peak"),
        CravingRating(session_id=1, elapsed_sec=60, value=5, kind="periodic"),
        CravingRating(session_id=1, elapsed_sec=90, value=2, kind="endpoint"),
    ]
    m = reports.session_metrics(s, rs)
    assert m["cue_reactivity"] == 5                      # 9-4
    assert m["mean_exposure"] == (9 + 5 + 2) / 3         # exposure kinds only (baseline excluded)
    assert round(m["pct_reduction"], 1) == round((9 - 2) / 9 * 100, 1)
    assert m["time_to_peak_sec"] == 30
    assert m["slope"] == -0.05


def test_session_metrics_handles_missing():
    m = reports.session_metrics(Session(), [])
    assert m["mean_exposure"] is None and m["cue_reactivity"] is None
    assert m["pct_reduction"] is None and m["time_to_peak_sec"] is None


def test_spontaneous_recovery():
    ss = [
        Session(baseline_vas=8, endpoint_vas=2),   # idx1 -> None (no prev)
        Session(baseline_vas=5, endpoint_vas=1),   # idx2 -> 5 - 2 = 3
        Session(baseline_vas=3, endpoint_vas=1),   # idx3 -> 3 - 1 = 2
        Session(baseline_vas=None),                # excluded (unfinished)
    ]
    assert reports.spontaneous_recovery(ss) == [(1, None), (2, 3.0), (3, 2.0)]


def test_metric_trends_indexes_finished():
    ss = [Session(baseline_vas=4, peak_vas=9, endpoint_vas=3),
          Session(baseline_vas=None),
          Session(baseline_vas=5, peak_vas=8, endpoint_vas=2)]
    t = reports.metric_trends(ss)
    assert [x[0] for x in t["cue_reactivity"]] == [1, 2]
    assert t["cue_reactivity"][0][1] == 5.0 and t["cue_reactivity"][1][1] == 3.0
