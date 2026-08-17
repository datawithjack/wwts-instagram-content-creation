"""Tests for the CLI helpers in generate.py."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from generate import _parse_ids, _slug, fetch_live_data


class TestParseIds:
    def test_splits_a_comma_list(self):
        assert _parse_ids("46,69,68,205") == [46, 69, 68, 205]

    def test_tolerates_spaces(self):
        assert _parse_ids("46, 69 , 68") == [46, 69, 68]

    def test_empty_input_is_an_empty_list(self):
        assert _parse_ids("") == []
        assert _parse_ids(None) == []


class TestSlug:
    def test_lowercases_and_underscores(self):
        assert _slug("MEN QUARTER FINAL 4") == "men_quarter_final_4"

    def test_strips_punctuation_and_accents(self):
        assert _slug("Tenerife Grand Slam *****") == "tenerife_grand_slam"
        assert _slug("Men's Semi Final") == "mens_semi_final"

    def test_collapses_runs_of_separators(self):
        assert _slug("  a  --  b  ") == "a_b"

    def test_empty_input_is_empty(self):
        assert _slug("") == ""
        assert _slug(None) == ""


# ── Per-event top 10 routing ─────────────────────────────────────────────────

class TestTop10PerEventRouting:
    """Per-event top 10 should come from the API. The DB is the fallback, not
    the default: it only answers through an SSH tunnel that CI does not have.
    Jumps used to be forced down the DB path because only the DB carried the
    trick modifier; the stats endpoint now returns move_variation too."""

    def _args(self, score_type):
        return SimpleNamespace(
            template="top_10_carousel", score_type=score_type, sex="Men",
            event=124, year=None, rounds=None, counting_only=False,
            mode=None, day=None,
        )

    def test_waves_use_the_api(self):
        with patch("generate.fetch_event_top_scores") as api, \
             patch("generate.run_query") as db:
            api.return_value = {"entries": []}
            result = fetch_live_data("top_10_carousel", self._args("Wave"))

        api.assert_called_once()
        assert api.call_args.kwargs["event_id"] == 124
        db.assert_not_called()
        assert result == {"entries": []}

    def test_jumps_use_the_api(self):
        with patch("generate.fetch_event_top_scores") as api, \
             patch("generate.run_query") as db:
            api.return_value = {"entries": []}
            fetch_live_data("top_10_carousel", self._args("Jump"))

        api.assert_called_once()
        assert api.call_args.kwargs["score_type"] == "Jump"
        db.assert_not_called()

    def test_jumps_fall_back_to_the_db_when_the_api_fails(self):
        with patch("generate.fetch_event_top_scores", side_effect=RuntimeError("404")), \
             patch("generate.run_query", return_value=[]) as db:
            fetch_live_data("top_10_carousel", self._args("Jump"))

        # Two queries on the DB path: the top 10 itself, then event metadata.
        assert db.called

    def test_all_time_still_uses_the_db(self):
        args = self._args("Wave")
        args.event = None
        with patch("generate.fetch_event_top_scores") as api, \
             patch("generate.run_query", return_value=[]) as db:
            fetch_live_data("top_10_carousel", args)

        api.assert_not_called()
        db.assert_called_once()
