"""Photo mode for the top 10 carousel: 5 score slides, then one table of 10."""

import pytest

from pipeline.carousel import build_slides


def _entry(rank, athlete, score, athlete_id=None, **extra):
    entry = {
        "rank": rank,
        "athlete": athlete,
        "athlete_id": athlete_id,
        "country": "es",
        "score": score,
        "event": "Tenerife Grand Slam",
        "round": "Final",
        "heat": "",
        "counting": 1,
    }
    entry.update(extra)
    return entry


def _data(entries=None, **extra):
    data = {
        "title_gender": "Men's",
        "title_metric": "Waves",
        "title_year": 2026,
        "is_per_event": True,
        "event_name": "Tenerife Grand Slam",
        "photo_mode": True,
        "photo_event_id": 124,
        "entries": entries or [
            _entry(i, f"Rider {i}", 10.0 - i, athlete_id=i) for i in range(1, 11)
        ],
    }
    data.update(extra)
    return data


def test_slide_plan_is_cover_five_photos_table_cta():
    slides = build_slides(_data())
    assert [s["type"] for s in slides] == [
        "cover", "wave_photo", "wave_photo", "wave_photo", "wave_photo",
        "wave_photo", "table", "cta",
    ]


def test_photo_slides_count_down_so_number_one_lands_last():
    slides = build_slides(_data())
    photos = [s for s in slides if s["type"] == "wave_photo"]
    assert [s["rank"] for s in photos] == [5, 4, 3, 2, 1]
    assert [s["rank_label"] for s in photos] == ["5TH", "4TH", "3RD", "2ND", "1ST"]


def test_photo_slides_are_literal_top_five_not_deduped_by_rider():
    """A rider holding two of the top five gets two slides.

    The post ranks waves, not riders. Tenerife 2026 men is the live case:
    Pare takes 1 and 2, Koster takes 4 and 5.
    """
    entries = [
        _entry(1, "Marc Pare Rico", 9.38, athlete_id=97),
        _entry(2, "Marc Pare Rico", 8.75, athlete_id=97),
        _entry(3, "Julian Salmonn", 8.50, athlete_id=65),
        _entry(4, "Philip Koster", 8.12, athlete_id=49),
        _entry(5, "Philip Koster", 8.12, athlete_id=49),
    ] + [_entry(i, f"Rider {i}", 8.0 - i * 0.1, athlete_id=i) for i in range(6, 11)]

    photos = [s for s in build_slides(_data(entries)) if s["type"] == "wave_photo"]
    assert [s["name"] for s in photos] == [
        "Philip Koster", "Philip Koster", "Julian Salmonn",
        "Marc Pare Rico", "Marc Pare Rico",
    ]
    assert [s["score"] for s in photos] == [8.12, 8.12, 8.50, 8.75, 9.38]


def test_rank_chip_names_what_is_being_counted():
    """A bare "5TH" on a photo of a rider reads as their event placing."""
    photos = [s for s in build_slides(_data()) if s["type"] == "wave_photo"]
    assert all(s["rank_suffix"] == "BEST WAVE" for s in photos)

    jumps = _data(title_metric="Jumps")
    photos = [s for s in build_slides(jumps) if s["type"] == "wave_photo"]
    assert all(s["rank_suffix"] == "BEST JUMP" for s in photos)


def test_photo_mode_title_drops_the_ten():
    """The cover promising 10 then opening a 5-4-3 countdown reads as a restart."""
    assert build_slides(_data())[0]["title"] == "MEN'S TOP WAVES"

    default = _data()
    default["photo_mode"] = False
    assert build_slides(default)[0]["title"] == "MEN'S TOP 10 WAVES"


def test_table_slide_carries_all_ten_rows_compact():
    slides = build_slides(_data())
    table = next(s for s in slides if s["type"] == "table")
    assert len(table["rows"]) == 10
    assert table["compact"] is True


def test_names_split_into_forename_and_surname():
    entries = [_entry(1, "Marc Pare Rico", 9.38, athlete_id=97)] + [
        _entry(i, f"Rider {i}", 9.0 - i, athlete_id=i) for i in range(2, 11)
    ]
    top = [s for s in build_slides(_data(entries)) if s["type"] == "wave_photo"][-1]
    assert top["first_name"] == "MARC"
    assert top["last_name"] == "PARE RICO"


def test_single_word_name_leaves_surname_empty():
    entries = [_entry(1, "Kauli", 9.38, athlete_id=1)] + [
        _entry(i, f"Rider {i}", 9.0 - i, athlete_id=i) for i in range(2, 11)
    ]
    top = [s for s in build_slides(_data(entries)) if s["type"] == "wave_photo"][-1]
    assert top["first_name"] == "KAULI"
    assert top["last_name"] == ""


@pytest.mark.parametrize("surname,expected", [
    ("PARE RICO", ""),
    ("DUNKERBECK", ""),
    ("VAN DER EYKEN", "long"),
    ("ELLEFSON RIEMENSCHNEIDER", "xlong"),
])
def test_long_surnames_step_the_type_size_down(surname, expected):
    entries = [_entry(1, f"Rider {surname}", 9.38, athlete_id=1)] + [
        _entry(i, f"Rider {i}", 9.0 - i, athlete_id=i) for i in range(2, 11)
    ]
    top = [s for s in build_slides(_data(entries)) if s["type"] == "wave_photo"][-1]
    assert top["name_class"] == expected


def test_rider_with_no_photo_falls_back_to_portrait_mode():
    """A face crop is never stretched into the full-bleed footprint."""
    entries = [_entry(i, f"Rider {i}", 10.0 - i, athlete_id=999000 + i)
               for i in range(1, 11)]
    photos = [s for s in build_slides(_data(entries)) if s["type"] == "wave_photo"]
    assert all(s["photo_mode"] == "portrait" for s in photos)


def test_photo_mode_off_keeps_the_hero_plus_two_tables_default():
    data = _data()
    data["photo_mode"] = False
    assert [s["type"] for s in build_slides(data)] == [
        "cover", "hero", "table", "table", "cta",
    ]


def test_slide_numbering_covers_all_eight():
    slides = build_slides(_data())
    assert [s["slide_number"] for s in slides] == list(range(1, 9))
    assert all(s["total_slides"] == 8 for s in slides)


def test_jump_fields_ride_along_for_a_jump_top_ten():
    entries = [_entry(i, f"Rider {i}", 10.0 - i, athlete_id=i,
                      trick_type="P", modifier="1-Foot") for i in range(1, 11)]
    data = _data(entries, title_metric="Jumps", show_trick_type=True)
    top = [s for s in build_slides(data) if s["type"] == "wave_photo"][-1]
    assert top["trick_type"] == "P"
    assert top["modifier"] == "1-Foot"


class TestCoverPhoto:
    """The cover is the grid thumbnail, so it gets a photo where one exists."""

    def test_prefers_a_generic_event_cover_over_the_top_rider(self, monkeypatch):
        """The #1 rider already carries the last photo slide.

        Opening on the same frame makes the post look like it has one picture.
        """
        monkeypatch.setattr("pipeline.carousel.resolve_event_cover_url",
                            lambda event_id: "file:///events/124/cover.jpg")
        monkeypatch.setattr("pipeline.carousel.resolve_hero_url",
                            lambda athlete_id, event_id: "file:///events/124/97.jpg")

        cover = build_slides(_data())[0]
        assert cover["cover_photo_url"] == "file:///events/124/cover.jpg"

    def test_falls_back_to_the_top_ranked_riders_hero_shot(self, monkeypatch):
        monkeypatch.setattr("pipeline.carousel.resolve_event_cover_url",
                            lambda event_id: "")
        monkeypatch.setattr("pipeline.carousel.resolve_hero_url",
                            lambda athlete_id, event_id: f"file:///hero/{athlete_id}.jpg")

        cover = build_slides(_data())[0]
        assert cover["cover_photo_url"] == "file:///hero/1.jpg"

    def test_no_photo_anywhere_leaves_the_plain_cover_untouched(self, monkeypatch):
        monkeypatch.setattr("pipeline.carousel.resolve_event_cover_url",
                            lambda event_id: "")
        monkeypatch.setattr("pipeline.carousel.resolve_hero_url",
                            lambda athlete_id, event_id: "")

        assert "cover_photo_url" not in build_slides(_data())[0]

    def test_default_mode_never_gets_a_cover_photo(self, monkeypatch):
        monkeypatch.setattr("pipeline.carousel.resolve_event_cover_url",
                            lambda event_id: "file:///events/124/cover.jpg")
        data = _data()
        data["photo_mode"] = False
        assert "cover_photo_url" not in build_slides(data)[0]

    def test_show_count_drives_the_covers_own_title_stack(self):
        """The cover assembles its own lines rather than using `title`."""
        assert build_slides(_data())[0]["show_count"] is False

        default = _data()
        default["photo_mode"] = False
        assert build_slides(default)[0]["show_count"] is True


def test_table_rows_carry_a_headshot_in_photo_mode(monkeypatch):
    import pipeline.carousel as carousel
    monkeypatch.setattr(carousel, "resolve_thumb_url",
                        lambda aid, url: f"faces/{aid}.jpg" if aid == 3 else "")
    table = next(s for s in build_slides(_data()) if s["type"] == "table")
    assert table["rows"][2]["thumb_url"] == "faces/3.jpg"
    assert table["rows"][0]["thumb_url"] == ""


def test_the_table_renders_a_headshot_or_an_initial(monkeypatch):
    import pipeline.carousel as carousel
    from pipeline.templates import render_template
    monkeypatch.setattr(carousel, "resolve_thumb_url",
                        lambda aid, url: "faces/3.jpg" if aid == 3 else "")
    table = next(s for s in build_slides(_data()) if s["type"] == "table")
    html = render_template("carousel/slide_table", table)
    assert 'src="faces/3.jpg"' in html
    assert 'class="thumb-placeholder">R<' in html


def test_a_riders_second_card_uses_their_second_hero_shot(monkeypatch):
    """Wissant 2026 men: Pare holds 3rd and 5th, one photo twice reads as a repeat."""
    import pipeline.carousel as carousel
    monkeypatch.setattr(carousel, "resolve_hero_url",
                        lambda aid, eid: {"7": "a.jpg", "7-2": "b.jpg"}.get(str(aid), ""))
    entries = [_entry(i, f"Rider {i}", 10.0 - i, athlete_id=7 if i in (3, 5) else i)
               for i in range(1, 11)]
    photos = {s["rank"]: s for s in build_slides(_data(entries)) if s["type"] == "wave_photo"}
    assert photos[3]["photo_url"] == "a.jpg"
    assert photos[5]["photo_url"] == "b.jpg"


def test_without_a_second_shot_the_first_is_reused(monkeypatch):
    import pipeline.carousel as carousel
    monkeypatch.setattr(carousel, "resolve_hero_url",
                        lambda aid, eid: "a.jpg" if str(aid) == "7" else "")
    entries = [_entry(i, f"Rider {i}", 10.0 - i, athlete_id=7 if i in (3, 5) else i)
               for i in range(1, 11)]
    photos = {s["rank"]: s for s in build_slides(_data(entries)) if s["type"] == "wave_photo"}
    assert photos[5]["photo_url"] == "a.jpg"
    assert photos[5]["photo_mode"] == "action"


def test_the_flag_sits_on_the_headshot_not_in_its_own_column(monkeypatch):
    """Same treatment as the Sylt Kings table: face and flag read as one unit."""
    import pipeline.carousel as carousel
    from pipeline.templates import render_template
    monkeypatch.setattr(carousel, "resolve_thumb_url", lambda aid, url: "faces/x.jpg")
    table = next(s for s in build_slides(_data()) if s["type"] == "table")
    html = render_template("carousel/slide_table", table)
    assert 'class="col-flag"' not in html
    assert html.count('class="thumb-flag"') == 10


def test_the_cover_shows_a_two_letter_event_country_as_a_flag():
    from pipeline.templates import render_template
    cover = next(s for s in build_slides(_data(event_country="FR")) if s["type"] == "cover")
    html = render_template("carousel/slide_cover", cover)
    assert 'flagcdn.com/w80/fr.png' in html
