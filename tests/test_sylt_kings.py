"""Tests for the Kings / Queens of Sylt carousel."""

import pytest

from pipeline import sylt_kings
from pipeline.captions import build_caption
from pipeline.queries import build_sylt_editions_query, build_sylt_kings_query
from pipeline.sylt_kings import build_sylt_kings_slides
from pipeline.templates import get_dummy_data, render_template


EDITIONS = {"editions": 10, "first_year": 2008, "last_year": 2025}


def _row(name, athlete_id, wins, podiums, starts=8, best=1, placings=""):
    return {
        "athlete": name,
        "nationality": "Spain",
        "athlete_id": athlete_id,
        "photo_url": None,
        "wins": wins,
        "podiums": podiums,
        "starts": starts,
        "best_finish": best,
        "avg_finish": 4.0,
        "placings": placings,
    }


ROWS = [
    _row("Victor Fernandez", 56, 2, 5, placings="2008:1,2012:3,2017:1,2018:3,2024:3"),
    _row("Marc Pare Rico", 97, 2, 3, placings="2022:2,2024:1,2025:1"),
    _row("Marcilio Browne", 68, 0, 4, best=2, placings="2017:2,2019:2,2022:3,2024:2"),
]


# ── Query ──

def test_query_counts_shared_titles_but_not_untied_fleets():
    """A two-way tie is a shared title; a whole fleet tied is no result.

    2005 records 8 men first and 2023 Wave Men records 16, so a query that
    trusted place='1' would hand three riders a title they did not win. But
    Sylt 2008 Wave Women ended joint first, and dropping that edition cost
    Iballa Ruano Moreno a real title, so the test is a range and not equality.
    """
    sql, params = build_sylt_kings_query("Men")
    assert "HAVING SUM(r2.place = '1') BETWEEN 1 AND 2" in sql
    assert params == ("Wave Men", "Wave Men")


def test_podiums_exclude_the_wins():
    """"2 titles, 5 podiums" is unreadable if the 5 already contains the 2."""
    sql, _ = build_sylt_kings_query("Men")
    assert "SUM(CAST(r.place AS UNSIGNED) BETWEEN 2 AND 3) AS podiums" in sql
    assert "SUM(CAST(r.place AS UNSIGNED) <= 3)" not in sql


def test_query_applies_the_inclusion_rule_and_title_order():
    sql, _ = build_sylt_kings_query("Women")
    assert "HAVING wins >= 1 OR podiums >= 2" in sql
    assert "ORDER BY wins DESC, podiums DESC" in sql


def test_editions_query_uses_the_same_winner_test():
    """The stated sample and the ranking must be drawn from one filter."""
    kings_sql, _ = build_sylt_kings_query("Men")
    ed_sql, ed_params = build_sylt_editions_query("Men")
    assert "HAVING SUM(r.place = '1') BETWEEN 1 AND 2" in ed_sql
    assert "HAVING SUM(r2.place = '1') BETWEEN 1 AND 2" in kings_sql
    assert ed_params == ("Wave Men",)


# ── Slides ──

def test_slide_sequence_is_cover_riders_chart_cta():
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    assert [s["type"] for s in slides] == [
        "sylt_cover", "sylt_rider", "sylt_rider", "sylt_rider",
        "sylt_table", "analysis_cta",
    ]
    assert all(s["total_slides"] == 6 for s in slides)
    assert [s["slide_number"] for s in slides] == [1, 2, 3, 4, 5, 6]


def test_every_qualifying_rider_gets_a_card_counted_down_to_first():
    """Cards run worst to best so the top rider lands before the chart."""
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    cards = [s for s in slides if s["type"] == "sylt_rider"]
    assert [c["athlete_name"] for c in cards] == [
        "Marcilio Browne", "Marc Pare Rico", "Victor Fernandez",
    ]
    assert slides[slides.index(cards[-1]) + 1]["type"] == "sylt_table"


def test_only_the_top_card_is_labelled():
    """The countdown carries the order, so the numbers come off the cards."""
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    cards = [s for s in slides if s["type"] == "sylt_rider"]
    assert [c["rank_label"] for c in cards] == ["", "", "MOST SUCCESSFUL RIDER"]


def test_riders_level_on_titles_and_podiums_share_a_rank():
    """Two riders with the same record must not be split by the tie-break."""
    rows = [
        _row("Koster", 1, 2, 5),
        _row("Fernandez", 2, 2, 5),
        _row("Pare", 3, 2, 3),
        _row("Mussolini", 4, 2, 3),
        _row("Browne", 5, 0, 4),
    ]
    table = build_sylt_kings_slides(rows, "Men", EDITIONS)[-2]["rows"]
    assert [r["rank"] for r in table] == [1, 1, 3, 3, 5]


def test_both_joint_leaders_are_labelled():
    rows = [_row("Koster", 1, 2, 5), _row("Fernandez", 2, 2, 5), _row("Browne", 3, 0, 4)]
    cards = [s for s in build_sylt_kings_slides(rows, "Men", EDITIONS)
             if s["type"] == "sylt_rider"]
    assert [c["rank_label"] for c in cards] == [
        "", "MOST SUCCESSFUL RIDER", "MOST SUCCESSFUL RIDER",
    ]


def test_sex_picks_the_title_word():
    men = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    women = build_sylt_kings_slides(ROWS, "Women", EDITIONS)
    assert men[0]["title_word"] == "KINGS"
    assert women[0]["title_word"] == "QUEENS"
    assert women[-2]["slide_title"] == "QUEENS OF SYLT"


def test_card_without_a_title_says_what_it_is_there_on():
    """A podium-only rider's card must not read like a champion's."""
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    browne = next(s for s in slides if s.get("athlete_name") == "Marcilio Browne")
    assert browne["is_champion"] is False
    # The span is the rider's own first and last Sylt, not the sample's
    # 2008-2025: "4 podiums" over four starts and over eighteen years are
    # different records.
    assert browne["years_line"] == "4 podiums at Sylt World Cup, 2017-2024"

    victor = next(s for s in slides if s.get("athlete_name") == "Victor Fernandez")
    assert victor["is_champion"] is True
    # The venue and the rider's own span go on every card, champions too.
    assert victor["years_line"] == "Won 2008, 2017 at Sylt World Cup, 2008-2024"


def test_query_returns_placings_for_the_year_lines():
    sql, _ = build_sylt_kings_query("Men")
    assert "AS placings" in sql


def test_card_falls_back_to_portrait_when_no_action_shot_resolves():
    """Riders with no landscape shot keep their card, in the portrait layout."""
    slides = build_sylt_kings_slides([_row("Nobody Here", 999999, 1, 2)], "Men", EDITIONS)
    card = slides[1]
    assert card["photo_mode"] == "portrait"


def test_action_shot_is_searched_across_every_sylt_edition(monkeypatch):
    """A venue post spans years, so one event folder cannot serve every rider.

    Marc Pare last sailed Sylt in 2025 and Alex Mussolini in 2019; both need a
    photo, so the lookup walks the Sylt folders newest first.
    """
    seen = []
    FLAT = "file:///repo/assets/photos/7.jpg"
    HIT = "file:///repo/assets/photos/events/48/7.jpg"

    def fake_hero(athlete_id, event_id):
        """As the real one: it runs its own chain to h2h and the flat photo.

        So an event with nothing of its own still answers with a url. The
        search must keep walking on that, or it stops at the newest folder for
        every rider who owns any photo at all and never reaches the older
        Sylt editions.
        """
        seen.append(event_id)
        return HIT if event_id == 48 else FLAT

    monkeypatch.setattr(sylt_kings, "resolve_hero_url", fake_hero)
    monkeypatch.setattr(sylt_kings, "resolve_hero_focus", lambda a, e, d: "20% 60%")

    card = build_sylt_kings_slides([_row("Late Finder", 7, 1, 2)], "Men", EDITIONS)[1]
    assert seen[:4] == [16, 27, 39, 48]  # newest Sylt first, stops on the real hit
    assert card["photo_mode"] == "action"
    assert card["photo_url"] == HIT
    assert card["photo_focus"] == "20% 60%"


def _card(slides, name):
    return next(s for s in slides if s.get("athlete_name") == name)


def test_stats_lead_on_titles():
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    victor = _card(slides, "Victor Fernandez")
    labels = [s["label"] for s in victor["stats"]]
    assert labels == ["Titles", "Podiums", "Appearances", "Best"]
    assert [s["note"] for s in victor["stats"][:2]] == ["", "2nd or 3rd"]
    assert victor["stats"][0]["value"] == "2"
    assert victor["stats"][1]["value"] == "5"
    assert victor["stats"][3]["value"] == "1ST"


def test_best_stat_names_every_year_the_rider_matched_it():
    """2nd once and 2nd three times are the same cell without the years."""
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    browne = _card(slides, "Marcilio Browne")["stats"][3]
    assert browne["value"] == "2ND"
    assert browne["note"] == "2017, 2019, 2024"

    victor = _card(slides, "Victor Fernandez")["stats"][3]
    assert victor["value"] == "1ST"
    assert victor["note"] == "2008, 2017"


def test_best_stat_survives_a_missing_placings_column():
    slides = build_sylt_kings_slides([_row("No Years", 1, 1, 2, best=3)], "Men", EDITIONS)
    best = slides[1]["stats"][3]
    assert best["value"] == "3RD"
    assert best["note"] == ""


def test_win_years_are_derived_from_the_placings():
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    assert (_card(slides, "Marc Pare Rico")["years_line"]
            == "Won 2024, 2025 at Sylt World Cup, 2022-2025")


def test_sample_line_states_the_editions_counted():
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    assert slides[0]["sample_line"] == "10 editions, 2008-2025"
    assert slides[-2]["sample_line"] == "10 editions, 2008-2025"


def test_sample_line_survives_missing_edition_counts():
    slides = build_sylt_kings_slides(ROWS, "Men", None)
    assert slides[0]["sample_line"] == "Sylt, Germany"


def test_criteria_is_stated_on_the_cover_and_the_chart():
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    expected = ("Riders with at least 1 win or 2 podiums \u00b7 "
                "Titles are wins, podiums are 2nd and 3rd places")
    assert slides[0]["criteria_note"] == expected
    assert slides[-2]["criteria_note"] == expected


# ── Chart ──

def test_table_keeps_ranking_order_not_the_countdown_order():
    """The cards count down; the table is the ranking, so it reads 1 first."""
    table = build_sylt_kings_slides(ROWS, "Men", EDITIONS)[-2]["rows"]
    assert [r["rank"] for r in table] == [1, 2, 3]
    assert [r["athlete"] for r in table] == [
        "Victor Fernandez", "Marc Pare Rico", "Marcilio Browne",
    ]


def test_table_carries_titles_podiums_appearances_and_the_best_finish():
    table = build_sylt_kings_slides(ROWS, "Men", EDITIONS)[-2]["rows"]
    victor, _, browne = table
    assert (victor["wins"], victor["podiums"], victor["starts"]) == (2, 5, 8)
    assert (browne["wins"], browne["podiums"], browne["starts"]) == (0, 4, 8)
    assert browne["best_label"] == "2ND"
    assert browne["best_years"] == "2017, 2019, 2024"


def test_empty_roster_renders_a_carousel_without_cards():
    slides = build_sylt_kings_slides([], "Men", EDITIONS)
    assert [s["type"] for s in slides] == ["sylt_cover", "sylt_table", "analysis_cta"]
    assert slides[1]["rows"] == []


# ── Rendering ──

@pytest.mark.parametrize("sex", ["Men", "Women"])
def test_every_slide_renders(sex):
    slides = build_sylt_kings_slides(ROWS, sex, EDITIONS)
    for slide in slides:
        html = render_template(f"carousel/slide_{slide['type']}", slide)
        assert "<html" in html.lower()


def test_rider_card_renders_its_numbers_and_years():
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    html = render_template("carousel/slide_sylt_rider", _card(slides, "Victor Fernandez"))
    assert "FERNANDEZ" in html
    assert "WON 2008, 2017" in html.upper()
    assert "PODIUMS" in html.upper()


def test_rider_card_renders_the_best_finish_years():
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    html = render_template("carousel/slide_sylt_rider", _card(slides, "Marcilio Browne"))
    assert "2ND" in html
    assert "2017, 2019, 2024" in html


def test_table_renders_every_rider_and_the_criteria_footnote():
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    html = render_template("carousel/slide_sylt_table", slides[-2])
    assert "at least 1 win or 2 podiums" in html
    for row in ROWS:
        assert row["athlete"].upper() in html


def test_dummy_data_drives_the_full_men_carousel():
    data = get_dummy_data("sylt_kings")
    slides = build_sylt_kings_slides(data["rows"], data["sex"], data["editions"])
    assert len(slides) == 10  # cover + 7 riders + chart + cta
    for slide in slides:
        render_template(f"carousel/slide_{slide['type']}", slide)


# ── Caption ──

def test_caption_names_the_title_leader_and_the_rule():
    data = {"rows": ROWS, "sex": "Men", "editions": EDITIONS}
    caption = build_caption("sylt_kings", data, {})
    assert "King of Sylt" in caption
    assert "Victor Fernandez leads on titles with 2" in caption
    assert "at least 1 win or 2 podiums" in caption
    assert "10 editions, 2008 to 2025" in caption


def test_caption_separates_most_titles_from_most_podiums():
    """When the leader is not the most decorated, the caption must say so."""
    rows = [
        _row("Winner", 2, 4, 4, placings="2016:1,2017:1,2018:1,2019:1"),
        _row("Consistent", 1, 0, 6, best=2, placings="2016:2,2017:2"),
    ]
    caption = build_caption("sylt_kings", {"rows": rows, "sex": "Women", "editions": EDITIONS}, {})
    assert "Queen of Sylt" in caption
    assert "Winner leads on titles with 4" in caption
    assert "Consistent has the most podiums with 6" in caption


def test_a_shared_title_year_is_asterisked_on_the_card_and_explained():
    """The titles outnumber the editions unless the shared year is marked."""
    rows = [
        _row("Iballa Ruano Moreno", 63, 5, 2, placings="2008:1,2009:1,2012:1,2016:1,2017:1"),
        _row("Daida Ruano Moreno", 64, 1, 4, placings="2008:1,2009:2,2012:2,2016:2,2017:3"),
    ]
    slides = build_sylt_kings_slides(rows, "Women", EDITIONS)
    iballa = _card(slides, "Iballa Ruano Moreno")
    assert iballa["years_line"].startswith("Won 2008*, 2009")
    assert "2008 title shared" in slides[0]["criteria_note"]

    table = next(s for s in slides if s["type"] == "sylt_table")
    assert "2008 title shared" in table["criteria_note"]
    assert "2008*" in table["rows"][0]["best_years"]


def test_no_asterisk_when_no_title_is_shared():
    """The men's record has no shared edition, so it must carry no asterisk."""
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS)
    assert "*" not in slides[0]["criteria_note"]
    assert all("*" not in s.get("years_line", "") for s in slides)


def test_caption_notes_a_shared_title():
    """Sylt 2008 was won jointly, so the title counts must be explained.

    Without the note the caption claims five titles from a sample where only
    one edition had two winners, which reads as an arithmetic error.
    """
    rows = [
        _row("Iballa Ruano Moreno", 63, 5, 2, placings="2008:1,2009:1,2012:1,2016:1,2017:1"),
        _row("Daida Ruano Moreno", 64, 1, 4, placings="2008:1,2009:2,2012:2,2016:2,2017:3"),
    ]
    caption = build_caption("sylt_kings", {"rows": rows, "sex": "Women",
                                           "editions": EDITIONS}, {})
    assert "2008 is a shared title" in caption
    assert "Iballa Ruano Moreno and Daida Ruano Moreno" in caption


def test_caption_omits_the_note_when_no_title_is_shared():
    """No men's edition is shared, so the men's caption must not claim one."""
    caption = build_caption("sylt_kings", {"rows": ROWS, "sex": "Men",
                                           "editions": EDITIONS}, {})
    assert "shared title" not in caption


def test_caption_has_no_em_dashes():
    caption = build_caption("sylt_kings", {"rows": ROWS, "sex": "Men", "editions": EDITIONS}, {})
    assert "—" not in caption
