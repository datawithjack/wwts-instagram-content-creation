"""Tests for the event picks carousel slide builder and template rendering.

A "picks" post is a pre-event editorial carousel: a cover, then one slide per
pick revealed in suspense order (rank 4 -> 1). Data is driven entirely from a
small JSON file (data/picks/<event>.json), so future events need new data only.
"""
import pytest

from pipeline.picks_carousel import (
    build_slides,
    parse_highlight,
    strip_markers,
    _resolve_pick_photo,
    ACCENT_PICKS,
    ACCENT_TOUR,
    WINNER_COLOR,
)
from pipeline.templates import get_dummy_data, render_template


# ── Helpers ──────────────────────────────────────────────────────────────────

def _data():
    """Fiji sample picks data (4 picks: ranks 4,3,2,1)."""
    return get_dummy_data("event_picks")


def _riders(slides):
    """Just the rider slides (excludes cover + cta)."""
    return [s for s in slides if s["type"] == "picks_rider"]


# ── Highlight parsing ──────────────────────────────────────────────────────────

class TestParseHighlight:
    def test_single_marker_becomes_bold(self):
        assert parse_highlight("a {{big wave}} day") == "a <b>big wave</b> day"

    def test_no_marker_unchanged(self):
        assert parse_highlight("plain text") == "plain text"

    def test_multiple_markers(self):
        assert parse_highlight("{{one}} and {{two}}") == "<b>one</b> and <b>two</b>"

    def test_empty_string(self):
        assert parse_highlight("") == ""

    def test_none_safe(self):
        assert parse_highlight(None) == ""

    def test_strip_markers_removes_braces(self):
        assert strip_markers("a {{big wave}} day") == "a big wave day"


# ── Slide structure ────────────────────────────────────────────────────────────

class TestSlideStructure:
    def test_count_is_cover_plus_picks_plus_cta(self):
        data = _data()
        slides = build_slides(data)
        assert len(slides) == 1 + len(data["picks"]) + 1

    def test_first_slide_is_cover(self):
        assert build_slides(_data())[0]["type"] == "picks_cover"

    def test_last_slide_is_cta(self):
        last = build_slides(_data())[-1]
        assert last["type"] == "cta"
        assert last["hide_footer"] is True

    def test_slide_types_in_order(self):
        types = [s["type"] for s in build_slides(_data())]
        assert types == ["picks_cover", "picks_rider", "picks_rider",
                         "picks_rider", "picks_rider", "cta"]

    def test_cover_carries_event_fields(self):
        cover = build_slides(_data())[0]
        assert cover["event_name"] == "Fiji Surf Pro"
        assert cover["venue"] == "Cloudbreak"
        assert cover["dates"] == "6-14 Jun 2026"
        assert cover["stars"] == 4
        assert cover["cover_sub"]

    def test_rider_carries_event_name_for_context(self):
        slides = build_slides(_data())
        assert slides[1]["event_name"] == "Fiji Surf Pro"


# ── Reveal order ────────────────────────────────────────────────────────────────

class TestRevealOrder:
    def test_ranks_descend_4_to_1(self):
        ranks = [s["rank"] for s in _riders(build_slides(_data()))]
        assert ranks == [4, 3, 2, 1]

    def test_unsorted_input_is_reordered(self):
        data = _data()
        data["picks"] = list(reversed(data["picks"]))  # now 1,2,3,4
        ranks = [s["rank"] for s in _riders(build_slides(data))]
        assert ranks == [4, 3, 2, 1]


# ── Winner highlighting ──────────────────────────────────────────────────────────

class TestWinner:
    def test_rank_1_is_winner(self):
        slides = build_slides(_data())
        winner = [s for s in slides if s.get("rank") == 1][0]
        assert winner["is_winner"] is True

    def test_others_not_winner(self):
        for s in _riders(build_slides(_data())):
            if s["rank"] != 1:
                assert s["is_winner"] is False


# ── Rider fields ────────────────────────────────────────────────────────────────

class TestRiderFields:
    def _by_rank(self, rank):
        return [s for s in build_slides(_data()) if s.get("rank") == rank][0]

    def test_winner_basic_fields(self):
        w = self._by_rank(1)
        assert w["name"] == "Robby Swift"
        assert w["sail"] == "K-89"
        assert w["label"] == "Pick to Win"

    def test_nation_iso_resolved(self):
        assert self._by_rank(1)["nation_iso"] == "gb"   # British
        assert self._by_rank(2)["nation_iso"] == "fr"   # France
        assert self._by_rank(3)["nation_iso"] == "jp"   # Japan
        assert self._by_rank(4)["nation_iso"] == "gp"   # Guadeloupe

    def test_why_html_marks_highlight(self):
        # A {{...}} marker in a pick's why becomes bold in why_html.
        data = {"event": {}, "picks": [{"rank": 1, "why": "a {{big}} day"}]}
        assert build_slides(data)[1]["why_html"] == "a <b>big</b> day"

    def test_empty_why_is_blank(self):
        # Picks may ship with an empty why (justification added later).
        data = {"event": {}, "picks": [{"rank": 1, "why": ""}]}
        assert build_slides(data)[1]["why_html"] == ""


# ── Photo resolution ─────────────────────────────────────────────────────────────

class TestPhoto:
    def test_null_photo_has_no_photo(self):
        data = {"event": {}, "picks": [{"rank": 3, "photo": None}]}
        slide = build_slides(data)[1]
        assert slide["has_photo"] is False
        assert slide["photo_url"] == ""

    def test_all_fiji_picks_have_photos(self):
        for s in _riders(build_slides(_data())):
            assert s["has_photo"] is True

    def test_resolver_returns_empty_for_missing_file(self):
        assert _resolve_pick_photo("assets/does_not_exist_xyz.jpg") == ""

    def test_resolver_returns_empty_for_none(self):
        assert _resolve_pick_photo(None) == ""

    def test_resolver_resolves_existing_absolute_file(self, tmp_path):
        f = tmp_path / "rider.jpg"
        f.write_bytes(b"x")
        url = _resolve_pick_photo(str(f))
        assert url.startswith("file:///")
        assert "rider.jpg" in url


# ── Accent colour by mode ────────────────────────────────────────────────────────

class TestAccent:
    def test_picks_mode_uses_violet(self):
        data = _data()
        data["event"]["mode"] = "picks"
        for s in build_slides(data):
            assert s["accent_color"] == ACCENT_PICKS

    def test_tour_mode_uses_muted_cyan(self):
        data = _data()
        data["event"]["mode"] = "tour"
        for s in build_slides(data):
            assert s["accent_color"] == ACCENT_TOUR


# ── Slide numbers ────────────────────────────────────────────────────────────────

class TestSlideNumbers:
    def test_numbers_sequential(self):
        slides = build_slides(_data())
        total = len(slides)
        for i, s in enumerate(slides, 1):
            assert s["slide_number"] == i
            assert s["total_slides"] == total


# ── Template rendering ───────────────────────────────────────────────────────────

class TestTemplateRendering:
    def setup_method(self):
        self.slides = build_slides(_data())

    def test_cover_renders_valid_html(self):
        html = render_template("carousel/slide_picks_cover", self.slides[0])
        assert "<html" in html
        assert "1080" in html and "1350" in html

    def test_cover_shows_event_and_venue(self):
        html = render_template("carousel/slide_picks_cover", self.slides[0])
        assert "CLOUDBREAK" in html.upper()

    def test_rider_renders_valid_html(self):
        rider = self.slides[1]
        html = render_template("carousel/slide_picks_rider", rider)
        assert "<html" in html
        assert rider["name"].upper() in html.upper()

    def test_winner_slide_marked(self):
        winner = [s for s in self.slides if s.get("rank") == 1][0]
        html = render_template("carousel/slide_picks_rider", winner)
        assert "rider--winner" in html

    def test_non_winner_not_marked(self):
        loser = [s for s in self.slides if s.get("rank") == 4][0]
        html = render_template("carousel/slide_picks_rider", loser)
        assert "rider--winner" not in html

    def test_why_bold_rendered(self):
        data = {"event": {}, "picks": [{"rank": 2, "name": "X", "why": "a {{big}} day"}]}
        slide = build_slides(data)[1]
        html = render_template("carousel/slide_picks_rider", slide)
        assert "<b>" in html

    def test_placeholder_renders_when_no_photo(self):
        data = {"event": {}, "picks": [{"rank": 3, "name": "TBC", "sail": "#__", "photo": None}]}
        slide = build_slides(data)[1]
        html = render_template("carousel/slide_picks_rider", slide)
        assert "photo-placeholder" in html

    def test_all_slides_render_at_size(self):
        for slide in self.slides:
            html = render_template(f"carousel/slide_{slide['type']}", slide)
            assert "1080" in html
            assert "1350" in html

    def test_footer_present(self):
        html = render_template("carousel/slide_picks_cover", self.slides[0])
        assert "carousel-footer" in html
