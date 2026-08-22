"""Tests for the freestyle top 10 query builder."""
import pytest

from pipeline.queries import build_freestyle_top10_query


class TestBuildFreestyleTop10Query:
    def test_returns_sql_string(self):
        sql, params = build_freestyle_top10_query()
        assert isinstance(sql, str)
        assert "SELECT" in sql

    def test_reads_the_freestyle_scores_table(self):
        # Freestyle scores live in their own table, not PWA_IWT_HEAT_SCORES.
        sql, _ = build_freestyle_top10_query()
        assert "PWA_IWT_FREESTYLE_HEAT_SCORES" in sql
        assert "PWA_IWT_HEAT_SCORES" not in sql.replace(
            "PWA_IWT_FREESTYLE_HEAT_SCORES", ""
        )

    def test_joins_move_dictionary_on_slug(self):
        # MOVE_DICTIONARY.slug matches the scores table's `abbreviation`
        # column, NOT `move_name`.
        sql, _ = build_freestyle_top10_query()
        assert "MOVE_DICTIONARY" in sql
        assert "slug" in sql
        assert "abbreviation" in sql

    def test_selects_difficulty(self):
        sql, _ = build_freestyle_top10_query()
        assert "difficulty" in sql

    def test_filters_by_sex(self):
        sql, params = build_freestyle_top10_query(sex="Men")
        assert "Men" in params

    def test_filters_by_event_id(self):
        sql, params = build_freestyle_top10_query(event_id=389)
        assert 389 in params

    def test_filters_by_year(self):
        sql, params = build_freestyle_top10_query(year=2026)
        assert 2026 in params

    def test_excludes_bails(self):
        # score = 0 means attempted and not landed. A highest-scoring list
        # must never show one.
        sql, _ = build_freestyle_top10_query()
        assert "f.score > 0" in sql

    def test_excludes_crash(self):
        # `Crash` (slug CRSH) is a dictionary entry at difficulty 0.00.
        _, params = build_freestyle_top10_query()
        assert "CRSH" in params

    def test_counting_only_is_opt_in(self):
        # Matches the wave/jump default: non-counting scores are included
        # unless the caller asks otherwise.
        sql, _ = build_freestyle_top10_query()
        assert "f.counting = 1" not in sql

        sql, _ = build_freestyle_top10_query(counting_only=True)
        assert "f.counting = 1" in sql

    def test_placeholders_included_by_default(self):
        # Placeholder slugs are real new tricks that were landed, just not
        # named yet. They belong in a highest-scoring list.
        # It is still SELECTed as a column; what must be absent is the filter.
        sql, _ = build_freestyle_top10_query()
        assert "is_placeholder, 0) = 0" not in sql

    def test_placeholders_can_be_excluded(self):
        sql, _ = build_freestyle_top10_query(exclude_placeholders=True)
        assert "is_placeholder, 0) = 0" in sql

    def test_limits_to_10_by_default(self):
        sql, _ = build_freestyle_top10_query()
        assert "LIMIT 10" in sql

    def test_limit_is_configurable(self):
        sql, _ = build_freestyle_top10_query(limit=12)
        assert "LIMIT 12" in sql

    def test_orders_by_score_desc(self):
        sql, _ = build_freestyle_top10_query()
        assert "ORDER BY" in sql
        assert "DESC" in sql

    def test_selects_required_columns(self):
        sql, _ = build_freestyle_top10_query()
        for col in ("athlete", "country", "score", "move", "event", "round", "heat_id"):
            assert col in sql
