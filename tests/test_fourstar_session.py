"""Tests for the 4-star Session announcement carousel."""
import os

import pytest

from pipeline.fourstar_session import (
    SESSION_COLOR,
    build_fourstar_session_slides,
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
        assert slides[0]["type"] == "fantasy_rules_cover"
        assert slides[-1]["type"] == "fantasy_rules_cta"

    def test_every_slide_carries_the_session_colour(self, slides):
        """Shared with the Freestyle and Slalom Session posts so the three read
        as one series, and it matches the mode's colour in the app."""
        assert all(s["accent_color"] == SESSION_COLOR for s in slides)

    def test_two_slides_are_screenshots(self, slides):
        shots = [s for s in slides if s["type"] == "screenshot"]
        assert len(shots) == 2


class TestNarrative:
    def test_names_both_events_with_dates(self, slides):
        text = " ".join(slides[1]["points"])
        assert "Wissant" in text and "12 to 20 September" in text
        assert "Tiree" in text and "10 to 16 October" in text

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


class TestCaption:
    def test_caption_states_both_conditions(self):
        caption = build_caption("fourstar_session", {}, {})
        assert "20 riders have entered" in caption
        assert "four opens the second" in caption.lower()

    def test_caption_names_both_events(self):
        caption = build_caption("fourstar_session", {}, {})
        assert "Wissant" in caption and "Tiree" in caption

    def test_caption_has_no_em_dashes(self):
        """House style: no em dashes in post copy."""
        assert "—" not in build_caption("fourstar_session", {}, {})
