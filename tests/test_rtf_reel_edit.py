"""Road to Finals reel — the pure segment planner.

Only `footage_segments` is unit-testable here; the render and ffmpeg passes drive a
real browser and a real encoder and are verified by running. What matters is that a
partial recording degrades into a shorter reel rather than a crash: the recorder can
lose the outcome step to a slow page without losing the whole take.
"""
import pytest

from pipeline.rtf_reel_edit import footage_segments

FULL = {
    "race_start": 5.95, "race_end": 17.74,
    "predict_start": 17.74, "predict_end": 35.6,
    "outcome_start": 35.6, "outcome_end": 49.54,
}


def test_plans_every_segment_when_all_markers_are_present():
    assert footage_segments(FULL) == {
        "race": (5.95, 17.74),
        "predict": (17.74, 35.6),
        "outcome": (35.6, 49.54),
    }


def test_drops_a_segment_whose_end_marker_is_missing():
    """The recorder writes `_end` only once a step actually completed."""
    markers = {**FULL}
    del markers["outcome_end"]
    assert set(footage_segments(markers)) == {"race", "predict"}


def test_requires_the_race_segment():
    """Without the standings there is no evidence the predictor exists."""
    with pytest.raises(ValueError):
        footage_segments({"predict_start": 1.0, "predict_end": 2.0})
