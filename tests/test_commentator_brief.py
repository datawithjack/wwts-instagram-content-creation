"""Tests for the commentator brief builder (one detailed sheet per heat)."""
import pytest

from pipeline.commentator_brief import build_pages


def _rider(athlete_id, name, **kw):
    rider = {
        "athlete_id": athlete_id,
        "name": name,
        "nationality": "Spain",
        "photo_url": f"https://example.com/{athlete_id}.jpg",
        "sail_number": "E-11",
        "world_rank": 3,
        "best_heat": 20.01,
        "avg_heat": 17.5,
        "heat_wins": 2,
        "best_wave": 6.4,
        "avg_wave": 5.82,
        "best_jump": 9.1,
        "avg_jump": 8.38,
        "route_round": "Seeding R1",
        "route_place": 1,
        "route_order": 1,
        "history": [
            {"round": "Seeding R1", "heat": "8", "place": 1, "total": 20.01, "advanced": True},
            {"round": "Elimination R3", "heat": "2", "place": 2, "total": 15.4, "advanced": True},
        ],
    }
    rider.update(kw)
    return rider


def _data(heats=None, **kw):
    data = {
        "division_label": "MEN'S",
        "heats": heats if heats is not None else [
            {"label": "QUARTER FINAL 1", "athletes": [_rider(97, "Marc Paré Rico"), _rider(49, "Philip Köster")]},
            {"label": "QUARTER FINAL 2", "athletes": [_rider(68, "Marcilio Browne")]},
        ],
        "event_meta": {"event_name": "Tenerife Grand Slam", "year": 2026, "stars": 5},
        "generated_at": "5 Aug 2026, 09:40",
    }
    data.update(kw)
    return data


class TestPages:
    def test_one_page_per_heat_no_cover(self):
        pages = build_pages(_data())
        assert len(pages) == 2
        assert all(p["type"] == "brief_heat" for p in pages)

    def test_page_titled_by_division_and_heat(self):
        pages = build_pages(_data())
        assert pages[0]["title"] == "MEN QUARTER FINAL 1"
        assert pages[1]["title"] == "MEN QUARTER FINAL 2"

    def test_event_and_timestamp_on_every_page(self):
        pages = build_pages(_data())
        for p in pages:
            assert p["event_name"] == "Tenerife Grand Slam"
            assert p["generated_at"] == "5 Aug 2026, 09:40"

    def test_riders_ordered_seeded_first(self):
        heats = [{"label": "QUARTER FINAL 1", "athletes": [
            _rider(1, "Late Elim", route_order=3),
            _rider(2, "Early Seed", route_order=1),
        ]}]
        pages = build_pages(_data(heats=heats))
        assert [r["first_name"] for r in pages[0]["riders"]] == ["EARLY", "LATE"]


class TestRider:
    def _rider0(self, **kw):
        heats = [{"label": "QUARTER FINAL 1", "athletes": [_rider(97, "Marc Paré Rico", **kw)]}]
        return build_pages(_data(heats=heats))[0]["riders"][0]

    def test_identity_fields(self):
        r = self._rider0()
        assert r["first_name"] == "MARC"
        assert r["last_name"] == "PARÉ RICO"
        assert r["country"] == "es"
        assert r["sail_number"] == "E-11"

    def test_world_rank_prefixed_wr(self):
        assert self._rider0()["rank_label"] == "WR #3"

    def test_missing_rank_is_blank(self):
        assert self._rider0(world_rank=None)["rank_label"] == ""

    def test_route_line(self):
        assert self._rider0()["route"] == "QUALIFIED FROM: SEEDING R1 · 1ST"

    def test_all_seven_stats_present_in_order(self):
        labels = [s["label"] for s in self._rider0()["stats"]]
        assert labels == [
            "BEST HEAT", "AVG HEAT", "HEATS WON",
            "BEST WAVE", "AVG WAVE", "BEST JUMP", "AVG JUMP",
        ]

    def test_scores_two_dp(self):
        stats = {s["label"]: s["value"] for s in self._rider0()["stats"]}
        assert stats["BEST HEAT"] == "20.01"
        assert stats["AVG HEAT"] == "17.50"

    def test_missing_stat_renders_dash(self):
        stats = {s["label"]: s["value"] for s in self._rider0(best_jump=None, avg_jump=None)["stats"]}
        assert stats["BEST JUMP"] == "-"
        assert stats["AVG JUMP"] == "-"

    def test_heats_won_is_a_fraction_of_heats_sailed(self):
        # A percentage off one or two heats invents precision; the fraction
        # carries its own denominator.
        stats = {s["label"]: s["value"] for s in self._rider0(heat_wins=2)["stats"]}
        assert stats["HEATS WON"] == "2/2"

    def test_zero_wins_still_shows_the_denominator(self):
        stats = {s["label"]: s["value"] for s in self._rider0(heat_wins=0)["stats"]}
        assert stats["HEATS WON"] == "0/2"

    def test_heats_won_without_history_is_a_dash(self):
        stats = {s["label"]: s["value"] for s in self._rider0(history=[])["stats"]}
        assert stats["HEATS WON"] == "-"

    def test_heats_won_is_never_highlighted(self):
        # 1/1 and 4/5 are not comparable, so nothing on this column leads.
        heats = [{"label": "QF 1", "athletes": [
            _rider(1, "A B", heat_wins=1), _rider(2, "C D", heat_wins=0),
        ]}]
        riders = build_pages(_data(heats=heats))[0]["riders"]
        for r in riders:
            won = next(s for s in r["stats"] if s["label"] == "HEATS WON")
            assert won["is_leader"] is False


class TestHistory:
    def _history(self, **kw):
        heats = [{"label": "QF 1", "athletes": [_rider(97, "Marc Paré Rico", **kw)]}]
        return build_pages(_data(heats=heats))[0]["riders"][0]["history"]

    def test_each_sailed_heat_is_one_line(self):
        assert len(self._history()) == 2

    def test_line_names_round_score_and_place(self):
        assert self._history()[0] == "Seeding R1 H8 · 20.01 · 1st"

    def test_heat_without_a_score_omits_it(self):
        rows = [{"round": "Elimination R3", "heat": "2", "place": 3, "total": None, "advanced": False}]
        assert self._history(history=rows)[0] == "Elimination R3 H2 · 3rd"

    def test_no_history_is_empty(self):
        assert self._history(history=[]) == []


class TestLeaders:
    def test_best_in_heat_flagged_per_stat(self):
        heats = [{"label": "QF 1", "athletes": [
            _rider(1, "High One", best_heat=25.0, avg_wave=3.0),
            _rider(2, "Low Two", best_heat=10.0, avg_wave=7.0),
        ]}]
        riders = build_pages(_data(heats=heats))[0]["riders"]
        by_label = lambda r, l: next(s for s in r["stats"] if s["label"] == l)
        assert by_label(riders[0], "BEST HEAT")["is_leader"] is True
        assert by_label(riders[0], "AVG WAVE")["is_leader"] is False
        assert by_label(riders[1], "AVG WAVE")["is_leader"] is True


class TestDrawNote:
    """The draw itself is the headline: which heat holds the top seeds."""

    def _pages(self, ranks_by_heat):
        heats = []
        for i, ranks in enumerate(ranks_by_heat, 1):
            athletes = [_rider(j + i * 10, f"R{j} S{j}", world_rank=rank)
                        for j, rank in enumerate(ranks, 1)]
            heats.append({"label": f"QF {i}", "athletes": athletes})
        return build_pages(_data(heats=heats))

    def test_lists_world_ranks_ascending(self):
        pages = self._pages([[10, 2, 21]])
        assert pages[0]["draw_note"] == "World ranks #2, #10, #21"

    def test_unranked_riders_are_left_out(self):
        pages = self._pages([[4, None, 12]])
        assert pages[0]["draw_note"] == "World ranks #4, #12"

    def test_no_ranks_means_no_note(self):
        pages = self._pages([[None, None]])
        assert pages[0]["draw_note"] == ""

    def test_strongest_heat_flagged(self):
        pages = self._pages([[1, 2, 3], [14, 21, 30]])
        assert pages[0]["is_strongest"] is True
        assert pages[1]["is_strongest"] is False

    def test_single_heat_has_nothing_to_compare(self):
        pages = self._pages([[1, 2, 3]])
        assert pages[0]["is_strongest"] is False

    def test_tied_strength_flags_neither(self):
        pages = self._pages([[2, 4], [2, 4]])
        assert all(p["is_strongest"] is False for p in pages)


class TestBestJumpMove:
    """The move behind the best jump, read off the heat scores.

    Waves are typed "Wave"; jumps carry a code in ``type`` ("F") and the full
    name in ``move_type`` ("Forward Loop"), so anything not typed Wave is a
    jump.
    """

    def _note(self, scored_heats, **kw):
        history = [{"round": "Seeding R1", "heat": "1", "place": 1, "total": 18.0,
                    "advanced": True, "scores": s} for s in scored_heats]
        heats = [{"label": "QF 1", "athletes": [_rider(97, "Marc Paré Rico", history=history, **kw)]}]
        rider = build_pages(_data(heats=heats))[0]["riders"][0]
        return next(s for s in rider["stats"] if s["label"] == "BEST JUMP")["note"]

    def test_names_the_move_of_the_highest_jump(self):
        scores = [[
            {"score": 5.12, "type": "B", "move_type": "Back Loop"},
            {"score": 8.40, "type": "F", "move_type": "Forward Loop"},
        ]]
        assert self._note(scores) == "Forward Loop"

    def test_wave_scores_are_ignored(self):
        scores = [[
            {"score": 9.50, "type": "Wave", "move_type": "Wave"},
            {"score": 4.10, "type": "B", "move_type": "Back Loop"},
        ]]
        assert self._note(scores) == "Back Loop"

    def test_looks_across_every_heat(self):
        scores = [
            [{"score": 4.00, "type": "B", "move_type": "Back Loop"}],
            [{"score": 7.20, "type": "P", "move_type": "Push Loop"}],
        ]
        assert self._note(scores) == "Push Loop"

    def test_falls_back_to_the_code_when_no_full_name(self):
        # Codes map through the shared trick-label table ("F" -> "Forward").
        assert self._note([[{"score": 6.0, "type": "F"}]]) == "Forward"

    def test_no_jumps_means_no_note(self):
        assert self._note([[{"score": 9.5, "type": "Wave", "move_type": "Wave"}]]) == ""

    def test_no_scores_means_no_note(self):
        assert self._note([[]]) == ""

    def test_other_stats_carry_no_note(self):
        heats = [{"label": "QF 1", "athletes": [_rider(97, "Marc Paré Rico")]}]
        rider = build_pages(_data(heats=heats))[0]["riders"][0]
        assert all(s["note"] == "" for s in rider["stats"] if s["label"] != "BEST JUMP")


class TestMetaFitting:
    """Forename + sail + WR has to fit one line inside the card.

    "SARAH-QUITA ARU-91 WR #10" overflows at full size and squeezes the WR
    badge off the card, so long combinations step the whole row down.
    """

    def _meta_class(self, first_and_last, sail):
        heats = [{"label": "QF 1", "athletes": [
            _rider(97, first_and_last, sail_number=sail),
        ]}]
        return build_pages(_data(heats=heats))[0]["riders"][0]["meta_class"]

    def test_short_names_stay_full_size(self):
        assert self._meta_class("Takuma Sugi", "J-7") == ""
        assert self._meta_class("Marcilio Browne", "BRA-105") == ""

    def test_long_forename_and_sail_tightens(self):
        assert self._meta_class("Sarah-Quita Offringa", "ARU-91") == "tight"

    def test_long_forename_with_a_normal_sail_tightens(self):
        # A short sail buys back enough room that "Christopher E-1" is fine;
        # a normal-length one is not.
        assert self._meta_class("Christopher Anderson", "E-1") == ""
        assert self._meta_class("Christopher Anderson", "AUS-111") == "tight"

    def test_missing_sail_is_not_counted(self):
        assert self._meta_class("Philip Köster", "") == ""
