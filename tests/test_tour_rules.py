"""Tests for the Tour-rules explainer reel data builder and rendering.

The Tour rules reel is a single animated 1080x1920 page (like site_stats_reel),
NOT a swipeable carousel. Copy is distilled from the in-app rules page
(frontend FantasyRules.tsx — "The Tour" tab).
"""
import os

import pytest
import yaml

from pipeline.templates import get_dummy_data, render_template
from pipeline.tour_rules import build_tour_rules_reel_data


# ── Data Builder ────────────────────────────────────────────────────────────

class TestBuildTourRulesReelData:
    def setup_method(self):
        self.data = build_tour_rules_reel_data()

    def test_has_title_and_tagline(self):
        assert self.data["title"]
        assert self.data["tagline"]

    def test_has_five_picks(self):
        assert isinstance(self.data["picks"], list)
        assert len(self.data["picks"]) == 5
        for pick in self.data["picks"]:
            assert pick["slot"]
            assert pick["tier"]

    def test_pick_slots_cover_men_women_wildcard(self):
        slots = " ".join(p["slot"] for p in self.data["picks"]).lower()
        assert "man" in slots
        assert "woman" in slots
        assert "wildcard" in slots

    def test_one_pick_rule_copy(self):
        assert "once" in self.data["one_pick_text"].lower()

    def test_captains_points(self):
        pts = " ".join(self.data["captains_points"]).lower()
        assert isinstance(self.data["captains_points"], list)
        assert len(self.data["captains_points"]) >= 1
        assert "twice" in pts  # the key captain rule
        assert "top 5" in pts

    def test_scoring_rows_present_and_position_based(self):
        rows = self.data["scoring_rows"]
        assert isinstance(rows, list)
        assert len(rows) >= 4
        # 1st place should be the top points value
        assert rows[0]["place"].lower().startswith("1")
        for row in rows:
            assert row["place"]
            assert row["points"]

    def test_best_four_events_copy(self):
        text = self.data["counting_text"].lower()
        assert "4" in text or "four" in text

    def test_cta_has_handle_and_url(self):
        assert "@windsurfworldtourstats" in self.data["handle"]
        assert "windsurfworldtourstats.com" in self.data["url"]


# ── Dummy Data wiring ───────────────────────────────────────────────────────

class TestDummyData:
    def test_tour_rules_reel_dummy_data(self):
        data = get_dummy_data("tour_rules_reel")
        assert data["title"]
        assert len(data["picks"]) == 5


# ── Template Rendering ──────────────────────────────────────────────────────

class TestTourRulesReelRendering:
    def setup_method(self):
        self.data = get_dummy_data("tour_rules_reel")
        self.html = render_template("tour_rules_reel", self.data)

    def test_returns_html_string(self):
        assert isinstance(self.html, str)
        assert "<html" in self.html

    def test_configured_as_vertical_reel(self):
        # Dimensions are applied at render time from config.yaml (Playwright
        # viewport), not baked into the HTML — assert the reel config directly.
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "config.yaml"
        )
        with open(config_path) as f:
            config = yaml.safe_load(f)
        reel = config["templates"]["tour_rules_reel"]
        assert reel["width"] == 1080
        assert reel["height"] == 1920  # vertical 9:16 reel

    def test_contains_key_copy(self):
        html_upper = self.html.upper()
        assert "THE TOUR" in html_upper
        assert "WILDCARD" in html_upper
        assert "CAPTAIN" in html_upper

    def test_contains_scoring_values(self):
        assert "10,000" in self.html  # 1st place points

    def test_contains_animation_script(self):
        assert "runAnimation" in self.html or "animate" in self.html

    def test_contains_brand_fonts_and_url(self):
        assert "Bebas Neue" in self.html
        assert "Inter" in self.html
        assert "windsurfworldtourstats.com" in self.html
