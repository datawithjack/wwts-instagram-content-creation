"""Tests for the freestyle path through the finals recap.

Two halves. The fetch, which has to derive everything from the heats endpoint
because the aggregate endpoints answer a freestyle question with wave numbers;
and the builder, which swaps four wave-and-jump stats for the two a move has
and leaves the rest of the carousel alone.
"""
from unittest.mock import MagicMock, patch

import pytest

from pipeline.api import (
    _freestyle_aggregates,
    _freestyle_final,
    _freestyle_final_scores,
    fetch_freestyle_recap,
)
from pipeline.finals_recap import build_slides


def _move(score, move_type="Shifty", counting=True):
    return {"score": score, "type": "Freestyle", "move_type": move_type,
            "counting": counting, "tack": "port"}


def _entry(round_name, total, place, scores=None):
    return {"round": round_name, "heat": "1a", "place": place, "total": total,
            "advanced": place == 1, "scores": scores or []}


# ---------------------------------------------------------------- the fetch

def test_aggregates_read_bests_over_all_moves_and_averages_over_counting():
    entries = [
        _entry("Round 1", 40.0, 1, [_move(9.5), _move(5.0), _move(9.9, counting=False)]),
        _entry("Round 2", 30.0, 2, [_move(6.5), _move(4.5)]),
    ]

    agg = _freestyle_aggregates(entries)

    assert agg["best_heat"] == 40.0
    assert agg["avg_heat"] == 35.0
    assert agg["heat_wins"] == 1
    # The non-counting 9.9 is still the rider's best move of the event.
    assert agg["best_move"] == 9.9
    # ...but it stays out of the average, which counts only counting moves:
    # (9.5 + 5.0 + 6.5 + 4.5) / 4, not (9.9 + ...) / 5.
    assert agg["avg_move"] == 6.38


def test_aggregates_of_a_rider_with_no_heats_are_empty_not_zero():
    agg = _freestyle_aggregates([])

    assert agg["best_heat"] is None
    assert agg["avg_heat"] is None
    assert agg["best_move"] is None
    assert agg["avg_move"] is None
    assert agg["heat_wins"] == 0


def test_final_is_the_heat_holding_the_top_two_not_the_last_one():
    """Third against fourth runs in the same round as the final itself.

    At Sylt 2025 both 16a and 17a sit in round "Final", so "the last heat"
    is a coin toss between the real final and the small final.
    """
    raw = {"rounds": [{
        "round_name": "Final", "round_order": 4,
        "heats": [
            {"heat_number": "16a", "heat_order": 16,
             "athletes": [{"athlete_id": 74}, {"athlete_id": 890}]},
            {"heat_number": "17a", "heat_order": 17,
             "athletes": [{"athlete_id": 75}, {"athlete_id": 892}]},
        ],
    }]}

    round_, heat = _freestyle_final(raw, [75, 892])

    assert heat["heat_number"] == "17a"
    assert round_["round_order"] == 4


def test_final_picks_the_small_final_when_it_ran_second():
    """Heat order must not decide it: the top two are what identify the final."""
    raw = {"rounds": [{
        "round_name": "Final", "round_order": 4,
        "heats": [
            {"heat_number": "17a", "heat_order": 16,
             "athletes": [{"athlete_id": 75}, {"athlete_id": 892}]},
            {"heat_number": "16a", "heat_order": 17,
             "athletes": [{"athlete_id": 74}, {"athlete_id": 890}]},
        ],
    }]}

    _, heat = _freestyle_final(raw, [75, 892])

    assert heat["heat_number"] == "17a"


def test_final_scores_split_the_best_move_out_with_its_name():
    scores = _freestyle_final_scores({
        "result_total": 44.2,
        "scores": [_move(7.9, "Shifty Shaka"), _move(7.5, "Culo"), {"score": None}],
    })

    assert scores["final_total"] == 44.2
    assert scores["final_moves"] == [7.9, 7.5]
    assert scores["final_best_move"] == "Shifty Shaka"


def test_final_scores_are_empty_for_a_rider_who_did_not_sail_the_final():
    """Third and fourth sailed each other, so they carry no final score.

    That absence is what tells the carousel the final was man on man.
    """
    scores = _freestyle_final_scores(None)

    assert scores["final_total"] is None
    assert scores["final_moves"] == []
    assert scores["final_best_move"] == ""


def _sylt_heats():
    """A four-round freestyle ladder, cut down to the top four."""
    def athlete(aid, name, total, place, best):
        return {"athlete_id": aid, "athlete_name": name, "place": place,
                "result_total": total, "advanced": place == 1,
                "scores": [_move(best, "Shifty Shaka"), _move(5.0)]}

    return {"rounds": [
        {"round_name": "Round 4", "round_order": 3, "heats": [
            {"heat_number": "14a", "heat_order": 14, "athletes": [
                athlete(75, "Lennart Neubauer", 48.2, 1, 9.5),
                athlete(74, "Jacopo Testa", 40.7, 2, 9.1)]},
            {"heat_number": "15a", "heat_order": 15, "athletes": [
                athlete(892, "Yentel Caers", 43.5, 1, 8.4),
                athlete(890, "Van Broeckhoven", 35.5, 2, 7.9)]},
        ]},
        {"round_name": "Final", "round_order": 4, "heats": [
            {"heat_number": "16a", "heat_order": 16, "athletes": [
                athlete(74, "Jacopo Testa", 36.0, 1, 8.0),
                athlete(890, "Van Broeckhoven", 35.5, 2, 7.6)]},
            {"heat_number": "17a", "heat_order": 17, "athletes": [
                athlete(75, "Lennart Neubauer", 44.2, 1, 7.9),
                athlete(892, "Yentel Caers", 42.0, 2, 7.7)]},
        ]},
    ]}


def _sylt_athletes():
    return {"athletes": [
        {"athlete_id": 75, "name": "Lennart Neubauer", "country": "Greece",
         "sail_number": "GRE-734", "profile_image": "", "overall_position": 1},
        {"athlete_id": 892, "name": "Yentel Caers", "country": "Unknown",
         "sail_number": "B-16", "profile_image": "", "overall_position": 2},
        {"athlete_id": 74, "name": "Jacopo Testa", "country": "Italy",
         "sail_number": "ITA-261", "profile_image": "", "overall_position": 3},
        {"athlete_id": 890, "name": "Van Broeckhoven", "country": "Unknown",
         "sail_number": "B-72", "profile_image": "", "overall_position": 4},
        # An entrant who sailed the wave but not the freestyle. The athletes
        # endpoint hands out a position per discipline, so at a Grand Slam
        # somebody else is also holding a "1".
        {"athlete_id": 49, "name": "Philip Koster", "country": "Germany",
         "sail_number": "G-901", "profile_image": "", "overall_position": 1},
    ]}


def _mock_get(heats=None, athletes=None):
    def _get(url, **kwargs):
        payload = (heats if "/heats" in url else athletes)
        return MagicMock(status_code=200, raise_for_status=lambda: None,
                         json=lambda: payload)
    return _get


def test_fetch_builds_the_top_four_with_their_aggregates():
    with patch("pipeline.api.requests.get",
               side_effect=_mock_get(_sylt_heats(), _sylt_athletes())):
        result = fetch_freestyle_recap(16, "Men")

    assert result["round_order"] == 4
    riders = result["riders"]
    assert [r["place"] for r in riders] == [1, 2, 3, 4]
    assert [r["name"] for r in riders] == [
        "Lennart Neubauer", "Yentel Caers", "Jacopo Testa", "Van Broeckhoven"]

    winner = riders[0]
    assert winner["best_heat"] == 48.2
    assert winner["avg_heat"] == 46.2
    assert winner["heat_wins"] == 2
    assert winner["best_move"] == 9.5
    assert winner["sail_number"] == "GRE-734"
    assert len(winner["history"]) == 2


def test_fetch_leaves_third_and_fourth_without_a_final_score():
    with patch("pipeline.api.requests.get",
               side_effect=_mock_get(_sylt_heats(), _sylt_athletes())):
        riders = fetch_freestyle_recap(16, "Men")["riders"]

    assert riders[0]["final_total"] == 44.2
    assert riders[1]["final_total"] == 42.0
    assert riders[2]["final_total"] is None
    assert riders[3]["final_total"] is None


def test_fetch_drops_an_entrant_who_sailed_no_freestyle_heat():
    """A wave rider's position 1 must not displace the freestyle winner."""
    with patch("pipeline.api.requests.get",
               side_effect=_mock_get(_sylt_heats(), _sylt_athletes())):
        riders = fetch_freestyle_recap(16, "Men")["riders"]

    assert 49 not in [r["athlete_id"] for r in riders]
    assert riders[0]["athlete_id"] == 75


def test_fetch_raises_where_the_event_ran_no_freestyle():
    with patch("pipeline.api.requests.get",
               side_effect=_mock_get({"rounds": []}, {"athletes": []})):
        with pytest.raises(ValueError, match="No freestyle heats"):
            fetch_freestyle_recap(16, "Men")


# --------------------------------------------------------------- the slides

def _rider(athlete_id, name, place, **extra):
    rider = {
        "athlete_id": athlete_id,
        "name": name,
        "nationality": "Greece",
        "sail_number": "GRE-734",
        "photo_url": "",
        "place": place,
        "final_total": 44.2 if place <= 2 else None,
        "final_moves": [7.9, 7.5] if place <= 2 else [],
        "final_best_move": "Shifty Shaka" if place <= 2 else "",
        "best_heat": 48.2,
        "avg_heat": 45.0,
        "heat_wins": 4,
        "best_move": 9.5,
        "avg_move": 7.52,
        "history": [_entry("Final", 44.2, 1, [_move(9.5, "Shifty Shaka")])],
    }
    rider.update(extra)
    return rider


def _data(**overrides):
    data = {
        "riders": [
            _rider(75, "Lennart Neubauer", 1),
            _rider(892, "Yentel Caers", 2),
            _rider(74, "Jacopo Testa", 3),
            _rider(890, "Van Broeckhoven", 4),
        ],
        "division": "Men",
        "discipline": "Freestyle",
        "event_meta": {"event_name": "Sylt, Germany Grand Slam", "year": 2025,
                       "country": "GER", "stars": 7, "event_id": 16},
    }
    data.update(overrides)
    return data


def _labels(slide):
    return [s["label"] for s in slide["stats"]]


def test_rider_cards_carry_the_move_stats_not_the_wave_ones():
    slides = build_slides(_data())
    card = next(s for s in slides if s["type"] == "recap_rider")

    assert _labels(card) == ["BEST HEAT", "AVG HEAT", "HEATS WON",
                             "BEST MOVE", "AVG MOVE"]


def test_best_move_cell_names_the_move():
    slides = build_slides(_data())
    card = next(s for s in slides if s["type"] == "recap_rider")

    best_move = next(s for s in card["stats"] if s["label"] == "BEST MOVE")
    assert best_move["note"] == "Shifty Shaka"


def test_the_score_row_breaks_at_best_move():
    slides = build_slides(_data())
    card = next(s for s in slides if s["type"] == "recap_rider")

    breaks = [s["label"] for s in card["stats"] if s["row_break"]]
    assert breaks == ["BEST MOVE"]


def test_counting_note_is_about_moves():
    slides = build_slides(_data())
    card = next(s for s in slides if s["type"] == "recap_rider")

    assert card["counting_note"] == "Move averages use counting scores only"


def test_the_cover_names_the_discipline():
    """A Grand Slam runs three of them, and a rider can place in more than one."""
    slides = build_slides(_data())

    assert slides[0]["title_lines"] == ["MEN'S FREESTYLE", "TOP 4"]


def test_the_event_label_names_the_discipline_too():
    slides = build_slides(_data())
    card = next(s for s in slides if s["type"] == "recap_rider")

    assert "FREESTYLE" in card["source_note"]


def test_the_summary_says_only_the_top_two_sailed_the_final():
    slides = build_slides(_data())
    compare = next(s for s in slides if s["type"] == "recap_compare")

    final_rows = [r for r in compare["rows"] if r["group"].startswith("IN THE FINAL")]
    assert [r["label"] for r in final_rows] == ["FINAL SCORE", "BEST MOVE"]
    assert final_rows[0]["group"] == "IN THE FINAL (1ST V 2ND)"
    # Third and fourth show a dash, which is why the group header names the heat.
    assert [c["value"] for c in final_rows[0]["cells"]][2:] == ["-", "-"]


def test_the_summary_event_group_carries_the_move_stats():
    slides = build_slides(_data())
    compare = next(s for s in slides if s["type"] == "recap_compare")

    event_rows = [r["label"] for r in compare["rows"] if r["group"] == "AT THIS EVENT"]
    assert event_rows == ["BEST HEAT", "AVG HEAT", "HEATS WON",
                          "BEST MOVE", "AVG MOVE"]


def test_a_wave_recap_is_untouched_by_the_freestyle_path():
    """The discipline key is absent on every wave post already in the backlog."""
    riders = [
        _rider(97, "Marc Pare Rico", 1, best_wave=8.5, avg_wave=6.0,
               best_jump=9.5, avg_jump=7.0, final_waves=[8.0], final_jumps=[9.0]),
        _rider(49, "Philip Koster", 2, best_wave=8.0, avg_wave=5.5,
               best_jump=9.0, avg_jump=6.5, final_waves=[7.5], final_jumps=[8.5]),
    ]
    slides = build_slides({**_data(riders=riders), "discipline": "Wave"})
    card = next(s for s in slides if s["type"] == "recap_rider")

    assert _labels(card) == ["BEST HEAT", "AVG HEAT", "HEATS WON", "BEST WAVE",
                            "AVG WAVE", "BEST JUMP", "AVG JUMP"]
    assert slides[0]["title_lines"] == ["MEN'S FINALISTS"]
