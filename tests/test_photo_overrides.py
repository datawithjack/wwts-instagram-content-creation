"""Tests for manual athlete photo override functionality."""
import os
import tempfile

import pytest

from pipeline.templates import (
    resolve_photo_override,
    resolve_action_url,
    resolve_thumb_url,
    PHOTOS_DIR,
)


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


def _mk(path):
    """Create a parent dir tree and write a stub file at path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


class TestResolveActionUrl:
    """Cover/action chain: events/{event}/{id} → flat {id} → current_url.

    Deliberately NO faces/ fallback — a tight headshot must never be used as
    the full-bleed cover. When nothing resolves, the cover falls back to the
    plain (non-photo) background via an empty result.
    """

    def test_returns_current_url_when_nothing_local(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        assert resolve_action_url(42, 25, "https://x/p.webp") == "https://x/p.webp"

    def test_returns_empty_when_no_local_and_no_url(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        assert resolve_action_url(42, 25, "") == ""

    def test_returns_empty_when_no_athlete_id(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        assert resolve_action_url(None, 25, "") == ""

    def test_finds_event_specific_photo(self, tmp_path, monkeypatch):
        _mk(tmp_path / "events" / "25" / "42.jpg")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        result = resolve_action_url(42, 25, "")
        assert result.startswith("file:///")
        assert "events/25/42.jpg" in result

    def test_event_photo_beats_flat_and_url(self, tmp_path, monkeypatch):
        _mk(tmp_path / "42.jpg")  # legacy flat
        _mk(tmp_path / "events" / "25" / "42.webp")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        result = resolve_action_url(42, 25, "https://x/p.webp")
        assert "events/25/42.webp" in result

    def test_falls_back_to_flat_when_no_event_photo(self, tmp_path, monkeypatch):
        _mk(tmp_path / "42.jpg")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        result = resolve_action_url(42, 25, "https://x/p.webp")
        assert "42.jpg" in result and "events" not in result

    def test_no_event_id_uses_flat(self, tmp_path, monkeypatch):
        _mk(tmp_path / "42.jpg")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        assert "42.jpg" in resolve_action_url(42, None, "")

    def test_prefers_webp_in_event_folder(self, tmp_path, monkeypatch):
        _mk(tmp_path / "events" / "25" / "42.webp")
        _mk(tmp_path / "events" / "25" / "42.jpg")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        assert "events/25/42.webp" in resolve_action_url(42, 25, "")

    def test_does_not_fall_back_to_face_for_cover(self, tmp_path, monkeypatch):
        """A faces/{id} headshot must NOT satisfy the cover action photo."""
        _mk(tmp_path / "faces" / "42.jpg")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        assert resolve_action_url(42, 25, "") == ""


class TestResolveThumbUrl:
    """Thumbnail chain (data-slide square): faces/{id} → flat {id} → current_url."""

    def test_returns_current_url_when_nothing_local(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        assert resolve_thumb_url(42, "https://x/p.webp") == "https://x/p.webp"

    def test_returns_empty_when_no_athlete_id(self, tmp_path, monkeypatch):
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        assert resolve_thumb_url(None, "") == ""

    def test_finds_face_photo(self, tmp_path, monkeypatch):
        _mk(tmp_path / "faces" / "42.jpg")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        result = resolve_thumb_url(42, "")
        assert result.startswith("file:///")
        assert "faces/42.jpg" in result

    def test_face_beats_flat(self, tmp_path, monkeypatch):
        _mk(tmp_path / "42.jpg")  # legacy flat action
        _mk(tmp_path / "faces" / "42.webp")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        assert "faces/42.webp" in resolve_thumb_url(42, "")

    def test_falls_back_to_flat_when_no_face(self, tmp_path, monkeypatch):
        _mk(tmp_path / "42.jpg")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        result = resolve_thumb_url(42, "")
        assert "42.jpg" in result and "faces" not in result

    def test_prefers_webp_in_faces_folder(self, tmp_path, monkeypatch):
        _mk(tmp_path / "faces" / "42.webp")
        _mk(tmp_path / "faces" / "42.jpg")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))
        assert "faces/42.webp" in resolve_thumb_url(42, "")


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

    def test_thumb_uses_face_subfolder_when_present(self, tmp_path, monkeypatch):
        """A faces/{id} file drives athlete_thumb_url, separate from the action photo."""
        (tmp_path / "55.jpg").write_bytes(b"action")
        _mk(tmp_path / "faces" / "55.jpg")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        from pipeline.templates import _apply_photo_overrides

        data = {"athlete_id": 55, "athlete_photo_url": ""}
        _apply_photo_overrides(data)

        # Action photo = legacy flat {id}
        assert "55.jpg" in data["athlete_photo_url"]
        assert "faces" not in data["athlete_photo_url"]
        # Thumb = faces/{id}
        assert data["athlete_thumb_url"].startswith("file:///")
        assert "faces/55.jpg" in data["athlete_thumb_url"]

    def test_event_photo_drives_cover(self, tmp_path, monkeypatch):
        """An events/{event}/{id} photo overrides the API url for the cover."""
        _mk(tmp_path / "events" / "25" / "55.jpg")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        from pipeline.templates import _apply_photo_overrides

        data = {"athlete_id": 55, "event_id": 25, "athlete_photo_url": "https://api/x.webp"}
        _apply_photo_overrides(data)

        assert "events/25/55.jpg" in data["athlete_photo_url"]

    def test_no_local_cover_keeps_api_url(self, tmp_path, monkeypatch):
        """With no local action photo, the cover keeps the API url unchanged."""
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        from pipeline.templates import _apply_photo_overrides

        data = {"athlete_id": 55, "event_id": 25, "athlete_photo_url": "https://api/x.webp"}
        _apply_photo_overrides(data)

        assert data["athlete_photo_url"] == "https://api/x.webp"

    def test_thumb_falls_back_to_action_photo(self, tmp_path, monkeypatch):
        """With no face file, the thumb falls back to the (overridden) action photo."""
        (tmp_path / "55.jpg").write_bytes(b"action")
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        from pipeline.templates import _apply_photo_overrides

        data = {"athlete_id": 55, "athlete_photo_url": ""}
        _apply_photo_overrides(data)

        assert data["athlete_thumb_url"] == data["athlete_photo_url"]
        assert "55.jpg" in data["athlete_thumb_url"]

    def test_thumb_falls_back_to_api_url_when_no_local_files(self, monkeypatch, tmp_path):
        """No local files at all → thumb falls back to whatever athlete_photo_url holds (API url)."""
        monkeypatch.setattr("pipeline.templates.PHOTOS_DIR", str(tmp_path))

        from pipeline.templates import _apply_photo_overrides

        data = {"athlete_id": 55, "athlete_photo_url": "https://example.com/api.webp"}
        _apply_photo_overrides(data)

        assert data["athlete_thumb_url"] == "https://example.com/api.webp"
