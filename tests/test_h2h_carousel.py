"""Tests for H2H carousel slide builder and template rendering."""
import pytest

from pipeline.h2h_carousel import build_slides, ACCENT_WAVES, ACCENT_JUMPS
from pipeline.templates import get_dummy_data, render_template


# ── Helpers ──────────────────────────────────────────────────────────────────

def _wave_data():
    """Return H2H data for wave-only event."""
    return get_dummy_data("head_to_head")


def _jump_data():
    """Return H2H data for wave+jump event."""
    return get_dummy_data("head_to_head_jump")


# ── Slide Count ──────────────────────────────────────────────────────────────

class TestSlideCount:
    def test_wave_only_returns_5_slides(self):
        slides = build_slides(_wave_data())
        assert len(slides) == 5

    def test_wave_jump_returns_6_slides(self):
        slides = build_slides(_jump_data())
        assert len(slides) == 6


# ── Slide Types ──────────────────────────────────────────────────────────────

class TestSlideTypes:
    def test_wave_only_types(self):
        slides = build_slides(_wave_data())
        types = [s["type"] for s in slides]
        assert types == ["h2h_cover", "h2h_stat", "h2h_stat", "h2h_stat", "cta"]

    def test_wave_jump_types(self):
        slides = build_slides(_jump_data())
        types = [s["type"] for s in slides]
        assert types == ["h2h_cover", "h2h_stat", "h2h_stat", "h2h_stat", "h2h_stat", "cta"]


# ── Slide Numbering ──────────────────────────────────────────────────────────

class TestSlideNumbering:
    def test_wave_only_numbering(self):
        slides = build_slides(_wave_data())
        for i, slide in enumerate(slides, 1):
            assert slide["slide_number"] == i
            assert slide["total_slides"] == 5

    def test_wave_jump_numbering(self):
        slides = build_slides(_jump_data())
        for i, slide in enumerate(slides, 1):
            assert slide["slide_number"] == i
            assert slide["total_slides"] == 6


# ── Accent Colors ────────────────────────────────────────────────────────────

class TestAccentColors:
    def test_wave_only_uses_cyan(self):
        slides = build_slides(_wave_data())
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
        assert cover["event_name"] == "2026 Margaret River Wave Classic"

    def test_cover_has_athlete_names(self):
        slides = build_slides(_wave_data())
        cover = slides[0]
        assert cover["athlete_1_name"] == "Sarah Kenyon"
        assert cover["athlete_2_name"] == "Jane Seman"

    def test_cover_has_event_metadata(self):
        slides = build_slides(_wave_data())
        cover = slides[0]
        assert "event_country" in cover
        assert "event_date_start" in cover
        assert "event_date_end" in cover
        assert "event_tier" in cover


# ── Stat Slides ──────────────────────────────────────────────────────────────

class TestStatSlides:
    def test_each_stat_slide_has_2_metrics(self):
        slides = build_slides(_wave_data())
        stat_slides = [s for s in slides if s["type"] == "h2h_stat"]
        for slide in stat_slides:
            assert len(slide["metrics"]) == 2

    def test_stat_slide_sections_wave_only(self):
        slides = build_slides(_wave_data())
        stat_slides = [s for s in slides if s["type"] == "h2h_stat"]
        sections = [s["section"] for s in stat_slides]
        assert sections == ["OVERVIEW", "HEAT SCORES", "WAVE SCORES"]

    def test_stat_slide_sections_wave_jump(self):
        slides = build_slides(_jump_data())
        stat_slides = [s for s in slides if s["type"] == "h2h_stat"]
        sections = [s["section"] for s in stat_slides]
        assert sections == ["OVERVIEW", "HEAT SCORES", "WAVE SCORES", "JUMP SCORES"]

    def test_overview_metrics(self):
        slides = build_slides(_wave_data())
        overview = slides[1]
        labels = [m["label"] for m in overview["metrics"]]
        assert labels == ["FINAL PLACEMENT", "HEAT WINS"]

    def test_heat_scores_metrics(self):
        slides = build_slides(_wave_data())
        heats = slides[2]
        labels = [m["label"] for m in heats["metrics"]]
        assert labels == ["BEST HEAT SCORE", "AVERAGE HEAT SCORE"]

    def test_wave_scores_metrics(self):
        slides = build_slides(_wave_data())
        waves = slides[3]
        labels = [m["label"] for m in waves["metrics"]]
        assert labels == ["BEST WAVE", "AVG. COUNTING WAVE"]

    def test_jump_scores_metrics(self):
        slides = build_slides(_jump_data())
        jumps = slides[4]
        labels = [m["label"] for m in jumps["metrics"]]
        assert labels == ["BEST JUMP", "AVG. COUNTING JUMP"]


# ── Metric Winners ───────────────────────────────────────────────────────────

class TestMetricWinners:
    def test_placement_winner_is_lower(self):
        """Lower placement is better (1st beats 2nd)."""
        slides = build_slides(_wave_data())
        overview = slides[1]
        placement = overview["metrics"][0]
        assert placement["winner"] == 1  # athlete 1 has placement 1

    def test_heat_wins_winner(self):
        slides = build_slides(_wave_data())
        overview = slides[1]
        heat_wins = overview["metrics"][1]
        assert heat_wins["winner"] == 1  # athlete 1 has 2 wins vs 1

    def test_best_heat_winner(self):
        slides = build_slides(_wave_data())
        heats = slides[2]
        best_heat = heats["metrics"][0]
        # athlete 2 has 12.03 vs 9.33
        assert best_heat["winner"] == 2

    def test_tie_winner_is_zero(self):
        """When values are equal, winner should be 0."""
        data = _wave_data()
        data["athlete_1_best_heat"] = 10.00
        data["athlete_2_best_heat"] = 10.00
        slides = build_slides(data)
        heats = slides[2]
        best_heat = heats["metrics"][0]
        assert best_heat["winner"] == 0


# ── Metric Values ────────────────────────────────────────────────────────────

class TestMetricValues:
    def test_placement_values_are_ordinals(self):
        slides = build_slides(_wave_data())
        overview = slides[1]
        placement = overview["metrics"][0]
        assert placement["val1"] == "1st"
        assert placement["val2"] == "2nd"

    def test_heat_wins_values_are_integers(self):
        slides = build_slides(_wave_data())
        overview = slides[1]
        heat_wins = overview["metrics"][1]
        assert heat_wins["val1"] == "2"
        assert heat_wins["val2"] == "1"

    def test_score_values_are_formatted(self):
        slides = build_slides(_wave_data())
        heats = slides[2]
        best_heat = heats["metrics"][0]
        assert best_heat["val1"] == "9.33"
        assert best_heat["val2"] == "12.03"

    def test_delta_on_winner_side(self):
        slides = build_slides(_wave_data())
        heats = slides[2]
        best_heat = heats["metrics"][0]
        # athlete 2 wins with 12.03 vs 9.33, delta = 2.70
        assert best_heat["delta"] == "+2.70"

    def test_placement_delta(self):
        """Placement uses integer delta."""
        slides = build_slides(_wave_data())
        overview = slides[1]
        heat_wins = overview["metrics"][1]
        assert heat_wins["delta"] == "+1"


# ── Stat Slides Have Athlete Info ────────────────────────────────────────────

class TestStatSlideAthleteInfo:
    def test_stat_slides_have_athlete_names(self):
        slides = build_slides(_wave_data())
        for slide in slides:
            if slide["type"] == "h2h_stat":
                assert "athlete_1_name" in slide
                assert "athlete_2_name" in slide

    def test_stat_slides_have_athlete_photos(self):
        slides = build_slides(_wave_data())
        for slide in slides:
            if slide["type"] == "h2h_stat":
                assert "athlete_1_photo_url" in slide
                assert "athlete_2_photo_url" in slide


# ── Template Rendering ───────────────────────────────────────────────────────

class TestH2HCarouselTemplateRendering:
    def setup_method(self):
        self.slides = build_slides(_wave_data())

    def test_cover_renders_valid_html(self):
        html = render_template("carousel/slide_h2h_cover", self.slides[0])
        assert "<html" in html
        assert "HEAD TO HEAD" in html

    def test_cover_shows_event_name(self):
        html = render_template("carousel/slide_h2h_cover", self.slides[0])
        assert "MARGARET RIVER" in html

    def test_cover_shows_athlete_names(self):
        html = render_template("carousel/slide_h2h_cover", self.slides[0])
        assert "SARAH" in html
        assert "JANE" in html

    def test_cover_shows_vs(self):
        html = render_template("carousel/slide_h2h_cover", self.slides[0])
        assert "VS" in html

    def test_cover_shows_swipe_hint(self):
        html = render_template("carousel/slide_h2h_cover", self.slides[0])
        assert "Swipe" in html

    def test_stat_slide_renders_valid_html(self):
        html = render_template("carousel/slide_h2h_stat", self.slides[1])
        assert "<html" in html

    def test_stat_slide_shows_section_title(self):
        html = render_template("carousel/slide_h2h_stat", self.slides[1])
        assert "OVERVIEW" in html

    def test_stat_slide_shows_metric_labels(self):
        html = render_template("carousel/slide_h2h_stat", self.slides[1])
        assert "FINAL PLACEMENT" in html
        assert "HEAT WINS" in html

    def test_stat_slide_shows_values(self):
        html = render_template("carousel/slide_h2h_stat", self.slides[1])
        assert "1st" in html
        assert "2nd" in html

    def test_cta_slide_renders(self):
        html = render_template("carousel/slide_cta", self.slides[-1])
        assert "<html" in html
        assert "windsurfworldtourstats.com" in html.lower()

    def test_all_slides_1080x1350(self):
        for slide in self.slides:
            template = f"carousel/slide_{slide['type']}"
            html = render_template(template, slide)
            assert "1080" in html
            assert "1350" in html


# ── Dummy Data ───────────────────────────────────────────────────────────────

class TestH2HCarouselDummyData:
    def test_h2h_carousel_returns_h2h_data(self):
        data = get_dummy_data("h2h_carousel")
        assert "athlete_1_name" in data
        assert "athlete_2_name" in data
        assert "event_name" in data

    def test_h2h_carousel_jump_returns_jump_data(self):
        data = get_dummy_data("h2h_carousel_jump")
        assert "athlete_1_best_jump" in data
        assert "athlete_2_best_jump" in data
