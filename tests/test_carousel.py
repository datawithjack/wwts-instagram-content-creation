"""Tests for Top 10 carousel slide builder and template rendering."""
import pytest

from pipeline.templates import get_dummy_data, render_template
from pipeline.carousel import build_slides, PODIUM_COLOURS


class TestBuildSlides:
    def setup_method(self):
        self.data = get_dummy_data("top_10")
        self.slides = build_slides(self.data)

    def test_returns_five_slides(self):
        assert len(self.slides) == 5

    def test_slide_types_in_order(self):
        expected = ["cover", "hero", "podium", "table", "table_cta"]
        assert [s["type"] for s in self.slides] == expected

    def test_all_slides_have_common_fields(self):
        for slide in self.slides:
            assert "type" in slide
            assert "title" in slide
            assert "discipline" in slide

    def test_cover_slide(self):
        cover = self.slides[0]
        assert cover["type"] == "cover"
        assert cover["title"] == "MEN'S TOP 10 WAVES"
        assert cover["year"] == 2025

    def test_hero_slide_has_rank_1(self):
        hero = self.slides[1]
        assert hero["type"] == "hero"
        assert hero["row"]["rank"] == 1
        assert hero["row"]["athlete"] == "Marc Pare Rico"
        assert "podium_colour" in hero

    def test_hero_slide_gold_colour(self):
        hero = self.slides[1]
        assert hero["podium_colour"]["accent"] == PODIUM_COLOURS[1]["accent"]

    def test_podium_slide_has_ranks_2_and_3(self):
        podium = self.slides[2]
        assert podium["type"] == "podium"
        assert len(podium["rows"]) == 2
        assert podium["rows"][0]["rank"] == 2
        assert podium["rows"][1]["rank"] == 3

    def test_podium_slide_has_colours(self):
        podium = self.slides[2]
        assert len(podium["podium_colours"]) == 2

    def test_table_slide_has_ranks_4_to_7(self):
        table = self.slides[3]
        assert table["type"] == "table"
        assert len(table["rows"]) == 4
        assert table["rows"][0]["rank"] == 4
        assert table["rows"][-1]["rank"] == 7
        assert table["label"] == "Positions 4–7"

    def test_table_cta_slide_has_ranks_8_to_10(self):
        cta = self.slides[4]
        assert cta["type"] == "table_cta"
        assert len(cta["rows"]) == 3
        assert cta["rows"][0]["rank"] == 8
        assert cta["rows"][-1]["rank"] == 10
        assert cta["label"] == "Positions 8–10"

    def test_discipline_derived_from_metric(self):
        # "Waves" -> discipline "waves"
        for slide in self.slides:
            assert slide["discipline"] == "waves"

    def test_jumps_discipline(self):
        data = {**self.data, "title_metric": "Jumps"}
        slides = build_slides(data)
        for slide in slides:
            assert slide["discipline"] == "jumps"


class TestPodiumColours:
    def test_gold_for_rank_1(self):
        assert PODIUM_COLOURS[1]["accent"] == "#F0C040"

    def test_silver_for_rank_2(self):
        assert PODIUM_COLOURS[2]["accent"] == "#C0C8D4"

    def test_bronze_for_rank_3(self):
        assert PODIUM_COLOURS[3]["accent"] == "#CD7F32"


class TestCarouselTemplateRendering:
    """Test that each carousel slide template renders valid HTML."""

    def setup_method(self):
        self.data = get_dummy_data("top_10")
        self.slides = build_slides(self.data)

    def test_cover_slide_renders(self):
        html = render_template("carousel/slide_cover", self.slides[0])
        assert "<html" in html
        assert "MEN" in html
        assert "WAVES" in html
        assert "2025" in html

    def test_cover_uses_design_system_accent(self):
        html = render_template("carousel/slide_cover", self.slides[0])
        assert "var(--color-athlete-left)" in html
        assert "#00D4FF" not in html

    def test_cover_extends_base(self):
        html = render_template("carousel/slide_cover", self.slides[0])
        assert "var(--font-display)" in html
        assert "var(--font-body)" in html

    def test_hero_slide_renders(self):
        html = render_template("carousel/slide_hero", self.slides[1])
        assert "<html" in html
        assert "MARC PARE RICO" in html
        assert "8.83" in html

    def test_hero_uses_design_system_vars(self):
        html = render_template("carousel/slide_hero", self.slides[1])
        assert "#00D4FF" not in html
        assert "#00A878" not in html

    def test_podium_slide_renders(self):
        html = render_template("carousel/slide_podium", self.slides[2])
        assert "<html" in html
        assert "TAKARA ISHII" in html
        assert "BERND ROEDIGER" in html

    def test_podium_has_flag_images(self):
        html = render_template("carousel/slide_podium", self.slides[2])
        assert "flagcdn.com" in html

    def test_table_slide_renders(self):
        html = render_template("carousel/slide_table", self.slides[3])
        assert "<html" in html
        for row in self.slides[3]["rows"]:
            assert row["athlete"] in html

    def test_table_has_flag_images(self):
        html = render_template("carousel/slide_table", self.slides[3])
        assert "flagcdn.com" in html

    def test_table_has_section_label(self):
        html = render_template("carousel/slide_table", self.slides[3])
        assert "Positions 4" in html

    def test_table_cta_slide_renders(self):
        html = render_template("carousel/slide_table_cta", self.slides[4])
        assert "<html" in html
        assert "windsurfworldtourstats.com" in html.lower()

    def test_table_cta_has_follow_prompt(self):
        html = render_template("carousel/slide_table_cta", self.slides[4])
        assert "follow" in html.lower()

    def test_all_slides_1080x1350(self):
        """All carousel slides should be 1080x1350 portrait."""
        for slide in self.slides:
            html = render_template(
                f"carousel/slide_{slide['type']}", slide
            )
            assert "1080" in html
            assert "1350" in html

    def test_jumps_discipline_uses_right_accent(self):
        data = {**self.data, "title_metric": "Jumps"}
        slides = build_slides(data)
        html = render_template("carousel/slide_cover", slides[0])
        assert "var(--color-athlete-right)" in html


class TestGetDummyDataCarousel:
    def test_top_10_carousel_returns_valid_data(self):
        data = get_dummy_data("top_10_carousel")
        assert "entries" in data
        assert len(data["entries"]) == 10
        assert "title_gender" in data
        assert "title_metric" in data
        assert "title_year" in data
