"""Tests for athlete rise carousel — query builder, slide builder, dummy data, captions."""
import pytest

from pipeline.queries import build_athlete_rise_query
from pipeline.athlete_rise_carousel import build_athlete_rise_slides, ACCENT_COLOR, COLOR_WAVE, COLOR_JUMP, COLOR_OVERVIEW
from pipeline.templates import get_dummy_data, render_template
from pipeline.captions import build_caption


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_yearly_data():
    """Sample yearly progression data (based on real Marino GC data)."""
    return [
        {"year": 2017, "placement": 33, "best_heat": 16.50, "best_wave": 5.50, "best_jump": 7.38, "best_jump_type": "B"},
        {"year": 2018, "placement": 17, "best_heat": 25.38, "best_wave": 7.38, "best_jump": 7.25, "best_jump_type": "F"},
        {"year": 2019, "placement": 17, "best_heat": 26.65, "best_wave": 7.95, "best_jump": 7.00, "best_jump_type": "B"},
        {"year": 2022, "placement": 6, "best_heat": 20.43, "best_wave": 7.38, "best_jump": 7.50, "best_jump_type": "F"},
        {"year": 2023, "placement": 2, "best_heat": 31.25, "best_wave": 8.12, "best_jump": 10.00, "best_jump_type": "PF"},
        {"year": 2024, "placement": 1, "best_heat": 28.43, "best_wave": 6.62, "best_jump": 9.57, "best_jump_type": "PF"},
        {"year": 2025, "placement": 3, "best_heat": 27.47, "best_wave": 5.62, "best_jump": 10.00, "best_jump_type": "PF"},
    ]


def _make_data(**overrides):
    """Build a full data dict for the athlete rise carousel."""
    base = {
        "title": "THE RISE OF MARINO GIL GHERARDI IN GRAN CANARIA",
        "subtitle": "Check out the meteoric rise of Marino's world cup performances at his home spot in Gran Canaria",
        "athlete_name": "Marino Gil Gherardi",
        "location": "Gran Canaria",
        "accent_color": ACCENT_COLOR,
        "yearly_data": _make_yearly_data(),
    }
    base.update(overrides)
    return base


# ── Query Builder ────────────────────────────────────────────────────────────

class TestBuildAthleteRiseQuery:
    def test_returns_tuple_of_two(self):
        result = build_athlete_rise_query(48, "%Gran Canaria%", "Men")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_sql_and_params(self):
        sql, params = build_athlete_rise_query(48, "%Gran Canaria%", "Men")
        assert isinstance(sql, str)
        assert isinstance(params, tuple)

    def test_sql_contains_athlete_id_param(self):
        sql, params = build_athlete_rise_query(48, "%Gran Canaria%", "Men")
        assert "%s" in sql
        assert 48 in params

    def test_sql_contains_event_pattern_param(self):
        sql, params = build_athlete_rise_query(48, "%Gran Canaria%", "Men")
        assert "%Gran Canaria%" in params

    def test_sql_contains_sex_param(self):
        sql, params = build_athlete_rise_query(48, "%Gran Canaria%", "Men")
        assert "Men" in params

    def test_sql_selects_year(self):
        sql, _ = build_athlete_rise_query(48, "%Gran Canaria%", "Men")
        assert "year" in sql.lower()

    def test_sql_selects_placement(self):
        sql, _ = build_athlete_rise_query(48, "%Gran Canaria%", "Men")
        assert "place" in sql.lower()

    def test_sql_selects_best_wave(self):
        sql, _ = build_athlete_rise_query(48, "%Gran Canaria%", "Men")
        assert "wave" in sql.lower()

    def test_sql_orders_by_year(self):
        sql, _ = build_athlete_rise_query(48, "%Gran Canaria%", "Men")
        assert "ORDER BY" in sql
        # Check the outer ORDER BY (last one) sorts by year
        last_order_by = sql.lower().rsplit("order by", 1)[1]
        assert "year" in last_order_by


# ── Slide Builder ────────────────────────────────────────────────────────────

class TestBuildAthleteRiseSlides:
    def setup_method(self):
        self.data = _make_data()
        self.slides = build_athlete_rise_slides(self.data)

    def test_returns_five_slides(self):
        assert len(self.slides) == 5

    def test_slide_types_in_order(self):
        types = [s["type"] for s in self.slides]
        assert types == [
            "rise_cover",
            "rise_explanation",
            "rise_dual_chart",
            "rise_dual_chart",
            "analysis_cta",
        ]

    def test_all_slides_have_accent_color(self):
        for slide in self.slides:
            assert "accent_color" in slide

    def test_all_slides_have_numbering(self):
        for i, slide in enumerate(self.slides, 1):
            assert slide["slide_number"] == i
            assert slide["total_slides"] == 5

    def test_cover_has_title(self):
        cover = self.slides[0]
        assert "RISE" in cover["title"]
        assert "MARINO GIL GHERARDI" in cover["title"]

    def test_cover_has_eyebrow(self):
        cover = self.slides[0]
        assert "eyebrow" in cover
        assert "Gran Canaria" in cover["eyebrow"]

    def test_cover_has_name_and_location(self):
        cover = self.slides[0]
        assert cover["cover_name"] == "MARINO GIL GHERARDI"
        assert "GRAN CANARIA" in cover["cover_location"]
        assert "AT THE" in cover["cover_location"]

    def test_chart_slides_have_header(self):
        for slide in self.slides[2:4]:
            assert "header_eyebrow" in slide
            assert "header_athlete" in slide
            assert "MARINO GIL GHERARDI" in slide["header_athlete"]

    def test_jump_chart_uses_teal(self):
        slide4 = self.slides[3]
        assert slide4["top_chart"]["color"] == COLOR_JUMP

    def test_wave_chart_uses_cyan(self):
        slide4 = self.slides[3]
        assert slide4["bottom_chart"]["color"] == COLOR_WAVE

    def test_overview_charts_use_purple(self):
        slide3 = self.slides[2]
        assert slide3["top_chart"]["color"] == COLOR_OVERVIEW
        assert slide3["bottom_chart"]["color"] == COLOR_OVERVIEW

    def test_jump_chart_has_labels(self):
        slide4 = self.slides[3]
        assert slide4["top_chart"]["show_labels"] is True
        labels = [p["label"] for p in slide4["top_chart"]["points"]]
        assert "Backloop" in labels
        assert "Push Forward" in labels

    def test_explanation_has_body_text(self):
        explanation = self.slides[1]
        assert "body_text" in explanation
        assert "Marino" in explanation["body_text"]

    def test_slide_3_has_placement_and_heat_charts(self):
        slide = self.slides[2]
        assert slide["type"] == "rise_dual_chart"
        assert "top_chart" in slide
        assert "bottom_chart" in slide
        assert slide["top_chart"]["chart_title"] == "EVENT PLACEMENT"
        assert slide["bottom_chart"]["chart_title"] == "BEST HEAT SCORE"

    def test_slide_4_has_jump_and_wave_charts(self):
        slide = self.slides[3]
        assert slide["type"] == "rise_dual_chart"
        assert slide["top_chart"]["chart_title"] == "BEST JUMP SCORE"
        assert slide["bottom_chart"]["chart_title"] == "BEST WAVE SCORE"

    def test_placement_chart_is_line_type(self):
        slide = self.slides[2]
        assert slide["top_chart"]["chart_type"] == "line"

    def test_score_charts_are_column_type(self):
        slide = self.slides[2]
        assert slide["bottom_chart"]["chart_type"] == "column"
        slide4 = self.slides[3]
        assert slide4["top_chart"]["chart_type"] == "column"
        assert slide4["bottom_chart"]["chart_type"] == "column"

    def test_chart_has_data_points(self):
        chart = self.slides[2]["top_chart"]
        assert "points" in chart
        assert len(chart["points"]) == 7  # 7 years of data

    def test_placement_points_have_correct_years(self):
        chart = self.slides[2]["top_chart"]
        years = [p["year"] for p in chart["points"]]
        assert years == [2017, 2018, 2019, 2022, 2023, 2024, 2025]

    def test_placement_points_have_values(self):
        chart = self.slides[2]["top_chart"]
        values = [p["value"] for p in chart["points"]]
        assert values == [33, 17, 17, 6, 2, 1, 3]

    def test_placement_points_have_height_pct(self):
        chart = self.slides[2]["top_chart"]
        for p in chart["points"]:
            assert "height_pct" in p
            assert 0 <= p["height_pct"] <= 100

    def test_placement_inverted_y(self):
        """1st place should have highest height_pct (inverted Y axis)."""
        chart = self.slides[2]["top_chart"]
        pcts = {p["value"]: p["height_pct"] for p in chart["points"]}
        assert pcts[1] > pcts[33]  # 1st place higher than 33rd

    def test_column_chart_height_pcts(self):
        chart = self.slides[2]["bottom_chart"]
        for p in chart["points"]:
            assert "height_pct" in p
            assert 0 <= p["height_pct"] <= 100

    def test_column_chart_max_is_100(self):
        chart = self.slides[3]["bottom_chart"]  # best wave
        pcts = [p["height_pct"] for p in chart["points"] if p["value"] is not None]
        assert max(pcts) == 100

    def test_none_values_get_zero_height(self):
        """Years with no data should have 0 height."""
        data = _make_data(yearly_data=[
            {"year": 2019, "placement": 25, "best_heat": None, "best_wave": 5.50, "best_jump": None},
            {"year": 2020, "placement": 10, "best_heat": 12.00, "best_wave": 7.00, "best_jump": 8.00},
        ])
        slides = build_athlete_rise_slides(data)
        chart = slides[2]["bottom_chart"]  # best heat
        point_2019 = [p for p in chart["points"] if p["year"] == 2019][0]
        assert point_2019["height_pct"] == 0

    def test_cta_is_analysis_cta(self):
        cta = self.slides[4]
        assert cta["type"] == "analysis_cta"


# ── Dummy Data ───────────────────────────────────────────────────────────────

class TestGetDummyDataAthleteRise:
    def test_returns_valid_data(self):
        data = get_dummy_data("athlete_rise")
        assert "title" in data
        assert "subtitle" in data
        assert "athlete_name" in data
        assert "location" in data
        assert "accent_color" in data
        assert "yearly_data" in data

    def test_has_yearly_data(self):
        data = get_dummy_data("athlete_rise")
        assert len(data["yearly_data"]) >= 4

    def test_yearly_data_has_required_keys(self):
        data = get_dummy_data("athlete_rise")
        for row in data["yearly_data"]:
            assert "year" in row
            assert "placement" in row
            assert "best_wave" in row

    def test_yearly_data_ordered_by_year(self):
        data = get_dummy_data("athlete_rise")
        years = [r["year"] for r in data["yearly_data"]]
        assert years == sorted(years)


# ── Template Rendering ───────────────────────────────────────────────────────

class TestAthleteRiseTemplateRendering:
    def setup_method(self):
        self.data = get_dummy_data("athlete_rise")
        self.slides = build_athlete_rise_slides(self.data)

    def test_cover_renders(self):
        html = render_template("carousel/slide_rise_cover", self.slides[0])
        assert "<html" in html
        assert "RISE" in html

    def test_explanation_renders(self):
        html = render_template("carousel/slide_rise_explanation", self.slides[1])
        assert "<html" in html
        assert "Marino" in html or "meteoric" in html.lower()

    def test_dual_chart_renders(self):
        html = render_template("carousel/slide_rise_dual_chart", self.slides[2])
        assert "<html" in html
        assert "EVENT PLACEMENT" in html
        assert "svg" in html.lower()

    def test_second_dual_chart_renders(self):
        html = render_template("carousel/slide_rise_dual_chart", self.slides[3])
        assert "<html" in html
        assert "BEST JUMP SCORE" in html or "BEST WAVE SCORE" in html

    def test_cta_renders(self):
        html = render_template("carousel/slide_analysis_cta", self.slides[4])
        assert "<html" in html
        assert "windsurfworldtourstats" in html.lower()

    def test_all_slides_1080x1350(self):
        for slide in self.slides:
            html = render_template(f"carousel/slide_{slide['type']}", slide)
            assert "1080" in html
            assert "1350" in html


# ── Captions ─────────────────────────────────────────────────────────────────

class TestAthleteRiseCaption:
    def test_caption_contains_athlete_name(self):
        data = get_dummy_data("athlete_rise")
        config = {"captions": {"site_url": "windsurfworldtourstats.com"}, "hashtags": {}}
        caption = build_caption("athlete_rise", data, config)
        assert "Marino Gil Gherardi" in caption

    def test_caption_contains_location(self):
        data = get_dummy_data("athlete_rise")
        config = {"captions": {"site_url": "windsurfworldtourstats.com"}, "hashtags": {}}
        caption = build_caption("athlete_rise", data, config)
        assert "Gran Canaria" in caption

    def test_caption_contains_site_url(self):
        data = get_dummy_data("athlete_rise")
        config = {"captions": {"site_url": "windsurfworldtourstats.com"}, "hashtags": {}}
        caption = build_caption("athlete_rise", data, config)
        assert "windsurfworldtourstats.com" in caption
