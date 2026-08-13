"""Tests for Fantasy Rules overview carousel slide builder and rendering."""
import pytest

from pipeline.templates import get_dummy_data, render_template
from pipeline.fantasy_rules import build_fantasy_rules_slides


# ── Slide Building ──────────────────────────────────────────────────────────

class TestBuildFantasyRulesSlides:
    def setup_method(self):
        self.slides = build_fantasy_rules_slides()

    def test_returns_four_slides(self):
        assert len(self.slides) == 4

    def test_slide_types_in_order(self):
        types = [s["type"] for s in self.slides]
        assert types == [
            "fantasy_rules_cover",
            "fantasy_rules_game",
            "fantasy_rules_game",
            "fantasy_rules_cta",
        ]

    def test_all_slides_have_required_fields(self):
        for slide in self.slides:
            assert "type" in slide
            assert "slide_number" in slide
            assert "total_slides" in slide
            assert "accent_color" in slide

    def test_slides_have_numbering(self):
        for i, slide in enumerate(self.slides, 1):
            assert slide["slide_number"] == i
            assert slide["total_slides"] == 4

    def test_cover_has_title_and_subtitle(self):
        cover = self.slides[0]
        assert cover["title"]
        assert cover["subtitle"]

    def test_game_slides_have_name_tagline_points(self):
        for slide in self.slides[1:3]:
            assert slide["name"]
            assert slide["tagline"]
            assert isinstance(slide["points"], list)
            assert len(slide["points"]) >= 1

    def test_game_slides_are_tour_then_session(self):
        assert self.slides[1]["name"] == "The Tour"
        assert self.slides[2]["name"] == "The Session"

    def test_tour_mentions_five_riders_and_wildcard(self):
        tour_text = " ".join(self.slides[1]["points"]).lower()
        assert "5 riders" in tour_text
        assert "wildcard" in tour_text

    def test_session_mentions_every_heat(self):
        session_text = " ".join(self.slides[2]["points"]).lower()
        assert "heat" in session_text

    def test_cta_has_handle_and_headline(self):
        cta = self.slides[-1]
        assert "@windsurfworldtourstats" in cta["handle"]
        assert cta["headline"]


# ── Dummy Data ──────────────────────────────────────────────────────────────

class TestDummyData:
    def test_fantasy_rules_dummy_data_returns_slides(self):
        data = get_dummy_data("fantasy_rules")
        assert "slides" in data
        assert len(data["slides"]) == 4


# ── Template Rendering ──────────────────────────────────────────────────────

class TestFantasyRulesTemplateRendering:
    def setup_method(self):
        self.slides = build_fantasy_rules_slides()

    def test_cover_renders(self):
        html = render_template("carousel/slide_fantasy_rules_cover", self.slides[0])
        assert "<html" in html
        assert self.slides[0]["title"].upper() in html.upper()

    def test_game_slides_render(self):
        for slide in self.slides[1:3]:
            html = render_template("carousel/slide_fantasy_rules_game", slide)
            assert "<html" in html
            assert slide["name"].upper() in html.upper()
            for point in slide["points"]:
                assert point in html

    def test_cta_renders(self):
        html = render_template("carousel/slide_fantasy_rules_cta", self.slides[-1])
        assert "<html" in html
        assert "@windsurfworldtourstats" in html

    def test_all_slides_1080x1350(self):
        type_map = {
            "fantasy_rules_cover": "carousel/slide_fantasy_rules_cover",
            "fantasy_rules_game": "carousel/slide_fantasy_rules_game",
            "fantasy_rules_cta": "carousel/slide_fantasy_rules_cta",
        }
        for slide in self.slides:
            html = render_template(type_map[slide["type"]], slide)
            assert "1080" in html
            assert "1350" in html
