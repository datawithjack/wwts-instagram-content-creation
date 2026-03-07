"""Tests for API client module."""
from datetime import date
from unittest.mock import patch, MagicMock, call
import pytest

from pipeline.api import fetch_head_to_head, fetch_site_stats, fetch_event


def _mock_event_response():
    return MagicMock(
        status_code=200,
        json=lambda: {
            "id": 42,
            "event_name": "2026 Margaret River Wave Classic",
            "start_date": "2026-01-31",
            "end_date": "2026-02-08",
            "stars": 4,
            "country_code": "AU",
        },
    )


def _mock_h2h_response(**overrides):
    data = {
        "event_id": 42,
        "event_name": "2026 Margaret River Wave Classic",
        "division": "Women",
        "athlete1": {
            "athlete_id": 1,
            "name": "Sarah Kenyon",
            "nationality": "Great Britain",
            "place": 1,
            "profile_image": "https://example.com/photo1.jpg",
            "heat_scores_best": 9.33,
            "heat_scores_avg": 8.85,
            "jumps_best": None,
            "jumps_avg_counting": None,
            "waves_best": 5.00,
            "waves_avg_counting": 4.43,
            "heat_wins": 2,
        },
        "athlete2": {
            "athlete_id": 2,
            "name": "Jane Seman",
            "nationality": "United States",
            "place": 2,
            "profile_image": "https://example.com/photo2.jpg",
            "heat_scores_best": 12.03,
            "heat_scores_avg": 10.65,
            "jumps_best": None,
            "jumps_avg_counting": None,
            "waves_best": 6.30,
            "waves_avg_counting": 5.33,
            "heat_wins": 1,
        },
        "comparison": {},
        "generated_at": "2026-03-07T10:00:00Z",
    }
    data.update(overrides)
    return MagicMock(status_code=200, json=lambda: data)


class TestFetchHeadToHead:
    @patch("pipeline.api.requests.get")
    def test_returns_formatted_data(self, mock_get):
        mock_get.side_effect = [_mock_h2h_response(), _mock_event_response()]

        result = fetch_head_to_head(event_id=42, athlete1_id=1, athlete2_id=2, division="Women")

        assert result["event_name"] == "2026 Margaret River Wave Classic"
        assert result["athlete_1_name"] == "Sarah Kenyon"
        assert result["athlete_2_name"] == "Jane Seman"
        assert result["athlete_1_placement"] == 1
        assert result["athlete_2_placement"] == 2
        assert result["athlete_1_best_heat"] == 9.33
        assert result["athlete_2_best_wave"] == 6.30
        assert result["athlete_1_heat_wins"] == 2

    @patch("pipeline.api.requests.get")
    def test_includes_event_metadata(self, mock_get):
        mock_get.side_effect = [_mock_h2h_response(), _mock_event_response()]

        result = fetch_head_to_head(event_id=42, athlete1_id=1, athlete2_id=2, division="Women")

        assert result["event_country"] == "AU"
        assert result["event_tier"] == 4
        assert result["event_date_start"] == date(2026, 1, 31)
        assert result["event_date_end"] == date(2026, 2, 8)

    @patch("pipeline.api.requests.get")
    def test_includes_jump_stats_when_present(self, mock_get):
        h2h = _mock_h2h_response()
        raw = h2h.json()
        raw["athlete1"]["jumps_best"] = 7.5
        raw["athlete1"]["jumps_avg_counting"] = 6.2
        raw["athlete2"]["jumps_best"] = 8.1
        raw["athlete2"]["jumps_avg_counting"] = 6.8
        h2h.json = lambda: raw

        mock_get.side_effect = [h2h, _mock_event_response()]

        result = fetch_head_to_head(event_id=42, athlete1_id=1, athlete2_id=2, division="Men")

        assert result["athlete_1_best_jump"] == 7.5
        assert result["athlete_2_avg_jump"] == 6.8

    @patch("pipeline.api.requests.get")
    def test_calls_correct_urls(self, mock_get):
        mock_get.side_effect = [_mock_h2h_response(), _mock_event_response()]

        fetch_head_to_head(event_id=42, athlete1_id=1, athlete2_id=2, division="Women")

        assert mock_get.call_count == 2
        # First call: H2H endpoint
        h2h_call = mock_get.call_args_list[0]
        assert "/events/42/head-to-head" in h2h_call[0][0]
        assert h2h_call[1]["params"]["athlete1_id"] == 1
        # Second call: event details
        event_call = mock_get.call_args_list[1]
        assert "/events/42" in event_call[0][0]

    @patch("pipeline.api.requests.get")
    def test_raises_on_http_error(self, mock_get):
        mock_resp = MagicMock(status_code=404)
        mock_resp.raise_for_status.side_effect = Exception("Not Found")
        mock_get.return_value = mock_resp

        with pytest.raises(Exception):
            fetch_head_to_head(event_id=999, athlete1_id=1, athlete2_id=2, division="Women")


class TestFetchSiteStats:
    @patch("pipeline.api.requests.get")
    def test_returns_formatted_data(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "stats": [
                    {"metric": "total_events", "value": "118"},
                    {"metric": "total_athletes", "value": "359"},
                    {"metric": "total_results", "value": "2052"},
                    {"metric": "total_scores", "value": "43515"},
                ],
                "generated_at": "2026-03-07T10:00:00Z",
            },
        )

        result = fetch_site_stats()

        assert result["events_count"] == 118
        assert result["athletes_count"] == 359
        assert result["scores_count"] == 43515

    @patch("pipeline.api.requests.get")
    def test_calls_stats_endpoint(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "stats": [
                    {"metric": "total_events", "value": "58"},
                    {"metric": "total_athletes", "value": "359"},
                    {"metric": "total_scores", "value": "43515"},
                ],
                "generated_at": "2026-03-07T10:00:00Z",
            },
        )

        fetch_site_stats()

        call_args = mock_get.call_args
        assert "/stats" in call_args[0][0]
