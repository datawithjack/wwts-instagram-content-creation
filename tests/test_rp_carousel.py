"""Tests for rider profile carousel slide builder and template rendering."""
import pytest

from pipeline.rp_carousel import build_slides, ACCENT_WAVES, ACCENT_JUMPS
from pipeline.templates import get_dummy_data, render_template


# ── Helpers ──────────────────────────────────────────────────────────────────

def _wave_data():
    """Return rider profile data for wave-only event."""
    return get_dummy_data("rider_profile")


def _jump_data():
    """Return rider profile data for wave+jump event (has best_jump + top_jumps)."""
    data = get_dummy_data("rider_profile")
    data["best_jump"] = 7.50
    data["top_jumps"] = [
        {"rank": 1, "score": 10.00, "round": "Round 7", "move": "Push Loop Forward"},
        {"rank": 2, "score": 9.00, "round": "Round 7", "move": "Push Loop Forward"},
        {"rank": 3, "score": 7.50, "round": "Round 7", "move": "Double Forward Loop"},
        {"rank": 4, "score": 4.38, "round": "Round 7", "move": "Back Loop"},
        {"rank": 5, "score": 3.38, "round": "Round 7", "move": "Double Forward Loop"},
    ]
    return data


def _wave_only_data():
    """Return rider profile data with no jump score."""
    data = get_dummy_data("rider_profile")
    data.pop("best_jump", None)
    data.pop("top_jumps", None)
    return data


# ── Slide Count ──────────────────────────────────────────────────────────────

class TestSlideCount:
    def test_wave_only_returns_4_slides(self):
        slides = build_slides(_wave_only_data())
        assert len(slides) == 4

    def test_wave_jump_returns_5_slides(self):
        slides = build_slides(_jump_data())
        assert len(slides) == 5


# ── Slide Types ──────────────────────────────────────────────────────────────

class TestSlideTypes:
    def test_wave_only_slide_types(self):
        slides = build_slides(_wave_only_data())
        types = [s["type"] for s in slides]
        assert types == ["rp_cover", "rp_hero", "rp_waves", "cta"]

    def test_wave_jump_slide_types(self):
        slides = build_slides(_jump_data())
        types = [s["type"] for s in slides]
        assert types == ["rp_cover", "rp_hero", "rp_waves", "rp_jumps", "cta"]


# ── Accent Colors ────────────────────────────────────────────────────────────

class TestAccentColors:
    def test_wave_only_uses_cyan(self):
        slides = build_slides(_wave_only_data())
        for slide in slides:
            assert slide["accent_color"] == ACCENT_WAVES

    def test_wave_jump_uses_teal(self):
        slides = build_slides(_jump_data())
        for slide in slides:
            assert slide["accent_color"] == ACCENT_JUMPS


# ── Cover Slide ──────────────────────────────────────────────────────────────

class TestCoverSlide:
    def test_cover_has_event_name(self):
        slides = build_slides(_wave_data())
        cover = slides[0]
        assert cover["event_name"] == "2026 Chile World Cup"

    def test_cover_has_athlete_name(self):
        slides = build_slides(_wave_data())
        cover = slides[0]
        assert cover["athlete_name"] == "Marc Pare Rico"

    def test_cover_has_athlete_surname(self):
        slides = build_slides(_wave_data())
        cover = slides[0]
        assert cover["athlete_surname"] == "RICO"

    def test_cover_has_athlete_firstname(self):
        slides = build_slides(_wave_data())
        cover = slides[0]
        assert cover["athlete_firstname"] == "MARC"

    def test_cover_has_event_metadata(self):
        slides = build_slides(_wave_data())
        cover = slides[0]
        assert "event_country" in cover
        assert "event_date_start" in cover
        assert "event_date_end" in cover
        assert "event_tier" in cover

    def test_cover_has_placement(self):
        slides = build_slides(_wave_data())
        cover = slides[0]
        assert cover["placement"] == 1
        assert cover["placement_ordinal"] == "1st"


# ── Event-relative cover photo ───────────────────────────────────────────────

class TestEventRelativeCover:
    """Cover variant selection now keys on the resolved action photo (filesystem),
    so local-only event photos trigger rp_cover_photo, and headshots never do."""

    def test_event_id_carried_on_every_slide(self):
        data = _wave_data()
        data["athlete_id"] = 178
        data["event_id"] = 25
        for slide in build_slides(data):
            assert slide["event_id"] == 25

    def test_local_event_photo_triggers_photo_cover(self, tmp_path, monkeypatch):
        """A local events/{event}/{id} photo with an empty API url → rp_cover_photo."""
        ev = tmp_path / "events" / "25"
        ev.mkdir(parents=True)
        (ev / "178.jpg").write_bytes(b"x")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        data = _wave_data()
        data.update({"athlete_id": 178, "event_id": 25, "athlete_photo_url": ""})
        assert build_slides(data)[0]["type"] == "rp_cover_photo"

    def test_plain_cover_when_no_photo_anywhere(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        data = _wave_data()
        data.update({"athlete_id": 178, "event_id": 25, "athlete_photo_url": ""})
        assert build_slides(data)[0]["type"] == "rp_cover"

    def test_face_only_does_not_trigger_photo_cover(self, tmp_path, monkeypatch):
        """A headshot must not promote the cover to the photo variant."""
        faces = tmp_path / "faces"
        faces.mkdir(parents=True)
        (faces / "178.jpg").write_bytes(b"x")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        data = _wave_data()
        data.update({"athlete_id": 178, "event_id": 25, "athlete_photo_url": ""})
        assert build_slides(data)[0]["type"] == "rp_cover"


# ── Hero Slide (merged with stats) ──────────────────────────────────────────

class TestHeroSlide:
    def test_hero_has_photo(self):
        slides = build_slides(_wave_data())
        hero = slides[1]
        assert "athlete_photo_url" in hero

    def test_hero_has_thumb_key(self):
        """The face thumbnail source is carried on every slide via common."""
        slides = build_slides(_wave_data())
        hero = slides[1]
        assert "athlete_thumb_url" in hero

    def test_hero_has_sail_number(self):
        slides = build_slides(_wave_data())
        hero = slides[1]
        assert hero["athlete_sail_number"] == "E-73"

    def test_hero_has_placement(self):
        slides = build_slides(_wave_data())
        hero = slides[1]
        assert hero["placement"] == 1
        assert hero["placement_ordinal"] == "1st"

    def test_hero_has_athlete_country(self):
        slides = build_slides(_wave_data())
        hero = slides[1]
        assert hero["athlete_country"] == "ES"

    def test_hero_has_stats(self):
        slides = build_slides(_wave_data())
        hero = slides[1]
        assert "stats" in hero
        assert len(hero["stats"]) >= 3

    def test_wave_only_hero_has_3_stats(self):
        slides = build_slides(_wave_only_data())
        hero = slides[1]
        assert len(hero["stats"]) == 3

    def test_wave_jump_hero_has_4_stats(self):
        slides = build_slides(_jump_data())
        hero = slides[1]
        assert len(hero["stats"]) == 4

    def test_stats_have_label_and_value(self):
        slides = build_slides(_wave_data())
        hero = slides[1]
        for stat in hero["stats"]:
            assert "label" in stat
            assert "value" in stat

    def test_stat_values_formatted_2dp(self):
        slides = build_slides(_wave_data())
        hero = slides[1]
        for stat in hero["stats"]:
            assert "." in stat["value"]
            _, decimal = stat["value"].split(".")
            assert len(decimal) == 2

    def test_wave_only_stat_labels(self):
        slides = build_slides(_wave_only_data())
        hero = slides[1]
        labels = [s["label"] for s in hero["stats"]]
        assert labels == ["Best Heat", "Best Wave", "Avg Wave"]

    def test_wave_jump_stat_labels(self):
        slides = build_slides(_jump_data())
        hero = slides[1]
        labels = [s["label"] for s in hero["stats"]]
        assert labels == ["Best Heat", "Best Wave", "Best Jump", "Avg Wave"]

    def test_best_heat_has_round_detail(self):
        slides = build_slides(_wave_data())
        hero = slides[1]
        best_heat = hero["stats"][0]
        assert best_heat["detail"] == "Final"


# ── Rider of the Day mode (mid-comp, no placement) ──────────────────────────

class TestRiderOfDay:
    """`rider_of_day=True` drops the finish position everywhere and swaps the
    cover's placement hero for a 'RIDER OF THE DAY' eyebrow."""

    def _rod_data(self):
        data = _wave_data()
        data["rider_of_day"] = True
        return data

    def test_default_keeps_placement(self):
        cover = build_slides(_wave_data())[0]
        assert cover["show_placement"] is True
        assert cover.get("rider_of_day", False) is False

    def test_cover_hides_placement(self):
        cover = build_slides(self._rod_data())[0]
        assert cover["show_placement"] is False
        assert cover["rider_of_day"] is True

    def test_flag_on_every_slide(self):
        for slide in build_slides(self._rod_data()):
            assert slide["rider_of_day"] is True
            assert slide["show_placement"] is False

    def test_stats_lead_is_heats_sailed(self):
        data = self._rod_data()
        data["heats_sailed"] = 4
        hero = build_slides(data)[1]
        lead = [s for s in hero["stats"] if s.get("is_placing")]
        assert len(lead) == 1
        assert lead[0]["label"] == "Heats Sailed"
        assert lead[0]["value"] == "4"
        assert lead[0]["detail"] == "(so far)"

    def test_default_stats_show_placing_ordinal(self):
        hero = build_slides(_wave_data())[1]
        placing = [s for s in hero["stats"] if s.get("is_placing")]
        assert len(placing) == 1
        assert placing[0]["value"] == "1st"

    def test_plain_cover_shows_eyebrow_not_placement(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        data = self._rod_data()
        data.update({"athlete_id": 178, "event_id": 25, "athlete_photo_url": ""})
        cover = build_slides(data)[0]
        assert cover["type"] == "rp_cover"
        html = render_template("carousel/slide_rp_cover", cover)
        assert "RIDER OF THE DAY" in html
        # the placement ordinal must not appear as the hero element
        assert ">1st<" not in html.lower()

    def test_photo_cover_shows_eyebrow_not_badge(self, tmp_path, monkeypatch):
        ev = tmp_path / "events" / "25"
        ev.mkdir(parents=True)
        (ev / "178.jpg").write_bytes(b"x")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        data = self._rod_data()
        data.update({"athlete_id": 178, "event_id": 25, "athlete_photo_url": ""})
        cover = build_slides(data)[0]
        assert cover["type"] == "rp_cover_photo"
        html = render_template("carousel/slide_rp_cover_photo", cover)
        assert "RIDER OF THE DAY" in html
        # the badge div (and its rendered ordinal span) must not be emitted
        assert 'class="placement-text"' not in html


# ── Waves Slide ──────────────────────────────────────────────────────────────

class TestWavesSlide:
    def test_waves_has_5_entries(self):
        slides = build_slides(_wave_data())
        waves = slides[2]
        assert len(waves["top_waves"]) == 5

    def test_wave_entries_have_rank_score_round(self):
        slides = build_slides(_wave_data())
        waves = slides[2]
        for wave in waves["top_waves"]:
            assert "rank" in wave
            assert "score" in wave
            assert "round" in wave

    def test_wave_scores_formatted_2dp(self):
        slides = build_slides(_wave_data())
        waves = slides[2]
        for wave in waves["top_waves"]:
            assert "." in wave["score"]
            _, decimal = wave["score"].split(".")
            assert len(decimal) == 2


# ── Jumps Slide ──────────────────────────────────────────────────────────────

class TestJumpsSlide:
    def test_jumps_slide_exists_when_jump_data(self):
        slides = build_slides(_jump_data())
        types = [s["type"] for s in slides]
        assert "rp_jumps" in types

    def test_jumps_slide_absent_for_wave_only(self):
        slides = build_slides(_wave_only_data())
        types = [s["type"] for s in slides]
        assert "rp_jumps" not in types

    def test_jumps_has_5_entries(self):
        slides = build_slides(_jump_data())
        jumps = [s for s in slides if s["type"] == "rp_jumps"][0]
        assert len(jumps["top_jumps"]) == 5

    def test_jump_entries_have_rank_score_round_move(self):
        slides = build_slides(_jump_data())
        jumps = [s for s in slides if s["type"] == "rp_jumps"][0]
        for j in jumps["top_jumps"]:
            assert "rank" in j
            assert "score" in j
            assert "round" in j
            assert "move" in j

    def test_jump_scores_formatted_2dp(self):
        slides = build_slides(_jump_data())
        jumps = [s for s in slides if s["type"] == "rp_jumps"][0]
        for j in jumps["top_jumps"]:
            assert "." in j["score"]
            _, decimal = j["score"].split(".")
            assert len(decimal) == 2


# ── CTA Slide ────────────────────────────────────────────────────────────────

class TestCTASlide:
    def test_cta_has_hide_footer(self):
        slides = build_slides(_wave_data())
        cta = slides[-1]
        assert cta["hide_footer"] is True

    def test_cta_type(self):
        slides = build_slides(_wave_data())
        cta = slides[-1]
        assert cta["type"] == "cta"


# ── Slide Numbers ────────────────────────────────────────────────────────────

class TestSlideNumbers:
    def test_wave_only_slide_numbers(self):
        slides = build_slides(_wave_only_data())
        for i, slide in enumerate(slides, 1):
            assert slide["slide_number"] == i
            assert slide["total_slides"] == 4

    def test_wave_jump_slide_numbers(self):
        slides = build_slides(_jump_data())
        for i, slide in enumerate(slides, 1):
            assert slide["slide_number"] == i
            assert slide["total_slides"] == 5


# ── Template Rendering ───────────────────────────────────────────────────────

class TestRPCarouselTemplateRendering:
    def setup_method(self):
        self.slides = build_slides(_wave_data())

    def test_cover_renders_valid_html(self):
        html = render_template("carousel/slide_rp_cover", self.slides[0])
        assert "<html" in html

    def test_cover_shows_placement(self):
        html = render_template("carousel/slide_rp_cover", self.slides[0])
        assert "1st" in html.lower() or "1ST" in html

    def test_cover_shows_event_name(self):
        html = render_template("carousel/slide_rp_cover", self.slides[0])
        assert "CHILE WORLD CUP" in html

    def test_cover_shows_athlete_name(self):
        html = render_template("carousel/slide_rp_cover", self.slides[0])
        assert "RICO" in html

    def test_hero_renders_valid_html(self):
        html = render_template("carousel/slide_rp_hero", self.slides[1])
        assert "<html" in html
        assert "MARC PARE RICO" in html

    def test_hero_shows_placement(self):
        html = render_template("carousel/slide_rp_hero", self.slides[1])
        assert "1st" in html

    def test_hero_shows_sail_number(self):
        html = render_template("carousel/slide_rp_hero", self.slides[1])
        assert "E-73" in html

    def test_hero_shows_stats(self):
        html = render_template("carousel/slide_rp_hero", self.slides[1])
        assert "Best Heat" in html
        assert "Best Wave" in html
        assert "16.33" in html
        assert "8.83" in html

    def test_waves_renders_valid_html(self):
        html = render_template("carousel/slide_rp_waves", self.slides[2])
        assert "<html" in html
        assert "TOP 5 WAVES" in html
        assert "RIDER PROFILE" not in html

    def test_waves_shows_scores(self):
        html = render_template("carousel/slide_rp_waves", self.slides[2])
        assert "8.83" in html
        assert "7.60" in html

    def test_cta_renders(self):
        html = render_template("carousel/slide_cta", self.slides[-1])
        assert "<html" in html
        assert "windsurfworldtourstats.com" in html.lower()

    def test_all_slides_1080x1350(self):
        for slide in self.slides:
            template = f"carousel/slide_{slide['type']}"
            html = render_template(template, slide)
            assert "1080" in html
            assert "1350" in html

    def test_cover_has_footer(self):
        html = render_template("carousel/slide_rp_cover", self.slides[0])
        assert "carousel-footer" in html

    def test_cta_hides_footer(self):
        assert self.slides[-1].get("hide_footer") is True


class TestRPJumpTemplateRendering:
    def setup_method(self):
        self.slides = build_slides(_jump_data())

    def test_jumps_renders_valid_html(self):
        jumps = [s for s in self.slides if s["type"] == "rp_jumps"][0]
        html = render_template("carousel/slide_rp_jumps", jumps)
        assert "<html" in html
        assert "TOP 5 JUMPS" in html

    def test_jumps_shows_scores(self):
        jumps = [s for s in self.slides if s["type"] == "rp_jumps"][0]
        html = render_template("carousel/slide_rp_jumps", jumps)
        assert "10.00" in html
        assert "9.00" in html

    def test_jumps_shows_move_names(self):
        jumps = [s for s in self.slides if s["type"] == "rp_jumps"][0]
        html = render_template("carousel/slide_rp_jumps", jumps)
        assert "Push Loop Forward" in html
