"""Tests for the slalom Session MVP carousel builder.

The scoring helpers here are a PORT of the windsurf-world-tour-stats-app kernel
(backend/src/api/slalom_session_scoring.py). These tests pin the ported rules to
the same behaviour so the post can never quietly disagree with the live fantasy
leaderboard; pipeline/slalom_mvps.py documents the provenance.
"""

import pytest

from pipeline.queries import (
    build_slalom_elimination_view_query,
    build_slalom_mvp_classify_query,
    build_slalom_mvp_heats_query,
)
from pipeline.helpers import sail_prefix_to_iso2
from pipeline.slalom_mvps import (
    assemble_slalom_mvp_data,
    best_elimination_example,
    resolve_country_iso,
    athlete_event_points,
    build_slides,
    final_multipliers_for_event,
    heat_points,
    parse_fleet,
    penalty_for_code,
)


# ── Country fallback ────────────────────────────────────────────


class TestSailPrefixToIso2:
    """Most slalom riders have every country column NULL in ATHLETES (an upstream
    gap), but they do carry a sail number whose prefix is their national code.
    """

    def test_maps_three_letter_national_codes(self):
        assert sail_prefix_to_iso2("NED-69") == "nl"
        assert sail_prefix_to_iso2("ITA-160") == "it"
        assert sail_prefix_to_iso2("GER-7") == "de"
        assert sail_prefix_to_iso2("FRA-330") == "fr"
        assert sail_prefix_to_iso2("GBR-68") == "gb"

    def test_maps_legacy_single_letter_codes(self):
        # Older sails use the pre-ISO letters, e.g. Pierre Mortefon is F-14.
        assert sail_prefix_to_iso2("F-14") == "fr"
        assert sail_prefix_to_iso2("I-15") == "it"

    def test_maps_caribbean_and_overseas_codes(self):
        assert sail_prefix_to_iso2("ARU-91") == "aw"    # Aruba
        assert sail_prefix_to_iso2("NB-9") == "bq"      # Bonaire
        assert sail_prefix_to_iso2("GPE-1052") == "gp"  # Guadeloupe
        assert sail_prefix_to_iso2("BRA-41") == "br"

    def test_is_case_and_whitespace_insensitive(self):
        assert sail_prefix_to_iso2(" ned-69 ") == "nl"

    def test_unknown_or_missing_returns_empty_string(self):
        assert sail_prefix_to_iso2("") == ""
        assert sail_prefix_to_iso2(None) == ""
        assert sail_prefix_to_iso2("ZZZ-1") == ""

    def test_handles_a_sail_with_no_separator(self):
        assert sail_prefix_to_iso2("FRA") == "fr"


class TestResolveCountryIso:
    def test_prefers_the_country_code_column(self):
        assert resolve_country_iso("IT", "France", "FRA-1") == "it"

    def test_falls_back_to_nationality(self):
        assert resolve_country_iso(None, "France", None) == "fr"

    def test_falls_back_to_the_sail_prefix_when_country_is_null(self):
        # The common case at Fuerteventura: 35 of 52 riders had no country at all.
        assert resolve_country_iso(None, None, "NED-69") == "nl"

    def test_returns_empty_when_nothing_resolves(self):
        assert resolve_country_iso(None, None, None) == ""


# ── Queries ─────────────────────────────────────────────────────


class TestSlalomQueries:
    def test_heats_query_is_parameterised_on_event(self):
        sql, params = build_slalom_mvp_heats_query(123)
        assert params[0] == 123
        assert "%s" in sql

    def test_heats_query_isolates_slalom_heats_by_id_pattern(self):
        # Slalom heat_ids are {ladder}_r{round}_h{n}; wave/freestyle heats use a
        # different format and must not leak into a slalom board.
        sql, params = build_slalom_mvp_heats_query(123)
        assert "REGEXP" in sql.upper()
        assert r"_r[0-9]+_h" in params

    def test_heats_query_selects_place_and_result_code(self):
        sql, _ = build_slalom_mvp_heats_query(123)
        assert "place" in sql
        assert "result_code" in sql

    def test_heats_query_resolves_unified_athlete_ids(self):
        sql, _ = build_slalom_mvp_heats_query(123)
        assert "ATHLETE_SOURCE_IDS" in sql
        assert "ATHLETES" in sql

    def test_heats_query_is_not_limited_to_picked_athletes(self):
        # The MVP board scores the whole fleet, unlike the app's own engine.
        sql, _ = build_slalom_mvp_heats_query(123)
        assert "FANTASY_SESSION_PICKS" not in sql

    def test_classify_query_returns_heat_and_overall_place(self):
        sql, params = build_slalom_mvp_classify_query(123)
        assert params[0] == 123
        assert "overall_place" in sql
        assert "PWA_IWT_SLALOM_ELIMINATION_RESULTS" in sql

    def test_elimination_view_query_returns_fleet_and_win_fields(self):
        sql, params = build_slalom_elimination_view_query(123)
        assert params == (123,)
        assert "SLALOM_ELIMINATION_VIEW" in sql
        for field in ("athlete_id", "ladder_id", "elimination_name", "place"):
            assert field in sql


# ── Ported scoring kernel ───────────────────────────────────────


class TestHeatPoints:
    def test_top_10_descending_curve(self):
        # 1st = 10, 2nd = 9, ... 10th = 1
        assert heat_points(1) == 10
        assert heat_points(2) == 9
        assert heat_points(10) == 1

    def test_outside_top_10_scores_zero(self):
        assert heat_points(11) == 0
        assert heat_points(999) == 0
        assert heat_points(None) == 0

    def test_winners_final_doubles_place_points(self):
        assert heat_points(1, final_multiplier=2.0) == 20
        assert heat_points(4, final_multiplier=2.0) == 14

    def test_penalty_replaces_place_points(self):
        assert heat_points(1, penalty=-5.0) == -5.0

    def test_penalty_is_never_scaled_by_final_multiplier(self):
        # A DQ in the final still costs a flat -5, not -10.
        assert heat_points(1, penalty=-5.0, final_multiplier=2.0) == -5.0


class TestPenaltyForCode:
    @pytest.mark.parametrize("code", ["PMS", "DNE", "OCS", "DSQ", "DQ"])
    def test_disqualifications_cost_five(self, code):
        assert penalty_for_code(code) == -5.0

    @pytest.mark.parametrize("code", ["DNF", "RAF"])
    def test_did_not_finish_costs_one(self, code):
        assert penalty_for_code(code) == -1.0

    def test_dns_is_neutral_zero_not_none(self):
        # A non-start must override the finish place, so it returns 0.0 and not
        # None (None would fall through to the place curve).
        assert penalty_for_code("DNS") == 0.0

    def test_normal_finish_and_unknown_codes_return_none(self):
        assert penalty_for_code(None) is None
        assert penalty_for_code("") is None
        assert penalty_for_code("WTF") is None

    def test_is_case_and_whitespace_insensitive(self):
        assert penalty_for_code(" dnf ") == -1.0


class TestAthleteEventPoints:
    def test_sums_points_across_heats(self):
        heats = [{"place": 1}, {"place": 3}, {"place": 11}]
        assert athlete_event_points(heats) == 18  # 10 + 8 + 0

    def test_applies_result_code_penalties(self):
        heats = [{"place": 1}, {"place": 2, "result_code": "DNF"}]
        assert athlete_event_points(heats) == 9  # 10 + (-1)

    def test_no_heats_scores_zero(self):
        assert athlete_event_points([]) == 0


class TestFinalMultipliers:
    def test_straight_final_is_the_championship_final(self):
        # One round, one heat = the whole fleet races a single decider -> x2.
        rows = [
            {"heat_id": "lad_r1_h1", "overall_place": 1},
            {"heat_id": "lad_r1_h1", "overall_place": 2},
        ]
        assert final_multipliers_for_event(rows) == {"lad_r1_h1": 2.0}

    def test_one_round_split_across_heats_is_not_a_final(self):
        rows = [
            {"heat_id": "lad_r1_h1", "overall_place": 1},
            {"heat_id": "lad_r1_h2", "overall_place": 2},
        ]
        assert final_multipliers_for_event(rows) == {}

    def test_only_winners_final_is_boosted_in_a_bracket(self):
        rows = [
            {"heat_id": "lad_r1_h1", "overall_place": 1},
            {"heat_id": "lad_r1_h2", "overall_place": 5},
            # Max round: the heat holding the best overall places is the final.
            {"heat_id": "lad_r2_h1", "overall_place": 1},
            {"heat_id": "lad_r2_h2", "overall_place": 5},
        ]
        assert final_multipliers_for_event(rows) == {"lad_r2_h1": 2.0}

    def test_ambiguous_finals_are_skipped(self):
        rows = [
            {"heat_id": "lad_r1_h1", "overall_place": 1},
            {"heat_id": "lad_r2_h1", "overall_place": 3},
            {"heat_id": "lad_r2_h2", "overall_place": 3},
        ]
        assert final_multipliers_for_event(rows) == {}


class TestParseFleet:
    def test_reads_mens_and_womens_from_elimination_name(self):
        assert parse_fleet("Men's Slalom X - Elimination 1") == "Men"
        assert parse_fleet("Women's Slalom X - Elimination 1") == "Women"

    def test_women_wins_over_the_men_substring(self):
        # "women" contains "men" — the women test must run first.
        assert parse_fleet("Women's Slalom X - Elimination 15") == "Women"

    def test_handles_curly_apostrophes_from_the_source(self):
        # The DB holds both "Men's" and "Men’s" spellings.
        assert parse_fleet("Men’s Slalom X - Elimination 8") == "Men"

    def test_unknown_name_returns_none(self):
        assert parse_fleet("Slalom X - Elimination 1") is None
        assert parse_fleet("") is None


# ── Assembly ────────────────────────────────────────────────────


@pytest.fixture
def heat_rows():
    # Two men, one ladder each of two heats; athlete 1 outscores athlete 2.
    return [
        {"athlete_id": 1, "athlete": "Fast Rider", "country": "Italy", "country_code": "IT",
         "heat_id": "ladA_r1_h1", "place": 1, "result_code": None},
        {"athlete_id": 1, "athlete": "Fast Rider", "country": "Italy", "country_code": "IT",
         "heat_id": "ladB_r1_h1", "place": 2, "result_code": None},
        {"athlete_id": 2, "athlete": "Slow Rider", "country": "France", "country_code": "FR",
         "heat_id": "ladA_r1_h1", "place": 5, "result_code": None},
        {"athlete_id": 2, "athlete": "Slow Rider", "country": "France", "country_code": "FR",
         "heat_id": "ladB_r1_h1", "place": 6, "result_code": None},
    ]


@pytest.fixture
def elim_rows():
    return [
        {"athlete_id": 1, "ladder_id": "ladA", "elimination_no": 1,
         "elimination_name": "Men's Slalom X - Elimination 1", "place": 1},
        {"athlete_id": 1, "ladder_id": "ladB", "elimination_no": 2,
         "elimination_name": "Men's Slalom X - Elimination 2", "place": 2},
        {"athlete_id": 2, "ladder_id": "ladA", "elimination_no": 1,
         "elimination_name": "Men's Slalom X - Elimination 1", "place": 5},
        {"athlete_id": 2, "ladder_id": "ladB", "elimination_no": 2,
         "elimination_name": "Men's Slalom X - Elimination 2", "place": 6},
    ]


@pytest.fixture
def pct_rows():
    return [{"athlete_id": "1", "pick_count": 5, "total_entries": 10}]


@pytest.fixture
def classify_rows():
    # Each ladder is one round of one heat = a straight final, so both score x2.
    return [
        {"heat_id": "ladA_r1_h1", "overall_place": 1},
        {"heat_id": "ladA_r1_h1", "overall_place": 5},
        {"heat_id": "ladB_r1_h1", "overall_place": 2},
        {"heat_id": "ladB_r1_h1", "overall_place": 6},
    ]


@pytest.fixture
def assembled(heat_rows, classify_rows, elim_rows, pct_rows):
    return assemble_slalom_mvp_data(
        heat_rows, classify_rows, elim_rows, pct_rows,
        {"location": "Fuerteventura", "year": 2026},
    )


class TestAssembleSlalomMvpData:
    def test_returns_event_men_and_women(self, assembled):
        assert set(assembled) == {"event", "men", "women", "example"}

    def test_ranks_by_total_points_descending(self, assembled):
        assert [r["rank"] for r in assembled["men"]] == [1, 2]
        assert assembled["men"][0]["athlete"] == "Fast Rider"

    def test_totals_sum_the_place_curve_across_heats(self, assembled):
        # Both heats are straight finals (one round, one heat) -> x2 each.
        # Fast Rider: 1st (10*2) + 2nd (9*2) = 38
        assert assembled["men"][0]["total_pts"] == 38.0
        # Slow Rider: 5th (6*2) + 6th (5*2) = 22
        assert assembled["men"][1]["total_pts"] == 22.0

    def test_counts_elimination_wins_from_overall_place_one(self, assembled):
        assert assembled["men"][0]["wins"] == 1
        assert assembled["men"][1]["wins"] == 0

    def test_best_is_the_top_single_elimination_haul(self, assembled):
        assert assembled["men"][0]["best_pts"] == 20.0

    def test_avg_is_total_over_eliminations_sailed(self, assembled):
        assert assembled["men"][0]["avg_pts"] == 19.0  # 38 / 2

    def test_counts_eliminations_sailed(self, assembled):
        assert assembled["men"][0]["elims"] == 2

    def test_records_non_finish_codes(self, heat_rows, classify_rows, elim_rows, pct_rows):
        # A DNS/DNF is what separates a win leader from the MVP, so the codes
        # have to survive assembly for the caption to cite them.
        rows = [dict(r) for r in heat_rows]
        rows[1]["result_code"] = "DNS"
        data = assemble_slalom_mvp_data(rows, classify_rows, elim_rows, pct_rows, {})
        top = next(r for r in data["men"] if r["athlete"] == "Fast Rider")
        assert top["non_finishes"] == ["DNS"]

    def test_clean_records_have_no_non_finishes(self, assembled):
        assert assembled["men"][0]["non_finishes"] == []

    def test_maps_pick_percentage(self, assembled):
        assert assembled["men"][0]["pct_picked"] == 50
        assert assembled["men"][1]["pct_picked"] == 0

    def test_resolves_country_to_iso2(self, assembled):
        assert assembled["men"][0]["country"] == "it"

    def test_carries_preformatted_column_values(self, assembled):
        # The shared mvp_table template renders col_1..col_3 verbatim. Wins is a
        # count and slalom totals are always whole numbers (the place curve and
        # the x2 final are integers), so only the average carries a decimal.
        row = assembled["men"][0]
        assert row["col_1"] == "1"
        assert row["col_2"] == "19.0"
        assert row["col_3"] == "38"

    def test_splits_fleets_by_elimination_name(self, heat_rows, elim_rows, pct_rows):
        womens = [dict(r, elimination_name="Women's Slalom X - Elimination 1")
                  for r in elim_rows if r["athlete_id"] == 2]
        mens = [r for r in elim_rows if r["athlete_id"] == 1]
        data = assemble_slalom_mvp_data(heat_rows, [], mens + womens, pct_rows, {})
        assert [r["athlete"] for r in data["men"]] == ["Fast Rider"]
        assert [r["athlete"] for r in data["women"]] == ["Slow Rider"]

    def test_drops_athletes_who_scored_nothing(self, heat_rows, elim_rows, pct_rows):
        zeroed = [dict(r, place=20) for r in heat_rows if r["athlete_id"] == 2]
        kept = [r for r in heat_rows if r["athlete_id"] == 1]
        data = assemble_slalom_mvp_data(kept + zeroed, [], elim_rows, pct_rows, {})
        assert [r["athlete"] for r in data["men"]] == ["Fast Rider"]

    def test_limits_each_fleet_to_top_n(self, heat_rows, elim_rows, pct_rows):
        data = assemble_slalom_mvp_data(heat_rows, [], elim_rows, pct_rows, {}, top_n=1)
        assert len(data["men"]) == 1


class TestBestEliminationExample:
    def test_picks_the_single_biggest_elimination_haul(self, heat_rows, classify_rows, elim_rows):
        ex = best_elimination_example(heat_rows, classify_rows, elim_rows)
        # Fast Rider won ladA's straight final: 1st x2 = 20, beating every other
        # single-elimination run in the fixture.
        assert ex["athlete"] == "Fast Rider"
        assert ex["total"] == 20.0

    def test_labels_the_doubled_heat_as_the_final(self, heat_rows, classify_rows, elim_rows):
        ex = best_elimination_example(heat_rows, classify_rows, elim_rows)
        assert ex["steps"][-1]["label"] == "Final"

    def test_names_rounds_by_counting_back_from_the_final(self):
        # A 4-round ladder reads Qualifying -> Quarter Finals -> Semi Finals ->
        # Final, so the labels track the real bracket depth.
        heats, classify = [], []
        for rnd in (1, 2, 3, 4):
            heats.append({"athlete_id": 1, "athlete": "Deep Runner", "country": "Poland",
                          "country_code": "PL", "heat_id": f"lad_r{rnd}_h{rnd}",
                          "place": 1, "result_code": None})
            classify.append({"heat_id": f"lad_r{rnd}_h{rnd}", "overall_place": rnd})
        classify.append({"heat_id": "lad_r4_h99", "overall_place": 9})
        elims = [{"athlete_id": 1, "ladder_id": "lad", "elimination_no": 1,
                  "elimination_name": "Men's Slalom X - Elimination 1", "place": 1}]
        ex = best_elimination_example(heats, classify, elims)
        assert [s["label"] for s in ex["steps"]] == [
            "Qualifying", "Quarter Finals", "Semi Finals", "Final",
        ]

    def test_earlier_rounds_are_all_qualifying(self):
        heats, classify = [], []
        for rnd in (1, 2, 3, 4, 5):
            heats.append({"athlete_id": 1, "athlete": "Long Road", "country": "France",
                          "country_code": "FR", "heat_id": f"lad_r{rnd}_h{rnd}",
                          "place": 1, "result_code": None})
            classify.append({"heat_id": f"lad_r{rnd}_h{rnd}", "overall_place": rnd})
        classify.append({"heat_id": "lad_r5_h99", "overall_place": 9})
        ex = best_elimination_example(heats, classify, [])
        assert [s["label"] for s in ex["steps"]][:2] == ["Qualifying", "Qualifying"]

    def test_a_straight_final_is_just_the_final(self, heat_rows, classify_rows, elim_rows):
        ex = best_elimination_example(heat_rows, classify_rows, elim_rows)
        assert [s["label"] for s in ex["steps"]] == ["Final"]

    def test_orders_steps_by_round(self):
        heats = [
            {"athlete_id": 1, "athlete": "Deep Runner", "country": "Poland",
             "country_code": "PL", "heat_id": "lad_r3_h9", "place": 1, "result_code": None},
            {"athlete_id": 1, "athlete": "Deep Runner", "country": "Poland",
             "country_code": "PL", "heat_id": "lad_r1_h1", "place": 2, "result_code": None},
            {"athlete_id": 1, "athlete": "Deep Runner", "country": "Poland",
             "country_code": "PL", "heat_id": "lad_r2_h5", "place": 3, "result_code": None},
        ]
        classify = [
            {"heat_id": "lad_r1_h1", "overall_place": 4},
            {"heat_id": "lad_r2_h5", "overall_place": 3},
            {"heat_id": "lad_r3_h9", "overall_place": 1},
        ]
        elims = [{"athlete_id": 1, "ladder_id": "lad", "elimination_no": 1,
                  "elimination_name": "Men's Slalom X - Elimination 1", "place": 1}]
        ex = best_elimination_example(heats, classify, elims)
        assert [s["label"] for s in ex["steps"]] == [
            "Quarter Finals", "Semi Finals", "Final",
        ]
        # 9 (2nd) + 8 (3rd) + 10x2 (won the final) = 37
        assert [s["points"] for s in ex["steps"]] == [9.0, 8.0, 20.0]
        assert ex["total"] == 37.0

    def test_returns_none_without_heats(self):
        assert best_elimination_example([], [], []) is None


# ── Slides ──────────────────────────────────────────────────────


class TestBuildSlides:
    def test_four_slides_when_both_fleets_have_rows(self, assembled):
        assembled["women"] = [dict(assembled["men"][0])]
        slides = build_slides(assembled)
        assert [s["type"] for s in slides] == [
            "mvp_cover", "mvp_key", "mvp_table", "mvp_table", "mvp_cta",
        ]

    def test_womens_slide_dropped_when_that_fleet_is_empty(self, assembled):
        slides = build_slides(assembled)
        assert [s["type"] for s in slides] == [
            "mvp_cover", "mvp_key", "mvp_table", "mvp_cta",
        ]

    def test_numbers_slides_consistently(self, assembled):
        slides = build_slides(assembled)
        assert [s["slide_number"] for s in slides] == [1, 2, 3, 4]
        assert all(s["total_slides"] == 4 for s in slides)

    def test_key_slide_comes_before_the_tables_it_explains(self, assembled):
        types = [s["type"] for s in build_slides(assembled)]
        assert types.index("mvp_key") < types.index("mvp_table")

    def test_key_slide_explains_the_scoring_rules(self, assembled):
        key = next(s for s in build_slides(assembled) if s["type"] == "mvp_key")
        blob = " ".join(r["text"] for r in key["rules"]).lower()
        # The three facts the numbers are unreadable without.
        assert "10" in blob            # the place curve
        assert "double" in blob        # the x2 championship final
        assert "elimination" in blob   # points accumulate across eliminations

    def test_key_slide_rules_have_labels(self, assembled):
        key = next(s for s in build_slides(assembled) if s["type"] == "mvp_key")
        assert all(r.get("label") and r.get("text") for r in key["rules"])

    def test_key_slide_does_not_define_the_table_columns(self, assembled):
        # The columns are self-explanatory; the slide explains the POINTS only.
        key = next(s for s in build_slides(assembled) if s["type"] == "mvp_key")
        labels = " ".join(r["label"] for r in key["rules"]).lower()
        for column in ("wins", "picked"):
            assert column not in labels

    def test_key_slide_carries_a_worked_example(self, assembled):
        key = next(s for s in build_slides(assembled) if s["type"] == "mvp_key")
        example = key["example"]
        assert example["athlete"] == "Fast Rider"
        # One step per heat sailed, each with a label, a placing and points.
        assert [s["points"] for s in example["steps"]] == [20.0]
        assert all(s["label"] and s["detail"] for s in example["steps"])
        assert example["total"] == 20.0

    def test_key_slide_omits_the_example_when_there_is_no_data(self):
        key = next(s for s in build_slides({}) if s["type"] == "mvp_key")
        assert key.get("example") is None

    def test_table_slides_carry_slalom_column_labels(self, assembled):
        table = next(s for s in build_slides(assembled) if s["type"] == "mvp_table")
        assert table["col_1_label"] == "Wins"
        assert table["col_2_label"] == "Avg"
        assert table["col_3_label"] == "Total"

    def test_uses_the_slalom_discipline_colour(self, assembled):
        assert all("accent_color" in s for s in build_slides(assembled))

    def test_table_slides_are_labelled_slalom_not_freestyle(self, assembled):
        table = next(s for s in build_slides(assembled) if s["type"] == "mvp_table")
        assert table["discipline_label"] == "Slalom X"

    def test_footnote_explains_the_slalom_scoring(self, assembled):
        table = next(s for s in build_slides(assembled) if s["type"] == "mvp_table")
        footnote = table["footnote"].lower()
        assert "elimination" in footnote
        assert "heat scores" not in footnote  # that is the freestyle wording
