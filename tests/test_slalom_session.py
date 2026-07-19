"""Tests for the Slalom Session announce carousel slide builder + rendering."""
import pytest

from pipeline.templates import get_dummy_data, render_template
from pipeline.slalom_session import build_slalom_session_slides


# ── Slide Building ──────────────────────────────────────────────────────────

class TestBuildSlalomSessionSlides:
    def setup_method(self):
        self.slides = build_slalom_session_slides()

    def test_returns_six_slides(self):
        assert len(self.slides) == 6

    def test_slide_types_in_order(self):
        types = [s["type"] for s in self.slides]
        assert types == [
            "fantasy_rules_cover",
            "fantasy_rules_game",
            "fantasy_rules_game",
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
            assert slide["total_slides"] == 6

    def test_cover_mentions_slalom(self):
        cover = self.slides[0]
        blob = (cover["title"] + " " + cover["subtitle"] + " " + cover["eyebrow"]).lower()
        assert "slalom" in blob

    def test_game_slides_have_name_tagline_points(self):
        for slide in self.slides[1:5]:
            assert slide["name"]
            assert slide["tagline"]
            assert isinstance(slide["points"], list)
            assert len(slide["points"]) >= 1

    def test_squad_slide_mentions_six_men_and_wildcards(self):
        picks_text = " ".join(self.slides[2]["points"]).lower()
        assert "6" in picks_text or "six" in picks_text
        assert "wildcard" in picks_text

    def test_squad_slide_mentions_tiers(self):
        # Men's tier split seeded on last season's Slalom X rankings.
        blob = (self.slides[2]["tagline"] + " " + " ".join(self.slides[2]["points"])).lower()
        assert "top 5" in blob or "6-15" in blob or "6–15" in blob

    def test_cover_focuses_on_slalom_x(self):
        cover = self.slides[0]
        assert "x" in cover["title"].lower()

    def test_scoring_slide_is_place_based(self):
        # The Slalom Session's differentiator: it's a race, scored on finish place.
        scoring = self.slides[3]
        blob = (scoring["name"] + " " + scoring["tagline"] + " " + " ".join(scoring["points"])).lower()
        assert "place" in blob or "finish" in blob
        assert "10" in blob and "1st" in blob

    def test_penalties_slide_present(self):
        penalties = self.slides[4]
        blob = (penalties["name"] + " " + penalties["tagline"] + " " + " ".join(penalties["points"])).lower()
        assert "dq" in blob or "penalt" in blob or "dnf" in blob

    def test_cta_has_handle_and_headline(self):
        cta = self.slides[-1]
        assert "@windsurfworldtourstats" in cta["handle"]
        assert cta["headline"]

    def test_cta_states_pick_lock_deadline(self):
        # The launch CTA must tell players when picks lock (Fuerteventura event 123).
        deadline = self.slides[-1]["deadline"].lower()
        assert "22 july" in deadline
        assert "06:00" in deadline

    def test_no_em_dashes_in_copy(self):
        # House style: no em dashes anywhere in post copy.
        def texts(slide):
            for v in slide.values():
                if isinstance(v, str):
                    yield v
                elif isinstance(v, list):
                    yield from (x for x in v if isinstance(x, str))
        for slide in self.slides:
            for t in texts(slide):
                assert "—" not in t, f"em dash found in: {t!r}"


# ── Dummy Data ──────────────────────────────────────────────────────────────

class TestDummyData:
    def test_slalom_session_dummy_data_returns_slides(self):
        data = get_dummy_data("slalom_session")
        assert "slides" in data
        assert len(data["slides"]) == 6


# ── Template Rendering ──────────────────────────────────────────────────────

class TestSlalomSessionTemplateRendering:
    def setup_method(self):
        self.slides = build_slalom_session_slides()
        self.type_map = {
            "fantasy_rules_cover": "carousel/slide_fantasy_rules_cover",
            "fantasy_rules_game": "carousel/slide_fantasy_rules_game",
            "fantasy_rules_cta": "carousel/slide_fantasy_rules_cta",
        }

    def test_all_slides_render(self):
        for slide in self.slides:
            html = render_template(self.type_map[slide["type"]], slide)
            assert "<html" in html

    def test_game_slide_points_present_in_html(self):
        for slide in self.slides[1:5]:
            html = render_template("carousel/slide_fantasy_rules_game", slide)
            assert slide["name"].upper() in html.upper()
            for point in slide["points"]:
                assert point in html

    def test_all_slides_1080x1350(self):
        for slide in self.slides:
            html = render_template(self.type_map[slide["type"]], slide)
            assert "1080" in html
            assert "1350" in html
