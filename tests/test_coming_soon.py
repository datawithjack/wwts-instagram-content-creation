"""Tests for Coming Soon carousel slide builder and template rendering."""
import pytest

from pipeline.templates import get_dummy_data, render_template
from pipeline.coming_soon import build_coming_soon_slides


# ── Slide Building ──────────────────────────────────────────────────────────

class TestBuildComingSoonSlides:
    def setup_method(self):
        self.slides = build_coming_soon_slides()

    def test_returns_six_slides(self):
        assert len(self.slides) == 6

    def test_slide_types_in_order(self):
        types = [s["type"] for s in self.slides]
        assert types == [
            "coming_soon_cover",
            "coming_soon_feature",
            "coming_soon_feature",
            "coming_soon_feature",
            "coming_soon_feature",
            "coming_soon_cta",
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

    def test_accent_color_is_cyan(self):
        for slide in self.slides:
            assert slide["accent_color"] == "#00D4FF"

    def test_cover_has_title(self):
        cover = self.slides[0]
        assert "title" in cover
        assert cover["title"]  # not empty

    def test_cover_has_subtitle(self):
        cover = self.slides[0]
        assert "subtitle" in cover
        assert cover["subtitle"]

    def test_feature_slides_have_title_and_subtitle(self):
        for slide in self.slides[1:5]:
            assert "title" in slide
            assert "subtitle" in slide
            assert slide["title"]
            assert slide["subtitle"]

    def test_feature_slides_have_distinct_titles(self):
        titles = [s["title"] for s in self.slides[1:5]]
        assert len(set(titles)) == 4  # all different

    def test_cta_has_handle(self):
        cta = self.slides[-1]
        assert "handle" in cta
        assert "@windsurfworldtourstats" in cta["handle"]


# ── Dummy Data ──────────────────────────────────────────────────────────────

class TestDummyData:
    def test_coming_soon_dummy_data_returns_slides(self):
        data = get_dummy_data("coming_soon_carousel")
        assert "slides" in data
        assert len(data["slides"]) == 6


# ── Template Rendering ──────────────────────────────────────────────────────

class TestComingSoonTemplateRendering:
    def setup_method(self):
        self.slides = build_coming_soon_slides()

    def test_cover_renders(self):
        html = render_template("carousel/slide_coming_soon_cover", self.slides[0])
        assert "<html" in html
        assert "COMING SOON" in html

    def test_cover_has_title(self):
        html = render_template("carousel/slide_coming_soon_cover", self.slides[0])
        assert self.slides[0]["title"].upper() in html

    def test_cover_uses_cyan_accent(self):
        html = render_template("carousel/slide_coming_soon_cover", self.slides[0])
        assert "#00D4FF" in html

    def test_feature_slide_renders(self):
        slide = self.slides[1]
        html = render_template("carousel/slide_coming_soon_feature", slide)
        assert "<html" in html
        assert slide["title"].upper() in html.upper()

    def test_all_feature_slides_render(self):
        for slide in self.slides[1:5]:
            html = render_template("carousel/slide_coming_soon_feature", slide)
            assert "<html" in html
            assert slide["subtitle"] in html

    def test_cta_renders(self):
        html = render_template("carousel/slide_coming_soon_cta", self.slides[-1])
        assert "<html" in html
        assert "@windsurfworldtourstats" in html

    def test_cta_has_follow_text(self):
        html = render_template("carousel/slide_coming_soon_cta", self.slides[-1])
        assert "follow" in html.lower()

    def test_all_slides_1080x1350(self):
        type_map = {
            "coming_soon_cover": "carousel/slide_coming_soon_cover",
            "coming_soon_feature": "carousel/slide_coming_soon_feature",
            "coming_soon_cta": "carousel/slide_coming_soon_cta",
        }
        for slide in self.slides:
            template = type_map[slide["type"]]
            html = render_template(template, slide)
            assert "1080" in html
            assert "1350" in html
