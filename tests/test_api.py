"""Tests for API client module."""
from datetime import date
from unittest.mock import patch, MagicMock, call
import pytest

from pipeline.api import (
    fetch_head_to_head,
    fetch_site_stats,
    fetch_event,
    fetch_athlete_event_stats,
    fetch_event_top_scores,
)


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
                    {"metric": "total events", "value": "118"},
                    {"metric": "total athletes", "value": "359"},
                    {"metric": "total_results", "value": "2052"},
                    {"metric": "total scores", "value": "43515"},
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
                    {"metric": "total events", "value": "58"},
                    {"metric": "total athletes", "value": "359"},
                    {"metric": "total scores", "value": "43515"},
                ],
                "generated_at": "2026-03-07T10:00:00Z",
            },
        )

        fetch_site_stats()

        call_args = mock_get.call_args
        assert "/stats" in call_args[0][0]


def _mock_athlete_stats_response():
    return MagicMock(
        status_code=200,
        json=lambda: {
            "event_id": 42,
            "event_name": "2026 Margaret River Wave Classic",
            "athlete": {
                "id": 10,
                "name": "Marc Pare Rico",
                "country": "Spain",
                "country_code": "ES",
                "profile_image": "https://example.com/marc.jpg",
                "sail_number": "E-73",
                "overall_position": 1,
                "sponsors": ["Severne", "Starboard"],
            },
            "summary": {
                "best_heat": {
                    "score": 16.33,
                    "round": "Final",
                },
                "best_wave": 8.83,
                "best_jump": 7.50,
            },
            "wave_scores": [
                {"score": 8.83, "round": "Final"},
                {"score": 7.60, "round": "Semi"},
                {"score": 7.20, "round": "Quarter"},
                {"score": 6.90, "round": "Semi"},
                {"score": 6.50, "round": "Round 3"},
                {"score": 6.10, "round": "Round 2"},
            ],
            "heat_scores": [
                {"score": 16.33, "round": "Final"},
                {"score": 14.10, "round": "Semi"},
            ],
        },
    )


def _mock_athlete_stats_no_jumps():
    resp = _mock_athlete_stats_response()
    raw = resp.json()
    raw["summary"]["best_jump"] = None
    resp.json = lambda: raw
    return resp


class TestFetchAthleteEventStats:
    @patch("pipeline.api.requests.get")
    def test_returns_flattened_data(self, mock_get):
        mock_get.side_effect = [_mock_athlete_stats_response(), _mock_event_response()]

        result = fetch_athlete_event_stats(event_id=42, athlete_id=10, division="Men")

        assert result["athlete_name"] == "Marc Pare Rico"
        assert result["athlete_country"] == "ES"
        assert result["athlete_photo_url"] == "https://example.com/marc.jpg"
        assert result["athlete_sail_number"] == "E-73"
        assert result["placement"] == 1
        assert result["best_heat"] == 16.33
        assert result["best_heat_round"] == "Final"
        assert result["best_wave"] == 8.83
        assert result["best_jump"] == 7.50

    @patch("pipeline.api.requests.get")
    def test_includes_event_metadata(self, mock_get):
        mock_get.side_effect = [_mock_athlete_stats_response(), _mock_event_response()]

        result = fetch_athlete_event_stats(event_id=42, athlete_id=10, division="Men")

        assert result["event_name"] == "2026 Margaret River Wave Classic"
        assert result["event_country"] == "AU"
        assert result["event_tier"] == 4
        assert result["event_date_start"] == date(2026, 1, 31)
        assert result["event_date_end"] == date(2026, 2, 8)

    @patch("pipeline.api.requests.get")
    def test_top_waves_limited_to_5(self, mock_get):
        mock_get.side_effect = [_mock_athlete_stats_response(), _mock_event_response()]

        result = fetch_athlete_event_stats(event_id=42, athlete_id=10, division="Men")

        assert len(result["top_waves"]) == 5
        assert result["top_waves"][0]["rank"] == 1
        assert result["top_waves"][0]["score"] == 8.83
        assert result["top_waves"][0]["round"] == "Final"

    @patch("pipeline.api.requests.get")
    def test_avg_wave_computed(self, mock_get):
        mock_get.side_effect = [_mock_athlete_stats_response(), _mock_event_response()]

        result = fetch_athlete_event_stats(event_id=42, athlete_id=10, division="Men")

        # Average of all wave scores
        assert "avg_wave" in result
        assert isinstance(result["avg_wave"], float)

    @patch("pipeline.api.requests.get")
    def test_no_jumps_returns_none(self, mock_get):
        mock_get.side_effect = [_mock_athlete_stats_no_jumps(), _mock_event_response()]

        result = fetch_athlete_event_stats(event_id=42, athlete_id=10, division="Men")

        assert result["best_jump"] is None

    @patch("pipeline.api.requests.get")
    def test_calls_correct_urls(self, mock_get):
        mock_get.side_effect = [_mock_athlete_stats_response(), _mock_event_response()]

        fetch_athlete_event_stats(event_id=42, athlete_id=10, division="Men")

        assert mock_get.call_count == 2
        stats_call = mock_get.call_args_list[0]
        assert "/events/42/athletes/10/stats" in stats_call[0][0]
        assert stats_call[1]["params"]["sex"] == "Men"


def _mock_event_stats_response():
    return MagicMock(
        status_code=200,
        json=lambda: {
            "event_name": "2026 Gran Canaria Wind & Waves Festival",
            "top_wave_scores": [
                {"athlete_id": 1, "athlete_name": "Marc Pare Rico", "score": 8.83, "round_name": "Final", "heat_number": 1},
                {"athlete_id": 2, "athlete_name": "Takara Ishii", "score": 8.50, "round_name": "Semi Final", "heat_number": 3},
            ],
            "top_jump_scores": [
                {"athlete_id": 1, "athlete_name": "Marc Pare Rico", "score": 9.10, "round_name": "Final", "heat_number": 1, "move_type": "F"},
                {"athlete_id": 3, "athlete_name": "Antoine Martin", "score": 8.90, "round_name": "Semi Final", "heat_number": 2, "move_type": "P"},
            ],
        },
    )


def _mock_event_athletes_response():
    return MagicMock(
        status_code=200,
        json=lambda: {
            "athletes": [
                {"athlete_id": 1, "country": "Spain"},
                {"athlete_id": 2, "country": "Japan"},
                {"athlete_id": 3, "country": "Guadeloupe"},
            ]
        },
    )


class TestFetchEventTopScores:
    @patch("pipeline.api.requests.get")
    def test_returns_event_header_fields(self, mock_get):
        mock_get.side_effect = [
            _mock_event_stats_response(),
            _mock_event_athletes_response(),
            _mock_event_response(),
        ]

        result = fetch_event_top_scores(event_id=42, score_type="Wave", sex="Men")

        assert result["is_per_event"] is True
        assert result["event_name"] == "Gran Canaria Wind & Waves Festival"
        assert result["event_country"] == "AU"
        assert result["event_tier"] == 4
        assert result["event_date_start"] == date(2026, 1, 31)
        assert result["event_date_end"] == date(2026, 2, 8)

    @patch("pipeline.api.requests.get")
    def test_entries_include_heat(self, mock_get):
        mock_get.side_effect = [
            _mock_event_stats_response(),
            _mock_event_athletes_response(),
            _mock_event_response(),
        ]

        result = fetch_event_top_scores(event_id=42, score_type="Wave", sex="Men")

        assert "heat" in result["entries"][0]
        assert result["entries"][0]["heat"] == 1

    @patch("pipeline.api.requests.get")
    def test_wave_entries_formatted(self, mock_get):
        mock_get.side_effect = [
            _mock_event_stats_response(),
            _mock_event_athletes_response(),
            _mock_event_response(),
        ]

        result = fetch_event_top_scores(event_id=42, score_type="Wave", sex="Men")

        assert len(result["entries"]) == 2
        assert result["entries"][0]["athlete"] == "Marc Pare Rico"
        assert result["entries"][0]["score"] == 8.83
        assert result["entries"][0]["round"] == "Final"
        assert result["show_trick_type"] is False

    @patch("pipeline.api.requests.get")
    def test_jump_entries_include_trick_type(self, mock_get):
        mock_get.side_effect = [
            _mock_event_stats_response(),
            _mock_event_athletes_response(),
            _mock_event_response(),
        ]

        result = fetch_event_top_scores(event_id=42, score_type="Jump", sex="Men")

        assert result["show_trick_type"] is True
        assert result["entries"][0]["trick_type"] == "F"
