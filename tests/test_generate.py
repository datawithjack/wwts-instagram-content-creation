"""Tests for the CLI helpers in generate.py."""
import pytest

from generate import _parse_ids, _slug


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
