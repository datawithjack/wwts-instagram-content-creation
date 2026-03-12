"""Tests for scheduled publishing via Meta Graph API."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from pipeline.publisher import create_scheduled_container, schedule_post


@pytest.fixture
def meta_env(monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("META_INSTAGRAM_ACCOUNT_ID", "12345")


@pytest.fixture
def r2_env(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "test-account")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("R2_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("R2_PUBLIC_URL", "https://pub.r2.dev/test-bucket")


class TestCreateScheduledContainer:
    @patch("pipeline.publisher.requests.post")
    def test_sends_scheduled_publish_time(self, mock_post, meta_env):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "container-sched-1"},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        publish_time = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
        cid = create_scheduled_container(
            "https://example.com/img.png", "My caption", publish_time
        )

        assert cid == "container-sched-1"
        call_kwargs = mock_post.call_args
        params = call_kwargs[1]["params"]
        assert params["scheduled_publish_time"] == int(publish_time.timestamp())
        assert params["image_url"] == "https://example.com/img.png"
        assert params["caption"] == "My caption"

    @patch("pipeline.publisher.requests.post")
    def test_rejects_past_time(self, mock_post, meta_env):
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="must be in the future"):
            create_scheduled_container("https://example.com/img.png", "cap", past)

    @patch("pipeline.publisher.requests.post")
    def test_rejects_naive_datetime(self, mock_post, meta_env):
        naive = datetime(2030, 1, 1)
        with pytest.raises(ValueError, match="timezone-aware"):
            create_scheduled_container("https://example.com/img.png", "cap", naive)


class TestSchedulePost:
    @patch("pipeline.publisher.create_scheduled_container")
    @patch("pipeline.publisher.upload_to_r2")
    def test_full_schedule_flow(self, mock_upload, mock_create_sched, r2_env, meta_env):
        mock_upload.return_value = "https://pub.r2.dev/test-bucket/abc.png"
        mock_create_sched.return_value = "container-sched-1"

        publish_time = datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc)
        result = schedule_post("output/test.png", "My caption", publish_time)

        mock_upload.assert_called_once_with("output/test.png")
        mock_create_sched.assert_called_once_with(
            "https://pub.r2.dev/test-bucket/abc.png", "My caption", publish_time
        )
        assert result["container_id"] == "container-sched-1"
        # R2 image should NOT be deleted for scheduled posts (Meta needs it until publish time)
        assert result["image_url"] == "https://pub.r2.dev/test-bucket/abc.png"
