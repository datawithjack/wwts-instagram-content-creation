"""Tests for content scheduler module."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, call

from pipeline.scheduler import (
    load_calendar,
    filter_posts,
    resolve_post_data,
    run_calendar,
)


SAMPLE_CALENDAR = {
    "posts": [
        {
            "id": "alltime-mens-waves",
            "template": "top_10",
            "params": {"score_type": "Wave", "sex": "Men"},
            "caption": "The greatest men's waves in PWA history",
            "category": "evergreen",
        },
        {
            "id": "alltime-womens-waves",
            "template": "top_10",
            "params": {"score_type": "Wave", "sex": "Women"},
            "caption": "The greatest women's waves in PWA history",
            "category": "evergreen",
        },
        {
            "id": "2025-mens-waves",
            "template": "top_10",
            "params": {"score_type": "Wave", "sex": "Men", "year": 2025},
            "caption": "Top 10 men's waves of the 2025 season",
            "category": "seasonal",
        },
        {
            "id": "site-stats-weekly",
            "template": "site_stats",
            "category": "recurring",
        },
        {
            "id": "classic-h2h",
            "template": "head_to_head",
            "params": {
                "event": 38,
                "athlete1": 12,
                "athlete2": 7,
                "division": "Men",
            },
            "caption": "A rivalry for the ages",
            "category": "evergreen",
        },
    ]
}


class TestLoadCalendar:
    def test_loads_yaml_file(self, tmp_path):
        import yaml

        cal_file = tmp_path / "calendar.yaml"
        cal_file.write_text(yaml.dump(SAMPLE_CALENDAR))

        result = load_calendar(str(cal_file))
        assert len(result["posts"]) == 5
        assert result["posts"][0]["id"] == "alltime-mens-waves"

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_calendar("/nonexistent/calendar.yaml")


class TestFilterPosts:
    def test_filter_by_category(self):
        posts = filter_posts(SAMPLE_CALENDAR["posts"], category="evergreen")
        assert len(posts) == 3
        assert all(p["category"] == "evergreen" for p in posts)

    def test_filter_by_template(self):
        posts = filter_posts(SAMPLE_CALENDAR["posts"], template="top_10")
        assert len(posts) == 3
        assert all(p["template"] == "top_10" for p in posts)

    def test_filter_by_ids(self):
        posts = filter_posts(
            SAMPLE_CALENDAR["posts"],
            ids=["alltime-mens-waves", "classic-h2h"],
        )
        assert len(posts) == 2
        assert {p["id"] for p in posts} == {"alltime-mens-waves", "classic-h2h"}

    def test_filter_combined(self):
        posts = filter_posts(
            SAMPLE_CALENDAR["posts"], category="evergreen", template="top_10"
        )
        assert len(posts) == 2

    def test_no_filter_returns_all(self):
        posts = filter_posts(SAMPLE_CALENDAR["posts"])
        assert len(posts) == 5


class TestResolvePostData:
    @patch("pipeline.scheduler.fetch_site_stats")
    def test_site_stats_no_params_needed(self, mock_fetch):
        mock_fetch.return_value = {"athletes_count": 100, "scores_count": 5000}
        post = {"template": "site_stats", "category": "recurring"}

        data = resolve_post_data(post)
        assert data["athletes_count"] == 100
        mock_fetch.assert_called_once()

    @patch("pipeline.scheduler.run_query")
    def test_top10_uses_params(self, mock_query):
        mock_query.return_value = [
            {"athlete": "Marc Pare Rico", "country": "ES", "score": 8.83,
             "event": "Pozo", "round": "Final"},
        ]
        post = {
            "template": "top_10",
            "params": {"score_type": "Wave", "sex": "Men", "year": 2025},
        }

        data = resolve_post_data(post)
        assert data["title_gender"] == "Men's"
        assert data["title_metric"] == "Waves"
        assert data["title_year"] == 2025
        assert len(data["entries"]) == 1

    @patch("pipeline.scheduler.fetch_head_to_head")
    def test_h2h_uses_params(self, mock_fetch):
        mock_fetch.return_value = {"athlete_1_name": "Ath1", "athlete_2_name": "Ath2"}
        post = {
            "template": "head_to_head",
            "params": {"event": 38, "athlete1": 12, "athlete2": 7, "division": "Men"},
        }

        data = resolve_post_data(post)
        assert data["athlete_1_name"] == "Ath1"
        mock_fetch.assert_called_once_with(
            event_id=38, athlete1_id=12, athlete2_id=7, division="Men"
        )


class TestRunCalendar:
    @patch("pipeline.scheduler.publish")
    @patch("pipeline.scheduler.render_to_png")
    @patch("pipeline.scheduler.render_template")
    @patch("pipeline.scheduler.resolve_post_data")
    @patch("pipeline.scheduler.build_caption")
    @patch("pipeline.scheduler.load_config")
    def test_render_only_no_publish(
        self, mock_config, mock_caption, mock_resolve, mock_render_html,
        mock_render_png, mock_publish
    ):
        mock_config.return_value = {
            "templates": {"top_10": {"width": 1080, "height": 1350, "dpr": 2}},
            "hashtags": {},
            "captions": {"site_url": "windsurfworldtourstats.com"},
        }
        mock_resolve.return_value = {"title_gender": "Men's"}
        mock_render_html.return_value = "<html>test</html>"
        mock_render_png.return_value = "output/png/top_10_123.png"
        mock_caption.return_value = "caption text"

        posts = [SAMPLE_CALENDAR["posts"][0]]
        results = run_calendar(posts, publish_mode=None)

        assert len(results) == 1
        assert results[0]["id"] == "alltime-mens-waves"
        assert results[0]["output"] == "output/png/top_10_123.png"
        mock_publish.assert_not_called()

    @patch("pipeline.scheduler.publish")
    @patch("pipeline.scheduler.render_to_png")
    @patch("pipeline.scheduler.render_template")
    @patch("pipeline.scheduler.resolve_post_data")
    @patch("pipeline.scheduler.build_caption")
    @patch("pipeline.scheduler.load_config")
    def test_publish_now(
        self, mock_config, mock_caption, mock_resolve, mock_render_html,
        mock_render_png, mock_publish
    ):
        mock_config.return_value = {
            "templates": {"top_10": {"width": 1080, "height": 1350, "dpr": 2}},
            "hashtags": {},
            "captions": {"site_url": "windsurfworldtourstats.com"},
        }
        mock_resolve.return_value = {"title_gender": "Men's"}
        mock_render_html.return_value = "<html>test</html>"
        mock_render_png.return_value = "output/png/top_10_123.png"
        mock_caption.return_value = "caption text"
        mock_publish.return_value = {"media_id": "media-123"}

        posts = [SAMPLE_CALENDAR["posts"][0]]
        results = run_calendar(posts, publish_mode="now")

        mock_publish.assert_called_once_with("output/png/top_10_123.png", "caption text")
        assert results[0]["media_id"] == "media-123"

    @patch("pipeline.scheduler.schedule_post")
    @patch("pipeline.scheduler.render_to_png")
    @patch("pipeline.scheduler.render_template")
    @patch("pipeline.scheduler.resolve_post_data")
    @patch("pipeline.scheduler.build_caption")
    @patch("pipeline.scheduler.load_config")
    def test_publish_scheduled(
        self, mock_config, mock_caption, mock_resolve, mock_render_html,
        mock_render_png, mock_schedule
    ):
        mock_config.return_value = {
            "templates": {"top_10": {"width": 1080, "height": 1350, "dpr": 2}},
            "hashtags": {},
            "captions": {"site_url": "windsurfworldtourstats.com"},
        }
        mock_resolve.return_value = {"title_gender": "Men's"}
        mock_render_html.return_value = "<html>test</html>"
        mock_render_png.return_value = "output/png/top_10_123.png"
        mock_caption.return_value = "caption text"
        mock_schedule.return_value = {"container_id": "container-789"}

        publish_time = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
        posts = [SAMPLE_CALENDAR["posts"][0]]
        results = run_calendar(posts, publish_mode="schedule", schedule_time=publish_time)

        mock_schedule.assert_called_once_with(
            "output/png/top_10_123.png", "caption text", publish_time
        )
        assert results[0]["container_id"] == "container-789"

    @patch("pipeline.scheduler.publish")
    @patch("pipeline.scheduler.render_to_png")
    @patch("pipeline.scheduler.render_template")
    @patch("pipeline.scheduler.resolve_post_data")
    @patch("pipeline.scheduler.build_caption")
    @patch("pipeline.scheduler.load_config")
    def test_uses_post_caption_override(
        self, mock_config, mock_caption, mock_resolve, mock_render_html,
        mock_render_png, mock_publish
    ):
        mock_config.return_value = {
            "templates": {"top_10": {"width": 1080, "height": 1350, "dpr": 2}},
            "hashtags": {},
            "captions": {"site_url": "windsurfworldtourstats.com"},
        }
        mock_resolve.return_value = {"title_gender": "Men's"}
        mock_render_html.return_value = "<html>test</html>"
        mock_render_png.return_value = "output/png/top_10_123.png"
        mock_caption.return_value = "The greatest men's waves\n\n#windsurf"
        mock_publish.return_value = {"media_id": "media-123"}

        posts = [SAMPLE_CALENDAR["posts"][0]]  # has caption override
        results = run_calendar(posts, publish_mode="now")

        # Should use caption_override from the post definition
        mock_caption.assert_called_once_with(
            "top_10",
            {"title_gender": "Men's"},
            mock_config.return_value,
            "The greatest men's waves in PWA history",
        )

    @patch("pipeline.scheduler.render_to_png")
    @patch("pipeline.scheduler.render_template")
    @patch("pipeline.scheduler.resolve_post_data")
    @patch("pipeline.scheduler.build_caption")
    @patch("pipeline.scheduler.load_config")
    def test_continues_on_error(
        self, mock_config, mock_caption, mock_resolve, mock_render_html,
        mock_render_png
    ):
        mock_config.return_value = {
            "templates": {"top_10": {"width": 1080, "height": 1350, "dpr": 2}},
            "hashtags": {},
            "captions": {"site_url": "windsurfworldtourstats.com"},
        }
        mock_resolve.side_effect = [Exception("DB error"), {"title_gender": "Women's"}]
        mock_render_html.return_value = "<html>test</html>"
        mock_render_png.return_value = "output/png/top_10_123.png"
        mock_caption.return_value = "caption"

        posts = SAMPLE_CALENDAR["posts"][:2]  # two top_10 posts
        results = run_calendar(posts, publish_mode=None)

        assert len(results) == 2
        assert "error" in results[0]
        assert results[1]["output"] == "output/png/top_10_123.png"
