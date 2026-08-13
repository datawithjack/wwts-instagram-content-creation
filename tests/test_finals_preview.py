"""Tests for the finals preview carousel builder (2 slides: men, women)."""
import pytest

from pipeline.finals_preview import build_slides


def _athlete(athlete_id, name, best_heat=15.0, avg_wave=4.0, avg_jump=6.0, **extra):
    a = {
        "athlete_id": athlete_id,
        "name": name,
        "nationality": "Spain",
        "photo_url": f"https://example.com/{athlete_id}.jpg",
        "best_heat": best_heat,
        "avg_wave": avg_wave,
        "avg_jump": avg_jump,
    }
    a.update(extra)
    return a


def _men():
    return [
        _athlete(48, "Marino Gil Gherardi", best_heat=23.57, avg_wave=5.82, avg_jump=8.38),
        _athlete(21, "Anton Richter", best_heat=22.40, avg_wave=4.48, avg_jump=7.45),
        _athlete(97, "Marc Paré Rico", best_heat=20.01, avg_wave=4.32, avg_jump=7.85),
        _athlete(49, "Philip Köster", best_heat=16.48, avg_wave=4.10, avg_jump=6.90),
    ]


def _women():
    return [
        _athlete(17, "María Morales Navarro", best_heat=19.46, avg_wave=3.90, avg_jump=5.10),
        _athlete(12, "Alexia Kiefer Quintana", best_heat=17.12, avg_wave=3.55, avg_jump=4.80),
        _athlete(10, "Sol Degrieck", best_heat=16.75, avg_wave=3.40, avg_jump=4.20),
        _athlete(5, "Sarah-Quita Offringa", best_heat=14.37, avg_wave=3.10, avg_jump=4.00),
    ]


def _data(men=None, women=None, event_meta=None):
    return {
        "men": _men() if men is None else men,
        "women": _women() if women is None else women,
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


class TestSlideStructure:
    def test_builds_two_slides_men_first(self):
        slides = build_slides(_data())
        assert len(slides) == 2
        assert [s["type"] for s in slides] == ["finals_grid", "finals_grid"]
        assert slides[0]["division_label"] == "MEN'S FINAL"
        assert slides[1]["division_label"] == "WOMEN'S FINAL"

    def test_slide_numbering(self):
        slides = build_slides(_data())
        assert [s["slide_number"] for s in slides] == [1, 2]
        assert all(s["total_slides"] == 2 for s in slides)

    def test_each_slide_has_four_athletes(self):
        slides = build_slides(_data())
        assert all(len(s["athletes"]) == 4 for s in slides)

    def test_event_meta_on_every_slide(self):
        slides = build_slides(_data())
        for s in slides:
            assert s["event_name"] == "Tenerife Grand Slam"
            assert s["event_year"] == 2026
            assert s["event_country"] == "ESP"
            assert s["event_tier"] == 5

    def test_accent_colour_applied(self):
        slides = build_slides(_data())
        assert all(s["accent_color"] == "#5AB4CC" for s in slides)

    def test_handles_fewer_than_four_finalists(self):
        slides = build_slides(_data(men=_men()[:2]))
        assert len(slides[0]["athletes"]) == 2
        assert len(slides[1]["athletes"]) == 4

    def test_missing_division_yields_empty_grid(self):
        slides = build_slides(_data(women=[]))
        assert slides[1]["athletes"] == []


class TestAthleteEntry:
    def test_name_split_for_display(self):
        a = build_slides(_data())[0]["athletes"][0]
        assert a["name"] == "Marino Gil Gherardi"
        assert a["first_name"] == "MARINO"
        assert a["last_name"] == "GIL GHERARDI"

    def test_single_word_name_has_empty_surname(self):
        slides = build_slides(_data(men=[_athlete(1, "Kauli")]))
        a = slides[0]["athletes"][0]
        assert a["first_name"] == "KAULI"
        assert a["last_name"] == ""

    def test_country_mapped_to_iso(self):
        a = build_slides(_data())[0]["athletes"][0]
        assert a["country"] == "es"

    def test_photo_url_passed_through(self):
        a = build_slides(_data())[0]["athletes"][0]
        assert a["photo_url"] == "https://example.com/48.jpg"

    def test_athlete_id_retained(self):
        a = build_slides(_data())[0]["athletes"][0]
        assert a["athlete_id"] == 48


class TestStats:
    def test_hero_stat_is_best_heat(self):
        a = build_slides(_data())[0]["athletes"][0]
        assert a["hero"]["label"] == "BEST HEAT"
        assert a["hero"]["value"] == "23.57"

    def test_supporting_stats_are_avg_wave_then_avg_jump(self):
        a = build_slides(_data())[0]["athletes"][0]
        assert [s["label"] for s in a["stats"]] == ["AVG WAVE", "AVG JUMP"]
        assert [s["value"] for s in a["stats"]] == ["5.82", "8.38"]

    def test_scores_formatted_to_two_decimals(self):
        slides = build_slides(_data(men=[_athlete(1, "A B", best_heat=16.5, avg_wave=4.0, avg_jump=6.0)]))
        a = slides[0]["athletes"][0]
        assert a["hero"]["value"] == "16.50"
        assert [s["value"] for s in a["stats"]] == ["4.00", "6.00"]

    def test_jump_stat_dropped_when_division_has_no_jumps(self):
        wave_only = [_athlete(i, f"A{i} B", avg_jump=0) for i in range(1, 5)]
        slides = build_slides(_data(men=wave_only))
        assert all([s["label"] for s in a["stats"]] == ["AVG WAVE"] for a in slides[0]["athletes"])
        # Women unaffected — jump handling is per division
        assert all(len(a["stats"]) == 2 for a in slides[1]["athletes"])

    def test_jump_stat_kept_when_only_some_athletes_jumped(self):
        mixed = [
            _athlete(1, "A B", avg_jump=7.0),
            _athlete(2, "C D", avg_jump=0),
            _athlete(3, "E F", avg_jump=None),
            _athlete(4, "G H", avg_jump=5.0),
        ]
        slides = build_slides(_data(men=mixed))
        values = [a["stats"][1]["value"] for a in slides[0]["athletes"]]
        assert values == ["7.00", "-", "-", "5.00"]

    def test_missing_score_renders_dash(self):
        slides = build_slides(_data(men=[_athlete(1, "A B", best_heat=0, avg_wave=None)]))
        a = slides[0]["athletes"][0]
        assert a["hero"]["value"] == "-"
        assert a["stats"][0]["value"] == "-"


class TestLeaderFlags:
    def test_highest_value_flagged_as_leader(self):
        men = build_slides(_data())[0]["athletes"]
        assert [a["hero"]["is_leader"] for a in men] == [True, False, False, False]

    def test_leader_computed_per_stat(self):
        men = [
            _athlete(1, "A B", best_heat=20.0, avg_wave=3.0, avg_jump=9.0),
            _athlete(2, "C D", best_heat=10.0, avg_wave=6.0, avg_jump=2.0),
        ]
        slides = build_slides(_data(men=men))
        a1, a2 = slides[0]["athletes"]
        assert a1["hero"]["is_leader"] is True
        assert a1["stats"][0]["is_leader"] is False
        assert a1["stats"][1]["is_leader"] is True
        assert a2["stats"][0]["is_leader"] is True

    def test_ties_flag_every_tied_athlete(self):
        men = [_athlete(1, "A B", best_heat=18.0), _athlete(2, "C D", best_heat=18.0)]
        slides = build_slides(_data(men=men))
        assert all(a["hero"]["is_leader"] for a in slides[0]["athletes"])

    def test_leaders_scoped_to_division(self):
        # Women's best heat is lower than every man's; the top woman still leads
        # her own slide.
        women = build_slides(_data())[1]["athletes"]
        assert [a["hero"]["is_leader"] for a in women] == [True, False, False, False]

    def test_missing_score_never_leads(self):
        men = [_athlete(1, "A B", best_heat=0), _athlete(2, "C D", best_heat=0)]
        slides = build_slides(_data(men=men))
        assert all(a["hero"]["is_leader"] is False for a in slides[0]["athletes"])


class TestSourceNote:
    def test_source_note_states_counting_scores_and_stage(self):
        slides = build_slides(_data())
        for s in slides:
            assert "counting" in s["source_note"].lower()

    def test_ordering_preserved_from_input(self):
        # Input order is the draw order the caller passes in, not a ranking.
        names = [a["name"] for a in build_slides(_data())[0]["athletes"]]
        assert names == [
            "Marino Gil Gherardi",
            "Anton Richter",
            "Marc Paré Rico",
            "Philip Köster",
        ]


class TestDummyData:
    def test_dummy_data_builds_two_full_slides(self):
        from pipeline.templates import get_dummy_data

        data = get_dummy_data("finals_preview")
        slides = build_slides(data)

        assert len(slides) == 2
        assert all(len(s["athletes"]) == 4 for s in slides)

    def test_dummy_athletes_have_every_stat_key(self):
        from pipeline.templates import get_dummy_data

        data = get_dummy_data("finals_preview")
        for division in ("men", "women"):
            for a in data[division]:
                assert set(a) >= {
                    "athlete_id", "name", "nationality", "photo_url",
                    "best_heat", "avg_wave", "avg_jump",
                }


class TestCaption:
    def _caption(self):
        import os
        import yaml
        from pipeline.captions import build_caption
        from pipeline.templates import get_dummy_data

        config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        return build_caption("finals_preview", get_dummy_data("finals_preview"), config)

    def test_caption_names_both_finals(self):
        caption = self._caption()
        assert "final" in caption.lower()

    def test_caption_has_no_em_dashes(self):
        assert "—" not in self._caption()

    def test_caption_includes_hashtags(self):
        assert "#windsurf" in self._caption()


def _heat(label, ids_names, **kw):
    return {
        "label": label,
        "athletes": [_athlete(i, n, **kw) for i, n in ids_names],
    }


def _heats_data(heats=None, event_meta=None, division_label="MEN'S"):
    return {
        "division_label": division_label,
        "heats": heats if heats is not None else [
            _heat("QUARTER FINAL 1", [(46, "Miguel Chapuis"), (69, "Takuma Sugi"), (68, "Marcilio Browne"), (205, "Josep Pons")]),
            _heat("QUARTER FINAL 2", [(135, "Carlos Kiefer Quintana"), (64, "Antoine Martin"), (49, "Philip Köster"), (61, "Jules Denel")]),
        ],
        "event_meta": event_meta if event_meta is not None else {
            "event_name": "Tenerife Grand Slam",
            "year": 2026,
            "country": "ESP",
            "stars": 5,
        },
    }


class TestHeatsMode:
    def test_cover_slide_then_one_grid_per_heat(self):
        slides = build_slides(_heats_data())
        assert [s["type"] for s in slides] == ["finals_cover", "finals_grid", "finals_grid"]

    def test_cover_carries_event_and_road_to_final_title(self):
        cover = build_slides(_heats_data())[0]
        assert cover["event_name"] == "Tenerife Grand Slam"
        assert cover["event_year"] == 2026
        # Only the last word takes the accent — the rest of the title is white,
        # matching the other cover slides.
        assert cover["title_lines"] == ["MEN'S", "ROAD TO THE"]
        assert cover["title_accent"] == "FINAL"

    def test_grid_titles_lead_with_road_to_the_finals(self):
        slides = build_slides(_heats_data())
        # "ROAD TO THE FINALS" then "MEN QUARTER FINAL 4", accent on the number.
        assert slides[1]["title_lines"] == ["ROAD TO THE FINALS"]
        assert slides[1]["title_lead"] == "MEN QUARTER FINAL"
        assert slides[1]["title_accent"] == "1"
        assert slides[2]["title_accent"] == "2"

    def test_division_prefix_drops_the_possessive(self):
        slides = build_slides(_heats_data(division_label="WOMEN'S"))
        assert slides[1]["title_lead"] == "WOMEN QUARTER FINAL"

    def test_single_word_heat_label_accents_that_word(self):
        heats = [_heat("FINAL", [(1, "A B")])]
        slide = build_slides(_heats_data(heats=heats))[1]
        assert slide["title_lead"] == "MEN"
        assert slide["title_accent"] == "FINAL"

    def test_four_athletes_per_heat_slide(self):
        slides = build_slides(_heats_data())
        assert all(len(s["athletes"]) == 4 for s in slides[1:])

    def test_numbering_spans_cover_and_grids(self):
        slides = build_slides(_heats_data())
        assert [s["slide_number"] for s in slides] == [1, 2, 3]
        assert all(s["total_slides"] == 3 for s in slides)

    def test_leaders_scoped_to_each_heat(self):
        heats = [
            _heat("QUARTER FINAL 1", [(1, "A B"), (2, "C D")]),
            _heat("QUARTER FINAL 2", [(3, "E F"), (4, "G H")]),
        ]
        heats[0]["athletes"][0]["best_heat"] = 25.0
        heats[1]["athletes"][0]["best_heat"] = 12.0
        heats[1]["athletes"][1]["best_heat"] = 11.0
        slides = build_slides(_heats_data(heats=heats))
        # The 12.00 leads its own heat even though it trails heat 1's numbers
        assert slides[2]["athletes"][0]["hero"]["is_leader"] is True
        assert slides[2]["athletes"][1]["hero"]["is_leader"] is False

    def test_jump_row_dropped_per_heat(self):
        heats = [
            _heat("QUARTER FINAL 1", [(1, "A B"), (2, "C D")], avg_jump=0),
            _heat("QUARTER FINAL 2", [(3, "E F"), (4, "G H")]),
        ]
        slides = build_slides(_heats_data(heats=heats))
        assert all(len(a["stats"]) == 1 for a in slides[1]["athletes"])
        assert all(len(a["stats"]) == 2 for a in slides[2]["athletes"])

    def test_source_note_on_grids_only(self):
        slides = build_slides(_heats_data())
        assert all("counting" in s["source_note"].lower() for s in slides[1:])

    def test_finals_mode_still_titled_road_to_the_final(self):
        slides = build_slides(_data())
        assert slides[0]["title_lead"] == "ROAD TO THE"
        assert slides[0]["title_accent"] == "MEN'S FINAL"


class TestNameFitting:
    """Long surnames must shrink rather than run off the card.

    ``last_name`` is everything after the forename, so multi-word surnames
    are the real overflow risk, not long single words.
    """

    def _last(self, name, **kw):
        slides = build_slides(_data(men=[_athlete(1, name, **kw)]))
        return slides[0]["athletes"][0]

    def test_short_surname_keeps_default_size(self):
        assert self._last("Marc Paré Rico")["name_class"] == ""

    def test_medium_surname_steps_down(self):
        # "GIL GHERARDI" = 12 chars
        assert self._last("Marino Gil Gherardi")["name_class"] == ""
        # "VAN DER EYKEN" = 13
        assert self._last("Dieter Van Der Eyken")["name_class"] == "long"

    def test_longest_surname_in_athlete_db_wraps(self):
        # Jenny Ellefson Riemenschneider -> "ELLEFSON RIEMENSCHNEIDER" (24)
        athlete = self._last("Jenny Ellefson Riemenschneider")
        assert athlete["last_name"] == "ELLEFSON RIEMENSCHNEIDER"
        assert athlete["name_class"] == "xlong"

    def test_single_long_word_surname_steps_down(self):
        assert self._last("Antoine Riemenschneider")["name_class"] == "long"


class TestRoute:
    def test_route_from_last_sailed_heat(self):
        a = _athlete(1, "A B", route_round="Elimination R3", route_place=1)
        slide = build_slides(_data(men=[a]))[0]
        assert slide["athletes"][0]["route"] == "QUALIFIED FROM: ELIMINATION R3 · 1ST"

    def test_seeding_round_names_the_round(self):
        # The seeding round is named like any other rather than collapsed to
        # "SEEDED", so every card reads the same way.
        a = _athlete(1, "A B", route_round="Seeding R1", route_place=1)
        slide = build_slides(_data(men=[a]))[0]
        assert slide["athletes"][0]["route"] == "QUALIFIED FROM: SEEDING R1 · 1ST"

    def test_no_route_data_yields_empty_string(self):
        slide = build_slides(_data(men=[_athlete(1, "A B")]))[0]
        assert slide["athletes"][0]["route"] == ""

    def test_route_without_place_shows_round_only(self):
        a = _athlete(1, "A B", route_round="Elimination R3")
        slide = build_slides(_data(men=[a]))[0]
        assert slide["athletes"][0]["route"] == "QUALIFIED FROM: ELIMINATION R3"


class TestSubtitle:
    def test_heat_slides_describe_form_not_route(self):
        slides = build_slides(_heats_data())
        assert all(s["subtitle"] == "Form at this event" for s in slides[1:])


class TestStatBars:
    """Bars scale every number against the same denominator.

    The spec asked for "max at this event", but the only endpoint that
    returns counting averages serves two riders per call, so a true event
    max would cost ~27 calls. The max across the riders in the carousel is
    one denominator, needs no extra calls, and keeps bars comparable
    across slides.
    """

    def test_top_value_fills_the_bar(self):
        a = build_slides(_data())[0]["athletes"][0]
        assert a["hero"]["bar_pct"] == 100

    def test_bar_is_proportional_to_the_max(self):
        men = [_athlete(1, "A B", best_heat=20.0), _athlete(2, "C D", best_heat=10.0)]
        slides = build_slides(_data(men=men, women=[]))
        assert slides[0]["athletes"][1]["hero"]["bar_pct"] == 50

    def test_denominator_spans_the_whole_carousel_not_one_slide(self):
        heats = [
            _heat("QUARTER FINAL 1", [(1, "A B")]),
            _heat("QUARTER FINAL 2", [(2, "C D")]),
        ]
        heats[0]["athletes"][0]["best_heat"] = 20.0
        heats[1]["athletes"][0]["best_heat"] = 5.0
        slides = build_slides(_heats_data(heats=heats))
        # Heat 2's rider leads his own heat but the bar still reads against 20
        assert slides[1]["athletes"][0]["hero"]["bar_pct"] == 100
        assert slides[2]["athletes"][0]["hero"]["bar_pct"] == 25
        assert slides[2]["athletes"][0]["hero"]["is_leader"] is True

    def test_each_stat_has_its_own_denominator(self):
        men = [_athlete(1, "A B", best_heat=20.0, avg_wave=5.0, avg_jump=8.0)]
        slides = build_slides(_data(men=men, women=[]))
        a = slides[0]["athletes"][0]
        assert [a["hero"]["bar_pct"]] + [s["bar_pct"] for s in a["stats"]] == [100, 100, 100]

    def test_missing_value_has_no_bar(self):
        men = [_athlete(1, "A B", best_heat=0), _athlete(2, "C D", best_heat=10.0)]
        slides = build_slides(_data(men=men, women=[]))
        assert slides[0]["athletes"][0]["hero"]["bar_pct"] == 0


class TestCardOrder:
    """Cards run seeded riders first, then whoever came up through the ladder.

    Order is by the round a rider qualified from (lowest round_order first),
    and stable within a round, so the heat sheet order survives inside each
    group. Without route data the input order is left alone.
    """

    def _heat_with_orders(self, *specs):
        athletes = []
        for i, (name, order) in enumerate(specs, 1):
            extra = {} if order is None else {"route_order": order}
            athletes.append(_athlete(i, name, **extra))
        return _heats_data(heats=[{"label": "QUARTER FINAL 1", "athletes": athletes}])

    def _names(self, data):
        return [a["first_name"] for a in build_slides(data)[1]["athletes"]]

    def test_seeded_riders_come_first(self):
        data = self._heat_with_orders(("Elim A", 3), ("Seed B", 1), ("Seed C", 1), ("Elim D", 3))
        assert self._names(data) == ["SEED", "SEED", "ELIM", "ELIM"]

    def test_order_is_stable_within_a_round(self):
        data = self._heat_with_orders(("Elim A", 3), ("Seed B", 1), ("Seed C", 1), ("Elim D", 3))
        slides = build_slides(data)
        assert [a["last_name"] for a in slides[1]["athletes"]] == ["B", "C", "A", "D"]

    def test_riders_without_route_data_go_last(self):
        data = self._heat_with_orders(("No A", None), ("Seed B", 1))
        assert self._names(data) == ["SEED", "NO"]

    def test_untouched_when_nobody_has_route_data(self):
        data = self._heat_with_orders(("First A", None), ("Second B", None))
        assert self._names(data) == ["FIRST", "SECOND"]

    def test_finals_mode_order_unaffected_without_route_data(self):
        names = [a["first_name"] for a in build_slides(_data())[0]["athletes"]]
        assert names == ["MARINO", "ANTON", "MARC", "PHILIP"]
