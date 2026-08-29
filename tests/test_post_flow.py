"""The steps between picking photos and having a backlog entry.

Picking is step one of five. These are the other four: build the post, review
it, confirm the caption, set the time, save. The browser page is the shell; the
decisions live here where they can be tested.
"""

import pytest

from pipeline import post_flow


CONFIG = {"captions": {"site_url": "windsurfworldtourstats.com"},
          "hashtags": {"top_10_carousel": ["#windsurfing"]}}


def _data():
    return {
        "title_gender": "Women's", "title_metric": "Waves", "title_year": 2026,
        "is_per_event": True, "event_name": "Tenerife Grand Slam",
        "entries": [{"rank": i, "athlete": f"Rider {i}", "athlete_id": i,
                     "country": "es", "score": 10.0 - i, "event": "Tenerife",
                     "round": "Final", "heat": "", "counting": 1}
                    for i in range(1, 11)],
    }


@pytest.fixture
def stub_post(monkeypatch):
    """A built post, without the API or the renderer."""
    monkeypatch.setattr(post_flow, "fetch_event_top_scores",
                        lambda **kwargs: _data())
    monkeypatch.setattr("pipeline.post_options.photo_credits",
                        lambda data: ["@jcwindsurf"])
    monkeypatch.setattr(post_flow, "slide_html",
                        lambda slides: [f"<html>{s['type']}</html>"
                                        for s in slides])
    monkeypatch.setattr(post_flow, "load_config", lambda: CONFIG)


PLAN = {"event_id": 124, "score_type": "Wave", "sex": "Women"}


class TestBuildPost:
    def test_the_post_is_the_photo_variant(self, stub_post):
        data, slides = post_flow.build_post(PLAN)
        assert data["photo_mode"] is True
        assert data["photo_event_id"] == 124
        assert len(slides) == 8

    def test_the_credits_come_with_it(self, stub_post):
        data, _ = post_flow.build_post(PLAN)
        assert data["photo_credits"] == ["@jcwindsurf"]


class TestReviewPayload:
    def test_it_carries_the_slides_the_caption_and_the_hashtags(self, stub_post):
        payload = post_flow.review_payload(PLAN, "Tenerife Grand Slam", 2026)
        assert len(payload["slides"]) == 8
        assert "\U0001f4f8 @jcwindsurf" in payload["caption"]
        assert payload["hashtags"] == "#windsurfing"

    def test_the_prefilled_caption_carries_no_hashtags(self, stub_post):
        """They are appended at publish time; storing them doubles them."""
        payload = post_flow.review_payload(PLAN, "Tenerife Grand Slam", 2026)
        assert "#windsurfing" not in payload["caption"]

    def test_it_proposes_an_id_and_the_params_to_store(self, stub_post):
        payload = post_flow.review_payload(PLAN, "Tenerife Grand Slam", 2026)
        assert payload["post_id"] == "tenerife2026-womens-waves-top10"
        assert payload["params"] == {"score_type": "Wave", "sex": "Women",
                                     "event": 124, "photos": True}

    def test_the_params_say_photos_so_the_poller_renders_the_right_thing(
            self, stub_post):
        payload = post_flow.review_payload(PLAN, "Tenerife Grand Slam", 2026)
        assert payload["params"]["photos"] is True

    def test_it_carries_the_credits_so_the_page_can_warn_live(self, stub_post):
        payload = post_flow.review_payload(PLAN, "Tenerife Grand Slam", 2026)
        assert payload["credits"] == ["@jcwindsurf"]


class TestLocalAssetUrls:
    """The page is served over http, so a file:// image on it is blocked by
    the browser. Slide photos are rewritten to a route this server serves."""

    def test_a_file_url_becomes_a_local_route(self):
        html = '<img src="file:///C:/repo/assets/photos/events/124/5.jpg">'
        out = post_flow.local_asset_urls(html)
        assert "file:///" not in out
        assert "/local?p=C%3A/repo/assets/photos/events/124/5.jpg" in out

    def test_a_space_in_the_path_survives(self):
        html = "url('file:///C:/My Repo/assets/bg.jpg')"
        out = post_flow.local_asset_urls(html)
        assert "My%20Repo" in out

    def test_http_urls_are_left_alone(self):
        html = '<link href="https://fonts.googleapis.com/css2?family=Inter">'
        assert post_flow.local_asset_urls(html) == html


class TestNormaliseSchedule:
    def test_it_canonicalises_to_seconds(self):
        when, warning = post_flow.normalise_schedule("2099-09-01T18:00")
        assert when == "2099-09-01T18:00:00"
        assert warning is None

    def test_a_trailing_z_is_accepted(self):
        when, _ = post_flow.normalise_schedule("2099-09-01T18:00:00Z")
        assert when == "2099-09-01T18:00:00"

    def test_a_past_time_is_flagged_not_refused(self):
        """The poller treats any past unpublished post as due, so this
        publishes at the next poll rather than never."""
        when, warning = post_flow.normalise_schedule("2020-01-01T09:00:00")
        assert when == "2020-01-01T09:00:00"
        assert "past" in warning.lower()

    def test_nonsense_is_refused(self):
        with pytest.raises(ValueError):
            post_flow.normalise_schedule("next tuesday")

    def test_an_empty_time_is_refused(self):
        with pytest.raises(ValueError):
            post_flow.normalise_schedule("")


class TestSaveToBacklog:
    @pytest.fixture
    def backlog(self, tmp_path):
        path = tmp_path / "content_backlog.yaml"
        path.write_text("posts:\n  - id: existing-post\n    template: top_10_carousel\n"
                        "    params:\n      event: 124\n    caption: |-\n      Old words.\n"
                        "    category: seasonal\n    scheduled_date: \"2026-08-18T08:00:00\"\n",
                        encoding="utf-8")
        return str(path)

    def _entry(self, **over):
        entry = {"id": "new-post", "template": "top_10_carousel",
                 "params": {"score_type": "Wave", "sex": "Women", "event": 124,
                            "photos": True},
                 "caption": "Words.\n\n\U0001f4f8 @jcwindsurf",
                 "category": "seasonal",
                 "scheduled_date": "2099-09-01T18:00"}
        entry.update(over)
        return entry

    def test_a_new_post_is_created(self, backlog):
        result = post_flow.save_to_backlog(backlog, self._entry(),
                                           ["@jcwindsurf"])
        assert result["action"] == "created"
        assert result["scheduled_date"] == "2099-09-01T18:00:00"

    def test_a_deleted_credit_line_is_put_back_and_reported(self, backlog):
        result = post_flow.save_to_backlog(
            backlog, self._entry(caption="Just my words."),
            ["@jcwindsurf"])
        assert result["credits_restored"] == ["@jcwindsurf"]
        assert "@jcwindsurf" in result["caption"]

    def test_a_kept_credit_line_is_not_touched(self, backlog):
        result = post_flow.save_to_backlog(backlog, self._entry(),
                                           ["@jcwindsurf"])
        assert result["credits_restored"] == []
        assert result["caption"].count("@jcwindsurf") == 1

    def test_an_existing_id_updates_and_shows_what_it_replaced(self, backlog):
        result = post_flow.save_to_backlog(
            backlog, self._entry(id="existing-post"), [])
        assert result["action"] == "updated"
        assert "Old words." in result["replaced"]["caption"]

    def test_the_credits_the_review_step_produced_are_the_ones_it_repairs(
            self, backlog, stub_post):
        """The two steps have to agree on what a credit list looks like. They
        did not: the page's payload keys it `credits`, the repair read
        `photo_credits` off a data dict, so a deleted line stayed deleted and
        the post would have published someone else's photographs uncredited."""
        payload = post_flow.review_payload(PLAN, "Tenerife Grand Slam", 2026)
        result = post_flow.save_to_backlog(
            backlog, self._entry(caption="No credit here."), payload["credits"])
        assert result["credits_restored"] == ["@jcwindsurf"]
        assert "\U0001f4f8 @jcwindsurf" in result["caption"]

    def test_it_says_the_entry_is_not_scheduled_until_pushed(self, backlog):
        result = post_flow.save_to_backlog(backlog, self._entry(), [])
        assert "commit" in result["message"].lower()
        assert "push" in result["message"].lower()

    def test_an_id_is_required(self, backlog):
        with pytest.raises(ValueError):
            post_flow.save_to_backlog(backlog, self._entry(id="  "), [])

    def test_a_bad_time_is_refused_before_anything_is_written(self, backlog):
        before = open(backlog, encoding="utf-8").read()
        with pytest.raises(ValueError):
            post_flow.save_to_backlog(backlog, self._entry(scheduled_date=""), [])
        assert open(backlog, encoding="utf-8").read() == before


class TestLookup:
    @pytest.fixture
    def backlog(self, tmp_path):
        path = tmp_path / "content_backlog.yaml"
        path.write_text("posts:\n  - id: existing-post\n    template: top_10_carousel\n"
                        "    params:\n      event: 124\n    caption: |-\n      Old words.\n"
                        "    category: seasonal\n    scheduled_date: \"2026-08-18T08:00:00\"\n"
                        "    published: true\n", encoding="utf-8")
        return str(path)

    def test_a_free_id_reports_no_collision(self, backlog):
        assert post_flow.lookup(backlog, "brand-new")["exists"] is False

    def test_a_taken_id_reports_what_is_there(self, backlog):
        found = post_flow.lookup(backlog, "existing-post")
        assert found["exists"] is True
        assert found["caption"] == "Old words."
        assert found["scheduled_date"] == "2026-08-18T08:00:00"
        assert found["published"] is True
