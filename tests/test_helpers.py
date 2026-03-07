"""Tests for template helper/formatting functions."""
from datetime import date

import pytest

from pipeline.helpers import (
    ordinal,
    format_date_range,
    star_rating,
    format_delta,
    compute_deltas,
    format_number,
    country_flag,
)


class TestOrdinal:
    def test_first(self):
        assert ordinal(1) == "1st"

    def test_second(self):
        assert ordinal(2) == "2nd"

    def test_third(self):
        assert ordinal(3) == "3rd"

    def test_fourth(self):
        assert ordinal(4) == "4th"

    def test_eleventh(self):
        assert ordinal(11) == "11th"

    def test_twelfth(self):
        assert ordinal(12) == "12th"

    def test_thirteenth(self):
        assert ordinal(13) == "13th"

    def test_twenty_first(self):
        assert ordinal(21) == "21st"

    def test_twenty_second(self):
        assert ordinal(22) == "22nd"

    def test_hundred_and_eleventh(self):
        assert ordinal(111) == "111th"


class TestFormatDateRange:
    def test_same_month(self):
        result = format_date_range(date(2026, 1, 31), date(2026, 2, 8))
        assert result == "Jan 31 - Feb 08"

    def test_same_month_range(self):
        result = format_date_range(date(2026, 3, 1), date(2026, 3, 15))
        assert result == "Mar 01 - Mar 15"

    def test_single_day(self):
        result = format_date_range(date(2026, 6, 10), date(2026, 6, 10))
        assert result == "Jun 10"


class TestStarRating:
    def test_five_stars(self):
        assert star_rating(5) == "\u2605\u2605\u2605\u2605\u2605"

    def test_three_of_five(self):
        assert star_rating(3, max_stars=5) == "\u2605\u2605\u2605\u2606\u2606"

    def test_zero_stars(self):
        assert star_rating(0) == "\u2606\u2606\u2606\u2606\u2606"

    def test_four_stars(self):
        assert star_rating(4) == "\u2605\u2605\u2605\u2605\u2606"


class TestFormatDelta:
    def test_positive(self):
        assert format_delta(2.70) == "+2.70"

    def test_negative(self):
        assert format_delta(-1.50) == "-1.50"

    def test_zero(self):
        assert format_delta(0.0) == "+0.00"

    def test_large(self):
        assert format_delta(10.5) == "+10.50"


class TestComputeDeltas:
    def test_basic_deltas(self):
        row = {
            "athlete_1_best_heat": 9.33,
            "athlete_2_best_heat": 12.03,
            "athlete_1_avg_heat": 8.85,
            "athlete_2_avg_heat": 10.65,
            "athlete_1_best_wave": 5.00,
            "athlete_2_best_wave": 6.30,
            "athlete_1_avg_wave": 4.43,
            "athlete_2_avg_wave": 5.33,
        }
        fields = ["best_heat", "avg_heat", "best_wave", "avg_wave"]
        result = compute_deltas(row, fields)
        assert result["delta_best_heat"] == pytest.approx(2.70)
        assert result["delta_avg_heat"] == pytest.approx(1.80)
        assert result["delta_best_wave"] == pytest.approx(1.30)
        assert result["delta_avg_wave"] == pytest.approx(0.90)

    def test_negative_deltas(self):
        row = {
            "athlete_1_best_heat": 12.00,
            "athlete_2_best_heat": 9.00,
        }
        result = compute_deltas(row, ["best_heat"])
        assert result["delta_best_heat"] == pytest.approx(-3.00)


class TestFormatNumber:
    def test_thousands(self):
        assert format_number(43515) == "43,515"

    def test_small(self):
        assert format_number(58) == "58"

    def test_millions(self):
        assert format_number(1000000) == "1,000,000"


class TestCountryFlag:
    def test_spain(self):
        assert country_flag("ES") == "\U0001F1EA\U0001F1F8"

    def test_australia(self):
        assert country_flag("AU") == "\U0001F1E6\U0001F1FA"

    def test_lowercase(self):
        assert country_flag("jp") == "\U0001F1EF\U0001F1F5"
