"""Tests for the wave-count-per-athlete query builder."""
import pytest

from pipeline.queries import build_wave_count_query


class TestBuildWaveCountQuery:
    def test_returns_sql_string(self):
        sql, params = build_wave_count_query(sex="Men", event_id=490099)
        assert isinstance(sql, str)
        assert "SELECT" in sql

    def test_counts_waves(self):
        sql, _ = build_wave_count_query(sex="Men", event_id=490099)
        sql_upper = sql.upper()
        assert "COUNT(*)" in sql_upper
        assert "WAVE_COUNT" in sql_upper

    def test_counts_distinct_heats(self):
        sql, _ = build_wave_count_query(sex="Men", event_id=490099)
        sql_upper = sql.upper()
        assert "COUNT(DISTINCT" in sql_upper
        assert "HEATS" in sql_upper

    def test_filters_by_wave_type(self):
        sql, _ = build_wave_count_query(sex="Men", event_id=490099)
        assert "s.type = 'Wave'" in sql

    def test_filters_by_event_id(self):
        sql, params = build_wave_count_query(sex="Men", event_id=490099)
        assert 490099 in params

    def test_filters_by_sex(self):
        sql, params = build_wave_count_query(sex="Women", event_id=490099)
        assert "Women" in params

    def test_param_order_is_event_then_sex(self):
        sql, params = build_wave_count_query(sex="Men", event_id=42)
        assert params == (42, "Men")

    def test_groups_by_athlete(self):
        sql, _ = build_wave_count_query(sex="Men", event_id=490099)
        assert "GROUP BY" in sql

    def test_orders_by_count_desc(self):
        sql, _ = build_wave_count_query(sex="Men", event_id=490099)
        assert "ORDER BY" in sql
        assert "DESC" in sql

    def test_joins_athlete_table(self):
        sql, _ = build_wave_count_query(sex="Men", event_id=490099)
        assert "ATHLETES" in sql

    def test_selects_required_columns(self):
        sql, _ = build_wave_count_query(sex="Men", event_id=490099)
        sql_lower = sql.lower()
        assert "primary_name" in sql_lower
        assert "nationality" in sql_lower
        assert "liveheats_image_url" in sql_lower

    def test_includes_non_counting_by_default(self):
        # "Most waves caught" = all waves scored, counting or not.
        sql, _ = build_wave_count_query(sex="Men", event_id=490099)
        assert "s.counting = 1" not in sql

    def test_counting_only_adds_counting_filter(self):
        sql, _ = build_wave_count_query(
            sex="Men", event_id=490099, include_non_counting=False
        )
        assert "s.counting = 1" in sql
