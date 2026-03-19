"""Tests for content scheduler module."""
import pytest
import textwrap
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, call

from pipeline.scheduler import (
    load_calendar,
    filter_posts,
    filter_posts_due,
    mark_post_published,
    resolve_post_data,
    run_calendar,
    run_poll,
    sort_by_scheduled_date,
    validate_scheduled_dates,
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


# ── Per-post scheduled_date support ──────────────────────────────


SCHEDULED_POSTS = [
    {
        "id": "post-later",
        "template": "top_10",
        "params": {"score_type": "Wave", "sex": "Men"},
        "category": "evergreen",
        "scheduled_date": "2026-04-02T12:00:00",
    },
    {
        "id": "post-sooner",
        "template": "top_10",
        "params": {"score_type": "Wave", "sex": "Women"},
        "category": "evergreen",
        "scheduled_date": "2026-03-25T09:00:00",
    },
    {
        "id": "post-no-date",
        "template": "site_stats",
        "category": "recurring",
    },
]


class TestSortByScheduledDate:
    def test_sorts_posts_by_date_ascending(self):
        sorted_posts = sort_by_scheduled_date(SCHEDULED_POSTS[:2])
        assert sorted_posts[0]["id"] == "post-sooner"
        assert sorted_posts[1]["id"] == "post-later"

    def test_posts_without_date_go_last(self):
        sorted_posts = sort_by_scheduled_date(SCHEDULED_POSTS)
        assert sorted_posts[-1]["id"] == "post-no-date"

    def test_empty_list(self):
        assert sort_by_scheduled_date([]) == []


class TestValidateScheduledDates:
    def test_rejects_past_dates(self):
        posts = [{
            "id": "past-post",
            "template": "top_10",
            "params": {"score_type": "Wave", "sex": "Men"},
            "scheduled_date": "2020-01-01T09:00:00",
        }]
        with pytest.raises(ValueError, match="past"):
            validate_scheduled_dates(posts)

    def test_accepts_future_dates(self):
        posts = [{
            "id": "future-post",
            "template": "top_10",
            "params": {"score_type": "Wave", "sex": "Men"},
            "scheduled_date": "2099-01-01T09:00:00",
        }]
        # Should not raise
        validate_scheduled_dates(posts)

    def test_skips_posts_without_date(self):
        posts = [{"id": "no-date", "template": "site_stats"}]
        # Should not raise
        validate_scheduled_dates(posts)


class TestRunCalendarWithScheduledDate:
    """Test that run_calendar uses per-post scheduled_date when publish_mode='schedule'."""

    MOCK_CONFIG = {
        "templates": {"top_10": {"width": 1080, "height": 1350, "dpr": 2}},
        "hashtags": {},
        "captions": {"site_url": "windsurfworldtourstats.com"},
    }

    @patch("pipeline.scheduler.schedule_post")
    @patch("pipeline.scheduler.render_to_png")
    @patch("pipeline.scheduler.render_template")
    @patch("pipeline.scheduler.resolve_post_data")
    @patch("pipeline.scheduler.build_caption")
    @patch("pipeline.scheduler.load_config")
    def test_uses_per_post_scheduled_date(
        self, mock_config, mock_caption, mock_resolve, mock_render_html,
        mock_render_png, mock_schedule
    ):
        mock_config.return_value = self.MOCK_CONFIG
        mock_resolve.return_value = {"title_gender": "Men's"}
        mock_render_html.return_value = "<html>test</html>"
        mock_render_png.return_value = "output/png/top_10_123.png"
        mock_caption.return_value = "caption text"
        mock_schedule.return_value = {"container_id": "container-abc"}

        posts = [SCHEDULED_POSTS[0]]  # has scheduled_date: 2026-04-02T12:00:00
        results = run_calendar(posts, publish_mode="schedule")

        expected_time = datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc)
        mock_schedule.assert_called_once_with(
            "output/png/top_10_123.png", "caption text", expected_time
        )
        assert results[0]["container_id"] == "container-abc"
        assert results[0]["scheduled_date"] == "2026-04-02T12:00:00"

    @patch("pipeline.scheduler.schedule_post")
    @patch("pipeline.scheduler.render_to_png")
    @patch("pipeline.scheduler.render_template")
    @patch("pipeline.scheduler.resolve_post_data")
    @patch("pipeline.scheduler.build_caption")
    @patch("pipeline.scheduler.load_config")
    def test_skips_scheduling_posts_without_date(
        self, mock_config, mock_caption, mock_resolve, mock_render_html,
        mock_render_png, mock_schedule
    ):
        mock_config.return_value = self.MOCK_CONFIG
        mock_resolve.return_value = {"title_gender": "Men's"}
        mock_render_html.return_value = "<html>test</html>"
        mock_render_png.return_value = "output/png/top_10_123.png"
        mock_caption.return_value = "caption text"

        posts = [SCHEDULED_POSTS[2]]  # no scheduled_date
        results = run_calendar(posts, publish_mode="schedule")

        mock_schedule.assert_not_called()
        assert len(results) == 1
        assert results[0]["id"] == "post-no-date"
        assert "skipped" in results[0]

    @patch("pipeline.scheduler.schedule_post")
    @patch("pipeline.scheduler.render_to_png")
    @patch("pipeline.scheduler.render_template")
    @patch("pipeline.scheduler.resolve_post_data")
    @patch("pipeline.scheduler.build_caption")
    @patch("pipeline.scheduler.load_config")
    def test_cli_schedule_time_overrides_post_date(
        self, mock_config, mock_caption, mock_resolve, mock_render_html,
        mock_render_png, mock_schedule
    ):
        """CLI --schedule-start should still work as override."""
        mock_config.return_value = self.MOCK_CONFIG
        mock_resolve.return_value = {"title_gender": "Men's"}
        mock_render_html.return_value = "<html>test</html>"
        mock_render_png.return_value = "output/png/top_10_123.png"
        mock_caption.return_value = "caption text"
        mock_schedule.return_value = {"container_id": "container-xyz"}

        cli_time = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)
        posts = [SCHEDULED_POSTS[0]]  # has scheduled_date
        results = run_calendar(posts, publish_mode="schedule", schedule_time=cli_time)

        # CLI schedule_time takes precedence
        mock_schedule.assert_called_once_with(
            "output/png/top_10_123.png", "caption text", cli_time
        )


# ── Backlog polling ─────────────────────────────────────────────


class TestFilterPostsDue:
    """Test filter_posts_due() — returns posts whose scheduled_date is within the window."""

    def _make_post(self, post_id, scheduled_date=None, published=False):
        post = {"id": post_id, "template": "top_10", "params": {"score_type": "Wave", "sex": "Men"}}
        if scheduled_date:
            post["scheduled_date"] = scheduled_date
        if published:
            post["published"] = True
        return post

    def test_returns_post_due_now(self):
        now = datetime.now(timezone.utc)
        post = self._make_post("due-now", now.isoformat())
        result = filter_posts_due([post], now=now)
        assert len(result) == 1
        assert result[0]["id"] == "due-now"

    def test_returns_post_due_within_lookback(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=20)
        post = self._make_post("due-past", past.isoformat())
        result = filter_posts_due([post], now=now, window_minutes=35)
        assert len(result) == 1

    def test_excludes_post_outside_lookback(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(minutes=60)
        post = self._make_post("too-old", old.isoformat())
        result = filter_posts_due([post], now=now, window_minutes=35)
        assert len(result) == 0

    def test_includes_post_slightly_in_future(self):
        now = datetime.now(timezone.utc)
        future = now + timedelta(minutes=3)
        post = self._make_post("soon", future.isoformat())
        result = filter_posts_due([post], now=now)
        assert len(result) == 1

    def test_excludes_post_far_in_future(self):
        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=2)
        post = self._make_post("later", future.isoformat())
        result = filter_posts_due([post], now=now)
        assert len(result) == 0

    def test_excludes_already_published(self):
        now = datetime.now(timezone.utc)
        post = self._make_post("done", now.isoformat(), published=True)
        result = filter_posts_due([post], now=now)
        assert len(result) == 0

    def test_excludes_no_scheduled_date(self):
        post = self._make_post("no-date")
        result = filter_posts_due([post])
        assert len(result) == 0

    def test_empty_list(self):
        assert filter_posts_due([]) == []

    def test_mixed_posts(self):
        now = datetime.now(timezone.utc)
        posts = [
            self._make_post("due", now.isoformat()),
            self._make_post("published", now.isoformat(), published=True),
            self._make_post("future", (now + timedelta(hours=5)).isoformat()),
            self._make_post("no-date"),
        ]
        result = filter_posts_due(posts, now=now)
        assert len(result) == 1
        assert result[0]["id"] == "due"


class TestMarkPostPublished:
    """Test mark_post_published() — updates YAML in-place preserving comments."""

    def test_marks_post_published(self, tmp_path):
        yaml_content = textwrap.dedent("""\
            # Backlog header comment
            posts:
              - id: post-1
                template: top_10
                scheduled_date: "2026-03-19T15:35:00"

              # Week separator
              - id: post-2
                template: site_stats
                scheduled_date: "2026-03-20T12:00:00"
        """)
        cal_file = tmp_path / "backlog.yaml"
        cal_file.write_text(yaml_content)

        mark_post_published(str(cal_file), "post-1")

        text = cal_file.read_text()
        # Comment preserved
        assert "# Backlog header comment" in text
        assert "# Week separator" in text
        # Post marked
        assert "published: true" in text
        assert "published_at:" in text

        # Only post-1 is marked, not post-2
        from ruamel.yaml import YAML
        ry = YAML()
        data = ry.load(cal_file.read_text())
        p1 = next(p for p in data["posts"] if p["id"] == "post-1")
        p2 = next(p for p in data["posts"] if p["id"] == "post-2")
        assert p1["published"] is True
        assert p1["published_at"] is not None
        assert "published" not in p2 or p2.get("published") is not True

    def test_raises_on_unknown_post_id(self, tmp_path):
        yaml_content = "posts:\n  - id: post-1\n    template: top_10\n"
        cal_file = tmp_path / "backlog.yaml"
        cal_file.write_text(yaml_content)

        with pytest.raises(ValueError, match="not found"):
            mark_post_published(str(cal_file), "nonexistent")


class TestRunPoll:
    """Test run_poll() — orchestrates load → filter → publish → mark."""

    MOCK_CONFIG = {
        "templates": {"top_10": {"width": 1080, "height": 1350, "dpr": 2}},
        "hashtags": {},
        "captions": {"site_url": "windsurfworldtourstats.com"},
    }

    @patch("pipeline.scheduler.mark_post_published")
    @patch("pipeline.scheduler.run_calendar")
    @patch("pipeline.scheduler.filter_posts_due")
    def test_publishes_due_posts_and_marks_them(
        self, mock_filter, mock_run, mock_mark, tmp_path
    ):
        cal_file = tmp_path / "backlog.yaml"
        cal_file.write_text("posts:\n  - id: post-1\n    template: top_10\n")

        due_post = {"id": "post-1", "template": "top_10", "params": {"score_type": "Wave", "sex": "Men"}}
        mock_filter.return_value = [due_post]
        mock_run.return_value = [{"id": "post-1", "output": "out.png", "media_id": "m1"}]

        results = run_poll(str(cal_file))

        mock_run.assert_called_once_with([due_post], publish_mode="now")
        mock_mark.assert_called_once_with(str(cal_file), "post-1")
        assert len(results) == 1

    @patch("pipeline.scheduler.mark_post_published")
    @patch("pipeline.scheduler.run_calendar")
    @patch("pipeline.scheduler.filter_posts_due")
    def test_skips_marking_on_error(self, mock_filter, mock_run, mock_mark, tmp_path):
        cal_file = tmp_path / "backlog.yaml"
        cal_file.write_text("posts:\n  - id: post-1\n    template: top_10\n")

        due_post = {"id": "post-1", "template": "top_10"}
        mock_filter.return_value = [due_post]
        mock_run.return_value = [{"id": "post-1", "error": "API down"}]

        results = run_poll(str(cal_file))

        mock_mark.assert_not_called()
        assert len(results) == 1

    @patch("pipeline.scheduler.run_calendar")
    @patch("pipeline.scheduler.filter_posts_due")
    def test_returns_empty_when_nothing_due(self, mock_filter, mock_run, tmp_path):
        cal_file = tmp_path / "backlog.yaml"
        cal_file.write_text("posts:\n  - id: post-1\n    template: top_10\n")

        mock_filter.return_value = []

        results = run_poll(str(cal_file))

        mock_run.assert_not_called()
        assert results == []
