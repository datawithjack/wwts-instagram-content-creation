"""Tests for the finals recap carousel builder (cover, 4th->1st, comparison)."""
import pytest

from pipeline.finals_recap import build_slides


def _rider(athlete_id, name, place, final_total=20.0, **extra):
    r = {
        "athlete_id": athlete_id,
        "name": name,
        "nationality": "Spain",
        "photo_url": f"https://example.com/{athlete_id}.jpg",
        "place": place,
        "final_total": final_total,
        "final_waves": [8.0, 7.5],
        "final_jumps": [9.0, 8.5],
        "best_heat": 30.0,
        "avg_wave": 6.0,
        "avg_jump": 7.0,
        "best_wave": 8.5,
        "best_jump": 9.5,
        "heat_wins": 3,
        "avg_heat": 24.0,
    }
    r.update(extra)
    return r


def _riders():
    return [
        _rider(97, "Marc Pare Rico", 1, final_total=36.63, best_heat=36.63),
        _rider(49, "Philip Koster", 2, final_total=35.00, best_heat=35.00),
        _rider(48, "Marino Gil Gherardi", 3, final_total=28.84, best_heat=28.84),
        _rider(75, "Lennart Neubauer", 4, final_total=27.87, best_heat=27.87),
    ]


def _data(riders=None, division="Men", event_meta=None):
    return {
        "riders": _riders() if riders is None else riders,
        "division": division,
        "event_meta": event_meta
        if event_meta is not None
        else {
            "event_name": "Tenerife Grand Slam",
            "year": 2026,
            "country": "ESP",
            "stars": 5,
            "event_id": 124,
        },
    }


def _rider_slides(slides):
    return [s for s in slides if s["type"] == "recap_rider"]


class TestSlideStructure:
    def test_builds_six_slides_in_order(self):
        slides = build_slides(_data())
        assert [s["type"] for s in slides] == [
            "finals_cover",
            "recap_rider",
            "recap_rider",
            "recap_rider",
            "recap_rider",
            "recap_compare",
        ]

    def test_riders_run_fourth_to_first(self):
        slides = _rider_slides(build_slides(_data()))
        assert [s["place"] for s in slides] == [4, 3, 2, 1]

    def test_input_order_does_not_matter(self):
        shuffled = [_riders()[2], _riders()[0], _riders()[3], _riders()[1]]
        slides = _rider_slides(build_slides(_data(riders=shuffled)))
        assert [s["place"] for s in slides] == [4, 3, 2, 1]

    def test_place_labels_are_ordinals(self):
        slides = _rider_slides(build_slides(_data()))
        assert [s["place_label"] for s in slides] == ["4TH", "3RD", "2ND", "1ST"]

    def test_only_the_winner_is_flagged(self):
        slides = _rider_slides(build_slides(_data()))
        assert [s["is_winner"] for s in slides] == [False, False, False, True]

    def test_slide_numbering_covers_whole_carousel(self):
        slides = build_slides(_data())
        assert [s["slide_number"] for s in slides] == [1, 2, 3, 4, 5, 6]
        assert all(s["total_slides"] == 6 for s in slides)

    def test_cover_names_the_division(self):
        slides = build_slides(_data(division="Women"))
        assert "WOMEN'S" in " ".join(slides[0]["title_lines"])

    def test_event_meta_reaches_every_slide(self):
        slides = build_slides(_data())
        assert all(s["event_name"] == "Tenerife Grand Slam" for s in slides)
        assert all(s["event_year"] == 2026 for s in slides)


class TestRiderSlide:
    def test_carries_identity(self):
        winner = _rider_slides(build_slides(_data()))[-1]
        assert winner["athlete_id"] == 97
        assert winner["name"] == "Marc Pare Rico"
        assert winner["first_name"] == "MARC"
        assert winner["last_name"] == "PARE RICO"

    def test_country_is_iso(self):
        winner = _rider_slides(build_slides(_data()))[-1]
        assert winner["country"] == "es"

    def test_expanded_stats_are_present(self):
        winner = _rider_slides(build_slides(_data()))[-1]
        labels = [s["label"] for s in winner["stats"]]
        for expected in ("BEST HEAT", "BEST WAVE", "BEST JUMP", "AVG WAVE", "AVG JUMP"):
            assert expected in labels

    def test_final_score_is_the_hero(self):
        winner = _rider_slides(build_slides(_data()))[-1]
        assert winner["hero"]["label"] == "FINAL SCORE"
        assert winner["hero"]["value"] == "36.63"

    def test_missing_stat_renders_a_dash_not_a_crash(self):
        riders = _riders()
        riders[0]["best_jump"] = None
        riders[0]["avg_jump"] = None
        slides = _rider_slides(build_slides(_data(riders=riders)))
        winner = slides[-1]
        values = {s["label"]: s["value"] for s in winner["stats"]}
        assert values["BEST JUMP"] == "-"

    def test_missing_final_total_renders_a_dash(self):
        riders = _riders()
        riders[0]["final_total"] = None
        winner = _rider_slides(build_slides(_data(riders=riders)))[-1]
        assert winner["hero"]["value"] == "-"

    def test_no_qualifying_route_on_a_recap(self):
        """The preview shows how a rider reached the final because it has not
        been sailed yet. On a recap the ladder is history and the result is
        the story, so the route line is dropped."""
        riders = _riders()
        riders[0]["route_round"] = "Semis R5"
        riders[0]["route_place"] = 1
        winner = _rider_slides(build_slides(_data(riders=riders)))[-1]
        assert "route" not in winner


class TestPhotoFallback:
    def test_action_photo_drives_the_full_bleed_layout(self):
        riders = _riders()
        riders[0]["action_url"] = "file:///photos/events/124/97.jpg"
        winner = _rider_slides(build_slides(_data(riders=riders)))[-1]
        assert winner["photo_mode"] == "action"
        assert winner["photo_url"] == "file:///photos/events/124/97.jpg"

    def test_without_an_action_shot_it_falls_back_to_a_framed_portrait(self):
        winner = _rider_slides(build_slides(_data()))[-1]
        assert winner["photo_mode"] == "portrait"

    def test_a_face_crop_is_never_stretched_full_bleed(self):
        """The whole point of the fallback: no action shot must not mean a
        tight headshot blown up to 1080x1350."""
        for slide in _rider_slides(build_slides(_data())):
            if slide["photo_mode"] == "action":
                assert slide["photo_url"]

    def test_no_photo_at_all_still_builds(self):
        riders = _riders()
        for r in riders:
            r["photo_url"] = ""
        slides = _rider_slides(build_slides(_data(riders=riders)))
        assert len(slides) == 4
        assert all(s["photo_mode"] == "portrait" for s in slides)


class TestComparisonCard:
    def test_has_one_row_per_stat(self):
        compare = build_slides(_data())[-1]
        labels = [row["label"] for row in compare["rows"]]
        assert "FINAL SCORE" in labels
        assert "BEST WAVE" in labels
        assert "BEST JUMP" in labels

    def test_every_row_covers_all_four_riders(self):
        compare = build_slides(_data())[-1]
        for row in compare["rows"]:
            assert len(row["cells"]) == 4

    def test_riders_are_listed_first_to_fourth(self):
        compare = build_slides(_data())[-1]
        assert [r["place"] for r in compare["riders"]] == [1, 2, 3, 4]

    def test_leader_is_marked_per_row(self):
        compare = build_slides(_data())[-1]
        final_row = next(r for r in compare["rows"] if r["label"] == "FINAL SCORE")
        leaders = [v["is_leader"] for v in final_row["cells"]]
        assert leaders == [True, False, False, False]

    def test_ties_mark_every_tied_rider(self):
        riders = _riders()
        riders[0]["final_total"] = 30.0
        riders[1]["final_total"] = 30.0
        compare = build_slides(_data(riders=riders))[-1]
        final_row = next(r for r in compare["rows"] if r["label"] == "FINAL SCORE")
        assert sum(1 for v in final_row["cells"] if v["is_leader"]) == 2

    def test_comparison_uses_the_finals_own_numbers(self):
        """Event-wide averages are not like-for-like once the event is over;
        the card compares what happened in the final itself."""
        riders = _riders()
        riders[0]["final_total"] = 36.63
        riders[0]["best_heat"] = 99.0  # event-wide, must not be used here
        compare = build_slides(_data(riders=riders))[-1]
        final_row = next(r for r in compare["rows"] if r["label"] == "FINAL SCORE")
        assert final_row["cells"][0]["value"] == "36.63"

    def test_best_wave_comes_from_the_final_heat(self):
        riders = _riders()
        riders[0]["final_waves"] = [9.25, 6.0]
        riders[0]["best_wave"] = 10.0  # event-wide
        compare = build_slides(_data(riders=riders))[-1]
        wave_row = next(r for r in compare["rows"] if r["label"] == "BEST WAVE")
        assert wave_row["cells"][0]["value"] == "9.25"

    def test_no_jumps_in_the_final_drops_only_the_final_jump_row(self):
        """A wave-only final in a jumping event: the final group loses its
        jump row, but the riders still jumped earlier in the event."""
        riders = _riders()
        for r in riders:
            r["final_jumps"] = []
        rows = build_slides(_data(riders=riders))[-1]["rows"]
        final_labels = [r["label"] for r in rows if r["group"] == "IN THE FINAL"]
        event_labels = [r["label"] for r in rows if r["group"] == "AT THIS EVENT"]
        assert "BEST JUMP" not in final_labels
        assert "BEST JUMP" in event_labels


class TestJumpsHandling:
    def test_wave_only_division_drops_jump_rows(self):
        riders = _riders()
        for r in riders:
            r["final_jumps"] = []
            r["avg_jump"] = 0
            r["best_jump"] = None
        slides = build_slides(_data(riders=riders))
        compare = slides[-1]
        assert "BEST JUMP" not in [row["label"] for row in compare["rows"]]
        for slide in _rider_slides(slides):
            assert "AVG JUMP" not in [s["label"] for s in slide["stats"]]

    def test_jumps_kept_when_the_division_has_them(self):
        slides = build_slides(_data())
        compare = slides[-1]
        assert "BEST JUMP" in [row["label"] for row in compare["rows"]]


class TestEdgeCases:
    def test_fewer_than_four_riders_still_builds(self):
        riders = _riders()[:3]
        slides = build_slides(_data(riders=riders))
        assert len(_rider_slides(slides)) == 3
        assert slides[-1]["type"] == "recap_compare"

    def test_no_riders_returns_no_carousel(self):
        assert build_slides(_data(riders=[])) == []

    def test_long_surname_gets_a_size_class(self):
        riders = _riders()
        riders[0]["name"] = "Marino Ellefson Riemenschneider"
        winner = _rider_slides(build_slides(_data(riders=riders)))[-1]
        assert winner["name_class"] in ("long", "xlong")


class TestCommentaryStats:
    """The fuller stat set carried over from the commentator brief."""

    def _winner(self, **rider_extra):
        riders = _riders()
        riders[0].update(rider_extra)
        return _rider_slides(build_slides(_data(riders=riders)))[-1]

    def test_carries_the_full_seven_stat_set(self):
        winner = self._winner(history=[{}, {}, {}, {}, {}], heat_wins=3)
        labels = [s["label"] for s in winner["stats"]]
        for expected in ("BEST HEAT", "AVG HEAT", "HEATS WON",
                         "BEST WAVE", "AVG WAVE", "BEST JUMP", "AVG JUMP"):
            assert expected in labels

    def test_avg_heat_is_shown_post_event(self):
        """finals_preview hides avg heat because the draw distorts it mid-event.
        Once the ladder has run in full it is a fair number."""
        winner = self._winner(avg_heat=24.5)
        values = {s["label"]: s["value"] for s in winner["stats"]}
        assert values["AVG HEAT"] == "24.50"

    def test_heats_won_prints_as_a_fraction(self):
        winner = self._winner(history=[{}, {}, {}, {}, {}], heat_wins=3)
        values = {s["label"]: s["value"] for s in winner["stats"]}
        assert values["HEATS WON"] == "3/5"

    def test_heats_won_is_never_highlighted(self):
        """Denominators differ per rider, so the values are not comparable."""
        slides = _rider_slides(build_slides(_data(riders=[
            _rider(97, "Marc Pare Rico", 1, heat_wins=5, history=[{}] * 5),
            _rider(49, "Philip Koster", 2, heat_wins=1, history=[{}] * 1),
            _rider(48, "Marino Gil Gherardi", 3, heat_wins=2, history=[{}] * 4),
            _rider(75, "Lennart Neubauer", 4, heat_wins=0, history=[{}] * 3),
        ])))
        for slide in slides:
            won = next(s for s in slide["stats"] if s["label"] == "HEATS WON")
            assert won["is_leader"] is False

    def test_heats_won_dashes_when_no_history(self):
        winner = self._winner(heat_wins=3, history=[])
        values = {s["label"]: s["value"] for s in winner["stats"]}
        assert values["HEATS WON"] == "-"

    def test_best_jump_carries_the_move_name(self):
        winner = self._winner(history=[
            {"scores": [{"type": "PF", "move_type": "Pushloop Forward", "score": 10.0},
                        {"type": "Wave", "move_type": "Wave", "score": 8.75}]},
        ])
        jump = next(s for s in winner["stats"] if s["label"] == "BEST JUMP")
        assert jump.get("note") == "Pushloop Forward"

    def test_sail_number_and_world_rank_reach_the_slide(self):
        winner = self._winner(sail_number="E-334", world_rank=2)
        assert winner["sail_number"] == "E-334"
        assert winner["rank_label"] == "WR #2"

    def test_missing_world_rank_leaves_no_badge(self):
        """World rank comes from the DB, so it is absent without the tunnel."""
        winner = self._winner(sail_number="E-334")
        assert winner["rank_label"] == ""
        assert winner["sail_number"] == "E-334"

    def test_history_lines_are_carried(self):
        winner = self._winner(history=[
            {"round": "Semis R5", "heat": 1, "total": 30.5, "place": 1},
        ])
        assert winner["history"]
        assert "Semis R5" in winner["history"][0]


class TestHeroPhoto:
    def test_action_shot_gives_a_full_bleed_hero(self):
        riders = _riders()
        riders[0]["action_url"] = "file:///photos/events/124/97.jpg"
        winner = _rider_slides(build_slides(_data(riders=riders)))[-1]
        assert winner["photo_mode"] == "action"

    def test_without_one_the_hero_still_renders_large(self):
        """Same slide, same gradient -- the fallback is a bigger portrait, not
        a small framed thumbnail."""
        winner = _rider_slides(build_slides(_data()))[-1]
        assert winner["photo_mode"] == "portrait"
        assert winner["photo_url"]

    def test_comparison_card_keeps_headshots(self):
        compare = build_slides(_data())[-1]
        for rider in compare["riders"]:
            assert "photo_url" in rider


class TestSummarySheetFullStats:
    """The summary sheet carries every stat, grouped by what it measures."""

    def _rows(self, riders=None):
        return build_slides(_data(riders=riders))[-1]["rows"]

    def test_every_stat_appears(self):
        labels = [r["label"] for r in self._rows()]
        for expected in ("FINAL SCORE", "BEST WAVE", "BEST JUMP", "BEST HEAT",
                         "AVG HEAT", "HEATS WON", "AVG WAVE", "AVG JUMP"):
            assert expected in labels

    def test_rows_are_grouped_by_scope(self):
        """Final-only and event-wide numbers are not like-for-like, so they
        are labelled as separate groups rather than pooled into one table."""
        rows = self._rows()
        groups = {r["group"] for r in rows}
        assert groups == {"IN THE FINAL", "AT THIS EVENT"}

    def test_final_group_comes_first(self):
        rows = self._rows()
        assert rows[0]["group"] == "IN THE FINAL"
        first_event = next(i for i, r in enumerate(rows) if r["group"] == "AT THIS EVENT")
        last_final = max(i for i, r in enumerate(rows) if r["group"] == "IN THE FINAL")
        assert last_final < first_event

    def test_final_group_uses_the_finals_own_scores(self):
        riders = _riders()
        riders[0]["final_waves"] = [9.25, 6.0]
        riders[0]["best_wave"] = 10.0  # event-wide, must not leak in
        rows = self._rows(riders)
        wave = next(r for r in rows if r["label"] == "BEST WAVE" and r["group"] == "IN THE FINAL")
        assert wave["cells"][0]["value"] == "9.25"

    def test_event_group_uses_event_aggregates(self):
        riders = _riders()
        riders[0]["best_heat"] = 40.0
        rows = self._rows(riders)
        heat = next(r for r in rows if r["label"] == "BEST HEAT")
        assert heat["group"] == "AT THIS EVENT"
        assert heat["cells"][0]["value"] == "40.00"

    def test_heats_won_is_a_fraction_and_unhighlighted(self):
        riders = _riders()
        for i, r in enumerate(riders):
            r["heat_wins"] = 4 - i
            r["history"] = [{}] * 4
        rows = self._rows(riders)
        won = next(r for r in rows if r["label"] == "HEATS WON")
        assert won["cells"][0]["value"] == "4/4"
        assert all(c["is_leader"] is False for c in won["cells"])

    def test_wave_only_division_drops_every_jump_row(self):
        riders = _riders()
        for r in riders:
            r["final_jumps"] = []
            r["avg_jump"] = 0
            r["best_jump"] = None
        labels = [r["label"] for r in self._rows(riders)]
        assert "BEST JUMP" not in labels
        assert "AVG JUMP" not in labels


class TestJumpMoveOnSummary:
    """The move behind a best jump belongs everywhere the score appears."""

    def test_final_best_jump_names_the_move(self):
        riders = _riders()
        riders[0]["final_best_jump_move"] = "Double Forward"
        rows = build_slides(_data(riders=riders))[-1]["rows"]
        jump = next(r for r in rows if r["label"] == "BEST JUMP" and r["group"] == "IN THE FINAL")
        assert jump["cells"][0]["note"] == "Double Forward"

    def test_event_best_jump_names_the_move(self):
        riders = _riders()
        riders[0]["history"] = [
            {"scores": [{"type": "PF", "move_type": "Pushloop Forward", "score": 9.5}]},
        ]
        rows = build_slides(_data(riders=riders))[-1]["rows"]
        jump = next(r for r in rows if r["label"] == "BEST JUMP" and r["group"] == "AT THIS EVENT")
        assert jump["cells"][0]["note"] == "Pushloop Forward"

    def test_non_jump_rows_carry_no_note(self):
        rows = build_slides(_data())[-1]["rows"]
        score_row = next(r for r in rows if r["label"] == "FINAL SCORE")
        assert all(c["note"] == "" for c in score_row["cells"])

    def test_unknown_move_leaves_the_note_empty(self):
        rows = build_slides(_data())[-1]["rows"]
        jump = next(r for r in rows if r["label"] == "BEST JUMP" and r["group"] == "IN THE FINAL")
        assert jump["cells"][0]["note"] == ""
