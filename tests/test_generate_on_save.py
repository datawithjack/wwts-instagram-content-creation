"""Saving picks should produce the post, not just the photos."""

import pytest

from pick_photos import generation_plan


class TestGenerationPlan:
    """A run only builds a post when it knows what post to build."""

    def test_a_leaderboard_run_can_generate(self):
        plan = generation_plan(124, "Wave", "Women", athletes_mode=False)
        assert plan == {"event_id": 124, "score_type": "Wave", "sex": "Women"}

    def test_athletes_mode_cannot_generate(self):
        """--athletes names riders, not a leaderboard, so there is no post."""
        assert generation_plan(122, "Wave", None, athletes_mode=True) is None

    def test_missing_sex_still_generates(self):
        """The API defaults to the whole fleet when no division is given."""
        plan = generation_plan(124, "Jump", None, athletes_mode=False)
        assert plan["sex"] is None


class TestGenerateAfterInstall:
    """The photos are on disk by the time generation runs, so a failure there
    must report rather than swallow the work."""

    def test_failure_reports_but_keeps_the_installed_photos(self, monkeypatch, capsys):
        import pick_photos

        def boom(**kwargs):
            raise RuntimeError("API down")

        monkeypatch.setattr(pick_photos, "generate_post", boom)
        result = pick_photos.generate_after_save(
            {"event_id": 124, "score_type": "Wave", "sex": "Women"},
            installed=["13 <- TF26_wv_SUI4_1190.jpg"],
        )
        assert result["ok"] is False
        assert "API down" in result["error"]
        # The message has to name what survived, or it reads as a total failure.
        assert "13 <- TF26_wv_SUI4_1190.jpg" in result["installed"]

    def test_success_reports_the_slide_count(self, monkeypatch):
        import pick_photos
        monkeypatch.setattr(pick_photos, "generate_post",
                            lambda **kwargs: ["a.html", "b.html"])
        result = pick_photos.generate_after_save(
            {"event_id": 124, "score_type": "Wave", "sex": "Women"},
            installed=["13 <- x.jpg"],
        )
        assert result["ok"] is True
        assert result["slides"] == 2

    def test_no_plan_skips_generation_without_failing(self, monkeypatch):
        import pick_photos

        def boom(**kwargs):
            raise AssertionError("should not be called")

        monkeypatch.setattr(pick_photos, "generate_post", boom)
        result = pick_photos.generate_after_save(None, installed=["49 <- x.jpg"])
        assert result["ok"] is True
        assert result["skipped"] is True
