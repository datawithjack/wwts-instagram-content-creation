"""Tests for rider profile carousel slide builder and template rendering."""
import pytest

from pipeline.rp_carousel import build_slides, ACCENT_WAVES, ACCENT_JUMPS
from pipeline.templates import get_dummy_data, render_template


# ── Helpers ──────────────────────────────────────────────────────────────────

def _wave_data():
    """Return rider profile data for wave-only event."""
    return get_dummy_data("rider_profile")


def _jump_data():
    """Return rider profile data for wave+jump event (has best_jump)."""
    data = get_dummy_data("rider_profile")
    data["best_jump"] = 7.50
    return data


def _wave_only_data():
    """Return rider profile data with no jump score."""
    data = get_dummy_data("rider_profile")
    data.pop("best_jump", None)
    return data


# ── Slide Count ──────────────────────────────────────────────────────────────

class TestSlideCount:
    def test_wave_only_returns_5_slides(self):
        slides = build_slides(_wave_only_data())
        assert len(slides) == 5

    def test_wave_jump_returns_5_slides(self):
        slides = build_slides(_jump_data())
        assert len(slides) == 5


# ── Slide Types ──────────────────────────────────────────────────────────────

class TestSlideTypes:
    def test_slide_types(self):
        slides = build_slides(_wave_data())
        types = [s["type"] for s in slides]
        assert types == ["rp_cover", "rp_hero", "rp_stats", "rp_waves", "cta"]


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


# ── Hero Slide ───────────────────────────────────────────────────────────────

class TestHeroSlide:
    def test_hero_has_photo(self):
        slides = build_slides(_wave_data())
        hero = slides[1]
        assert "athlete_photo_url" in hero

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


# ── Stats Slide ──────────────────────────────────────────────────────────────

class TestStatsSlide:
    def test_wave_only_has_3_stats(self):
        slides = build_slides(_wave_only_data())
        stats = slides[2]
        assert len(stats["stats"]) == 3

    def test_wave_jump_has_4_stats(self):
        slides = build_slides(_jump_data())
        stats = slides[2]
        assert len(stats["stats"]) == 4

    def test_stats_have_label_and_value(self):
        slides = build_slides(_wave_data())
        stats = slides[2]
        for stat in stats["stats"]:
            assert "label" in stat
            assert "value" in stat

    def test_stat_values_formatted_2dp(self):
        slides = build_slides(_wave_data())
        stats = slides[2]
        for stat in stats["stats"]:
            assert "." in stat["value"]
            _, decimal = stat["value"].split(".")
            assert len(decimal) == 2

    def test_wave_only_stat_labels(self):
        slides = build_slides(_wave_only_data())
        stats = slides[2]
        labels = [s["label"] for s in stats["stats"]]
        assert labels == ["Best Heat", "Best Wave", "Avg Wave"]

    def test_wave_jump_stat_labels(self):
        slides = build_slides(_jump_data())
        stats = slides[2]
        labels = [s["label"] for s in stats["stats"]]
        assert labels == ["Best Heat", "Best Wave", "Best Jump", "Avg Wave"]

    def test_best_heat_has_round_detail(self):
        slides = build_slides(_wave_data())
        stats = slides[2]
        best_heat = stats["stats"][0]
        assert best_heat["detail"] == "Final"

    def test_stats_has_surname(self):
        slides = build_slides(_wave_data())
        stats = slides[2]
        assert stats["athlete_surname"] == "RICO"


# ── Waves Slide ──────────────────────────────────────────────────────────────

class TestWavesSlide:
    def test_waves_has_5_entries(self):
        slides = build_slides(_wave_data())
        waves = slides[3]
        assert len(waves["top_waves"]) == 5

    def test_wave_entries_have_rank_score_round(self):
        slides = build_slides(_wave_data())
        waves = slides[3]
        for wave in waves["top_waves"]:
            assert "rank" in wave
            assert "score" in wave
            assert "round" in wave

    def test_wave_scores_formatted_2dp(self):
        slides = build_slides(_wave_data())
        waves = slides[3]
        for wave in waves["top_waves"]:
            assert "." in wave["score"]
            _, decimal = wave["score"].split(".")
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
    def test_all_slides_have_slide_number(self):
        slides = build_slides(_wave_data())
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
        assert "RIDER PROFILE" in html

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

    def test_stats_renders_valid_html(self):
        html = render_template("carousel/slide_rp_stats", self.slides[2])
        assert "<html" in html

    def test_stats_shows_stat_labels(self):
        html = render_template("carousel/slide_rp_stats", self.slides[2])
        assert "Best Heat" in html
        assert "Best Wave" in html

    def test_stats_shows_values(self):
        html = render_template("carousel/slide_rp_stats", self.slides[2])
        assert "16.33" in html
        assert "8.83" in html

    def test_waves_renders_valid_html(self):
        html = render_template("carousel/slide_rp_waves", self.slides[3])
        assert "<html" in html
        assert "TOP 5 WAVES" in html

    def test_waves_shows_scores(self):
        html = render_template("carousel/slide_rp_waves", self.slides[3])
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
