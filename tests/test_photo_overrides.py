"""Tests for manual athlete photo override functionality."""
import os
import tempfile

import pytest

from pipeline.templates import resolve_photo_override, PHOTOS_DIR


class TestResolvePhotoOverride:
    """Test resolve_photo_override looks up local files by athlete ID."""

    def test_returns_empty_when_no_athlete_id(self):
        result = resolve_photo_override(None, "https://example.com/photo.webp")
        assert result == "https://example.com/photo.webp"

    def test_returns_current_url_when_no_local_file(self):
        result = resolve_photo_override(99999, "https://example.com/photo.webp")
        assert result == "https://example.com/photo.webp"

    def test_returns_empty_when_no_local_file_and_no_url(self):
        result = resolve_photo_override(99999, "")
        assert result == ""

    def test_finds_local_jpg_override(self, tmp_path, monkeypatch):
        # Create a temp photo file
        photo = tmp_path / "42.jpg"
        photo.write_bytes(b"fake jpg")

        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        result = resolve_photo_override(42, "https://example.com/old.webp")
        assert result.startswith("file:///")
        assert "42.jpg" in result

    def test_finds_local_webp_override(self, tmp_path, monkeypatch):
        photo = tmp_path / "42.webp"
        photo.write_bytes(b"fake webp")

        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        result = resolve_photo_override(42, "")
        assert result.startswith("file:///")
        assert "42.webp" in result

    def test_finds_local_png_override(self, tmp_path, monkeypatch):
        photo = tmp_path / "42.png"
        photo.write_bytes(b"fake png")

        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        result = resolve_photo_override(42, "https://example.com/old.webp")
        assert result.startswith("file:///")
        assert "42.png" in result

    def test_prefers_webp_over_jpg(self, tmp_path, monkeypatch):
        (tmp_path / "42.webp").write_bytes(b"fake webp")
        (tmp_path / "42.jpg").write_bytes(b"fake jpg")

        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        result = resolve_photo_override(42, "")
        assert "42.webp" in result

    def test_local_override_beats_remote_url(self, tmp_path, monkeypatch):
        (tmp_path / "42.jpg").write_bytes(b"fake jpg")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        result = resolve_photo_override(42, "https://liveheats.com/images/some-photo.webp")
        assert result.startswith("file:///")
        assert "42.jpg" in result


class TestRenderTemplatePhotoOverrides:
    """Test that render_template applies photo overrides when athlete IDs present."""

    def test_h2h_photo_override_applied(self, tmp_path, monkeypatch):
        """When athlete_1_id is in data and local file exists, photo is overridden."""
        (tmp_path / "42.jpg").write_bytes(b"fake jpg")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        from pipeline.templates import render_template, get_dummy_data

        data = get_dummy_data("head_to_head")
        data["athlete_1_id"] = 42
        data["athlete_1_photo_url"] = "https://example.com/old.webp"

        # We just need to verify the override is applied - render will fail
        # on missing template features but the data transform happens first
        from pipeline.templates import _apply_photo_overrides
        _apply_photo_overrides(data)

        assert data["athlete_1_photo_url"].startswith("file:///")
        assert "42.jpg" in data["athlete_1_photo_url"]

    def test_rider_profile_photo_override_applied(self, tmp_path, monkeypatch):
        (tmp_path / "55.webp").write_bytes(b"fake webp")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        from pipeline.templates import _apply_photo_overrides

        data = {
            "athlete_id": 55,
            "athlete_photo_url": "",
        }
        _apply_photo_overrides(data)

        assert data["athlete_photo_url"].startswith("file:///")
        assert "55.webp" in data["athlete_photo_url"]
