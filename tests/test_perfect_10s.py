"""Tests for the 'Every Perfect 10' wave carousel one-off post."""
import pytest

from pipeline.queries import build_perfect_10s_wave_query
from pipeline.templates import get_dummy_data, render_template
from pipeline.carousel import build_slides
from pipeline.captions import build_caption


# ── Query builder ──────────────────────────────────────────────────────────

class TestBuildPerfect10sWaveQuery:
    def test_returns_sql_and_params(self):
        sql, params = build_perfect_10s_wave_query()
        assert isinstance(sql, str)
        assert isinstance(params, tuple)

    def test_no_params(self):
        sql, params = build_perfect_10s_wave_query()
        assert params == ()

    def test_filters_score_equals_10(self):
        sql, _ = build_perfect_10s_wave_query()
        assert "10.00" in sql or "10" in sql
        assert "s.score = 10" in sql

    def test_filters_wave_type(self):
        sql, _ = build_perfect_10s_wave_query()
        assert "'Wave'" in sql

    def test_filters_counting(self):
        sql, _ = build_perfect_10s_wave_query()
        assert "counting = 1" in sql

    def test_orders_by_year_desc(self):
        sql, _ = build_perfect_10s_wave_query()
        assert "e.year DESC" in sql

    def test_selects_required_columns(self):
        sql, _ = build_perfect_10s_wave_query()
        # year, event, round, heat, elimination_name needed for sex derivation
        assert "e.year" in sql
        assert "event_name" in sql
        assert "round_name" in sql
        assert "heat_id" in sql
        assert "elimination_name" in sql

    def test_joins_required_tables(self):
        sql, _ = build_perfect_10s_wave_query()
        assert "PWA_IWT_HEAT_SCORES" in sql
        assert "ATHLETES" in sql
        assert "PWA_IWT_EVENTS" in sql
        assert "PWA_IWT_HEAT_PROGRESSION" in sql


# ── Dummy data ─────────────────────────────────────────────────────────────

class TestPerfect10sDummyData:
    def test_returns_data_dict(self):
        data = get_dummy_data("perfect_10s")
        assert isinstance(data, dict)
        assert "entries" in data

    def test_has_12_entries(self):
        data = get_dummy_data("perfect_10s")
        assert len(data["entries"]) == 12

    def test_perfect_10s_mode_flag(self):
        data = get_dummy_data("perfect_10s")
        assert data.get("perfect_10s_mode") is True

    def test_all_scores_are_10(self):
        data = get_dummy_data("perfect_10s")
        for e in data["entries"]:
            assert e["score"] == 10.00

    def test_entries_have_year_and_sex_and_heat(self):
        data = get_dummy_data("perfect_10s")
        for e in data["entries"]:
            assert "year" in e
            assert "sex" in e
            assert "heat" in e
            assert e["sex"] in ("M", "W")

    def test_ordered_year_desc(self):
        data = get_dummy_data("perfect_10s")
        years = [e["year"] for e in data["entries"]]
        assert years == sorted(years, reverse=True)

    def test_includes_known_perfect_10s(self):
        data = get_dummy_data("perfect_10s")
        athletes = [e["athlete"] for e in data["entries"]]
        assert "Adam Lewis" in athletes
        assert "Daida Ruano Moreno" in athletes  # the one woman


# ── Slide builder ──────────────────────────────────────────────────────────

class TestBuildSlidesPerfect10s:
    def setup_method(self):
        self.data = get_dummy_data("perfect_10s")
        self.slides = build_slides(self.data)

    def test_five_total_slides(self):
        # cover + 3 tables (5+5+2) + cta
        assert len(self.slides) == 5

    def test_slide_types(self):
        types = [s["type"] for s in self.slides]
        assert types == ["cover", "table", "table", "table", "cta"]

    def test_no_hero_slide(self):
        assert all(s["type"] != "hero" for s in self.slides)

    def test_first_table_has_5_rows(self):
        assert len(self.slides[1]["rows"]) == 5

    def test_second_table_has_5_rows(self):
        assert len(self.slides[2]["rows"]) == 5

    def test_third_table_has_2_rows(self):
        assert len(self.slides[3]["rows"]) == 2

    def test_table_ranks_chronological_split(self):
        # rows are ranked 1-12 in chronological-desc order
        assert self.slides[1]["rows"][0]["rank"] == 1
        assert self.slides[1]["rows"][-1]["rank"] == 5
        assert self.slides[2]["rows"][0]["rank"] == 6
        assert self.slides[2]["rows"][-1]["rank"] == 10
        assert self.slides[3]["rows"][0]["rank"] == 11
        assert self.slides[3]["rows"][-1]["rank"] == 12

    def test_show_year_sex_flag_propagated(self):
        for slide in self.slides:
            assert slide.get("show_year_sex") is True

    def test_perfect_10s_mode_propagated(self):
        for slide in self.slides:
            assert slide.get("perfect_10s_mode") is True

    def test_custom_title_propagated(self):
        for slide in self.slides:
            assert slide.get("custom_title") == "EVERY PERFECT 10 WAVE"

    def test_title_overridden(self):
        # title used on table slides is "EVERY PERFECT 10 WAVE"
        assert self.slides[0]["title"] == "EVERY PERFECT 10 WAVE"

    def test_accent_color_waves(self):
        for slide in self.slides:
            assert slide["accent_color"] == "#5AB4CC"

    def test_slide_numbering(self):
        for i, slide in enumerate(self.slides, 1):
            assert slide["slide_number"] == i
            assert slide["total_slides"] == 5


# ── Caption ─────────────────────────────────────────────────────────────────

class TestPerfect10sCaption:
    def test_caption_mentions_perfect_10s(self):
        data = get_dummy_data("perfect_10s")
        caption = build_caption("top_10_carousel", data, {"captions": {"site_url": "wwts.com"}, "hashtags": {}})
        assert "perfect 10" in caption.lower()

    def test_caption_mentions_2019_cutoff(self):
        data = get_dummy_data("perfect_10s")
        caption = build_caption("top_10_carousel", data, {"captions": {"site_url": "wwts.com"}, "hashtags": {}})
        assert "2019" in caption

    def test_caption_includes_count(self):
        data = get_dummy_data("perfect_10s")
        caption = build_caption("top_10_carousel", data, {"captions": {"site_url": "wwts.com"}, "hashtags": {}})
        assert "12" in caption


# ── Template rendering ─────────────────────────────────────────────────────

class TestPerfect10sTemplateRendering:
    def setup_method(self):
        self.data = get_dummy_data("perfect_10s")
        self.slides = build_slides(self.data)

    def test_cover_renders(self):
        html = render_template("carousel/slide_cover", self.slides[0])
        assert "<html" in html
        assert "PERFECT 10" in html

    def test_table_renders_year_column(self):
        html = render_template("carousel/slide_table", self.slides[1])
        assert "YEAR" in html
        for row in self.slides[1]["rows"]:
            assert str(row["year"]) in html

    def test_table_omits_score_column(self):
        # All scores are 10.00, so the score column is dropped entirely
        html = render_template("carousel/slide_table", self.slides[1])
        assert ">SCORE<" not in html

    def test_table_renders_heat_id(self):
        # heat appears as subtitle under event
        all_html = "".join(
            render_template("carousel/slide_table", s)
            for s in self.slides if s["type"] == "table"
        )
        # at least one heat label like H20a should appear
        assert "H" in all_html

    def test_all_slides_1080x1350(self):
        for slide in self.slides:
            html = render_template(f"carousel/slide_{slide['type']}", slide)
            assert "1080" in html
            assert "1350" in html
