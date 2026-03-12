"""Tests for Top 10 carousel slide builder and template rendering."""
import pytest

from pipeline.templates import get_dummy_data, render_template
from pipeline.carousel import build_slides, MEDAL_COLOURS, _detect_top_ties


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_entries(scores, **kwargs):
    """Build a list of entry dicts from a list of scores."""
    return [
        {
            "rank": i + 1,
            "athlete": f"Athlete {i + 1}",
            "country": "ES",
            "score": s,
            "event": "Test Event",
            "round": "Final",
            **kwargs,
        }
        for i, s in enumerate(scores)
    ]


def _make_data(entries, **overrides):
    """Build a full data dict for build_slides."""
    base = {
        "title_gender": "Men's",
        "title_metric": "Jumps",
        "title_year": 2025,
        "is_per_event": True,
        "event_name": "Gran Canaria World Cup",
        "event_country": "ESP",
        "event_date_start": "Jul 05",
        "event_date_end": "Jul 13",
        "event_stars": 5,
        "show_trick_type": True,
        "entries": entries,
    }
    base.update(overrides)
    return base


# ── Tie Detection ────────────────────────────────────────────────────────────

class TestDetectTopTies:
    def test_no_ties_returns_empty(self):
        entries = _make_entries([10.00, 9.50, 9.00, 8.50, 8.00, 7.50, 7.00, 6.50, 6.00, 5.50])
        assert _detect_top_ties(entries) == []

    def test_two_way_tie(self):
        entries = _make_entries([10.00, 10.00, 9.00, 8.50, 8.00, 7.50, 7.00, 6.50, 6.00, 5.50])
        tied = _detect_top_ties(entries)
        assert len(tied) == 2
        assert all(e["score"] == 10.00 for e in tied)

    def test_four_way_tie(self):
        entries = _make_entries([10.00, 10.00, 10.00, 10.00, 8.00, 7.50, 7.00, 6.50, 6.00, 5.50])
        tied = _detect_top_ties(entries)
        assert len(tied) == 4

    def test_tie_not_at_top_ignored(self):
        entries = _make_entries([10.00, 9.00, 9.00, 8.50, 8.00, 7.50, 7.00, 6.50, 6.00, 5.50])
        assert _detect_top_ties(entries) == []


# ── Tied Slide Building ──────────────────────────────────────────────────────

class TestBuildSlidesTied:
    def setup_method(self):
        scores = [10.00, 10.00, 10.00, 10.00, 8.00, 7.50, 7.00, 6.50, 6.00, 5.50]
        entries = _make_entries(scores, trick_type="F")
        self.data = _make_data(entries)
        self.slides = build_slides(self.data)

    def test_four_way_tie_slide_types(self):
        types = [s["type"] for s in self.slides]
        assert types == ["cover", "tied_highlight", "tied_grid", "table", "table_cta"]

    def test_tied_highlight_data(self):
        hl = self.slides[1]
        assert hl["type"] == "tied_highlight"
        assert hl["tie_count"] == 4
        assert hl["tie_score"] == 10.00

    def test_tied_grid_has_four_rows(self):
        grid = self.slides[2]
        assert grid["type"] == "tied_grid"
        assert len(grid["rows"]) == 4

    def test_tied_grid_uses_gold_accent(self):
        grid = self.slides[2]
        assert grid["tie_accent"] == MEDAL_COLOURS["gold"]

    def test_table_starts_at_rank_5(self):
        table = self.slides[3]
        assert table["type"] == "table"
        assert table["rows"][0]["rank"] == 5

    def test_table_has_five_rows(self):
        table = self.slides[3]
        assert len(table["rows"]) == 5

    def test_table_cta_is_last_slide(self):
        last = self.slides[-1]
        assert last["type"] == "table_cta"
        assert len(last["rows"]) == 1

    def test_common_fields_present(self):
        for slide in self.slides:
            assert "title" in slide
            assert "discipline" in slide
            assert slide.get("is_per_event") is True
            assert "event_name" in slide
            assert "show_trick_type" in slide

    def test_cover_has_event_metadata(self):
        cover = self.slides[0]
        assert cover["event_stars"] == 5
        assert cover["event_date_start"] == "Jul 05"
        assert cover["event_date_end"] == "Jul 13"


# ── Medal Colours ────────────────────────────────────────────────────────────

class TestMedalColours:
    def test_gold(self):
        assert MEDAL_COLOURS["gold"] == "#F0C040"

    def test_silver(self):
        assert MEDAL_COLOURS["silver"] == "#C0C8D4"

    def test_bronze(self):
        assert MEDAL_COLOURS["bronze"] == "#CD7F32"


# ── Standard (No-Tie) Slide Building ────────────────────────────────────────

class TestBuildSlides:
    def setup_method(self):
        self.data = get_dummy_data("top_10")
        self.slides = build_slides(self.data)

    def test_returns_five_slides(self):
        assert len(self.slides) == 5

    def test_slide_types_in_order(self):
        expected = ["cover", "hero", "table", "table", "cta"]
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
        assert hero["podium_colour"]["accent"] == MEDAL_COLOURS["gold"]

    def test_table_slide_has_ranks_2_to_6(self):
        table = self.slides[2]
        assert table["type"] == "table"
        assert len(table["rows"]) == 5
        assert table["rows"][0]["rank"] == 2
        assert table["rows"][-1]["rank"] == 6
        assert table["label"] == "Positions 2\u20136"

    def test_table_slide_has_ranks_7_to_10(self):
        table = self.slides[3]
        assert table["type"] == "table"
        assert len(table["rows"]) == 4
        assert table["rows"][0]["rank"] == 7
        assert table["rows"][-1]["rank"] == 10
        assert table["label"] == "Positions 7\u201310"

    def test_cta_is_last_slide(self):
        cta = self.slides[4]
        assert cta["type"] == "cta"

    def test_slides_have_numbering(self):
        for i, slide in enumerate(self.slides, 1):
            assert slide["slide_number"] == i
            assert slide["total_slides"] == 5

    def test_discipline_derived_from_metric(self):
        for slide in self.slides:
            assert slide["discipline"] == "waves"

    def test_jumps_discipline(self):
        data = {**self.data, "title_metric": "Jumps"}
        slides = build_slides(data)
        for slide in slides:
            assert slide["discipline"] == "jumps"


# ── Template Rendering ───────────────────────────────────────────────────────

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

    def test_cover_uses_cyan_accent(self):
        html = render_template("carousel/slide_cover", self.slides[0])
        assert "#00D4FF" in html

    def test_cover_extends_base(self):
        html = render_template("carousel/slide_cover", self.slides[0])
        assert "var(--font-display)" in html
        assert "var(--font-body)" in html

    def test_cover_per_event_shows_stars(self):
        data = get_dummy_data("top_10_carousel")
        slides = build_slides(data)
        html = render_template("carousel/slide_cover", slides[0])
        assert "Swipe to reveal" in html
        # Should show stars for per-event
        assert "\u2605" in html

    def test_cover_per_event_shows_dates(self):
        data = get_dummy_data("top_10_carousel")
        slides = build_slides(data)
        html = render_template("carousel/slide_cover", slides[0])
        assert "Jul" in html

    def test_hero_slide_renders(self):
        html = render_template("carousel/slide_hero", self.slides[1])
        assert "<html" in html
        assert "MARC PARE RICO" in html
        assert "8.83" in html

    def test_hero_has_title(self):
        html = render_template("carousel/slide_hero", self.slides[1])
        assert "TOP 10" in html

    def test_hero_uses_gold(self):
        html = render_template("carousel/slide_hero", self.slides[1])
        assert "#F0C040" in html

    def test_hero_uses_flag_image(self):
        html = render_template("carousel/slide_hero", self.slides[1])
        assert "flagcdn.com" in html

    def test_table_slide_renders(self):
        html = render_template("carousel/slide_table", self.slides[2])
        assert "<html" in html
        for row in self.slides[2]["rows"]:
            assert row["athlete"] in html

    def test_table_has_flag_images(self):
        html = render_template("carousel/slide_table", self.slides[2])
        assert "flagcdn.com" in html

    def test_table_has_position_range(self):
        html = render_template("carousel/slide_table", self.slides[2])
        assert "2nd" in html
        assert "6th" in html

    def test_table_medal_colors_for_ranks_2_and_3(self):
        html = render_template("carousel/slide_table", self.slides[2])
        assert MEDAL_COLOURS["silver"] in html
        assert MEDAL_COLOURS["bronze"] in html

    def test_table_medal_row_shading(self):
        html = render_template("carousel/slide_table", self.slides[2])
        assert "medal-silver" in html
        assert "medal-bronze" in html

    def test_table_no_event_column(self):
        html = render_template("carousel/slide_table", self.slides[2])
        assert ">EVENT<" not in html

    def test_second_table_slide_renders(self):
        html = render_template("carousel/slide_table", self.slides[3])
        assert "<html" in html
        for row in self.slides[3]["rows"]:
            assert row["athlete"] in html

    def test_cta_slide_renders(self):
        html = render_template("carousel/slide_cta", self.slides[4])
        assert "<html" in html
        assert "windsurfworldtourstats.com" in html.lower()

    def test_cta_has_follow_prompt(self):
        html = render_template("carousel/slide_cta", self.slides[4])
        assert "follow" in html.lower()

    def test_all_slides_1080x1350(self):
        for slide in self.slides:
            html = render_template(
                f"carousel/slide_{slide['type']}", slide
            )
            assert "1080" in html
            assert "1350" in html


# ── Tied Template Rendering ──────────────────────────────────────────────────

class TestTiedTemplateRendering:
    def setup_method(self):
        self.data = get_dummy_data("top_10_carousel")
        self.slides = build_slides(self.data)

    def test_tied_highlight_renders(self):
        hl = self.slides[1]
        assert hl["type"] == "tied_highlight"
        html = render_template("carousel/slide_tied_highlight", hl)
        assert "<html" in html
        assert "4" in html

    def test_tied_highlight_uses_gold(self):
        hl = self.slides[1]
        html = render_template("carousel/slide_tied_highlight", hl)
        assert MEDAL_COLOURS["gold"] in html

    def test_tied_grid_renders(self):
        grid = self.slides[2]
        assert grid["type"] == "tied_grid"
        html = render_template("carousel/slide_tied_grid", grid)
        assert "<html" in html
        assert "flagcdn.com" in html

    def test_tied_grid_uses_gold_border(self):
        grid = self.slides[2]
        html = render_template("carousel/slide_tied_grid", grid)
        assert MEDAL_COLOURS["gold"] in html

    def test_tied_grid_shows_all_athletes(self):
        grid = self.slides[2]
        html = render_template("carousel/slide_tied_grid", grid)
        for row in grid["rows"]:
            assert row["athlete"].upper() in html

    def test_table_cta_slide_renders(self):
        cta = self.slides[-1]
        assert cta["type"] == "table_cta"
        html = render_template("carousel/slide_table_cta", cta)
        assert "<html" in html
        assert "windsurfworldtourstats.com" in html.lower()
        assert "follow" in html.lower()

    def test_table_shows_trick_type(self):
        table = self.slides[3]
        assert table["type"] == "table"
        html = render_template("carousel/slide_table", table)
        assert "TYPE" in html

    def test_all_tied_slides_1080x1350(self):
        for slide in self.slides:
            html = render_template(
                f"carousel/slide_{slide['type']}", slide
            )
            assert "1080" in html
            assert "1350" in html


class TestGetDummyDataCarousel:
    def test_top_10_carousel_returns_valid_data(self):
        data = get_dummy_data("top_10_carousel")
        assert "entries" in data
        assert len(data["entries"]) == 10
        assert "title_gender" in data
        assert "title_metric" in data
        assert "title_year" in data

    def test_top_10_carousel_has_ties(self):
        data = get_dummy_data("top_10_carousel")
        top_score = data["entries"][0]["score"]
        tied = [e for e in data["entries"] if e["score"] == top_score]
        assert len(tied) == 4

    def test_top_10_carousel_has_per_event_fields(self):
        data = get_dummy_data("top_10_carousel")
        assert data["is_per_event"] is True
        assert "event_name" in data
        assert data["show_trick_type"] is True

    def test_top_10_carousel_entries_have_trick_type(self):
        data = get_dummy_data("top_10_carousel")
        for entry in data["entries"]:
            assert "trick_type" in entry

    def test_top_10_carousel_has_event_metadata(self):
        data = get_dummy_data("top_10_carousel")
        assert "event_stars" in data
        assert "event_date_start" in data
        assert "event_date_end" in data
        assert "event_country" in data
