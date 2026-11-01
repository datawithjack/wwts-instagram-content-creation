"""Tests for the Kings / Queens carousel at venues other than Sylt (#35)."""

import pytest

from pipeline import sylt_kings
from pipeline.captions import build_caption
from pipeline.queries import build_venue_kings_query
from pipeline.sylt_kings import build_sylt_kings_slides, sylt_photo_credits


def _row(name, athlete_id, wins, podiums, placings=""):
    return {
        "athlete": name, "nationality": "France", "athlete_id": athlete_id,
        "photo_url": None, "wins": wins, "podiums": podiums, "starts": 6,
        "best_finish": 1 if wins else 2, "avg_finish": 3.0, "placings": placings,
    }


ROWS = [
    _row("Sarah-Quita Offringa", 5, 4, 1, "2016:1,2019:1,2023:1,2024:2,2025:1"),
    _row("Sarah Hauser", 477, 1, 2, "2016:2,2023:3,2024:1"),
]


# ── Query ──

def test_venue_query_reads_both_sources_through_the_unified_view():
    """Aloha 2024 and 2025 are LiveHeats rows. The Sylt query reads PWA only
    and would drop Noireaux's third title and Offringa's fourth."""
    sql, params = build_venue_kings_query("Aloha", "Women")
    assert "ATHLETE_RESULTS_VIEW" in sql
    assert "source = 'PWA'" not in sql
    assert params == ("Wave Women", "%Aloha%", "Wave Women", "%Aloha%")


def test_venue_query_keeps_the_winner_test():
    sql, _ = build_venue_kings_query("Aloha", "Men")
    assert "BETWEEN 1 AND 2" in sql
    assert "HAVING wins >= 1 OR podiums >= 2" in sql
    assert "ORDER BY wins DESC, podiums DESC" in sql


def test_venue_query_merges_a_rider_split_across_sources():
    """Sarah Hauser is 477 on PWA rows and 554 on LiveHeats rows; split, her
    2024 Aloha title sits on a card of its own."""
    sql, _ = build_venue_kings_query("Aloha", "Women")
    assert "WHEN 554 THEN 477" in sql


def test_unknown_venue_is_refused():
    with pytest.raises(KeyError):
        build_venue_kings_query("Nowhere", "Men")


# ── Slides ──

def test_cover_and_eyebrow_name_the_venue():
    cover = build_sylt_kings_slides(ROWS, "Women", venue="Aloha")[0]
    assert cover["title_lines"] == ("QUEENS", "OF", "ALOHA")
    assert cover["eyebrow_venue"] == "Maui, Hawaii"
    assert cover["eyebrow"] == "Maui, Hawaii · Wave"
    # No editions passed, and the place is already in the eyebrow.
    assert cover["sample_line"] == ""


def test_cards_name_the_event_not_sylt():
    slides = build_sylt_kings_slides(ROWS, "Women", venue="Aloha")
    card = next(s for s in slides if s.get("athlete_name") == "Sarah Hauser")
    assert card["years_line"] == "Won 2024 at Aloha Classic, 2016-2024"
    assert all("Sylt" not in str(s) for s in slides)


def test_action_shot_is_searched_in_the_venues_own_folders(monkeypatch):
    seen = []
    monkeypatch.setattr(sylt_kings, "resolve_hero_url",
                        lambda a, e: seen.append(e) or "file:///flat.jpg")
    build_sylt_kings_slides([_row("Anyone", 7, 1, 2)], "Men", venue="Aloha")
    assert seen[:3] == [128, 134, 29]
    assert "sylt2019" not in seen


def test_sylt_is_still_the_default():
    cover = build_sylt_kings_slides(ROWS, "Men")[0]
    assert cover["title_lines"] == ("KINGS", "OF", "SYLT")
    assert cover["eyebrow_venue"] == "Sylt, Germany"


# ── A second venue and discipline: Yokosuka slalom ──

def test_wave_query_carries_no_era_columns():
    """Wave never split by equipment; an era column would put FIN on cards."""
    sql, _ = build_venue_kings_query("Aloha", "Men")
    assert "foil_wins" not in sql


def test_slalom_query_reads_every_slalom_spelling_with_the_era():
    """Yokosuka is 'Slalom Men' on a fin, 'Foil Men' 2017-2019 and
    'Slalom Foil Men' from 2024, so one label would drop most of the record."""
    sql, params = build_venue_kings_query("Yokosuka", "Men", "Slalom")
    for label in ("Slalom Men", "Foil Men", "Slalom Foil Men"):
        assert label in params
    assert "Slalom Foil Women" not in params
    assert "%Yokosuka%" in params
    for col in ("fin_wins", "foil_wins", "fin_years", "foil_years"):
        assert f"AS {col}" in sql
    # 2017 and 2018 ran a fin and a foil race each: two titles, not one.
    assert "GROUP BY r2.event_db_id, r2.division_label" in sql


YOKO_ROWS = [
    dict(_row("Fin Rider", 11, 2, 0, "2017:1:fin,2018:1:fin"),
         fin_wins=2, foil_wins=0, fin_podiums=0, foil_podiums=0,
         fin_starts=2, foil_starts=0, fin_years="2017,2018", foil_years=None),
    dict(_row("Foil Rider", 12, 2, 0, "2018:1:foil,2024:1:foil"),
         fin_wins=0, foil_wins=2, fin_podiums=0, foil_podiums=0,
         fin_starts=0, foil_starts=2, fin_years=None, foil_years="2018,2024"),
]


def test_yokosuka_slalom_builds_the_slalom_post():
    slides = build_sylt_kings_slides(YOKO_ROWS, "Men", discipline="Slalom",
                                     venue="Yokosuka")
    assert slides[0]["title_lines"] == ("FASTEST", "MEN IN", "YOKOSUKA")
    assert slides[0]["eyebrow_venue"] == "Yokosuka, Japan"
    assert any(s["type"] == "sylt_eras" for s in slides)
    card = next(s for s in slides if s.get("athlete_name") == "Foil Rider")
    assert "at Yokosuka World Cup" in card["years_line"]
    assert all("Sylt" not in str(s) for s in slides)


# ── Credits and caption ──

def test_no_tour_handle_is_guessed_for_a_venue_without_one(monkeypatch):
    monkeypatch.setattr(sylt_kings, "resolve_hero_url",
                        lambda a, e: f"file:///assets/photos/events/{e}/{a}.jpg")
    monkeypatch.setattr(sylt_kings, "resolve_photo_credit", lambda a, e: None)
    monkeypatch.setattr(sylt_kings, "resolve_face_credit", lambda a: None)
    assert sylt_photo_credits(ROWS, "Wave", venue="Aloha") == []
    assert sylt_photo_credits(ROWS, "Wave") == ["@pwaworldtour"]


def test_caption_asks_the_covers_question():
    caption = build_caption("sylt_kings", {
        "rows": ROWS, "sex": "Women", "discipline": "Wave", "venue": "Aloha"}, {})
    assert "Who is the Queen of Aloha?" in caption
    assert "Sylt" not in caption
