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


def test_caption_credits_the_photographers_and_the_tour():
    """A card is someone else's photograph, so the caption must name them.

    The handles come from the folder each photo actually came from, and the
    tour handle closes the line because every Sylt folder is filled from the
    PWA library.
    """
    data = {"rows": ROWS, "sex": "Men", "editions": EDITIONS,
            "photo_credits": ["@jcwindsurf", "@pwaworldtour"]}
    caption = build_caption("sylt_kings", data, {})
    assert "\U0001f4f8 @jcwindsurf | @pwaworldtour" in caption


def test_credits_read_the_folder_the_photo_came_from(monkeypatch):
    """A venue post spans twenty years, so two riders' shots can be nine years
    and two photographers apart. Reading the newest folder for everyone would
    credit the wrong one."""
    monkeypatch.setattr(sylt_kings, "_hero",
                        lambda aid, events=None: ("x.jpg", "50% 50%",
                                                  {1: 16, 2: "sylt2019"}.get(aid)))
    monkeypatch.setattr(sylt_kings, "resolve_photo_credit",
                        lambda aid, ev: {16: "@newer", "sylt2019": "@older"}.get(ev, ""))
    credits = sylt_kings.sylt_photo_credits([{"athlete_id": 1}, {"athlete_id": 2}])
    assert credits == ["@newer", "@older", "@pwaworldtour"]


def test_untagged_photos_credit_only_the_tour(monkeypatch):
    """A missing credit beats a guessed one, but the library still gets named."""
    monkeypatch.setattr(sylt_kings, "_hero", lambda aid, events=None: ("x.jpg", "50% 50%", 16))
    monkeypatch.setattr(sylt_kings, "resolve_photo_credit", lambda aid, ev: "")
    assert sylt_kings.sylt_photo_credits([{"athlete_id": 1}]) == ["@pwaworldtour"]


def test_no_sylt_photo_credits_nobody(monkeypatch):
    """Nothing resolved from a Sylt folder means no photograph to credit."""
    monkeypatch.setattr(sylt_kings, "_hero", lambda aid, events=None: ("flat.jpg", "50% 50%", None))
    assert sylt_kings.sylt_photo_credits([{"athlete_id": 1}]) == []


def test_headshot_photographers_are_credited(monkeypatch):
    """The table slide is built from headshots, so those are photographs on the
    post too. Crediting only the rider cards drops whoever shot the thumbnails.
    """
    monkeypatch.setattr(sylt_kings, "_hero", lambda aid, events=None: ("x.jpg", "50% 50%", 16))
    monkeypatch.setattr(sylt_kings, "resolve_photo_credit", lambda aid, ev: "@action")
    monkeypatch.setattr(sylt_kings, "resolve_face_credit",
                        lambda aid: "@portrait" if aid == 2 else "")
    credits = sylt_kings.sylt_photo_credits([{"athlete_id": 1}, {"athlete_id": 2}])
    assert credits == ["@action", "@portrait", "@pwaworldtour"]


def test_a_headshot_photographer_is_not_repeated(monkeypatch):
    """One photographer who shot both the action frame and the headshot is
    named once, not twice."""
    monkeypatch.setattr(sylt_kings, "_hero", lambda aid, events=None: ("x.jpg", "50% 50%", 16))
    monkeypatch.setattr(sylt_kings, "resolve_photo_credit", lambda aid, ev: "@jc")
    monkeypatch.setattr(sylt_kings, "resolve_face_credit", lambda aid: "@jc")
    assert sylt_kings.sylt_photo_credits([{"athlete_id": 1}]) == ["@jc", "@pwaworldtour"]


def test_cover_carries_the_discipline_as_its_own_field():
    """The cover sets the discipline apart from the venue, so it can be styled
    on its own. One joined string would force the styling onto the venue too.
    """
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS, "Freestyle")
    cover = slides[0]
    assert cover["eyebrow_venue"] == "Sylt, Germany"
    assert cover["eyebrow_discipline"] == "Freestyle"
    # The table slide keeps the joined line it already had.
    table = next(s for s in slides if s["type"] == "sylt_table")
    assert table["eyebrow"] == "Sylt, Germany \u00b7 Freestyle"


def test_a_long_name_is_abbreviated_in_the_table():
    """The table cell is nowrap with an ellipsis, so a name past its width is
    cut mid-word: "STEVEN VAN BROECKHOVEN" rendered as "STEVEN VAN BROECK...".
    Dropping the first name to an initial keeps the surname, which is the part
    that identifies the rider.
    """
    rows = [_row("Steven Van Broeckhoven", 890, 0, 5),
            _row("Amado Vrieswijk", 113, 1, 3)]
    table = sylt_kings._table_rows(rows)
    assert table[0]["athlete"] == "S. Van Broeckhoven"
    # A name that already fits is left exactly as it is.
    assert table[1]["athlete"] == "Amado Vrieswijk"


def test_a_single_word_name_is_never_abbreviated():
    """There is no first name to drop, so the name has to stand as it is."""
    rows = [_row("Van Broeckhoven", 9001, 0, 5)]  # no NAME_OVERRIDES entry
    assert sylt_kings._table_rows(rows)[0]["athlete"] == "Van Broeckhoven"


def test_the_caption_uses_the_same_names_as_the_slides():
    """The cards apply NAME_OVERRIDES, the caption read the raw column, so a
    post showed "GOLLITO ESTREDO" on the slide and Jose "Gollito" Estredo in
    its own caption, quotes and all. Same rider, same name, both places.
    """
    rows = [_row("Jose \"Gollito\" Estredo", 202, 6, 1),
            _row("Van Broeckhoven", 890, 0, 5)]
    caption = build_caption("sylt_kings", {"rows": rows, "sex": "Men",
                                           "editions": EDITIONS}, {})
    assert "Gollito Estredo" in caption
    assert '"Gollito"' not in caption
    assert "Steven Van Broeckhoven" in caption


def _era_row(name, athlete_id, fin_wins, foil_wins, **kw):
    """A slalom row: the same shape plus the six era columns."""
    row = _row(name, athlete_id, fin_wins + foil_wins, kw.pop("podiums", 0))
    row.update({
        "fin_wins": fin_wins, "foil_wins": foil_wins,
        "fin_podiums": kw.pop("fin_podiums", 0),
        "foil_podiums": kw.pop("foil_podiums", 0),
        "fin_starts": kw.pop("fin_starts", 8),
        "foil_starts": kw.pop("foil_starts", 0),
    })
    row["podiums"] = row["fin_podiums"] + row["foil_podiums"]
    row["starts"] = row["fin_starts"] + row["foil_starts"]
    return row


def test_every_counter_on_a_slalom_card_carries_the_era_split():
    """Sylt raced on a fin to 2018 and on a foil from 2022, and the post ranks
    both. A bare "2 titles" is Bjorn Dunkerbeck twice on a fin against fleets
    of 120 and Johan Soe twice on a foil from four starts, and the number
    alone cannot tell them apart.
    """
    row = _era_row("Matteo Iachino", 428, 2, 0, fin_podiums=0, foil_podiums=3,
                   fin_starts=9, foil_starts=4)
    card = sylt_kings._rider_slide(row, 2, "16 editions", frozenset())
    notes = {stat["label"]: stat["note"] for stat in card["stats"]}
    assert notes["Titles"] == "2 FIN"
    assert notes["Podiums"] == "3 FOIL"
    assert notes["Appearances"] == "9 FIN \u00b7 4 FOIL"


def test_an_empty_era_is_dropped_from_titles_and_podiums():
    """A rider who won in one era only has a one-word record. "0 FOIL" spends
    a line saying nothing happened.
    """
    row = _era_row("Antoine Albeau", 700, 4, 0, fin_podiums=5, fin_starts=12,
                   foil_starts=1)
    card = sylt_kings._rider_slide(row, 1, "16 editions", frozenset())
    notes = {stat["label"]: stat["note"] for stat in card["stats"]}
    assert notes["Titles"] == "4 FIN"
    assert notes["Podiums"] == "5 FIN"


def test_appearances_keeps_both_halves_of_the_split():
    """There the zero is the point: twelve fin starts against one foil start
    is how a reader places an average finish that spans the boundary.
    """
    row = _era_row("Bjorn Dunkerbeck", 128, 2, 0, fin_podiums=2,
                   fin_starts=8, foil_starts=0)
    card = sylt_kings._rider_slide(row, 3, "16 editions", frozenset())
    notes = {stat["label"]: stat["note"] for stat in card["stats"]}
    assert notes["Appearances"] == "8 FIN \u00b7 0 FOIL"


def test_a_wave_card_keeps_its_own_notes():
    """The wave and freestyle records are single-era and their query returns
    no era columns, so those cards must not grow an empty split.
    """
    card = sylt_kings._rider_slide(_row("Philip Koster", 49, 3, 2),
                                   1, "10 editions", frozenset())
    notes = {stat["label"]: stat["note"] for stat in card["stats"]}
    assert notes["Titles"] == ""
    assert notes["Podiums"] == "2nd or 3rd"
    assert notes["Appearances"] == ""


def test_the_table_names_the_era_a_riders_titles_came_from():
    """One word, not three split counters: the row has space for a number and
    a short line, and every champion at Sylt won in one era only.
    """
    rows = [_era_row("Antoine Albeau", 700, 4, 0, fin_starts=13),
            _era_row("Johan Soe", 1423, 0, 2, fin_starts=2, foil_starts=2),
            _era_row("Cyril Moussilmani", 656, 0, 0, fin_podiums=4)]
    table = sylt_kings._table_rows(rows)
    assert table[0]["titles_era"] == "FIN"
    assert table[1]["titles_era"] == "FOIL"
    # No titles, so there is no era to name and the line is left off.
    assert table[2]["titles_era"] == ""


def test_a_rider_who_won_in_both_eras_gets_both_named():
    """Nobody has yet, but 2017 and 2018 ran fin and foil in the same week,
    so the missing foil editions could produce one. The tag must not silently
    pick a side.
    """
    rows = [_era_row("Future Champion", 9002, 1, 1, fin_starts=4,
                     foil_starts=2)]
    assert sylt_kings._table_rows(rows)[0]["titles_era"] == "FIN \u00b7 FOIL"


def test_the_table_leaves_the_era_off_a_wave_record():
    """Same rule as the cards: no era columns, no era line."""
    table = sylt_kings._table_rows([_row("Philip Koster", 49, 3, 2)])
    assert table[0]["titles_era"] == ""


def test_the_closing_table_runs_over_two_slides_when_it_is_too_long():
    """The table was laid out for the eight riders a wave record produces.
    Slalom returns thirteen, and thirteen rows squeezed into the same height
    is a table nobody reads on a phone.
    """
    table = [{"rank": i} for i in range(1, 14)]
    slides = sylt_kings._table_slides(table, "criteria")
    assert len(slides) == 2
    # A fixed chunk, the way the top 10 carousel already splits a long table.
    assert [len(s["rows"]) for s in slides] == [8, 5]
    assert [s["label"] for s in slides] == ["Positions 1\u20138",
                                            "Positions 9\u201313"]


def test_a_short_chunk_keeps_full_slide_row_heights():
    """The rows share out whatever space is left, so five rows sized to their
    own count stand taller than eight and one table reads as two. Capacity is
    what the slide holds, not what this chunk was given.
    """
    slides = sylt_kings._table_slides([{"rank": i} for i in range(1, 14)], "c")
    assert [s["table_capacity"] for s in slides] == [8, 8]


def test_a_table_that_fits_stays_on_one_slide():
    """The wave and freestyle records must be untouched by the split, and a
    single table has no range worth naming.
    """
    slides = sylt_kings._table_slides([{"rank": i} for i in range(1, 9)], "c")
    assert len(slides) == 1
    assert slides[0]["label"] == ""


def test_only_the_last_table_slide_carries_the_criteria_note():
    """It qualifies the whole ranking. On both slides it invites the reader to
    check whether the two are saying different things.
    """
    slides = sylt_kings._table_slides([{"rank": i} for i in range(1, 14)],
                                      "at least 1 win")
    assert slides[0]["criteria_note"] == ""
    assert slides[1]["criteria_note"] == "at least 1 win"


def test_the_foil_years_are_named_not_inferred_from_the_discipline():
    """The PWA only renamed the discipline "Foil Slalom" in 2024, but Sylt
    was already racing on foils in 2022. Reading the era off the discipline
    string put Amado Vrieswijk's two foil titles in the fin column beside
    Bjorn Dunkerbeck's.
    """
    from pipeline.queries import SYLT_FOIL_SLALOM_YEARS, build_sylt_slalom_query
    assert 2022 in SYLT_FOIL_SLALOM_YEARS and 2023 in SYLT_FOIL_SLALOM_YEARS
    sql, _ = build_sylt_slalom_query("Men")
    assert "__FOIL_YEARS__" not in sql
    assert "r.year IN (2022, 2023)" in sql


def test_the_slalom_cover_is_about_speed_not_royalty():
    """A slalom record is won on speed, and "fastest" says that where "kings"
    only says the venue twice. SYLT stays on its own last line either way.
    """
    assert sylt_kings._title_lines("Men", "Slalom") == ("FASTEST", "MEN IN",
                                                        "SYLT")
    assert sylt_kings._title_lines("Men", "Wave") == ("KINGS", "OF", "SYLT")
    assert sylt_kings._title_lines("Women", "Freestyle") == ("QUEENS", "OF",
                                                             "SYLT")


def test_the_position_range_counts_rows_not_ranks():
    """Ranks tie: Micah Buzianis and Marco Lang are both 8th on one title and
    no podium. Read off the rank column the ranges came out "Positions 1-8"
    then "Positions 8-12", with 8 on both slides.
    """
    table = [{"rank": r} for r in
             [1, 2, 3, 4, 4, 6, 6, 8, 8, 10, 11, 12, 12]]
    slides = sylt_kings._table_slides(table, "c")
    assert [s["label"] for s in slides] == ["Positions 1\u20138",
                                            "Positions 9\u201313"]


def test_the_slalom_cover_carries_no_discipline_tag():
    """FASTEST MEN IN SYLT already says which race this is, and a SLALOM tag
    above it says it twice. KINGS OF SYLT does not, so the wave cover keeps
    its tag. The inside slides keep theirs either way: the headline is gone
    there and the eyebrow is all the reader has.
    """
    slalom = build_sylt_kings_slides(ROWS, "Men", EDITIONS, "Slalom")
    wave = build_sylt_kings_slides(ROWS, "Men", EDITIONS, "Wave")
    assert slalom[0]["eyebrow_discipline"] == ""
    assert wave[0]["eyebrow_discipline"] == "Wave"
    assert "Slalom" in slalom[-2]["eyebrow"]


def test_the_fine_print_names_the_discipline_the_cover_dropped():
    """The slalom cover has no tag, so the fine print is where the discipline
    gets said.
    """
    slalom = build_sylt_kings_slides(ROWS, "Men", EDITIONS, "Slalom")
    wave = build_sylt_kings_slides(ROWS, "Men", EDITIONS, "Wave")
    assert slalom[0]["criteria_note"].startswith("Slalom sailors with at ")
    assert wave[0]["criteria_note"].startswith("Riders with at ")


def test_the_foil_era_gets_its_own_badge():
    """The overall leader at Sylt will be a fin sailor for a long time yet:
    four foil editions against twelve fin ones. Without a second badge the
    newer era has no top and its riders are cards you pass on the way.
    """
    rows = [_era_row("Antoine Albeau", 700, 4, 0, fin_starts=12,
                     foil_starts=1),
            _era_row("Johan Soe", 1423, 0, 2, foil_starts=4)]
    slides = build_sylt_kings_slides(rows, "Men", EDITIONS, "Slalom")
    labels = {s["athlete_name"]: s["rank_label"]
              for s in slides if s["type"] == "sylt_rider"}
    assert labels["Antoine Albeau"] == "MOST SUCCESSFUL RIDER"
    assert labels["Johan Soe"] == "MOST SUCCESSFUL ON FOIL"


def test_riders_level_on_the_foil_era_share_the_badge():
    """Johan Soe and Amado Vrieswijk have two foil titles each and neither has
    beaten the other to anything.
    """
    rows = [_era_row("Antoine Albeau", 700, 4, 0, fin_starts=12),
            _era_row("Johan Soe", 1423, 0, 2, foil_starts=4),
            _era_row("Amado Vrieswijk", 113, 0, 2, fin_starts=4,
                     foil_starts=4)]
    assert sylt_kings._foil_leaders(rows) == {1, 2}


def test_the_overall_badge_wins_a_clash():
    """Two badges on one card is a card arguing with itself, and leading the
    whole record is the more decorated of the two things.
    """
    rows = [_era_row("Johan Soe", 1423, 0, 2, foil_starts=4)]
    slides = build_sylt_kings_slides(rows, "Men", EDITIONS, "Slalom")
    card = [s for s in slides if s["type"] == "sylt_rider"][0]
    assert card["rank_label"] == "MOST SUCCESSFUL RIDER"


def test_a_record_with_no_foil_results_badges_nothing_extra():
    """A wave post, and a slalom record from before 2022."""
    slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS, "Wave")
    cards = [s for s in slides if s["type"] == "sylt_rider"]
    assert not [c for c in cards if c["rank_label"] == "MOST SUCCESSFUL ON FOIL"]


def test_a_discipline_searches_its_own_photo_folder_first():
    """Amado Vrieswijk is in both the freestyle folder and the slalom one, so
    a fixed order gives one post the wrong photograph: a slalom card showing
    him mid-freestyle move, or a freestyle card on a slalom board.
    """
    assert sylt_kings._photo_events("Slalom")[0] == "syltslalom"
    assert sylt_kings._photo_events("Freestyle")[0] == "syltfreestyle"
    # Wave has no folder of its own; the numbered editions are its folders.
    assert sylt_kings._photo_events("Wave") == sylt_kings.SYLT_PHOTO_EVENTS


def test_reordering_drops_no_folder():
    """Putting one folder first must not lose the rest: a slalom rider with no
    slalom shot should still fall through to every other Sylt edition.
    """
    for discipline in ("Slalom", "Freestyle", "Wave"):
        assert (set(sylt_kings._photo_events(discipline))
                == set(sylt_kings.SYLT_PHOTO_EVENTS))


# ── The 2019 foil edition, and the era slide ──

def _slalom_row(name, athlete_id, placings, foil_years):
    """A slalom row carrying the two columns the era split reads."""
    row = _era_row(name, athlete_id, 1, 0)
    row["placings"] = placings
    row["foil_years"] = foil_years
    return row


SLALOM_ROWS = [
    _slalom_row("Antoine Albeau", 700, "2006:2,2007:1,2018:2", ""),
    _slalom_row("Nicolas Goyard", 1127, "2019:1,2023:3", "2019,2023"),
]


def test_the_2019_foil_edition_is_unioned_in_from_the_results_table():
    """Sylt raced a foil-only edition in 2019. It is in PWA_IWT_RESULTS but
    not in PWA_RANKINGS, so the rankings-only query dropped a whole edition
    and with it the venue's first foil champion.
    """
    from pipeline.queries import build_sylt_slalom_query
    sql, _ = build_sylt_slalom_query("Men")
    assert "PWA_IWT_RESULTS" in sql
    assert "UNION ALL" in sql


def test_the_missing_edition_test_is_on_year_and_era_not_year_alone():
    """2017 and 2018 each ran a fin slalom *and* a separate foil event. The
    rankings hold only the fin one, so a year-level "is this year missing?"
    would answer no and keep both foil editions out for good.
    """
    from pipeline.queries import build_sylt_slalom_query
    sql, _ = build_sylt_slalom_query("Men")
    anti = sql[sql.index("UNION ALL"):]
    assert "NOT EXISTS" in anti
    assert "rk.year = " in anti
    assert "era" in anti


def test_nicolas_goyard_is_bridged_across_the_two_id_spaces():
    """The two tables key riders differently: PWA_RANKINGS on a numeric pwa
    id (Goyard 1538), PWA_IWT_RESULTS on a name-sail string
    (Goyard_F-465). Only the string form is in ATHLETE_SOURCE_IDS, so
    without this bridge his 2019 win and his rankings placings become two
    separate cards.
    """
    from pipeline.queries import SLALOM_ATHLETE_ID_FALLBACK
    assert SLALOM_ATHLETE_ID_FALLBACK[1538] == 1127


def test_riders_group_on_identity_not_on_the_source_key():
    """Grouping on pwa_athlete_id splits any rider who appears in both
    sources. Grouping on the resolved athlete id alone would be worse: 548
    of 615 riders resolve to NULL and would collapse into one row. So the
    key is the resolved id when there is one and the source key when not.
    """
    from pipeline.queries import build_sylt_slalom_query
    sql, _ = build_sylt_slalom_query("Men")
    assert "GROUP BY p.pwa_athlete_id, a.id" not in sql
    assert "GROUP BY COALESCE(" in sql


def test_the_editions_count_includes_the_unioned_edition():
    """The sample line and the ranking have to describe the same record."""
    from pipeline.queries import build_sylt_slalom_editions_query
    sql, _ = build_sylt_slalom_editions_query("Men")
    assert "PWA_IWT_RESULTS" in sql
    assert "UNION ALL" in sql


def test_the_era_slide_follows_the_cover():
    """Every card carries a FIN or FOIL note and the years wear daggers, so
    the reader needs to know what the two eras are before the countdown
    starts, not after it.
    """
    slides = build_sylt_kings_slides(SLALOM_ROWS, "Men", EDITIONS, "Slalom")
    assert slides[0]["type"] == "sylt_cover"
    assert slides[1]["type"] == "sylt_eras"


def test_only_the_slalom_post_gets_an_era_slide():
    """Wave and freestyle at Sylt have never split by equipment, so the
    slide would explain a distinction the post does not make.
    """
    for discipline in ("Wave", "Freestyle"):
        slides = build_sylt_kings_slides(ROWS, "Men", EDITIONS, discipline)
        assert not any(s["type"] == "sylt_eras" for s in slides)


def test_the_era_slide_reads_its_years_from_the_record():
    """Not written down twice. The slide splits the years the rows actually
    contain on the same foil set that marks the daggers, so a slide and a
    card can never disagree about which era a year belongs to.
    """
    rows = [_slalom_row("A", 1, "2006:1,2018:2,2019:1,2022:3", "2019,2022")]
    eras = sylt_kings._era_lines(rows, {2019, 2022})
    assert [e["label"] for e in eras] == ["FIN", "FOIL"]
    assert eras[0]["years"] == "2006–2018"
    assert eras[1]["years"] == "2019–2022"


def test_the_era_slide_counts_editions_not_the_span():
    """Sylt ran no slalom in 2011 and the 2020 and 2021 events were
    cancelled, so 2006-2018 is twelve editions and not thirteen.
    """
    rows = [_slalom_row("A", 1, "2006:1,2007:1,2010:1,2012:1", "")]
    eras = sylt_kings._era_lines(rows, set())
    assert eras[0]["detail"] == "4 editions"
    assert len(eras) == 1


def test_an_era_with_one_edition_reads_as_a_year_not_a_range():
    """"2019-2019" is a range with nothing in it."""
    rows = [_slalom_row("A", 1, "2006:1,2019:1", "2019")]
    eras = sylt_kings._era_lines(rows, {2019})
    assert eras[1]["years"] == "2019"
    assert eras[1]["detail"] == "1 edition"
