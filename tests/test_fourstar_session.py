"""Tests for the Wissant Session announcement carousel."""
import os

import pytest

from pipeline.fourstar_session import (
    SESSION_COLOR,
    build_fourstar_session_slides,
    logo_url,
    screenshot_url,
)
from pipeline.captions import build_caption
from pipeline.templates import get_dummy_data, render_template


@pytest.fixture
def slides():
    return build_fourstar_session_slides()


class TestSlideShape:
    def test_six_slides_numbered_in_order(self, slides):
        assert len(slides) == 6
        assert [s["slide_number"] for s in slides] == [1, 2, 3, 4, 5, 6]
        assert all(s["total_slides"] == 6 for s in slides)

    def test_opens_on_a_cover_and_closes_on_a_cta(self, slides):
        assert slides[0]["type"] == "fourstar_cover"
        assert slides[-1]["type"] == "fantasy_rules_cta"

    def test_every_slide_carries_the_session_colour(self, slides):
        """Shared with the Freestyle and Slalom Session posts so the three read
        as one series, and it matches the mode's colour in the app."""
        assert all(s["accent_color"] == SESSION_COLOR for s in slides)

    def test_two_slides_are_screenshots(self, slides):
        shots = [s for s in slides if s["type"] == "screenshot"]
        assert len(shots) == 2


class TestNarrative:
    def test_names_wissant_with_dates_on_the_cover(self, slides):
        """The event name and dates belong to the cover. Slide 2 used to repeat
        them, which left it with nothing of its own to say."""
        cover = slides[0]
        assert cover["event_name"] == "Wissant Wave Classic"
        assert cover["dates"] == "12 to 20 Sept 2026"

    def test_squad_slide_gives_the_slot_shape(self, slides):
        """Eleven slots, five of them women's. Without this the locked women's
        slots on slide 4 have no context."""
        points = slides[1]["points"]
        assert "11" in slides[1]["name"]
        assert points[0].startswith("Men:")
        assert points[1].startswith("Women:")

    def test_squad_slide_does_not_restate_the_cover(self, slides):
        """The cover already carries the event, the dates and the pitch. Slide 2
        repeating them is the failure mode this replaced."""
        text = " ".join(slides[1]["points"] + [slides[1]["tagline"]])
        assert "Wissant" not in text
        assert "September" not in text and "Sept" not in text

    def test_does_not_mention_tiree(self, slides):
        """Tiree works the same way but is not confirmed, so it must not be
        announced anywhere in the post."""
        blob = repr(slides).lower()
        assert "tiree" not in blob

    def test_says_session_only(self, slides):
        assert any("no Tour points" in p for p in slides[1]["points"])

    def test_states_the_20_rider_gate(self, slides):
        gate = slides[2]
        assert "20" in gate["title"]
        assert "20 riders have entered" in gate["tagline"]

    def test_gives_the_current_wissant_count(self, slides):
        assert "9" in slides[2]["lead"]

    def test_tier_rule_distinguishes_two_from_four(self, slides):
        """The app opens a band's FIRST slot at two riders and its second at
        four. Collapsing that to "two opens a tier" would misstate the rule."""
        unlock = slides[3]
        assert "Two in a tier opens its first slot." == unlock["lead"]
        assert "Four opens the second." == unlock["caption"]

    def test_promises_email_and_notifications(self, slides):
        points = " ".join(slides[4]["points"])
        assert "email" in points.lower()
        assert "start list grows" in points


class TestScreenshots:
    def test_screenshot_slides_resolve_to_committed_files(self, slides):
        for slide in [s for s in slides if s["type"] == "screenshot"]:
            assert slide["image_url"].startswith("file:///"), slide["title"]
            path = slide["image_url"].replace("file:///", "")
            assert os.path.exists(path), f"missing screenshot for {slide['title']}"

    def test_missing_screenshot_yields_empty_string(self):
        """A checkout without the PNGs should still preview: the frame renders
        empty rather than the whole carousel raising."""
        assert screenshot_url("does-not-exist.png") == ""

    def test_screenshot_slides_carry_alt_text(self, slides):
        for slide in [s for s in slides if s["type"] == "screenshot"]:
            assert slide["alt"]


class TestRendering:
    def test_every_slide_renders(self, slides):
        for slide in slides:
            html = render_template(f"carousel/slide_{slide['type']}", slide)
            assert "<html" in html.lower()

    def test_screenshot_slide_embeds_the_image_and_caption(self, slides):
        shot = [s for s in slides if s["type"] == "screenshot"][0]
        html = render_template("carousel/slide_screenshot", shot)
        assert shot["image_url"] in html
        assert shot["lead"] in html
        assert shot["caption"] in html

    def test_dummy_data_wires_the_builder(self):
        data = get_dummy_data("fourstar_session")
        assert [s["type"] for s in data["slides"]] == [
            s["type"] for s in build_fourstar_session_slides()
        ]


class TestCover:
    def test_cover_carries_the_event_logo(self, slides):
        """The cover should be recognisably this event, not a generic fantasy
        announcement."""
        cover = slides[0]
        assert cover["logo_url"].startswith("file:///")
        assert os.path.exists(cover["logo_url"].replace("file:///", ""))

    def test_cover_logo_has_alt_text(self, slides):
        assert slides[0]["logo_alt"]

    def test_cover_carries_the_event_meta(self, slides):
        """The star rating is the whole point of the post, so it belongs on the
        cover rather than only in the body."""
        cover = slides[0]
        assert cover["stars"] == 4
        assert cover["discipline"] == "Wave"
        assert "12 to 20 Sept 2026" == cover["dates"]
        assert cover["event_name"] == "Wissant Wave Classic"

    def test_cover_renders_logo_stars_and_dates(self, slides):
        html = render_template("carousel/slide_fourstar_cover", slides[0])
        assert slides[0]["logo_url"] in html
        assert "\u2605\u2605\u2605\u2605" in html
        assert "12 TO 20 SEPT 2026" in html

    def test_cover_renders_without_a_logo(self, slides):
        """The logo is optional, so the template must not break when an event
        has no poster on the site."""
        cover = dict(slides[0], logo_url="")
        html = render_template("carousel/slide_fourstar_cover", cover)
        assert "event-logo" not in html

    def test_missing_logo_yields_empty_string(self):
        assert logo_url("no-such-logo.png") == ""

    def test_shared_fantasy_rules_cover_is_untouched(self):
        """This post uses its own cover template, so the shared one the
        Freestyle, Slalom and rules posts render through stays as it was."""
        from pipeline.fantasy_rules import build_fantasy_rules_slides

        html = render_template(
            "carousel/slide_fantasy_rules_cover", build_fantasy_rules_slides()[0]
        )
        assert "cover-logo" not in html


class TestCaption:
    def test_caption_states_both_conditions(self):
        caption = build_caption("fourstar_session", {}, {})
        assert "20 riders have entered" in caption
        assert "four opens the second" in caption.lower()

    def test_caption_names_wissant_only(self):
        caption = build_caption("fourstar_session", {}, {})
        assert "Wissant" in caption
        assert "Tiree" not in caption

    def test_caption_has_no_em_dashes(self):
        """House style: no em dashes in post copy."""
        assert "—" not in build_caption("fourstar_session", {}, {})
