"""Tests for the Session-vs-Tour product infographic reel.

A single animated 1080x1920 reel contrasting the two fantasy game modes — The Tour
(season-long) vs The Session (single event): a spotlight on each, then a head-to-head
comparison. Pure product explainer, no live data.
"""
import os

import yaml

from pipeline.templates import get_dummy_data, render_template
from pipeline.fantasy_modes import build_fantasy_modes_reel_data


# ── Data Builder ────────────────────────────────────────────────────────────

class TestBuildFantasyModesData:
    def setup_method(self):
        self.data = build_fantasy_modes_reel_data()

    def test_has_both_mode_names(self):
        assert "TOUR" in self.data["tour"]["name"].upper()
        assert "SESSION" in self.data["session"]["name"].upper()

    def test_each_mode_has_points(self):
        for mode in ("tour", "session"):
            pts = self.data[mode]["points"]
            assert isinstance(pts, list)
            assert len(pts) >= 3
            assert all(p for p in pts)

    def test_pick_counts_present(self):
        # The Tour is 5 picks/event, the Session 8.
        tour = " ".join(self.data["tour"]["points"])
        session = " ".join(self.data["session"]["points"])
        assert "5" in tour
        assert "8" in session

    def test_comparison_rows(self):
        rows = self.data["comparison"]
        assert isinstance(rows, list)
        assert len(rows) >= 4
        for r in rows:
            assert r["label"]
            assert r["tour"]
            assert r["session"]

    def test_distinct_accents(self):
        assert self.data["accent_tour"] != self.data["accent_session"]

    def test_cta_has_handle_and_url(self):
        assert "@windsurfworldtourstats" in self.data["handle"]
        assert "windsurfworldtourstats.com" in self.data["url"]


# ── Dummy Data wiring ───────────────────────────────────────────────────────

class TestDummyData:
    def test_session_vs_tour_reel_dummy_data(self):
        data = get_dummy_data("session_vs_tour_reel")
        assert data["tour"]["points"]
        assert data["session"]["points"]


# ── Template Rendering ──────────────────────────────────────────────────────

class TestRendering:
    def setup_method(self):
        self.data = get_dummy_data("session_vs_tour_reel")
        self.html = render_template("session_vs_tour_reel", self.data)

    def test_returns_html_string(self):
        assert isinstance(self.html, str)
        assert "<html" in self.html

    def test_configured_as_vertical_reel(self):
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)
        reel = config["templates"]["session_vs_tour_reel"]
        assert reel["width"] == 1080
        assert reel["height"] == 1920

    def test_contains_both_modes(self):
        upper = self.html.upper()
        assert "THE TOUR" in upper
        assert "THE SESSION" in upper

    def test_contains_animation_script(self):
        assert "runAnimation" in self.html or "animate" in self.html

    def test_contains_brand_fonts_and_url(self):
        assert "Bebas Neue" in self.html
        assert "Inter" in self.html
        assert "windsurfworldtourstats.com" in self.html
