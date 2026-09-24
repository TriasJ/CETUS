"""Tests for reactivity-gated backlog rotation in playlist building.

Verifies that over-exposed cues are handled correctly:
- High-reactivity cues stay in position even when over-exposed
- Low-reactivity (habituated) cues get backlogged
- Craving weight used as fallback when no reactivity data
- Backlog applies across all session modes (intense, interspersed, custom)
"""

from __future__ import annotations

import random

from cravingcrave.domain.models import CueConfig, MediaItem
from cravingcrave.domain.playlist import (
    build_exposure_playlist,
    build_interspersed_playlist,
    build_playlist_for_mode,
    media_to_neutral_cues,
)


def _cue(rank: int, exposure: int = 0, weight: float | None = None,
         cid: int | None = None, neutral: bool = False) -> CueConfig:
    """Helper to create a CueConfig for testing."""
    return CueConfig(
        id=cid or rank,
        patient_id=1,
        substance="neutral" if neutral else "meth",
        media_path=f"meth/cue_{rank:02d}.jpg",
        media_type="image",
        appetitive_rank=rank,
        exposure_count=exposure,
        craving_weight=weight,
        is_neutral=neutral,
    )


# ---------------------------------------------------------------------------
# Test: basic backlog without reactivity data
# ---------------------------------------------------------------------------

class TestBasicBacklog:
    def test_no_backlog_when_off(self):
        """max_repeats=0 means no backlog — all cues in normal order."""
        cues = [_cue(0, exposure=100), _cue(1, exposure=50), _cue(2, exposure=0)]
        result = build_exposure_playlist(cues, max_repeats=0)
        assert [c.appetitive_rank for c in result] == [0, 1, 2]

    def test_over_exposed_without_data_goes_to_back(self):
        """Cues over max_repeats with no reactivity data → backlogged."""
        cues = [_cue(0, exposure=10), _cue(1, exposure=2), _cue(2, exposure=1)]
        result = build_exposure_playlist(cues, max_repeats=5)
        # rank 0 (exposure=10 > 5) should be backlogged
        assert result[0].appetitive_rank == 1  # fresh
        assert result[1].appetitive_rank == 2  # fresh
        assert result[2].appetitive_rank == 0  # backlogged

    def test_all_fresh_stays_in_order(self):
        """All cues under max_repeats → normal graded order."""
        cues = [_cue(0, exposure=3), _cue(1, exposure=2), _cue(2, exposure=1)]
        result = build_exposure_playlist(cues, max_repeats=5)
        assert [c.appetitive_rank for c in result] == [0, 1, 2]


# ---------------------------------------------------------------------------
# Test: reactivity-gated backlog
# ---------------------------------------------------------------------------

class TestReactivityGatedBacklog:
    def test_high_reactivity_stays_in_position(self):
        """Over-exposed cue with HIGH reactivity (>2.0) is NOT backlogged."""
        cues = [
            _cue(0, exposure=20, weight=9.0),  # over-exposed, high craving
            _cue(1, exposure=1, weight=3.0),    # fresh
            _cue(2, exposure=0, weight=1.0),    # fresh
        ]
        reactivity = {
            0: {"raw": 7.5, "n": 5},  # still provokes high craving!
            1: {"raw": 2.0, "n": 3},
            2: {"raw": 0.5, "n": 2},
        }
        result = build_exposure_playlist(cues, max_repeats=5,
                                          cue_reactivity=reactivity)
        # rank 0 should stay at position 0 because reactivity is high
        assert result[0].appetitive_rank == 0
        assert result[0].exposure_count == 20

    def test_low_reactivity_gets_backlogged(self):
        """Over-exposed cue with LOW reactivity (≤2.0) IS backlogged."""
        cues = [
            _cue(0, exposure=20, weight=9.0),  # over-exposed, but habituated
            _cue(1, exposure=1, weight=3.0),    # fresh
            _cue(2, exposure=0, weight=1.0),    # fresh
        ]
        reactivity = {
            0: {"raw": 1.5, "n": 5},  # habituated — low reactivity
            1: {"raw": 3.0, "n": 3},
            2: {"raw": 0.5, "n": 2},
        }
        result = build_exposure_playlist(cues, max_repeats=5,
                                          cue_reactivity=reactivity)
        # rank 0 should be backlogged because reactivity dropped
        assert result[0].appetitive_rank == 1  # fresh cue first
        assert result[1].appetitive_rank == 2
        assert result[2].appetitive_rank == 0  # backlogged

    def test_mixed_reactivity(self):
        """Multiple over-exposed cues: only low-reactivity ones backlogged."""
        cues = [
            _cue(0, exposure=15),  # over-exposed, high react
            _cue(1, exposure=12),  # over-exposed, low react (habituated)
            _cue(2, exposure=3),   # fresh
            _cue(3, exposure=1),   # fresh
        ]
        reactivity = {
            0: {"raw": 6.0, "n": 4},  # still high!
            1: {"raw": 1.0, "n": 4},  # habituated
            2: {"raw": 4.0, "n": 2},
            3: {"raw": 3.0, "n": 1},
        }
        result = build_exposure_playlist(cues, max_repeats=5,
                                          cue_reactivity=reactivity)
        ranks = [c.appetitive_rank for c in result]
        # rank 0 stays (high react), rank 1 backlogged (low react)
        assert ranks.index(0) < ranks.index(1)
        # rank 2 and 3 are fresh, appear before backlogged rank 1
        assert ranks.index(2) < ranks.index(1)
        assert ranks.index(3) < ranks.index(1)


# ---------------------------------------------------------------------------
# Test: craving_weight as fallback proxy
# ---------------------------------------------------------------------------

class TestWeightFallback:
    def test_high_weight_keeps_position(self):
        """No reactivity data but high craving_weight → kept in position."""
        cues = [
            _cue(0, exposure=20, weight=8.5),  # over-exposed, high weight
            _cue(1, exposure=1, weight=2.0),    # fresh
        ]
        result = build_exposure_playlist(cues, max_repeats=5,
                                          cue_reactivity=None)
        # rank 0 has high weight, should NOT be backlogged
        assert result[0].appetitive_rank == 0

    def test_low_weight_gets_backlogged(self):
        """No reactivity data and low craving_weight → backlogged."""
        cues = [
            _cue(0, exposure=20, weight=1.5),  # over-exposed, low weight
            _cue(1, exposure=1, weight=2.0),    # fresh
        ]
        result = build_exposure_playlist(cues, max_repeats=5,
                                          cue_reactivity=None)
        # rank 0 has low weight, should be backlogged
        assert result[0].appetitive_rank == 1
        assert result[1].appetitive_rank == 0

    def test_no_weight_no_reactivity_gets_backlogged(self):
        """No reactivity data AND no craving_weight → backlogged (safe default)."""
        cues = [
            _cue(0, exposure=20, weight=None),  # over-exposed, no data
            _cue(1, exposure=1, weight=None),    # fresh
        ]
        result = build_exposure_playlist(cues, max_repeats=5,
                                          cue_reactivity=None)
        assert result[0].appetitive_rank == 1
        assert result[1].appetitive_rank == 0


# ---------------------------------------------------------------------------
# Test: backlog in interspersed mode
# ---------------------------------------------------------------------------

class TestInterspersedBacklog:
    def test_backlog_applies_to_craving_cues_in_interspersed(self):
        """Backlog rotation deprioritizes habituated craving cues in interspersed mode."""
        craving_cues = [
            _cue(0, exposure=20, weight=1.0),  # over-exposed, habituated
            _cue(1, exposure=1, weight=5.0),   # fresh, moderate
            _cue(2, exposure=0, weight=8.0),   # fresh, high
        ]
        neutral_items = [
            MediaItem(path=f"neutral/n_{i}.jpg", absolute_path=f"/media/neutral/n_{i}.jpg",
                      substance="neutral", media_type="image", filename=f"n_{i}.jpg")
            for i in range(20)
        ]
        neutral_pool = media_to_neutral_cues(neutral_items)

        result = build_interspersed_playlist(
            craving_cues, neutral_pool, craving_pct=50, max_repeats=5,
            rng=random.Random(42),
        )
        # The craving cues in the result should have rank 1 and 2 before rank 0
        craving_in_result = [c for c in result if not c.is_neutral]
        ranks = [c.appetitive_rank for c in craving_in_result]
        # rank 0 (habituated) should be after rank 1 and 2 (fresh)
        if len(ranks) >= 2:
            assert ranks.index(1) < ranks.index(0) or 0 not in ranks

    def test_high_react_craving_cue_stays_in_interspersed(self):
        """High-reactivity over-exposed cue is NOT backlogged even in interspersed mode."""
        craving_cues = [
            _cue(0, exposure=20, weight=9.0),  # over-exposed but high react
            _cue(1, exposure=1, weight=3.0),
        ]
        neutral_items = [
            MediaItem(path=f"neutral/n_{i}.jpg", absolute_path=f"/media/neutral/n_{i}.jpg",
                      substance="neutral", media_type="image", filename=f"n_{i}.jpg")
            for i in range(10)
        ]
        neutral_pool = media_to_neutral_cues(neutral_items)
        reactivity = {0: {"raw": 8.0, "n": 5}, 1: {"raw": 2.5, "n": 2}}

        result = build_interspersed_playlist(
            craving_cues, neutral_pool, craving_pct=20, max_repeats=5,
            cue_reactivity=reactivity, rng=random.Random(42),
        )
        craving_in_result = [c for c in result if not c.is_neutral]
        # rank 0 should still appear (not excluded by backlog)
        assert any(c.appetitive_rank == 0 for c in craving_in_result)


# ---------------------------------------------------------------------------
# Test: mode dispatcher passes everything through
# ---------------------------------------------------------------------------

class TestModeDispatcher:
    def test_intense_mode_uses_backlog(self):
        cues = [
            _cue(0, exposure=20, weight=1.0),
            _cue(1, exposure=1, weight=5.0),
        ]
        result = build_playlist_for_mode("intense", cues, max_repeats=5)
        assert result[0].appetitive_rank == 1  # fresh first
        assert result[1].appetitive_rank == 0  # backlogged

    def test_intense_mode_with_reactivity(self):
        cues = [
            _cue(0, exposure=20, weight=9.0),
            _cue(1, exposure=1, weight=3.0),
        ]
        reactivity = {0: {"raw": 8.0, "n": 5}}
        result = build_playlist_for_mode("intense", cues, max_repeats=5,
                                          cue_reactivity=reactivity)
        # rank 0 has high reactivity, should NOT be backlogged
        assert result[0].appetitive_rank == 0

    def test_interspersed_mode_uses_backlog(self):
        cues = [_cue(0, exposure=20, weight=1.0), _cue(1, exposure=0, weight=5.0)]
        neutral_items = [
            MediaItem(path=f"neutral/n_{i}.jpg", absolute_path=f"/media/neutral/n_{i}.jpg",
                      substance="neutral", media_type="image", filename=f"n_{i}.jpg")
            for i in range(10)
        ]
        neutral_pool = media_to_neutral_cues(neutral_items)
        result = build_playlist_for_mode(
            "interspersed", cues, neutral_pool=neutral_pool,
            craving_pct=20, max_repeats=5, rng=random.Random(42),
        )
        craving_in_result = [c for c in result if not c.is_neutral]
        if len(craving_in_result) >= 2:
            ranks = [c.appetitive_rank for c in craving_in_result]
            # rank 0 (low weight, habituated) should be after rank 1
            assert ranks.index(1) < ranks.index(0)


# ---------------------------------------------------------------------------
# Test: percentage correctness in interspersed mode
# ---------------------------------------------------------------------------

class TestInterspersedPercentage:
    def test_craving_percentage_approximately_correct(self):
        """Verify the craving cue percentage is approximately what was requested."""
        craving_cues = [_cue(i, weight=float(i)) for i in range(20)]
        neutral_items = [
            MediaItem(path=f"neutral/n_{i}.jpg", absolute_path=f"/media/neutral/n_{i}.jpg",
                      substance="neutral", media_type="image", filename=f"n_{i}.jpg")
            for i in range(100)
        ]
        neutral_pool = media_to_neutral_cues(neutral_items)

        result = build_interspersed_playlist(
            craving_cues, neutral_pool, craving_pct=10, rng=random.Random(42),
        )
        n_craving = sum(1 for c in result if not c.is_neutral)
        n_total = len(result)
        actual_pct = n_craving / n_total * 100

        # Should be approximately 10% (within a few percentage points)
        assert 5 <= actual_pct <= 15, f"Expected ~10%, got {actual_pct:.1f}%"

    def test_last_third_is_neutral_only(self):
        """Verify craving cues don't appear in the last third of the playlist."""
        craving_cues = [_cue(i, weight=float(i)) for i in range(10)]
        neutral_items = [
            MediaItem(path=f"neutral/n_{i}.jpg", absolute_path=f"/media/neutral/n_{i}.jpg",
                      substance="neutral", media_type="image", filename=f"n_{i}.jpg")
            for i in range(50)
        ]
        neutral_pool = media_to_neutral_cues(neutral_items)

        result = build_interspersed_playlist(
            craving_cues, neutral_pool, craving_pct=10, rng=random.Random(42),
        )
        n_total = len(result)
        last_third_start = (n_total * 2) // 3
        last_third = result[last_third_start:]
        craving_in_last_third = [c for c in last_third if not c.is_neutral]

        assert len(craving_in_last_third) == 0, (
            f"Found {len(craving_in_last_third)} craving cues in last third "
            f"(positions {last_third_start}-{n_total})")

    def test_neutrals_are_shuffled(self):
        """Verify neutral cues are not in their original order (randomized)."""
        craving_cues = [_cue(0, weight=5.0)]
        neutral_items = [
            MediaItem(path=f"neutral/n_{i:03d}.jpg", absolute_path=f"/media/neutral/n_{i:03d}.jpg",
                      substance="neutral", media_type="image", filename=f"n_{i:03d}.jpg")
            for i in range(30)
        ]
        neutral_pool = media_to_neutral_cues(neutral_items)

        result = build_interspersed_playlist(
            craving_cues, neutral_pool, craving_pct=5, rng=random.Random(42),
        )
        neutral_paths = [c.media_path for c in result if c.is_neutral]
        sorted_paths = sorted(neutral_paths)
        # At least some should be out of order (shuffled)
        assert neutral_paths != sorted_paths, "Neutral cues were not shuffled"
