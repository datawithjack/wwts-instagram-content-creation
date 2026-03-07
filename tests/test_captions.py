"""Tests for caption generation module."""
import pytest

from pipeline.captions import build_caption


@pytest.fixture
def config():
    return {
        "hashtags": {
            "head_to_head": ["#windsurf", "#PWA", "#wavewindsurfing", "#windsurfstats"],
            "top_10": ["#windsurf", "#PWA", "#topwaves", "#windsurfstats"],
            "default": ["#windsurf", "#PWA", "#windsurfstats"],
        },
        "captions": {
            "site_url": "windsurfworldtourstats.com",
        },
    }


@pytest.fixture
def h2h_data():
    return {
        "event_name": "2026 Margaret River Wave Classic",
        "athlete_1_name": "Sarah Kenyon",
        "athlete_1_placement": 1,
        "athlete_2_name": "Jane Seman",
        "athlete_2_placement": 2,
    }


@pytest.fixture
def top10_data():
    return {
        "title_gender": "Men's",
        "title_metric": "Waves",
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


class TestHeadToHeadCaption:
    def test_includes_event_name(self, h2h_data, config):
        caption = build_caption("head_to_head", h2h_data, config)
        assert "2026 Margaret River Wave Classic" in caption

    def test_includes_athlete_names(self, h2h_data, config):
        caption = build_caption("head_to_head", h2h_data, config)
        assert "Sarah Kenyon" in caption
        assert "Jane Seman" in caption

    def test_includes_site_url(self, h2h_data, config):
        caption = build_caption("head_to_head", h2h_data, config)
        assert "windsurfworldtourstats.com" in caption

    def test_includes_template_hashtags(self, h2h_data, config):
        caption = build_caption("head_to_head", h2h_data, config)
        assert "#windsurf" in caption
        assert "#wavewindsurfing" in caption

    def test_h2h_jump_uses_same_hashtags(self, h2h_data, config):
        caption = build_caption("head_to_head_jump", h2h_data, config)
        assert "#wavewindsurfing" in caption


class TestTop10Caption:
    def test_includes_gender(self, top10_data, config):
        caption = build_caption("top_10", top10_data, config)
        assert "Men's" in caption

    def test_includes_metric(self, top10_data, config):
        caption = build_caption("top_10", top10_data, config)
        assert "Waves" in caption

    def test_includes_year(self, top10_data, config):
        caption = build_caption("top_10", top10_data, config)
        assert "2025" in caption

    def test_includes_template_hashtags(self, top10_data, config):
        caption = build_caption("top_10", top10_data, config)
        assert "#topwaves" in caption

    def test_includes_site_url(self, top10_data, config):
        caption = build_caption("top_10", top10_data, config)
        assert "windsurfworldtourstats.com" in caption


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
