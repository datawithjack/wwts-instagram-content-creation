"""Photo credits reaching the caption of a --photos top 10 post.

A photo post puts a photographer's work on five slides. Publishing it without
naming them is the one failure here that is visible to someone outside the repo.
"""

import pytest

from pipeline.captions import build_caption
from pipeline.carousel import photo_credits

EM_DASH = "—"


def _rows(*ids):
    return [{"rank": i + 1, "athlete": f"Rider {a}", "athlete_id": a, "score": 9.0 - i,
             "country": "es", "event": "Tenerife", "round": "Final", "counting": 1}
            for i, a in enumerate(ids)]


def _data(rows=None, **extra):
    data = {"title_gender": "Women's", "title_metric": "Waves", "title_year": 2026,
            "is_per_event": True, "event_name": "Tenerife Grand Slam",
            "photo_mode": True, "photo_event_id": 124,
            "entries": rows or _rows(16, 13, 12, 17, 5)}
    data.update(extra)
    return data


class TestPhotoCredits:

    def test_lead_image_first_then_the_countdown(self, monkeypatch):
        """The cover is the lead image, and the slides run 5th up to 1st."""
        monkeypatch.setattr("pipeline.carousel.resolve_event_cover_url",
                            lambda event_id: "")
        handles = {16: "@a", 13: "@b", 12: "@c", 17: "@d", 5: "@e"}
        monkeypatch.setattr("pipeline.carousel.resolve_photo_credit",
                            lambda aid, ev: handles.get(aid, ""))
        # No cover file, so the cover reuses the #1 rider (16) and is named first.
        assert photo_credits(_data()) == ["@a", "@e", "@d", "@c", "@b"]

    def test_a_dedicated_cover_photo_is_credited_first(self, monkeypatch):
        monkeypatch.setattr("pipeline.carousel.resolve_event_cover_url",
                            lambda event_id: "file:///cover.jpg")
        monkeypatch.setattr("pipeline.carousel.resolve_photo_credit",
                            lambda aid, ev: {"cover": "@cover"}.get(aid, "@rider"))
        assert photo_credits(_data())[0] == "@cover"

    def test_one_photographer_is_named_once(self, monkeypatch):
        monkeypatch.setattr("pipeline.carousel.resolve_event_cover_url",
                            lambda event_id: "")
        monkeypatch.setattr("pipeline.carousel.resolve_photo_credit",
                            lambda aid, ev: "@jcwindsurf")
        assert photo_credits(_data()) == ["@jcwindsurf"]

    def test_untagged_photos_contribute_nothing(self, monkeypatch):
        """Better no credit line than a guessed attribution."""
        monkeypatch.setattr("pipeline.carousel.resolve_event_cover_url",
                            lambda event_id: "")
        monkeypatch.setattr("pipeline.carousel.resolve_photo_credit",
                            lambda aid, ev: "@jc" if aid == 5 else "")
        assert photo_credits(_data()) == ["@jc"]

    def test_no_photos_no_credits(self):
        data = _data()
        data["photo_mode"] = False
        data.pop("photo_event_id")
        assert photo_credits(data) == []

    def test_only_the_riders_on_slides_are_credited(self, monkeypatch):
        """Ranks 6 to 10 appear in the table, not on a photo slide."""
        monkeypatch.setattr("pipeline.carousel.resolve_event_cover_url",
                            lambda event_id: "")
        seen = []

        def spy(aid, ev):
            seen.append(aid)
            return ""

        monkeypatch.setattr("pipeline.carousel.resolve_photo_credit", spy)
        photo_credits(_data(_rows(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)))
        assert 6 not in seen and 10 not in seen


class TestCaptionRendersCredits:

    def test_credit_line_is_appended(self):
        data = _data(photo_credits=["@jcwindsurf", "@rafasoulart"])
        caption = build_caption("top_10_carousel", data, {})
        assert "\U0001f4f8 @jcwindsurf | @rafasoulart" in caption

    def test_no_credits_means_no_credit_line_and_no_stray_separator(self):
        caption = build_caption("top_10_carousel", _data(photo_credits=[]), {})
        assert "\U0001f4f8" not in caption
        assert not caption.rstrip().endswith("|")

    def test_blank_entries_do_not_produce_an_empty_slot(self):
        data = _data(photo_credits=["@jcwindsurf", "", None])
        caption = build_caption("top_10_carousel", data, {})
        assert "\U0001f4f8 @jcwindsurf" in caption
        assert "| |" not in caption
        assert not caption.rstrip().endswith("|")

    def test_credit_sits_after_the_body(self):
        data = _data(photo_credits=["@jcwindsurf"])
        caption = build_caption("top_10_carousel", data, {})
        assert caption.index("windsurfworldtourstats.com") < caption.index("\U0001f4f8")


class TestNoEmDashes:
    """Standing rule: no em dashes in post copy. Use a colon, comma or period."""

    @pytest.mark.parametrize("extra", [
        {},
        {"day": 3},
        {"finals_day": True},
        {"so_far": True},
    ])
    def test_top_10_caption_variants_are_clean(self, extra):
        caption = build_caption("top_10_carousel", _data(**extra), {})
        assert EM_DASH not in caption, caption

    def test_perfect_10s_variant_is_clean(self):
        data = _data(perfect_10s_mode=True)
        assert EM_DASH not in build_caption("top_10_carousel", data, {})


class TestHandWrittenCaption:
    """A credit is owed whoever wrote the words."""

    def test_a_custom_caption_still_credits_the_photographer(self):
        data = _data(photo_credits=["@jcwindsurf"])
        caption = build_caption("top_10_carousel", data, {},
                                caption_override="My own words about the waves.")
        assert "My own words about the waves." in caption
        assert "\U0001f4f8 @jcwindsurf" in caption

    def test_a_custom_caption_with_no_photos_is_untouched(self):
        caption = build_caption("top_10_carousel", _data(), {},
                                caption_override="Just words.")
        assert "\U0001f4f8" not in caption

    def test_finals_recap_still_credits_exactly_once(self):
        """finals_recap had its own copy of this logic; it must not double up."""
        data = {"riders": [{"place": 1, "name": "Marc Pare Rico", "final_total": 24.5}],
                "division": "Men", "event_meta": {"event_name": "Tenerife", "year": 2026},
                "photo_credits": ["@jcwindsurf", "@jcwindsurf"]}
        caption = build_caption("finals_recap", data, {})
        assert caption.count("\U0001f4f8") == 1
        assert caption.count("@jcwindsurf") == 1
