"""Tests for the wave-count carousel slide builder + templates.

Structure: cover → top-woman hero → top-man hero → cta. Each hero slide
spotlights the single rider who caught the most waves at the event, with a
full-bleed action photo (name lower-left) and three stats: waves caught,
heats sailed, waves per heat.
"""
import pytest

from pipeline.templates import get_dummy_data, render_template
from pipeline.wave_count_carousel import build_wave_count_slides, _hero_slide, _top_tied


def _rows(counts_and_heats):
    """Build query-result-shaped rows from (wave_count, heats) tuples."""
    return [
        {
            "athlete": f"Athlete {i + 1}",
            "nationality": "Australia",
            "athlete_id": 100 + i,
            "photo_url": None,
            "wave_count": wc,
            "heats": h,
        }
        for i, (wc, h) in enumerate(counts_and_heats)
    ]


# ── Slide structure ──────────────────────────────────────────────────────────

class TestBuildWaveCountSlides:
    def setup_method(self):
        self.men = _rows([(40, 5), (30, 4), (20, 3)])
        self.women = _rows([(18, 3), (12, 2)])
        self.slides = build_wave_count_slides(self.men, self.women)

    def test_returns_four_slides(self):
        assert len(self.slides) == 4

    def test_slide_types_in_order(self):
        types = [s["type"] for s in self.slides]
        assert types == [
            "wavecount_cover",
            "wavecount_hero",
            "wavecount_hero",
            "wavecount_cta",
        ]

    def test_women_hero_is_second(self):
        assert self.slides[1]["division_label"] == "WOMEN"

    def test_men_hero_is_third(self):
        assert self.slides[2]["division_label"] == "MEN"

    def test_hero_spotlights_top_wave_catcher(self):
        # Women top scorer caught 18 waves
        assert self.slides[1]["wave_count"] == 18
        # Men top scorer caught 40
        assert self.slides[2]["wave_count"] == 40

    def test_slides_have_numbering(self):
        for i, slide in enumerate(self.slides, 1):
            assert slide["slide_number"] == i
            assert slide["total_slides"] == 4


class TestTieFeaturesBothRiders:
    def setup_method(self):
        # Two men tied at 30 → both must be featured
        self.men = _rows([(30, 5), (30, 5), (26, 4)])
        self.women = _rows([(18, 3), (12, 2)])
        self.slides = build_wave_count_slides(self.men, self.women)

    def test_extra_slide_for_tied_man(self):
        # cover + 1 woman + 2 men + cta = 5
        assert len(self.slides) == 5

    def test_slide_types(self):
        types = [s["type"] for s in self.slides]
        assert types == [
            "wavecount_cover",
            "wavecount_hero",
            "wavecount_hero",
            "wavecount_hero",
            "wavecount_cta",
        ]

    def test_both_men_featured(self):
        men_slides = [s for s in self.slides if s.get("division_label") == "MEN"]
        assert len(men_slides) == 2
        assert all(s["wave_count"] == 30 for s in men_slides)

    def test_tied_flag_set(self):
        men_slides = [s for s in self.slides if s.get("division_label") == "MEN"]
        assert all(s["tied"] for s in men_slides)

    def test_non_tied_woman_not_flagged(self):
        woman = self.slides[1]
        assert woman["division_label"] == "WOMEN"
        assert woman["tied"] is False

    def test_numbering_updates_to_five(self):
        for i, slide in enumerate(self.slides, 1):
            assert slide["slide_number"] == i
            assert slide["total_slides"] == 5


class TestTopTied:
    def test_returns_single_when_clear_leader(self):
        tied = _top_tied(_rows([(40, 5), (30, 4)]))
        assert len(tied) == 1
        assert int(tied[0]["wave_count"]) == 40

    def test_returns_all_tied_leaders(self):
        tied = _top_tied(_rows([(30, 5), (30, 4), (20, 3)]))
        assert len(tied) == 2

    def test_empty_returns_empty(self):
        assert _top_tied([]) == []


# ── Hero slide data ──────────────────────────────────────────────────────────

class TestHeroSlide:
    def test_carries_athlete_name(self):
        row = _rows([(40, 5)])[0]
        row["athlete"] = "Marcilio Browne"
        slide = _hero_slide(row, "MEN", {})
        assert slide["athlete_name"] == "Marcilio Browne"

    def test_carries_wave_count(self):
        slide = _hero_slide(_rows([(40, 5)])[0], "MEN", {})
        assert slide["wave_count"] == 40

    def test_carries_heats(self):
        slide = _hero_slide(_rows([(40, 5)])[0], "MEN", {})
        assert slide["heats"] == 5

    def test_waves_per_heat_computed(self):
        slide = _hero_slide(_rows([(40, 5)])[0], "MEN", {})
        assert slide["waves_per_heat"] == 8.0

    def test_waves_per_heat_rounded_one_dp(self):
        slide = _hero_slide(_rows([(10, 3)])[0], "MEN", {})
        assert slide["waves_per_heat"] == 3.3

    def test_zero_heats_safe(self):
        slide = _hero_slide(_rows([(0, 0)])[0], "MEN", {})
        assert slide["waves_per_heat"] == 0

    def test_country_converted_to_iso(self):
        slide = _hero_slide(_rows([(40, 5)])[0], "MEN", {})
        assert slide["country"] == "au"

    def test_has_three_stats(self):
        slide = _hero_slide(_rows([(40, 5)])[0], "MEN", {})
        labels = [s["label"].upper() for s in slide["stats"]]
        assert any("WAVES" in l for l in labels)
        assert any("HEAT" in l for l in labels)
        assert len(slide["stats"]) == 3

    def test_empty_division_safe(self):
        slide = _hero_slide(None, "WOMEN", {})
        assert slide["type"] == "wavecount_hero"
        assert slide["wave_count"] == 0


# ── Dummy data ───────────────────────────────────────────────────────────────

class TestWaveCountDummyData:
    def test_returns_men_and_women(self):
        data = get_dummy_data("wave_count")
        assert "men" in data
        assert "women" in data
        assert len(data["men"]) > 0
        assert len(data["women"]) > 0

    def test_rows_have_required_fields(self):
        data = get_dummy_data("wave_count")
        for row in data["men"] + data["women"]:
            assert "athlete" in row
            assert "wave_count" in row
            assert "heats" in row

    def test_builds_slides(self):
        data = get_dummy_data("wave_count")
        slides = build_wave_count_slides(
            data["men"], data["women"], data.get("event_meta")
        )
        assert len(slides) == 4


# ── Template rendering ───────────────────────────────────────────────────────

class TestWaveCountTemplateRendering:
    def setup_method(self):
        data = get_dummy_data("wave_count")
        self.slides = build_wave_count_slides(
            data["men"], data["women"], data.get("event_meta")
        )

    def test_cover_renders(self):
        html = render_template("carousel/slide_wavecount_cover", self.slides[0])
        assert "<html" in html
        assert "CLOUDBREAK" in html.upper()

    def test_hero_slide_renders_name(self):
        slide = self.slides[1]
        html = render_template("carousel/slide_wavecount_hero", slide)
        assert "<html" in html
        assert slide["athlete_name"].upper() in html

    def test_hero_slide_shows_stats(self):
        slide = self.slides[1]
        html = render_template("carousel/slide_wavecount_hero", slide)
        assert str(slide["wave_count"]) in html
        assert "HEAT" in html.upper()

    def test_cta_renders(self):
        html = render_template("carousel/slide_wavecount_cta", self.slides[3])
        assert "<html" in html
        assert "windsurfworldtourstats.com" in html.lower()

    def test_all_slides_1080x1350(self):
        for slide in self.slides:
            html = render_template(f"carousel/slide_{slide['type']}", slide)
            assert "1080" in html
            assert "1350" in html
