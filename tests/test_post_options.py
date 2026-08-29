"""Post options threading, shared by the CLI and the backlog poller.

``--photos`` and its friends used to be threaded into the data inside
``generate.main()`` only. The poller never goes through main(): it calls
``scheduler.resolve_post_data()``, so a backlog entry carrying ``photos: true``
rendered the old hero-plus-tables layout and published uncredited, silently and
in public. These tests pin the shared path both entry points now take.
"""

import argparse

import pytest

from pipeline.carousel import build_slides
from pipeline.post_options import apply_post_options


def _entry(rank, athlete_id):
    return {
        "rank": rank, "athlete": f"Rider {rank}", "athlete_id": athlete_id,
        "country": "es", "score": 10.0 - rank, "event": "Tenerife Grand Slam",
        "round": "Final", "heat": "", "counting": 1,
    }


def _top10():
    return {
        "title_gender": "Women's", "title_metric": "Waves", "title_year": 2026,
        "is_per_event": True, "event_name": "Tenerife Grand Slam",
        "entries": [_entry(i, i) for i in range(1, 11)],
    }


class TestApplyPostOptions:
    """The one place that turns options into data keys."""

    def test_photos_sets_the_mode_the_event_id_and_the_credits(self, monkeypatch):
        monkeypatch.setattr("pipeline.post_options.photo_credits",
                            lambda data: ["@jcwindsurf"])
        data = apply_post_options(_top10(), {"photos": True, "event": 124})
        assert data["photo_mode"] is True
        assert data["photo_event_id"] == 124
        assert data["photo_credits"] == ["@jcwindsurf"]

    def test_no_photos_leaves_the_data_alone(self):
        data = apply_post_options(_top10(), {"event": 124})
        assert "photo_mode" not in data
        assert "photo_credits" not in data

    def test_the_other_flags_ride_the_same_path(self):
        data = apply_post_options(_top10(), {
            "day": "Day 2", "so_far": True, "finals_day": True,
            "rider_of_day": True,
        })
        assert data["day"] == "Day 2"
        assert data["so_far"] is True
        assert data["finals_day"] is True
        assert data["rider_of_day"] is True

    def test_falsey_flags_are_not_written(self):
        """An argparse Namespace carries every flag, most of them off."""
        data = apply_post_options(_top10(), {
            "day": None, "so_far": False, "finals_day": False,
            "rider_of_day": False, "photos": False,
        })
        assert set(data) == set(_top10())

    def test_it_accepts_an_argparse_namespace_as_well_as_a_dict(self, monkeypatch):
        monkeypatch.setattr("pipeline.post_options.photo_credits", lambda data: [])
        args = argparse.Namespace(photos=True, event=124, day=None, so_far=False,
                                  finals_day=False, rider_of_day=False)
        data = apply_post_options(_top10(), vars(args))
        assert data["photo_mode"] is True


class TestSchedulerRendersThePhotoVariant:
    """The failure this ticket exists to stop: a scheduled photo post that
    renders as the old layout and publishes uncredited."""

    def _resolve(self, monkeypatch, params):
        import pipeline.scheduler as scheduler
        monkeypatch.setattr(scheduler, "fetch_event_top_scores",
                            lambda **kwargs: _top10())
        monkeypatch.setattr("pipeline.post_options.photo_credits",
                            lambda data: ["@jcwindsurf", "@pwaworldtour"])
        return scheduler.resolve_post_data(
            {"template": "top_10_carousel", "params": params}
        )

    def test_a_backlog_entry_with_photos_renders_photo_slides(self, monkeypatch):
        data = self._resolve(monkeypatch,
                             {"score_type": "Wave", "sex": "Women",
                              "event": 124, "photos": True})
        assert [s["type"] for s in build_slides(data)] == [
            "cover", "wave_photo", "wave_photo", "wave_photo", "wave_photo",
            "wave_photo", "table", "cta",
        ]

    def test_without_photos_it_is_still_the_ordinary_layout(self, monkeypatch):
        data = self._resolve(monkeypatch,
                             {"score_type": "Wave", "sex": "Women", "event": 124})
        types = [s["type"] for s in build_slides(data)]
        assert "wave_photo" not in types

    def test_the_scheduled_caption_carries_the_photographers(self, monkeypatch):
        from pipeline.captions import build_caption

        data = self._resolve(monkeypatch,
                             {"score_type": "Wave", "sex": "Women",
                              "event": 124, "photos": True})
        caption = build_caption("top_10_carousel", data, {"captions": {}})
        assert "\U0001f4f8 @jcwindsurf | @pwaworldtour" in caption

    def test_photos_is_not_passed_on_to_the_api_call(self, monkeypatch):
        """``photos`` is a rendering option, not a query filter."""
        import pipeline.scheduler as scheduler
        seen = {}

        def fake(**kwargs):
            seen.update(kwargs)
            return _top10()

        monkeypatch.setattr(scheduler, "fetch_event_top_scores", fake)
        monkeypatch.setattr("pipeline.post_options.photo_credits", lambda data: [])
        scheduler.resolve_post_data({
            "template": "top_10_carousel",
            "params": {"score_type": "Wave", "sex": "Women", "event": 124,
                       "photos": True},
        })
        assert "photos" not in seen

    def test_a_delegated_template_survives_an_unknown_option(self, monkeypatch):
        """``_CLI_ARG_DEFAULTS`` had no ``photos`` key, so the delegating path
        built a Namespace the CLI's own getattr calls could still read only by
        luck. Pin that a photos-carrying entry reaches fetch_live_data."""
        import pipeline.scheduler as scheduler
        import generate

        captured = {}

        def fake_fetch(template, args):
            captured["photos"] = getattr(args, "photos", "MISSING")
            return _top10()

        monkeypatch.setattr(generate, "fetch_live_data", fake_fetch)
        monkeypatch.setattr("pipeline.post_options.photo_credits", lambda data: [])
        scheduler.resolve_post_data({
            "template": "wave_count",
            "params": {"event": 391, "photos": True},
        })
        assert captured["photos"] is True
