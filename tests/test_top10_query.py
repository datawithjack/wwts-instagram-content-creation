"""Tests for top 10 query builder."""
import pytest

from pipeline.queries import build_top10_query


class TestBuildTop10Query:
    def test_returns_sql_string(self):
        sql, params = build_top10_query(score_type="Wave")
        assert isinstance(sql, str)
        assert "SELECT" in sql

    def test_filters_by_wave_type(self):
        sql, params = build_top10_query(score_type="Wave")
        assert "Wave" in params

    def test_filters_by_jump_type(self):
        sql, params = build_top10_query(score_type="Jump")
        # Jump queries use "type <> Wave" to include all trick types
        assert "Wave" in params
        assert "<>" in sql or "!=" in sql

    def test_filters_by_sex(self):
        sql, params = build_top10_query(score_type="Wave", sex="Men")
        assert "Men" in params

    def test_filters_by_year(self):
        sql, params = build_top10_query(score_type="Wave", year=2025)
        assert 2025 in params

    def test_filters_by_event_id(self):
        sql, params = build_top10_query(score_type="Wave", event_id=42)
        assert 42 in params

    def test_limits_to_10(self):
        sql, _ = build_top10_query(score_type="Wave")
        assert "LIMIT 10" in sql

    def test_orders_by_score_desc(self):
        sql, _ = build_top10_query(score_type="Wave")
        assert "ORDER BY" in sql
        assert "DESC" in sql

    def test_selects_required_columns(self):
        sql, _ = build_top10_query(score_type="Wave")
        sql_upper = sql.upper()
        assert "PRIMARY_NAME" in sql_upper or "ATHLETE_NAME" in sql_upper
        assert "SCORE" in sql_upper
        assert "EVENT_NAME" in sql_upper or "PWA_EVENT_NAME" in sql_upper

    def test_year_and_event_combined(self):
        sql, params = build_top10_query(score_type="Wave", year=2025, event_id=42)
        assert 2025 in params
        assert 42 in params

    def test_all_time_no_filters(self):
        sql, params = build_top10_query(score_type="Wave")
        # Only score_type filter, no year or event
        assert len(params) == 1

    def test_joins_athlete_table(self):
        sql, _ = build_top10_query(score_type="Wave")
        assert "ATHLETES" in sql or "athletes" in sql

    def test_joins_event_table(self):
        sql, _ = build_top10_query(score_type="Wave")
        assert "PWA_IWT_EVENTS" in sql or "pwa_iwt_events" in sql

    def test_includes_round_name(self):
        sql, _ = build_top10_query(score_type="Wave")
        assert "round_name" in sql.lower() or "round" in sql.lower()

    def test_filters_by_rounds(self):
        sql, params = build_top10_query(score_type="Wave", rounds=["Final", "R5 B-Final"])
        assert "Final" in params
        assert "R5 B-Final" in params
        assert "round_name IN" in sql or "hp.round_name IN" in sql

    def test_rounds_with_single_value(self):
        sql, params = build_top10_query(score_type="Wave", rounds=["Final"])
        assert "Final" in params

    def test_no_rounds_filter_by_default(self):
        sql, params = build_top10_query(score_type="Wave")
        assert "round_name IN" not in sql
