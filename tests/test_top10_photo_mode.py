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
