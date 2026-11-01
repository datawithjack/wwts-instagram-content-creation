"""Tests for the Wissant "picks are open" carousel."""
import os

import pytest

from pipeline.captions import build_caption
from pipeline.fourstar_picks_open import (
    ENTRY_THRESHOLD,
    build_fourstar_picks_open_slides,
)
from pipeline.fourstar_session import SESSION_COLOR, build_fourstar_session_slides
from pipeline.templates import get_dummy_data, render_template


@pytest.fixture
def slides():
    return build_fourstar_picks_open_slides()


class TestSlideShape:
    def test_six_slides_numbered_in_order(self, slides):
        assert len(slides) == 6
        assert [s["slide_number"] for s in slides] == [1, 2, 3, 4, 5, 6]
        assert all(s["total_slides"] == 6 for s in slides)

    def test_opens_on_a_cover_and_closes_on_a_cta(self, slides):
        assert slides[0]["type"] == "fourstar_cover"
        assert slides[-1]["type"] == "fantasy_rules_cta"

    def test_every_slide_carries_the_session_colour(self, slides):
        """Shared with the announcement post so the two read as one story."""
        assert all(s["accent_color"] == SESSION_COLOR for s in slides)


class TestNarrative:
    def test_cover_says_picks_are_open(self, slides):
        """The whole reason the post exists, so it gets the big type."""
        assert slides[0]["lede_accent"] == "Picks Are Open"

    def test_cover_states_the_gate_is_cleared(self, slides):
        """The announcement's cover carried the gate as a thing still to come.
        This one carries it as a thing that happened."""
        subtitle = slides[0]["subtitle"]
        assert str(ENTRY_THRESHOLD) in subtitle
        assert "passed" in subtitle.lower()
        assert "drafting" in subtitle.lower()

    def test_cover_cta_sends_people_to_draft(self, slides):
        cover = slides[0]
        assert "windsurfworldtourstats.com" in cover["cta_line"]
        assert cover["hide_footer"] is True

    def test_says_more_slots_are_coming(self, slides):
        """The third beat of the ask: the team is not finished today."""
        assert "unlock" in slides[2]["caption"].lower() or "waiting" in slides[2]["caption"].lower()
        points = " ".join(slides[4]["points"]).lower()
        assert "unlock" in points
        # Email and Instagram are one promise sent down two pipes, so they
        # share a line rather than spending one each on "we will tell you".
        assert "email and instagram" in points

    def test_does_not_mention_tiree(self, slides):
        """Still unconfirmed, same as when the announcement went out."""
        assert "tiree" not in repr(slides).lower()

    def test_tells_people_to_draft_not_confirm(self, slides):
        """The one piece of advice in the post. With tiers still unlocking,
        Confirm & Lock freezes a part-built team, and a saved draft
        auto-confirms at the deadline anyway, so drafting is strictly better.
        It gets its own slide, and every later slide that mentions picking
        repeats it, or one that does not reads as permission to lock."""
        assert "confirm" in slides[2]["caption"].lower()
        assert "draft" in slides[3]["lead"].lower()
        assert "confirm" in slides[3]["lead"].lower()
        assert any("confirm" in p.lower() for p in slides[4]["points"])
        assert "draft" in slides[5]["subtitle"].lower()

    def test_shows_the_app_making_the_case_itself(self, slides):
        """The action bar gives Save Draft the filled treatment and demotes
        Confirm & Lock (#190), so the product argues the post's case before a
        word is read. The draft-saved dialog was tried here and dropped: it
        lands a step later, after the click this slide is still asking for."""
        bar = slides[3]
        assert bar["type"] == "screenshot"
        assert "wissant_open_action_bar" in bar["image_url"]
        assert "Save Draft" in bar["alt"] and "demoted" in bar["alt"]
        assert "wissant_open_draft_saved" not in repr(slides)

    def test_shows_no_unconfirmed_team(self, slides):
        """The confirm dialog was the obvious shot for this and was dropped:
        it lists the account's own unconfirmed picks, and the app keeps a draft
        private until it is confirmed. Nothing here may put a team on screen."""
        blob = repr(slides).lower()
        assert "wissant_open_confirm" not in blob
        for name in ("lemaitre", "lebas", "adrien bell", "marine hunter"):
            assert name not in blob

    def test_no_slide_invites_a_confirm(self, slides):
        """Belt and braces, per slide rather than per line: any slide that
        raises confirming must also put drafting in front of the reader, so
        none of them can be read on its own as permission to lock."""
        for slide in slides:
            blob = " ".join(
                v for v in slide.values() if isinstance(v, str)
            ) + " ".join(slide.get("points", []))
            if "confirm" in blob.lower():
                assert "draft" in blob.lower(), slide.get("title") or slide["type"]

    def test_does_not_claim_every_slot_is_open(self, slides):
        """Wildcards are open, the ranked tiers are not. A post that says
        "all slots open" is contradicted by its own screenshot."""
        assert "locked" in slides[2]["title"].lower()


class TestScreenshots:
    def test_three_slides_are_screenshots(self, slides):
        assert len([s for s in slides if s["type"] == "screenshot"]) == 3

    def test_screenshot_slides_resolve_to_committed_files(self, slides):
        for slide in [s for s in slides if s["type"] == "screenshot"]:
            assert slide["image_url"].startswith("file:///"), slide["title"]
            path = slide["image_url"].replace("file:///", "")
            assert os.path.exists(path), f"missing screenshot for {slide['title']}"

    def test_screenshots_are_not_the_announcement_shots(self, slides):
        """Those show the locked state at 12 riders. Reusing one here would put
        a picture of a closed event on a post saying it is open."""
        announced = {
            s["image_url"]
            for s in build_fourstar_session_slides()
            if s["type"] == "screenshot"
        }
        shots = {s["image_url"] for s in slides if s["type"] == "screenshot"}
        assert not (shots & announced)

    def test_hub_card_shows_the_pick_cta_not_finish(self, slides):
        """The capture account holds a partial Wissant draft, so its own card
        renders "Finish Session Team". A reader who has not drafted sees the
        green "Pick Session Team" instead, and that is the state the post has
        to show."""
        card = slides[1]
        assert "Pick Session Team" in card["alt"]
        assert "Finish Session Team" not in card["alt"]

    def test_screenshot_slides_carry_alt_text(self, slides):
        for slide in [s for s in slides if s["type"] == "screenshot"]:
            assert slide["alt"]


class TestRendering:
    def test_every_slide_renders(self, slides):
        for slide in slides:
            html = render_template(f"carousel/slide_{slide['type']}", slide)
            assert "<html" in html.lower()

    def test_cover_renders_the_news_lines(self, slides):
        html = render_template("carousel/slide_fourstar_cover", slides[0])
        assert "WISSANT WAVE CLASSIC" in html
        assert "PICKS ARE OPEN" in html

    def test_dummy_data_wires_the_builder(self):
        data = get_dummy_data("fourstar_picks_open")
        assert [s["type"] for s in data["slides"]] == [
            s["type"] for s in build_fourstar_picks_open_slides()
        ]


class TestCaption:
    def test_caption_says_picks_are_open(self):
        caption = build_caption("fourstar_picks_open", {}, {})
        assert "picks are open" in caption.lower()

    def test_caption_threshold_matches_the_slide(self):
        """Both read off ENTRY_THRESHOLD, so they cannot drift apart."""
        caption = build_caption("fourstar_picks_open", {}, {})
        assert str(ENTRY_THRESHOLD) in caption

    def test_caption_claims_no_live_rider_count(self):
        """The app stops publishing a total once the gate is passed, so any
        number beyond the threshold would be unverifiable and going stale."""
        caption = build_caption("fourstar_picks_open", {}, {})
        assert "riders entered" not in caption

    def test_caption_says_draft_not_confirm(self):
        caption = build_caption("fourstar_picks_open", {}, {}).lower()
        assert "not confirm" in caption
        assert "draft" in caption

    def test_caption_gives_the_reason_not_just_the_instruction(self):
        """"Do not confirm" without the why reads as an arbitrary rule, and the
        why is the whole argument: locking early costs you the later slots."""
        caption = build_caption("fourstar_picks_open", {}, {}).lower()
        assert "part-built" in caption or "freeze" in caption

    def test_caption_carries_the_deadline(self):
        assert "12 September" in build_caption("fourstar_picks_open", {}, {})

    def test_caption_names_wissant_only(self):
        caption = build_caption("fourstar_picks_open", {}, {})
        assert "Wissant" in caption
        assert "Tiree" not in caption

    def test_caption_has_no_em_dashes(self):
        """House style: no em dashes in post copy."""
        assert "—" not in build_caption("fourstar_picks_open", {}, {})
