"""Tests for publisher module (R2 upload + Meta Graph API)."""
import pytest
from unittest.mock import patch, MagicMock, call

from pipeline.publisher import (
    upload_to_r2,
    delete_from_r2,
    create_container,
    create_carousel_child,
    create_carousel_container,
    check_recent_media,
    publish_carousel,
    check_container_status,
    wait_for_container,
    publish_container,
    publish,
)


@pytest.fixture
def r2_env(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "test-account")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("R2_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("R2_PUBLIC_URL", "https://pub.r2.dev/test-bucket")


@pytest.fixture
def meta_env(monkeypatch):
    monkeypatch.setenv("META_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("META_INSTAGRAM_ACCOUNT_ID", "12345")


class TestUploadToR2:
    @patch("pipeline.publisher.boto3.client")
    def test_uploads_file_and_returns_url(self, mock_boto_client, r2_env, tmp_path):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        img = tmp_path / "test.png"
        img.write_bytes(b"fake-png")

        url = upload_to_r2(str(img))

        mock_s3.upload_file.assert_called_once()
        call_args = mock_s3.upload_file.call_args
        assert call_args[1]["Filename"] == str(img)
        assert call_args[1]["Bucket"] == "test-bucket"
        assert call_args[1]["Key"].endswith(".png")
        assert url.startswith("https://pub.r2.dev/test-bucket/")

    @patch("pipeline.publisher.boto3.client")
    def test_sets_content_type(self, mock_boto_client, r2_env, tmp_path):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        img = tmp_path / "test.png"
        img.write_bytes(b"fake-png")

        upload_to_r2(str(img))

        call_args = mock_s3.upload_file.call_args
        assert call_args[1]["ExtraArgs"]["ContentType"] == "image/png"


class TestDeleteFromR2:
    @patch("pipeline.publisher.boto3.client")
    def test_deletes_object(self, mock_boto_client, r2_env):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        delete_from_r2("https://pub.r2.dev/test-bucket/abc123.png")

        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="abc123.png"
        )


class TestCreateContainer:
    @patch("pipeline.publisher.requests.post")
    def test_returns_container_id(self, mock_post, meta_env):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "container-789"},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        cid = create_container("https://example.com/img.png", "My caption")

        assert cid == "container-789"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "12345" in call_kwargs[0][0]
        assert call_kwargs[1]["params"]["image_url"] == "https://example.com/img.png"
        assert call_kwargs[1]["params"]["caption"] == "My caption"

    @patch("pipeline.publisher.requests.post")
    def test_raises_on_error(self, mock_post, meta_env):
        mock_post.return_value = MagicMock(status_code=400)
        mock_post.return_value.raise_for_status.side_effect = Exception("Bad request")

        with pytest.raises(Exception, match="Bad request"):
            create_container("https://example.com/img.png", "caption")


class TestCheckContainerStatus:
    @patch("pipeline.publisher.requests.get")
    def test_returns_status(self, mock_get, meta_env):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status_code": "FINISHED"},
        )
        mock_get.return_value.raise_for_status = MagicMock()

        status = check_container_status("container-789")
        assert status == "FINISHED"


class TestWaitForContainer:
    @patch("pipeline.publisher.time.sleep")
    @patch("pipeline.publisher.check_container_status")
    def test_returns_on_finished(self, mock_check, mock_sleep, meta_env):
        mock_check.side_effect = ["IN_PROGRESS", "FINISHED"]

        wait_for_container("container-789")

        assert mock_check.call_count == 2
        mock_sleep.assert_called_once()

    @patch("pipeline.publisher.time.sleep")
    @patch("pipeline.publisher.check_container_status")
    def test_raises_on_error(self, mock_check, mock_sleep, meta_env):
        mock_check.return_value = "ERROR"

        with pytest.raises(RuntimeError, match="failed"):
            wait_for_container("container-789")

    @patch("pipeline.publisher.time.sleep")
    @patch("pipeline.publisher.check_container_status")
    def test_raises_on_timeout(self, mock_check, mock_sleep, meta_env):
        mock_check.return_value = "IN_PROGRESS"

        with pytest.raises(TimeoutError):
            wait_for_container("container-789", max_attempts=3)

        assert mock_check.call_count == 3


class TestPublishContainer:
    @patch("pipeline.publisher.requests.post")
    def test_returns_media_id(self, mock_post, meta_env):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "media-456"},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        media_id = publish_container("container-789")

        assert media_id == "media-456"
        call_kwargs = mock_post.call_args
        assert "12345" in call_kwargs[0][0]
        assert call_kwargs[1]["params"]["creation_id"] == "container-789"

    @patch("pipeline.publisher.time.sleep")
    @patch("pipeline.publisher.check_container_status")
    @patch("pipeline.publisher.requests.post")
    def test_checks_status_before_retry_and_returns_if_published(
        self, mock_post, mock_check, mock_sleep, meta_env
    ):
        """If first publish attempt gets rate-limited but container is already
        PUBLISHED, should not retry — just return the media ID from the container."""
        rate_limit_resp = MagicMock(
            status_code=403,
            json=lambda: {"error": {"code": 4, "message": "rate limited"}},
        )
        rate_limit_resp.raise_for_status.side_effect = Exception("403")
        mock_post.return_value = rate_limit_resp

        # Container already published
        mock_check.return_value = "PUBLISHED"

        # Should not raise — should detect already published
        media_id = publish_container("container-789")

        # Should have checked status before retrying
        mock_check.assert_called_once_with("container-789")
        # Should NOT have retried the publish call
        assert mock_post.call_count == 1
        assert media_id == "container-789"

    @patch("pipeline.publisher.time.sleep")
    @patch("pipeline.publisher.check_container_status")
    @patch("pipeline.publisher.requests.post")
    def test_retries_when_rate_limited_and_not_published(
        self, mock_post, mock_check, mock_sleep, meta_env
    ):
        """If rate-limited and container is NOT published, should retry."""
        rate_limit_resp = MagicMock(
            status_code=403,
            json=lambda: {"error": {"code": 4, "message": "rate limited"}},
        )
        rate_limit_resp.raise_for_status.side_effect = Exception("403")

        success_resp = MagicMock(
            status_code=200,
            json=lambda: {"id": "media-456"},
        )

        mock_post.side_effect = [rate_limit_resp, success_resp]
        mock_check.return_value = "FINISHED"  # Not yet published

        media_id = publish_container("container-789")

        assert media_id == "media-456"
        assert mock_post.call_count == 2
        mock_check.assert_called_once_with("container-789")
        mock_sleep.assert_called_once()

    @patch("pipeline.publisher.time.sleep")
    @patch("pipeline.publisher.check_container_status")
    @patch("pipeline.publisher.requests.post")
    def test_raises_on_non_rate_limit_error(
        self, mock_post, mock_check, mock_sleep, meta_env
    ):
        """Non-rate-limit errors should still check status but raise if not published."""
        error_resp = MagicMock(
            status_code=500,
            json=lambda: {"error": {"code": 100, "message": "server error"}},
        )
        error_resp.raise_for_status.side_effect = Exception("500")
        mock_post.return_value = error_resp
        mock_check.return_value = "ERROR"

        with pytest.raises(Exception, match="500"):
            publish_container("container-789")

        mock_check.assert_called_once_with("container-789")
        assert mock_post.call_count == 1


class TestPublishOrchestration:
    @patch("pipeline.publisher.delete_from_r2")
    @patch("pipeline.publisher.publish_container")
    @patch("pipeline.publisher.wait_for_container")
    @patch("pipeline.publisher.create_container")
    @patch("pipeline.publisher.upload_to_r2")
    def test_full_flow(
        self, mock_upload, mock_create, mock_wait, mock_publish, mock_delete
    ):
        mock_upload.return_value = "https://pub.r2.dev/test-bucket/abc.png"
        mock_create.return_value = "container-789"
        mock_publish.return_value = "media-456"

        result = publish("output/test.png", "My caption")

        mock_upload.assert_called_once_with("output/test.png")
        mock_create.assert_called_once_with(
            "https://pub.r2.dev/test-bucket/abc.png", "My caption"
        )
        mock_wait.assert_called_once_with("container-789")
        mock_publish.assert_called_once_with("container-789")
        mock_delete.assert_called_once_with("https://pub.r2.dev/test-bucket/abc.png")

        assert result["media_id"] == "media-456"
        assert result["media_url"] == "https://pub.r2.dev/test-bucket/abc.png"

    @patch("pipeline.publisher.delete_from_r2")
    @patch("pipeline.publisher.publish_container")
    @patch("pipeline.publisher.wait_for_container")
    @patch("pipeline.publisher.create_container")
    @patch("pipeline.publisher.upload_to_r2")
    def test_cleans_up_on_failure(
        self, mock_upload, mock_create, mock_wait, mock_publish, mock_delete
    ):
        mock_upload.return_value = "https://pub.r2.dev/test-bucket/abc.png"
        mock_create.side_effect = Exception("API error")

        with pytest.raises(Exception, match="API error"):
            publish("output/test.png", "My caption")

        mock_delete.assert_called_once_with("https://pub.r2.dev/test-bucket/abc.png")


class TestCreateCarouselChild:
    @patch("pipeline.publisher.requests.post")
    def test_returns_child_id(self, mock_post, meta_env):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "child-111"},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        cid = create_carousel_child("https://example.com/img.png")

        assert cid == "child-111"
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["params"]["is_carousel_item"] == "true"
        assert call_kwargs[1]["params"]["image_url"] == "https://example.com/img.png"

    @patch("pipeline.publisher.time.sleep")
    @patch("pipeline.publisher.requests.post")
    def test_retries_on_500_then_succeeds(self, mock_post, mock_sleep, meta_env):
        """Transient 500 errors should be retried."""
        error_resp = MagicMock(status_code=500)
        error_resp.raise_for_status.side_effect = Exception("500 Server Error")

        success_resp = MagicMock(
            status_code=200,
            json=lambda: {"id": "child-111"},
        )
        success_resp.raise_for_status = MagicMock()

        mock_post.side_effect = [error_resp, success_resp]

        cid = create_carousel_child("https://example.com/img.png")

        assert cid == "child-111"
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once()

    @patch("pipeline.publisher.time.sleep")
    @patch("pipeline.publisher.requests.post")
    def test_raises_after_max_retries(self, mock_post, mock_sleep, meta_env):
        """Should raise after exhausting retries."""
        error_resp = MagicMock(status_code=500)
        error_resp.raise_for_status.side_effect = Exception("500 Server Error")
        mock_post.return_value = error_resp

        with pytest.raises(Exception, match="500 Server Error"):
            create_carousel_child("https://example.com/img.png")

        # 1 initial + 2 retries = 3 attempts
        assert mock_post.call_count == 3

    @patch("pipeline.publisher.requests.post")
    def test_no_retry_on_400(self, mock_post, meta_env):
        """Non-5xx errors should not be retried."""
        error_resp = MagicMock(status_code=400)
        error_resp.raise_for_status.side_effect = Exception("400 Bad Request")
        mock_post.return_value = error_resp

        with pytest.raises(Exception, match="400 Bad Request"):
            create_carousel_child("https://example.com/img.png")

        assert mock_post.call_count == 1


class TestCreateCarouselContainer:
    @patch("pipeline.publisher.requests.post")
    def test_returns_container_id(self, mock_post, meta_env):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "carousel-999"},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        cid = create_carousel_container(["child-1", "child-2", "child-3"], "My caption")

        assert cid == "carousel-999"
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["params"]["media_type"] == "CAROUSEL"
        assert call_kwargs[1]["params"]["children"] == "child-1,child-2,child-3"
        assert call_kwargs[1]["params"]["caption"] == "My caption"


class TestCheckRecentMedia:
    @patch("pipeline.publisher.requests.get")
    def test_returns_true_when_caption_matches(self, mock_get, meta_env):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"data": [
                {"id": "m1", "caption": "Top 10 men's waves — 2025.", "timestamp": "2026-03-19T16:50:00+0000"},
                {"id": "m2", "caption": "Old post", "timestamp": "2026-03-19T10:00:00+0000"},
            ]},
        )
        mock_get.return_value.raise_for_status = MagicMock()

        result = check_recent_media("Top 10 men's waves — 2025.")
        assert result is True

    @patch("pipeline.publisher.requests.get")
    def test_returns_false_when_no_match(self, mock_get, meta_env):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"data": [
                {"id": "m1", "caption": "Something else", "timestamp": "2026-03-19T16:50:00+0000"},
            ]},
        )
        mock_get.return_value.raise_for_status = MagicMock()

        result = check_recent_media("Top 10 men's waves")
        assert result is False

    @patch("pipeline.publisher.requests.get")
    def test_returns_false_on_api_error(self, mock_get, meta_env):
        mock_get.return_value = MagicMock()
        mock_get.return_value.raise_for_status.side_effect = Exception("API error")

        result = check_recent_media("anything")
        assert result is False

    @patch("pipeline.publisher.requests.get")
    def test_returns_false_when_empty(self, mock_get, meta_env):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"data": []},
        )
        mock_get.return_value.raise_for_status = MagicMock()

        result = check_recent_media("anything")
        assert result is False


class TestPublishCarousel:
    @patch("pipeline.publisher.delete_from_r2")
    @patch("pipeline.publisher.publish_container")
    @patch("pipeline.publisher.wait_for_container")
    @patch("pipeline.publisher.create_carousel_container")
    @patch("pipeline.publisher.create_carousel_child")
    @patch("pipeline.publisher.upload_to_r2")
    def test_full_carousel_flow(
        self, mock_upload, mock_child, mock_carousel, mock_wait, mock_publish, mock_delete
    ):
        mock_upload.side_effect = [
            "https://r2/img1.png",
            "https://r2/img2.png",
            "https://r2/img3.png",
        ]
        mock_child.side_effect = ["child-1", "child-2", "child-3"]
        mock_carousel.return_value = "carousel-999"
        mock_publish.return_value = "media-456"

        result = publish_carousel(
            ["out/1.png", "out/2.png", "out/3.png"], "My caption"
        )

        assert mock_upload.call_count == 3
        assert mock_child.call_count == 3
        mock_carousel.assert_called_once_with(
            ["child-1", "child-2", "child-3"], "My caption"
        )
        mock_wait.assert_called_once_with("carousel-999")
        mock_publish.assert_called_once_with("carousel-999")
        assert mock_delete.call_count == 3
        assert result["media_id"] == "media-456"

    @patch("pipeline.publisher.delete_from_r2")
    @patch("pipeline.publisher.create_carousel_child")
    @patch("pipeline.publisher.upload_to_r2")
    def test_cleans_up_r2_on_failure(self, mock_upload, mock_child, mock_delete):
        mock_upload.side_effect = ["https://r2/img1.png", "https://r2/img2.png"]
        mock_child.side_effect = Exception("API error")

        with pytest.raises(Exception, match="API error"):
            publish_carousel(["out/1.png", "out/2.png"], "caption")

        assert mock_delete.call_count == 2

    @patch("pipeline.publisher.time.sleep")
    @patch("pipeline.publisher.delete_from_r2")
    @patch("pipeline.publisher.check_recent_media")
    @patch("pipeline.publisher.check_container_status")
    @patch("pipeline.publisher.publish_container")
    @patch("pipeline.publisher.wait_for_container")
    @patch("pipeline.publisher.create_carousel_container")
    @patch("pipeline.publisher.create_carousel_child")
    @patch("pipeline.publisher.upload_to_r2")
    def test_detects_already_published_via_recent_media(
        self, mock_upload, mock_child, mock_carousel, mock_wait,
        mock_publish, mock_status, mock_recent, mock_delete, mock_sleep
    ):
        """When publish_container fails and container status is ERROR,
        check_recent_media should detect the post was actually published."""
        mock_upload.side_effect = ["https://r2/img1.png", "https://r2/img2.png"]
        mock_child.side_effect = ["child-1", "child-2"]
        mock_carousel.return_value = "carousel-999"
        mock_publish.side_effect = Exception("400 Bad Request")
        mock_status.return_value = "ERROR"
        mock_recent.return_value = True  # Post found on Instagram

        result = publish_carousel(["out/1.png", "out/2.png"], "My caption")

        mock_recent.assert_called_once_with("My caption")
        # Should return success, not raise
        assert result["media_id"] == "carousel-999"
        # Should clean up R2
        assert mock_delete.call_count == 2
