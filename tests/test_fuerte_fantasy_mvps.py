"""Tests for the Fuerteventura Fantasy MVPs freestyle-Session leaderboard carousel.

Ranks the pro riders who generated the most fantasy points at the Fuerteventura
freestyle Session, split into single-elim / double-elim / total, plus % picked.
"""
import pytest

from pipeline.queries import (
    build_fantasy_mvp_points_query,
    build_fantasy_session_pick_pct_query,
)
from pipeline.fuerte_fantasy_mvps import (
    parse_elimination,
    assemble_mvp_data,
    build_slides,
    resolve_country_iso,
    SESSION_COLOR,
)
from pipeline.templates import get_dummy_data, render_template
from pipeline.captions import build_caption


# ── Query builders ──────────────────────────────────────────────────────────

class TestBuildFantasyMvpPointsQuery:
    def test_returns_sql_and_params(self):
        sql, params = build_fantasy_mvp_points_query(123)
        assert isinstance(sql, str)
        assert params == (123,)

    def test_sums_heat_result_total(self):
        sql, _ = build_fantasy_mvp_points_query(123)
        assert "SUM(hr.result_total)" in sql
        assert "PWA_IWT_HEAT_RESULTS" in sql

    def test_groups_by_athlete_and_elimination(self):
        sql, _ = build_fantasy_mvp_points_query(123)
        assert "GROUP BY" in sql
        assert "elimination_name" in sql

    def test_joins_required_tables(self):
        sql, _ = build_fantasy_mvp_points_query(123)
        for table in (
            "PWA_IWT_HEAT_RESULTS",
            "PWA_IWT_EVENTS",
            "ATHLETE_SOURCE_IDS",
            "ATHLETES",
            "PWA_IWT_HEAT_PROGRESSION",
        ):
            assert table in sql

    def test_filters_to_freestyle_heats(self):
        # Freestyle heats are those WITH a row in PWA_IWT_FREESTYLE_HEAT_SCORES.
        sql, _ = build_fantasy_mvp_points_query(123)
        assert "PWA_IWT_FREESTYLE_HEAT_SCORES" in sql
        assert "EXISTS" in sql

    def test_filters_by_event_db_id(self):
        sql, _ = build_fantasy_mvp_points_query(123)
        assert "e.id = %s" in sql


class TestBuildFantasySessionPickPctQuery:
    def test_returns_sql_and_params(self):
        sql, params = build_fantasy_session_pick_pct_query(123)
        assert isinstance(sql, str)
        assert isinstance(params, tuple)
        assert 123 in params

    def test_defaults_to_freestyle_discipline(self):
        sql, params = build_fantasy_session_pick_pct_query(123)
        assert "freestyle" in params

    def test_reads_session_picks_confirmed_only(self):
        sql, _ = build_fantasy_session_pick_pct_query(123)
        assert "FANTASY_SESSION_PICKS" in sql
        assert "confirmed" in sql.lower()

    def test_counts_distinct_users(self):
        sql, _ = build_fantasy_session_pick_pct_query(123)
        assert "COUNT(DISTINCT user_id)" in sql

    def test_carries_total_entries(self):
        sql, _ = build_fantasy_session_pick_pct_query(123)
        assert "total_entries" in sql


# ── Elimination parsing ─────────────────────────────────────────────────────

class TestParseElimination:
    def test_mens_single(self):
        assert parse_elimination("Mens Single Elimination") == ("Men", "single")

    def test_womens_double(self):
        assert parse_elimination("Womens Double Elimination") == ("Women", "double")

    def test_case_insensitive(self):
        assert parse_elimination("mens double elimination") == ("Men", "double")

    def test_women_checked_before_men(self):
        # "women" contains the substring "men" — women must win.
        sex, _ = parse_elimination("Womens Single Elimination")
        assert sex == "Women"

    def test_unknown_returns_none(self):
        assert parse_elimination("") == (None, None)
        assert parse_elimination("Slalom Final") == (None, None)


# ── Country resolution ──────────────────────────────────────────────────────

class TestResolveCountryIso:
    def test_uses_country_code_column(self):
        assert resolve_country_iso("GR", "Greece") == "gr"

    def test_country_code_three_letter(self):
        assert resolve_country_iso("ESP", None) == "es"

    def test_nationality_word_fallback(self):
        assert resolve_country_iso(None, "Greece") == "gr"

    def test_nationality_iso_code_fallback(self):
        # Some rows store an ISO code in the nationality field (e.g. "IT").
        assert resolve_country_iso(None, "IT") == "it"

    def test_db_value_beats_override(self):
        # A populated country_code always wins over the sail-derived fallback.
        assert resolve_country_iso("FR", None, 985) == "fr"

    def test_sail_override_when_db_null(self):
        # id 892 = Yentel Caers (sail B-16 → be); all DB country cols NULL.
        assert resolve_country_iso(None, None, 892) == "be"

    def test_unknown_returns_empty(self):
        assert resolve_country_iso(None, None) == ""


# ── Data assembly ───────────────────────────────────────────────────────────

@pytest.fixture
def points_rows():
    # Two men, one woman, each across single + double elim.
    return [
        {"athlete": "Marino Gil", "country": "Spanish", "athlete_id": 10,
         "elimination_name": "Mens Single Elimination", "points": 40.0},
        {"athlete": "Marino Gil", "country": "Spanish", "athlete_id": 10,
         "elimination_name": "Mens Double Elimination", "points": 20.0},
        {"athlete": "Yentel Caers", "country": "Belgian", "athlete_id": 11,
         "elimination_name": "Mens Single Elimination", "points": 55.0},
        {"athlete": "Sarah Quita", "country": "Aruba", "athlete_id": 12,
         "elimination_name": "Womens Single Elimination", "points": 30.0},
        {"athlete": "Sarah Quita", "country": "Aruba", "athlete_id": 12,
         "elimination_name": "Womens Double Elimination", "points": 15.0},
    ]


@pytest.fixture
def pct_rows():
    return [
        {"athlete_id": "10", "pick_count": 40, "total_entries": 100},
        {"athlete_id": "12", "pick_count": 25, "total_entries": 100},
    ]


@pytest.fixture
def event_meta():
    return {"name": "Fuerteventura World Cup", "location": "Fuerteventura", "year": 2026}


class TestAssembleMvpData:
    def test_splits_by_sex(self, points_rows, pct_rows, event_meta):
        # Marino 40+20=60 outranks Yentel 55 (single only).
        data = assemble_mvp_data(points_rows, pct_rows, event_meta)
        assert [r["athlete"] for r in data["men"]] == ["Marino Gil", "Yentel Caers"]
        assert [r["athlete"] for r in data["women"]] == ["Sarah Quita"]

    def test_pivots_single_double_total(self, points_rows, pct_rows, event_meta):
        data = assemble_mvp_data(points_rows, pct_rows, event_meta)
        marino = next(r for r in data["men"] if r["athlete"] == "Marino Gil")
        assert marino["single_pts"] == 40.0
        assert marino["double_pts"] == 20.0
        assert marino["total_pts"] == 60.0

    def test_ranks_by_total_desc(self, points_rows, pct_rows, event_meta):
        # Marino total 60, Yentel 55 -> Marino ranks first.
        data = assemble_mvp_data(points_rows, pct_rows, event_meta)
        assert data["men"][0]["rank"] == 1
        assert data["men"][0]["athlete"] == "Marino Gil"
        assert data["men"][0]["total_pts"] == 60.0
        assert data["men"][1]["rank"] == 2
        assert data["men"][1]["athlete"] == "Yentel Caers"

    def test_joins_pct_picked(self, points_rows, pct_rows, event_meta):
        data = assemble_mvp_data(points_rows, pct_rows, event_meta)
        marino = next(r for r in data["men"] if r["athlete"] == "Marino Gil")
        assert marino["pct_picked"] == 40
        yentel = next(r for r in data["men"] if r["athlete"] == "Yentel Caers")
        assert yentel["pct_picked"] == 0  # not in pct_rows

    def test_country_converted_to_iso(self, points_rows, pct_rows, event_meta):
        data = assemble_mvp_data(points_rows, pct_rows, event_meta)
        assert data["men"][0]["country"] == "es"  # Spanish -> es
        assert data["women"][0]["country"] == "aw"  # Aruba -> aw

    def test_top_n_cap(self, pct_rows, event_meta):
        rows = [
            {"athlete": f"Rider {i}", "country": "Spanish", "athlete_id": i,
             "elimination_name": "Mens Single Elimination", "points": float(i)}
            for i in range(1, 15)
        ]
        data = assemble_mvp_data(rows, [], event_meta, top_n=10)
        assert len(data["men"]) == 10
        assert data["men"][0]["total_pts"] == 14.0  # highest first

    def test_event_meta_passed_through(self, points_rows, pct_rows, event_meta):
        data = assemble_mvp_data(points_rows, pct_rows, event_meta)
        assert data["event"]["location"] == "Fuerteventura"

    def test_zero_point_riders_dropped(self, event_meta):
        rows = [
            {"athlete": "Scorer", "country": "Spanish", "athlete_id": 1,
             "elimination_name": "Mens Single Elimination", "points": 12.0},
            {"athlete": "Blank", "country": "Spanish", "athlete_id": 2,
             "elimination_name": "Mens Single Elimination", "points": 0.0},
        ]
        data = assemble_mvp_data(rows, [], event_meta)
        assert [r["athlete"] for r in data["men"]] == ["Scorer"]


# ── Slide builder ───────────────────────────────────────────────────────────

class TestBuildSlides:
    def setup_method(self):
        self.data = get_dummy_data("fuerte_fantasy_mvps")
        self.slides = build_slides(self.data)

    def test_four_slides(self):
        assert len(self.slides) == 4

    def test_slide_types(self):
        types = [s["type"] for s in self.slides]
        assert types == ["mvp_cover", "mvp_table", "mvp_table", "mvp_cta"]

    def test_men_then_women_tables(self):
        assert self.slides[1]["sex_label"] == "MEN"
        assert self.slides[2]["sex_label"] == "WOMEN"

    def test_tables_carry_rows(self):
        assert len(self.slides[1]["rows"]) == len(self.data["men"])
        assert len(self.slides[2]["rows"]) == len(self.data["women"])

    def test_accent_color_session_teal(self):
        for slide in self.slides:
            assert slide["accent_color"] == SESSION_COLOR

    def test_slide_numbering(self):
        for i, slide in enumerate(self.slides, 1):
            assert slide["slide_number"] == i
            assert slide["total_slides"] == 4

    def test_event_meta_on_cover(self):
        assert self.slides[0]["event"]["location"]


# ── Dummy data ──────────────────────────────────────────────────────────────

class TestDummyData:
    def test_returns_dict_with_men_women(self):
        data = get_dummy_data("fuerte_fantasy_mvps")
        assert isinstance(data, dict)
        assert "men" in data and "women" in data
        assert "event" in data

    def test_ten_rows_each(self):
        data = get_dummy_data("fuerte_fantasy_mvps")
        assert len(data["men"]) == 10
        assert len(data["women"]) == 10

    def test_rows_have_required_fields(self):
        data = get_dummy_data("fuerte_fantasy_mvps")
        for row in data["men"] + data["women"]:
            for key in ("rank", "athlete", "country", "single_pts",
                        "double_pts", "total_pts", "pct_picked"):
                assert key in row

    def test_single_plus_double_equals_total(self):
        data = get_dummy_data("fuerte_fantasy_mvps")
        for row in data["men"] + data["women"]:
            assert round(row["single_pts"] + row["double_pts"], 2) == row["total_pts"]

    def test_ranked_by_total_desc(self):
        data = get_dummy_data("fuerte_fantasy_mvps")
        for fleet in ("men", "women"):
            totals = [r["total_pts"] for r in data[fleet]]
            assert totals == sorted(totals, reverse=True)


# ── Caption ─────────────────────────────────────────────────────────────────

class TestCaption:
    def _config(self):
        return {"captions": {"site_url": "windsurfworldtourstats.com"}, "hashtags": {}}

    def test_caption_mentions_mvps(self):
        data = get_dummy_data("fuerte_fantasy_mvps")
        caption = build_caption("fuerte_fantasy_mvps", data, self._config())
        assert "mvp" in caption.lower()

    def test_caption_names_top_scorers(self):
        data = get_dummy_data("fuerte_fantasy_mvps")
        caption = build_caption("fuerte_fantasy_mvps", data, self._config())
        assert data["men"][0]["athlete"] in caption
        assert data["women"][0]["athlete"] in caption

    def test_caption_no_em_dashes(self):
        data = get_dummy_data("fuerte_fantasy_mvps")
        caption = build_caption("fuerte_fantasy_mvps", data, self._config())
        assert "—" not in caption


# ── Template rendering ──────────────────────────────────────────────────────

class TestTemplateRendering:
    def setup_method(self):
        self.data = get_dummy_data("fuerte_fantasy_mvps")
        self.slides = build_slides(self.data)

    def test_cover_renders(self):
        html = render_template("carousel/slide_mvp_cover", self.slides[0])
        assert "<html" in html
        assert "MVP" in html.upper()

    def test_table_renders_athletes_and_points(self):
        html = render_template("carousel/slide_mvp_table", self.slides[1])
        top = self.data["men"][0]
        assert top["athlete"] in html

    def test_table_has_pct_picked_column(self):
        html = render_template("carousel/slide_mvp_table", self.slides[1])
        assert "PICKED" in html.upper()

    def test_all_slides_1080x1350(self):
        for slide in self.slides:
            html = render_template(f"carousel/slide_{slide['type']}", slide)
            assert "1080" in html
            assert "1350" in html
