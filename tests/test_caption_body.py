"""Caption pieces the post flow needs: the body alone, and the credit check.

The backlog stores a caption *body*. ``build_caption`` appends the config's
hashtag set to an override rather than replacing it, so a stored caption that
already carries hashtags posts them twice -- a trap the file's own notes record
against tenerife2026-womens-waves-top10. So the wizard prefills the body and
shows the hashtags separately as something appended at publish time.
"""

import pytest

from pipeline.captions import (
    build_caption,
    build_caption_body,
    hashtags_for,
    missing_photo_credits,
    with_photo_credits,
)


CONFIG = {"captions": {"site_url": "windsurfworldtourstats.com"},
          "hashtags": {"top_10_carousel": ["#windsurfing", "#pwaworldtour"]}}

DATA = {
    "title_gender": "Women's", "title_metric": "Waves", "title_year": 2026,
    "photo_credits": ["@jcwindsurf", "@pwaworldtour"],
    "entries": [],
}


class TestBuildCaptionBody:
    def test_the_body_carries_no_hashtags(self):
        body = build_caption_body("top_10_carousel", DATA, CONFIG)
        assert "#windsurfing" not in body

    def test_the_body_carries_the_photographers(self):
        body = build_caption_body("top_10_carousel", DATA, CONFIG)
        assert body.endswith("\U0001f4f8 @jcwindsurf | @pwaworldtour")

    def test_an_override_body_still_gains_the_credits(self):
        body = build_caption_body("top_10_carousel", DATA, CONFIG,
                                  caption_override="My own words.")
        assert body.startswith("My own words.")
        assert "@jcwindsurf" in body

    def test_build_caption_is_the_body_plus_the_hashtags(self):
        body = build_caption_body("top_10_carousel", DATA, CONFIG)
        assert build_caption("top_10_carousel", DATA, CONFIG) == (
            f"{body}\n\n#windsurfing #pwaworldtour"
        )


class TestHashtagsFor:
    def test_it_reads_the_config_set(self):
        assert hashtags_for("top_10_carousel", CONFIG) == "#windsurfing #pwaworldtour"

    def test_an_unknown_template_falls_back_to_the_default_set(self):
        config = {"hashtags": {"default": ["#windsurf"]}}
        assert hashtags_for("whatever", config) == "#windsurf"


class TestMissingPhotoCredits:
    """The credit line is not decoration: the whole point of #18 was that a
    photo post publishes credited."""

    def test_an_edited_body_that_kept_the_line_owes_nothing(self):
        body = "Words.\n\n\U0001f4f8 @jcwindsurf | @pwaworldtour"
        assert missing_photo_credits(body, DATA) == []

    def test_a_deleted_credit_is_reported(self):
        assert missing_photo_credits("Words.", DATA) == [
            "@jcwindsurf", "@pwaworldtour"]

    def test_a_partly_deleted_credit_line_names_only_what_is_missing(self):
        body = "Words.\n\n\U0001f4f8 @jcwindsurf"
        assert missing_photo_credits(body, DATA) == ["@pwaworldtour"]

    def test_a_post_with_no_photos_owes_nothing(self):
        assert missing_photo_credits("Words.", {"entries": []}) == []

    def test_a_reworded_credit_line_still_counts_as_credited(self):
        """What matters is the handle appearing, not the exact wording."""
        body = "Words.\n\nPhotos by @jcwindsurf and @pwaworldtour, thank you."
        assert missing_photo_credits(body, DATA) == []


class TestWithPhotoCredits:
    def test_it_puts_a_deleted_credit_line_back(self):
        assert with_photo_credits("Words.", DATA) == (
            "Words.\n\n\U0001f4f8 @jcwindsurf | @pwaworldtour")

    def test_it_does_not_double_a_line_that_is_already_there(self):
        body = "Words.\n\n\U0001f4f8 @jcwindsurf | @pwaworldtour"
        assert with_photo_credits(body, DATA) == body
