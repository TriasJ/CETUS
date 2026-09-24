"""Verify craving ratings always include elapsed_sec and cue_config_id."""
from cravingcrave.domain.models import CravingRating, CueConfig, RatingKind


def test_craving_rating_has_elapsed_sec():
    """Every CravingRating has elapsed_sec set."""
    r = CravingRating(session_id=1, elapsed_sec=45, value=7,
                      kind=RatingKind.PERIODIC.value, cue_config_id=5)
    assert r.elapsed_sec == 45
    assert r.cue_config_id == 5
    assert r.value == 7


def test_neutral_cue_has_no_id():
    """Neutral cues from media_to_neutral_cues have id=None."""
    from cravingcrave.domain.models import MediaItem
    from cravingcrave.domain.playlist import media_to_neutral_cues
    items = [MediaItem(path="neutral/n_01.jpg", absolute_path="/x/n_01.jpg",
                       substance="neutral", media_type="image", filename="n_01.jpg")]
    cues = media_to_neutral_cues(items)
    assert cues[0].id is None
    assert cues[0].is_neutral is True


def test_craving_cue_has_id():
    """Patient-assigned craving cues have a real id."""
    c = CueConfig(id=42, patient_id=1, substance="meth",
                  media_path="meth/cue.jpg", media_type="image")
    assert c.id == 42
    assert c.is_neutral is False
