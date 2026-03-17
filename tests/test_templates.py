"""Tests for Jinja2 template population."""
from datetime import date

import pytest

from pipeline.templates import render_template, get_dummy_data


class TestRenderHeadToHead:
    def setup_method(self):
        self.data = get_dummy_data("head_to_head")
        self.html = render_template("head_to_head", self.data)

    def test_returns_html_string(self):
        assert isinstance(self.html, str)
        assert "<html" in self.html

    def test_contains_event_name(self):
        assert self.data["event_name"].upper() in self.html

    def test_contains_athlete_names(self):
        for name_key in ("athlete_1_name", "athlete_2_name"):
            parts = self.data[name_key].split()
            for part in parts:
                assert part.upper() in self.html

    def test_contains_placements_as_ordinals(self):
        assert "1st" in self.html
        assert "2nd" in self.html

    def test_contains_delta_values(self):
        assert "+2.70" in self.html
        assert "+1.80" in self.html

    def test_contains_star_rating(self):
        # 4-star event
        assert "\u2605\u2605\u2605\u2605\u2606" in self.html

    def test_contains_date_range(self):
        assert "Jan 31 - Feb 08" in self.html

    def test_contains_brand_fonts(self):
        assert "Bebas Neue" in self.html
        assert "Inter" in self.html

    def test_contains_brand_colors(self):
        assert "#5AB4CC" in self.html  # muted cyan
        assert "#4DA89E" in self.html  # muted jade


class TestRenderTop10:
    def setup_method(self):
        self.data = get_dummy_data("top_10")
        self.html = render_template("top_10", self.data)

    def test_returns_html_string(self):
        assert isinstance(self.html, str)
        assert "<html" in self.html

    def test_contains_title_with_gender_and_metric(self):
        assert "MEN'S" in self.html
        assert "TOP 10" in self.html
        assert "WAVES" in self.html
        assert "2025" in self.html

    def test_contains_column_headers(self):
        assert "ATHLETE" in self.html
        assert "SCORE" in self.html
        assert "EVENT" in self.html
        assert "ROUND" in self.html

    def test_contains_all_10_athletes(self):
        for entry in self.data["entries"]:
            assert entry["athlete"] in self.html

    def test_contains_scores(self):
        for entry in self.data["entries"]:
            assert f"{entry['score']:.2f}" in self.html

    def test_contains_rank_numbers(self):
        for i in range(1, 11):
            assert f">{i}<" in self.html

    def test_contains_footer(self):
        assert "windsurfworldtourstats.com" in self.html.lower()

    def test_contains_brand_fonts(self):
        assert "Bebas Neue" in self.html
        assert "Inter" in self.html


class TestRenderTop10CrossEvent:
    """Cross-event mode: shows EVENT column, no event header."""

    def setup_method(self):
        self.data = get_dummy_data("top_10")
        self.html = render_template("top_10", self.data)

    def test_is_per_event_false(self):
        assert self.data.get("is_per_event") is False

    def test_shows_event_column(self):
        assert "col-event" in self.html

    def test_hides_heat_column(self):
        # HEAT header should not appear in the rendered HTML body
        assert ">HEAT<" not in self.html

    def test_no_event_header(self):
        # No event header include rendered in cross-event mode
        assert "event-meta" not in self.html.split("</style>")[-1]

    def test_title_includes_year(self):
        assert "2025" in self.html


class TestRenderTop10PerEvent:
    """Per-event mode: shows event header, HEAT column, hides EVENT column."""

    def setup_method(self):
        self.data = {
            **get_dummy_data("top_10"),
            "is_per_event": True,
            "event_name": "Gran Canaria Wind & Waves Festival",
            "event_country": "ES",
            "event_date_start": date(2026, 3, 1),
            "event_date_end": date(2026, 3, 8),
            "event_tier": 5,
        }
        # Add heat field to entries
        for i, entry in enumerate(self.data["entries"]):
            entry["heat"] = i + 1
        self.html = render_template("top_10", self.data)

    def test_shows_event_header(self):
        assert "event-title" in self.html
        assert "GRAN CANARIA" in self.html

    def test_shows_event_meta(self):
        assert "event-meta" in self.html

    def test_shows_heat_column(self):
        assert "col-heat" in self.html

    def test_hides_event_column(self):
        # In per-event mode, should not have the EVENT column
        assert ">EVENT<" not in self.html

    def test_title_no_year(self):
        # Title should be "MEN'S TOP 10 WAVES" without year
        assert "MEN&#39;S TOP 10 WAVES" in self.html or "MEN'S TOP 10 WAVES" in self.html


class TestGetDummyData:
    def test_head_to_head_has_required_fields(self):
        data = get_dummy_data("head_to_head")
        required = [
            "event_name", "event_country", "event_date_start", "event_date_end",
            "event_tier", "athlete_1_name", "athlete_2_name",
            "athlete_1_placement", "athlete_2_placement",
            "athlete_1_heat_wins", "athlete_2_heat_wins",
            "athlete_1_best_heat", "athlete_2_best_heat",
            "athlete_1_avg_heat", "athlete_2_avg_heat",
            "athlete_1_best_wave", "athlete_2_best_wave",
            "athlete_1_avg_wave", "athlete_2_avg_wave",
        ]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_top_10_has_required_fields(self):
        data = get_dummy_data("top_10")
        assert "title_gender" in data
        assert "title_metric" in data
        assert "title_year" in data
        assert "is_per_event" in data
        assert data["is_per_event"] is False
        assert "entries" in data
        assert len(data["entries"]) == 10

    def test_top_10_entries_have_required_fields(self):
        data = get_dummy_data("top_10")
        for entry in data["entries"]:
            assert "rank" in entry
            assert "athlete" in entry
            assert "country" in entry
            assert "score" in entry
            assert "event" in entry
            assert "round" in entry

    def test_rider_profile_has_required_fields(self):
        data = get_dummy_data("rider_profile")
        required = [
            "athlete_name", "athlete_country", "athlete_photo_url",
            "athlete_sail_number", "event_name", "event_country",
            "event_date_start", "event_date_end", "event_tier",
            "placement", "best_heat", "best_heat_round",
            "best_wave", "best_jump", "avg_wave", "top_waves",
        ]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_rider_profile_top_waves_structure(self):
        data = get_dummy_data("rider_profile")
        assert len(data["top_waves"]) == 5
        for wave in data["top_waves"]:
            assert "rank" in wave
            assert "score" in wave
            assert "round" in wave


class TestRenderRiderProfile:
    def setup_method(self):
        self.data = get_dummy_data("rider_profile")
        self.html = render_template("rider_profile", self.data)

    def test_returns_html_string(self):
        assert isinstance(self.html, str)
        assert "<html" in self.html

    def test_contains_athlete_name(self):
        assert "MARC" in self.html
        assert "PARE RICO" in self.html

    def test_contains_event_name(self):
        assert self.data["event_name"].upper() in self.html

    def test_contains_placement_ordinal(self):
        assert "1st" in self.html

    def test_contains_stat_values(self):
        assert "16.33" in self.html  # best heat
        assert "8.83" in self.html   # best wave

    def test_contains_top_waves_table(self):
        for wave in self.data["top_waves"]:
            assert f"{wave['score']:.2f}" in self.html

    def test_contains_footer(self):
        assert "windsurfworldtourstats.com" in self.html.lower()

    def test_contains_brand_fonts(self):
        assert "Bebas Neue" in self.html
        assert "Inter" in self.html
