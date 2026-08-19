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
    def test_five_slides_numbered_in_order(self, slides):
        assert len(slides) == 5
        assert [s["slide_number"] for s in slides] == [1, 2, 3, 4, 5]
        assert all(s["total_slides"] == 5 for s in slides)

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

    def test_cover_leads_straight_into_the_conditions(self, slides):
        """The squad-shape slide that sat between them is gone: the cover states
        the news in full, so an eleven-slot breakdown before the two conditions
        was a detour."""
        assert slides[1]["type"] == "screenshot"
        assert slides[2]["type"] == "screenshot"

    def test_does_not_mention_tiree(self, slides):
        """Tiree works the same way but is not confirmed, so it must not be
        announced anywhere in the post."""
        blob = repr(slides).lower()
        assert "tiree" not in blob

    def test_says_session_only(self, slides):
        """With the squad slide dropped, the cover is the only place left that
        can say this is the Session, so it has to. It lives in the eyebrow:
        the body copy is reserved for a fact nothing else on the slide
        carries."""
        assert "SESSION" in slides[0]["eyebrow"].upper()

    def test_states_the_20_rider_gate(self, slides):
        gate = slides[1]
        assert "20" in gate["title"]
        assert "20 riders have entered" in gate["tagline"]

    def test_gives_the_current_wissant_count(self, slides):
        """Must match the count in the committed screenshot, which was 12 when
        it was re-shot on 2026-08-19. If the shot is refreshed the copy moves
        with it, or the slide contradicts its own picture."""
        assert "12" in slides[1]["lead"]

    def test_category_rule_distinguishes_two_from_four(self, slides):
        """The app opens a category's FIRST slot at two riders and its second
        at four. Collapsing that to "two opens everything" misstates it."""
        unlock = slides[2]
        assert "Two riders in a category opens its slot." == unlock["lead"]
        assert unlock["caption"].startswith("Four opens the next one.")

    def test_unlock_slide_is_framed_by_category(self, slides):
        """The gate is per ranking category, not on the total start list, and
        the slide has to say so or it reads as a second 20-rider threshold."""
        assert "category" in slides[2]["tagline"].lower()

    def test_promises_email_and_notifications(self, slides):
        points = " ".join(slides[3]["points"])
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
    def test_cover_puts_the_news_in_the_biggest_type(self, slides):
        """Two earlier attempts ("It's On", then "Four Stars") gave the largest
        type on the slide to a word carrying no information and shrank the news
        to a line underneath. The news is the big type now, and there is no
        separate headline to compete with it."""
        cover = slides[0]
        assert "headline" not in cover
        assert cover["eyebrow"] == "NEW SESSION EVENT"
        assert cover["lede_lines"] == ["Wissant Wave Classic"]
        assert cover["lede_accent"] == "Joins The Fantasy League"

    def test_headline_is_exactly_two_lines(self, slides):
        """One line for the event, one for what happened to it. Three lines
        stair-stepped down the slide with a two-word orphan in the middle."""
        cover = slides[0]
        assert len(cover["lede_lines"]) + 1 == 2

    def test_cover_body_copy_does_not_repeat_the_slide(self, slides):
        """The star rating is in the meta strip and the mode is in the eyebrow.
        Body copy restating either spends two lines saying nothing new, so it
        carries the entry gate instead: the one fact nothing else has, and the
        setup for slide 2."""
        subtitle = slides[0]["subtitle"]
        assert "20 riders" in subtitle
        assert "4-star" not in subtitle
        assert "Session" not in subtitle
        assert "Fantasy League" not in subtitle

    def test_cover_ends_on_a_cta(self, slides):
        """It replaces the bottom-right watermark, which is switched off on
        this slide so the URL does not appear twice."""
        cover = slides[0]
        assert "windsurfworldtourstats.com" in cover["cta_line"]
        assert cover["hide_footer"] is True

    def test_cta_does_not_claim_picks_are_open(self, slides):
        """They are not, and will not be until the start list fills. The whole
        post exists to explain that."""
        assert "picks open" not in slides[0]["cta_line"].lower()

    def test_cover_drops_the_watermark(self, slides):
        """The class stays in the shared stylesheet every slide inherits; what
        must be gone is the rendered div."""
        html = render_template("carousel/slide_fourstar_cover", slides[0])
        assert '<div class="carousel-footer">' not in html

    def test_cover_has_no_swipe_hint(self, slides):
        """Dropped: the cover is dense enough without a second thing competing
        for the bottom-right corner."""
        html = render_template("carousel/slide_fourstar_cover", slides[0])
        assert "swipe-hint" not in html

    def test_cover_renders_the_news_lines(self, slides):
        html = render_template("carousel/slide_fourstar_cover", slides[0])
        assert "WISSANT WAVE CLASSIC" in html
        assert "JOINS THE FANTASY LEAGUE" in html

    def test_poster_sits_in_flow_not_pinned_to_a_corner(self, slides):
        """Absolutely positioned top-right, it left a ~400px hole between
        itself and the text and gave the slide two entry points. In flow above
        the eyebrow it is the first item of one left-anchored column."""
        html = render_template("carousel/slide_fourstar_cover", slides[0])
        logo_css = html.split(".event-logo {")[1].split("}")[0]
        assert "position: absolute" not in logo_css
        assert "260px" in logo_css

    def test_headline_box_keeps_the_right_margin(self, slides):
        """868px from the 72px left edge ends the longest line at x=940, so the
        right margin is never narrower than the left. Autofit measures against
        this box, so a longer event name shrinks rather than overflows."""
        html = render_template("carousel/slide_fourstar_cover", slides[0])
        assert "width: 868px" in html

    def test_cover_dimensions_are_overridable(self, slides):
        """Poster width, headline size and body measure are Jinja variables so
        a longer event name degrades gracefully."""
        cover = dict(slides[0], logo_width=200, headline_size=88, headline_width=700, body_width=520)
        html = render_template("carousel/slide_fourstar_cover", cover)
        assert "width: 200px" in html
        assert "font-size: 88px" in html
        assert "width: 700px" in html
        assert "max-width: 520px" in html

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
        assert "four opens the next one" in caption.lower()

    def test_caption_count_matches_the_slide(self):
        """Caption and slide read off the same screenshot, so they must not
        drift apart when the count is refreshed."""
        caption = build_caption("fourstar_session", {}, {})
        assert "Wissant is at 12." in caption

    def test_caption_names_wissant_only(self):
        caption = build_caption("fourstar_session", {}, {})
        assert "Wissant" in caption
        assert "Tiree" not in caption

    def test_caption_has_no_em_dashes(self):
        """House style: no em dashes in post copy."""
        assert "—" not in build_caption("fourstar_session", {}, {})
