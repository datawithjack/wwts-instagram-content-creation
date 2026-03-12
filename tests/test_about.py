"""Tests for About carousel slide builder and template rendering."""
import pytest

from pipeline.templates import get_dummy_data, render_template
from pipeline.about import build_about_slides


# ── Slide Building ──────────────────────────────────────────────────────────

class TestBuildAboutSlides:
    def setup_method(self):
        self.slides = build_about_slides()

    def test_returns_four_slides(self):
        assert len(self.slides) == 4

    def test_slide_types_in_order(self):
        types = [s["type"] for s in self.slides]
        assert types == ["about_cover", "about_text", "about_numbers", "about_cta"]

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

    def test_accent_color_is_cyan(self):
        for slide in self.slides:
            assert slide["accent_color"] == "#00D4FF"

    def test_cover_has_title_and_subtitle(self):
        cover = self.slides[0]
        assert cover["title"]
        assert cover["subtitle"]

    def test_text_slide_has_lines(self):
        text = self.slides[1]
        assert "lines" in text
        assert len(text["lines"]) == 4

    def test_numbers_slide_has_three_stats(self):
        numbers = self.slides[2]
        assert "stats" in numbers
        assert len(numbers["stats"]) == 3
        for stat in numbers["stats"]:
            assert "value" in stat
            assert "label" in stat

    def test_cta_has_handle(self):
        cta = self.slides[-1]
        assert "@windsurfworldtourstats" in cta["handle"]


# ── Dummy Data ──────────────────────────────────────────────────────────────

class TestDummyData:
    def test_about_dummy_data_returns_slides(self):
        data = get_dummy_data("about_carousel")
        assert "slides" in data
        assert len(data["slides"]) == 4


# ── Template Rendering ──────────────────────────────────────────────────────

class TestAboutTemplateRendering:
    def setup_method(self):
        self.slides = build_about_slides()

    def test_cover_renders(self):
        html = render_template("carousel/slide_about_cover", self.slides[0])
        assert "<html" in html
        assert "WINDSURF" in html

    def test_cover_uses_cyan_accent(self):
        html = render_template("carousel/slide_about_cover", self.slides[0])
        assert "#00D4FF" in html

    def test_text_slide_renders(self):
        html = render_template("carousel/slide_about_text", self.slides[1])
        assert "<html" in html
        assert "PWA" in html
        assert "2016" in html
        assert "LiveHeats" in html

    def test_text_slide_has_highlights(self):
        html = render_template("carousel/slide_about_text", self.slides[1])
        assert 'class="highlight"' in html

    def test_numbers_renders_all_stats(self):
        html = render_template("carousel/slide_about_numbers", self.slides[2])
        assert "<html" in html
        for stat in self.slides[2]["stats"]:
            assert stat["value"] in html
            assert stat["label"].upper() in html.upper()

    def test_cta_renders(self):
        html = render_template("carousel/slide_about_cta", self.slides[-1])
        assert "<html" in html
        assert "@windsurfworldtourstats" in html
        assert "follow" in html.lower()

    def test_all_slides_1080x1350(self):
        type_map = {
            "about_cover": "carousel/slide_about_cover",
            "about_text": "carousel/slide_about_text",
            "about_numbers": "carousel/slide_about_numbers",
            "about_cta": "carousel/slide_about_cta",
        }
        for slide in self.slides:
            template = type_map[slide["type"]]
            html = render_template(template, slide)
            assert "1080" in html
            assert "1350" in html
