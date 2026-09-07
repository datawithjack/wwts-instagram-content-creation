"""Road to Finals reel — the pure segment planner.

Only `footage_segments` is unit-testable here; the render and ffmpeg passes drive a
real browser and a real encoder and are verified by running. What matters is that a
partial recording degrades into a shorter reel rather than a crash -- except for the
chart, which is the beat the reel exists to show.
"""
import pytest

from pipeline.rtf_reel_edit import footage_segments

FULL = {
    "nav_start": 3.7, "nav_end": 15.2,
    "predict_start": 15.4, "predict_end": 24.6,
    "score_start": 24.6, "score_end": 27.0,
    "chart_start": 27.4, "chart_end": 32.6,
}


def test_plans_every_segment_when_all_markers_are_present():
    assert footage_segments(FULL) == {
        "nav": (3.7, 15.2),
        "predict": (15.4, 24.6),
        "score": (24.6, 27.0),
        "chart": (27.4, 32.6),
    }


def test_drops_a_segment_whose_end_marker_is_missing():
    """The recorder writes `_end` only once a beat actually completed."""
    markers = {**FULL}
    del markers["nav_end"]
    assert set(footage_segments(markers)) == {"predict", "score", "chart"}


def test_ignores_markers_for_a_segment_no_longer_in_the_spine():
    """Footage recorded before the matrix beat was cut still builds a reel."""
    markers = {**FULL, "matrix_start": 32.6, "matrix_end": 48.2}
    assert "matrix" not in footage_segments(markers)


def test_requires_the_chart_segment():
    """Without the chart redrawing there is nothing worth advertising."""
    with pytest.raises(ValueError):
        footage_segments({"predict_start": 1.0, "predict_end": 2.0})
