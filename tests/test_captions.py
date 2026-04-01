"""Tests for caption generation module."""
import pytest

from pipeline.captions import build_caption


@pytest.fixture
def config():
    return {
        "hashtags": {
            "head_to_head": ["#windsurf", "#PWA", "#wavewindsurfing", "#windsurfstats"],
            "h2h_carousel": ["#windsurf", "#PWA", "#wavewindsurfing", "#windsurfstats"],
            "top_10": ["#windsurf", "#PWA", "#topwaves", "#windsurfstats"],
            "rider_profile": ["#windsurf", "#PWA", "#riderprofile", "#windsurfstats"],
            "default": ["#windsurf", "#PWA", "#windsurfstats"],
        },
        "captions": {
            "site_url": "windsurfworldtourstats.com",
        },
    }


@pytest.fixture
def h2h_data():
    return {
        "event_name": "Gran Canaria 2025",
        "athlete_1_name": "Philip Köster",
        "athlete_1_placement": 1,
        "athlete_2_name": "Marcilio Browne",
        "athlete_2_placement": 2,
    }


@pytest.fixture
def top10_data():
    return {
        "title_gender": "Men's",
        "title_metric": "Wave Scores",
        "title_year": 2025,
        "entries": [
            {"rank": 1, "athlete": "Marc Pare Rico", "score": 8.83},
        ],
    }


@pytest.fixture
def site_stats_data():
    return {
        "athletes_count": 359,
        "scores_count": 43515,
        "events_count": 58,
    }


@pytest.fixture
def rider_profile_data():
    return {
        "athlete_name": "Sarah-Quita Offringa",
        "event_name": "Tenerife 2025",
        "placement": 1,
        "best_wave": 9.2,
    }


@pytest.fixture
def canary_kings_data():
    return {
        "men": [{"athlete": "Philip Köster", "total": 42}],
        "women": [{"athlete": "Sarah-Quita Offringa", "total": 38}],
    }


@pytest.fixture
def athlete_rise_data():
    return {
        "athlete_name": "Marc Pare Rico",
        "location": "Gran Canaria",
        "yearly_data": [
            {"year": 2019, "best_wave": 5.1},
            {"year": 2025, "best_wave": 8.83},
        ],
    }


# ── Structure tests ─────────────────────────────────────────────


class TestCaptionStructure:
    """All captions must follow the hook → body → CTA → hashtags structure."""

    def test_caption_has_engagement_cta(self, h2h_data, config):
        caption = build_caption("h2h_carousel", h2h_data, config)
        # Should have an engagement prompt (question mark or pointing down emoji)
        assert "?" in caption or "\U0001f447" in caption

    def test_caption_has_emoji(self, h2h_data, config):
        caption = build_caption("h2h_carousel", h2h_data, config)
        # Should contain at least one brand emoji
        brand_emojis = {"\U0001f30a", "\U0001f3c4", "\U0001f525", "\U0001f4ca", "\U0001f3c6"}
        assert any(e in caption for e in brand_emojis)

    def test_caption_has_link_with_arrow(self, h2h_data, config):
        caption = build_caption("h2h_carousel", h2h_data, config)
        assert "\u2192 windsurfworldtourstats.com" in caption

    def test_hashtags_separated_from_body(self, h2h_data, config):
        caption = build_caption("h2h_carousel", h2h_data, config)
        # Hashtags should be on their own line(s), separated by blank line
        parts = caption.split("\n\n")
        last_part = parts[-1].strip()
        assert last_part.startswith("#")

    def test_hook_is_first_line(self, h2h_data, config):
        caption = build_caption("h2h_carousel", h2h_data, config)
        first_line = caption.split("\n")[0]
        # Hook should start with emoji
        brand_emojis = {"\U0001f30a", "\U0001f3c4", "\U0001f525", "\U0001f4ca", "\U0001f3c6"}
        assert any(first_line.startswith(e) for e in brand_emojis)


# ── H2H caption ─────────────────────────────────────────────────


class TestHeadToHeadCaption:
    def test_includes_athlete_names(self, h2h_data, config):
        caption = build_caption("h2h_carousel", h2h_data, config)
        assert "Philip Köster" in caption
        assert "Marcilio Browne" in caption

    def test_includes_event_name(self, h2h_data, config):
        caption = build_caption("h2h_carousel", h2h_data, config)
        assert "Gran Canaria 2025" in caption

    def test_includes_site_url(self, h2h_data, config):
        caption = build_caption("h2h_carousel", h2h_data, config)
        assert "windsurfworldtourstats.com" in caption

    def test_includes_template_hashtags(self, h2h_data, config):
        caption = build_caption("h2h_carousel", h2h_data, config)
        assert "#windsurf" in caption
        assert "#wavewindsurfing" in caption

    def test_has_swipe_cta(self, h2h_data, config):
        caption = build_caption("h2h_carousel", h2h_data, config)
        assert "swipe" in caption.lower() or "Swipe" in caption

    def test_has_engagement_question(self, h2h_data, config):
        caption = build_caption("h2h_carousel", h2h_data, config)
        assert "?" in caption

    def test_legacy_h2h_uses_same_builder(self, h2h_data, config):
        c1 = build_caption("head_to_head", h2h_data, config)
        c2 = build_caption("h2h_carousel", h2h_data, config)
        # Both should have same structure (different hashtags is fine)
        assert "Philip Köster" in c1
        assert "?" in c1

    def test_h2h_jump_uses_same_builder(self, h2h_data, config):
        caption = build_caption("head_to_head_jump", h2h_data, config)
        assert "Philip Köster" in caption
        assert "?" in caption


# ── Top 10 caption ──────────────────────────────────────────────


class TestTop10Caption:
    def test_includes_gender_and_metric(self, top10_data, config):
        caption = build_caption("top_10", top10_data, config)
        assert "men's" in caption.lower() or "Men's" in caption
        assert "wave" in caption.lower() or "Wave" in caption

    def test_includes_year(self, top10_data, config):
        caption = build_caption("top_10", top10_data, config)
        assert "2025" in caption

    def test_includes_site_url(self, top10_data, config):
        caption = build_caption("top_10", top10_data, config)
        assert "windsurfworldtourstats.com" in caption

    def test_includes_template_hashtags(self, top10_data, config):
        caption = build_caption("top_10", top10_data, config)
        assert "#topwaves" in caption

    def test_has_engagement_question(self, top10_data, config):
        caption = build_caption("top_10", top10_data, config)
        assert "?" in caption

    def test_has_swipe_cta(self, top10_data, config):
        caption = build_caption("top_10", top10_data, config)
        assert "swipe" in caption.lower() or "Swipe" in caption

    def test_top10_carousel_alias(self, top10_data, config):
        caption = build_caption("top_10_carousel", top10_data, config)
        assert "?" in caption
        assert "windsurfworldtourstats.com" in caption


class TestTop10DailyCaption:
    def test_includes_day_number(self, top10_data, config):
        top10_data["day"] = 3
        top10_data["event_name"] = "Gran Canaria World Cup"
        caption = build_caption("top_10_carousel", top10_data, config)
        assert "Day 3" in caption

    def test_includes_event_name(self, top10_data, config):
        top10_data["day"] = 1
        top10_data["event_name"] = "Margaret River Wave Classic"
        caption = build_caption("top_10_carousel", top10_data, config)
        assert "Margaret River Wave Classic" in caption

    def test_no_day_uses_standard_caption(self, top10_data, config):
        caption = build_caption("top_10_carousel", top10_data, config)
        assert "Day" not in caption


# ── Site Stats caption ──────────────────────────────────────────


class TestSiteStatsCaption:
    def test_includes_counts(self, site_stats_data, config):
        caption = build_caption("site_stats", site_stats_data, config)
        assert "359" in caption
        assert "43,515" in caption
        assert "58" in caption

    def test_includes_site_url(self, site_stats_data, config):
        caption = build_caption("site_stats", site_stats_data, config)
        assert "windsurfworldtourstats.com" in caption

    def test_uses_default_hashtags(self, site_stats_data, config):
        caption = build_caption("site_stats", site_stats_data, config)
        assert "#windsurf" in caption
        assert "#windsurfstats" in caption

    def test_has_emoji_hook(self, site_stats_data, config):
        caption = build_caption("site_stats", site_stats_data, config)
        first_line = caption.split("\n")[0]
        assert "\U0001f4ca" in first_line

    def test_reel_uses_same_builder(self, site_stats_data, config):
        caption = build_caption("site_stats_reel", site_stats_data, config)
        assert "359" in caption
        assert "\U0001f4ca" in caption


# ── Rider Profile caption ──────────────────────────────────────


class TestRiderProfileCaption:
    def test_includes_athlete_name(self, rider_profile_data, config):
        caption = build_caption("rider_profile", rider_profile_data, config)
        assert "Sarah-Quita Offringa" in caption

    def test_includes_event_name(self, rider_profile_data, config):
        caption = build_caption("rider_profile", rider_profile_data, config)
        assert "Tenerife 2025" in caption

    def test_includes_placement(self, rider_profile_data, config):
        caption = build_caption("rider_profile", rider_profile_data, config)
        assert "1st" in caption

    def test_includes_site_url(self, rider_profile_data, config):
        caption = build_caption("rider_profile", rider_profile_data, config)
        assert "windsurfworldtourstats.com" in caption

    def test_includes_hashtags(self, rider_profile_data, config):
        caption = build_caption("rider_profile", rider_profile_data, config)
        assert "#windsurf" in caption

    def test_has_engagement_question(self, rider_profile_data, config):
        caption = build_caption("rider_profile", rider_profile_data, config)
        assert "?" in caption

    def test_has_swipe_cta(self, rider_profile_data, config):
        caption = build_caption("rider_profile", rider_profile_data, config)
        assert "swipe" in caption.lower() or "Swipe" in caption


# ── Canary Kings caption ────────────────────────────────────────


class TestCanaryKingsCaption:
    def test_includes_king_and_queen(self, canary_kings_data, config):
        caption = build_caption("canary_kings", canary_kings_data, config)
        assert "Philip Köster" in caption
        assert "Sarah-Quita Offringa" in caption

    def test_has_engagement_question(self, canary_kings_data, config):
        caption = build_caption("canary_kings", canary_kings_data, config)
        assert "?" in caption

    def test_has_emoji_hook(self, canary_kings_data, config):
        caption = build_caption("canary_kings", canary_kings_data, config)
        first_line = caption.split("\n")[0]
        brand_emojis = {"\U0001f30a", "\U0001f3c4", "\U0001f525", "\U0001f4ca", "\U0001f3c6"}
        assert any(e in first_line for e in brand_emojis)


# ── Athlete Rise caption ───────────────────────────────────────


class TestAthleteRiseCaption:
    def test_includes_athlete_name(self, athlete_rise_data, config):
        caption = build_caption("athlete_rise", athlete_rise_data, config)
        assert "Marc Pare Rico" in caption

    def test_includes_location(self, athlete_rise_data, config):
        caption = build_caption("athlete_rise", athlete_rise_data, config)
        assert "Gran Canaria" in caption

    def test_includes_year_range(self, athlete_rise_data, config):
        caption = build_caption("athlete_rise", athlete_rise_data, config)
        assert "2019" in caption
        assert "2025" in caption

    def test_has_engagement_question(self, athlete_rise_data, config):
        caption = build_caption("athlete_rise", athlete_rise_data, config)
        assert "?" in caption


# ── Fallback / Override ─────────────────────────────────────────


class TestHashtagFallback:
    def test_unknown_template_uses_default(self, config):
        caption = build_caption("unknown_template", {}, config)
        assert "#windsurf" in caption
        assert "#windsurfstats" in caption


class TestCaptionOverride:
    def test_custom_caption_preserves_hashtags(self, config):
        caption = build_caption(
            "site_stats", {}, config, caption_override="Custom caption here"
        )
        assert caption.startswith("Custom caption here")
        assert "#windsurf" in caption
