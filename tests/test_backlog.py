"""Writing an entry into content_backlog.yaml without wrecking the file.

The backlog is hand-maintained. It carries planning comments, commented-out
entry stubs and a reference block at the end, and those comments hold decisions
that exist nowhere else. A round trip through a YAML dumper deletes all of it,
so every write here is line-level text editing, the same approach
``mark_post_published`` already takes.
"""

import textwrap

import pytest
import yaml

from pipeline.backlog import (
    entry_text,
    find_entry,
    propose_id,
    upsert_entry,
)


SAMPLE = """\
# Content Backlog - WWT Instagram
#
# Planning notes that must survive every write.

posts:
  - id: tenerife2026-womens-waves-top10
    template: top_10_carousel
    params:
      score_type: Wave
      sex: Women
      event: 124
    caption: |-
      The best women's waves of Tenerife 2026.

      Swipe for the full top 10.
    category: seasonal
    scheduled_date: "2026-08-18T08:00:00"
    published: true
    published_at: "2026-08-18T08:02:38"
    notes: >
      A note that carries a real decision and must not be lost.

  # -- DRAFT (no scheduled_date - poller ignores until scheduled) --
  - id: fiji2026-wave-count
    template: wave_count
    params:
      event: 490099
    category: seasonal
    notes: >
      Needs photos before it can go.

  # -- Week of April 7 --
  # - id:
  #   template:
  #   scheduled_date: 2026-04-09T12:00:00


# -- Quick reference: available templates & params --
#
# top_10:
#   score_type: Wave | Jump
"""


@pytest.fixture
def backlog(tmp_path):
    path = tmp_path / "content_backlog.yaml"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def _posts(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))["posts"]


class TestFindEntry:
    def test_it_returns_an_existing_entry(self, backlog):
        entry = find_entry(str(backlog), "tenerife2026-womens-waves-top10")
        assert entry["template"] == "top_10_carousel"
        assert entry["params"]["event"] == 124
        assert entry["published"] is True

    def test_an_unknown_id_is_none(self, backlog):
        assert find_entry(str(backlog), "not-a-post") is None

    def test_a_commented_out_stub_is_not_an_entry(self, backlog):
        """The file is full of `# - id:` templates. None of them exist."""
        assert find_entry(str(backlog), "") is None


class TestAppend:
    def test_a_new_id_is_appended_as_a_real_entry(self, backlog):
        result = upsert_entry(str(backlog), {
            "id": "tenerife2026-mens-waves-top10",
            "template": "top_10_carousel",
            "params": {"score_type": "Wave", "sex": "Men", "event": 124,
                       "photos": True},
            "caption": "The best men's waves.",
            "category": "seasonal",
            "scheduled_date": "2026-09-01T08:00:00",
        })
        assert result["action"] == "created"
        posts = _posts(backlog)
        new = [p for p in posts if p["id"] == "tenerife2026-mens-waves-top10"][0]
        assert new["params"] == {"score_type": "Wave", "sex": "Men",
                                 "event": 124, "photos": True}
        assert new["caption"] == "The best men's waves."
        assert new["scheduled_date"] == "2026-09-01T08:00:00"

    def test_it_lands_inside_the_posts_list_not_after_the_reference_block(
            self, backlog):
        upsert_entry(str(backlog), {
            "id": "new-post", "template": "top_10_carousel",
            "params": {"event": 124}, "caption": "x",
            "category": "seasonal", "scheduled_date": "2026-09-01T08:00:00",
        })
        text = backlog.read_text(encoding="utf-8")
        assert text.index("- id: new-post") < text.index("Quick reference")
        assert len(_posts(backlog)) == 3

    def test_the_comments_and_the_other_entries_survive(self, backlog):
        upsert_entry(str(backlog), {
            "id": "new-post", "template": "top_10_carousel",
            "params": {"event": 124}, "caption": "x",
            "category": "seasonal", "scheduled_date": "2026-09-01T08:00:00",
        })
        text = backlog.read_text(encoding="utf-8")
        for comment in ("Planning notes that must survive every write.",
                        "-- DRAFT (no scheduled_date", "-- Week of April 7 --",
                        "# - id:", "Quick reference"):
            assert comment in text
        fiji = [p for p in _posts(backlog) if p["id"] == "fiji2026-wave-count"][0]
        assert "Needs photos" in fiji["notes"]

    def test_a_multi_line_caption_round_trips(self, backlog):
        caption = ("Line one.\n\nLine two with a colon: and a #hashtag.\n\n"
                   "\U0001f4f8 @jcwindsurf | @pwaworldtour")
        upsert_entry(str(backlog), {
            "id": "new-post", "template": "top_10_carousel",
            "params": {"event": 124}, "caption": caption,
            "category": "seasonal", "scheduled_date": "2026-09-01T08:00:00",
        })
        new = [p for p in _posts(backlog) if p["id"] == "new-post"][0]
        assert new["caption"] == caption

    def test_notes_are_written_when_given(self, backlog):
        upsert_entry(str(backlog), {
            "id": "new-post", "template": "top_10_carousel",
            "params": {"event": 124}, "caption": "x", "category": "seasonal",
            "scheduled_date": "2026-09-01T08:00:00",
            "notes": "Picked through the contact sheet.",
        })
        new = [p for p in _posts(backlog) if p["id"] == "new-post"][0]
        assert "contact sheet" in new["notes"]


class TestUpdate:
    def test_an_existing_id_is_updated_not_duplicated(self, backlog):
        result = upsert_entry(str(backlog), {
            "id": "tenerife2026-womens-waves-top10",
            "template": "top_10_carousel",
            "params": {"score_type": "Wave", "sex": "Women", "event": 124,
                       "photos": True},
            "caption": "A new caption.",
            "category": "seasonal",
            "scheduled_date": "2026-09-02T09:00:00",
        })
        assert result["action"] == "updated"
        posts = _posts(backlog)
        assert [p["id"] for p in posts].count(
            "tenerife2026-womens-waves-top10") == 1
        entry = [p for p in posts
                 if p["id"] == "tenerife2026-womens-waves-top10"][0]
        assert entry["caption"] == "A new caption."
        assert entry["scheduled_date"] == "2026-09-02T09:00:00"
        assert entry["params"]["photos"] is True

    def test_it_hands_back_what_it_replaced(self, backlog):
        """Nothing gets clobbered without the old value being shown first."""
        result = upsert_entry(str(backlog), {
            "id": "tenerife2026-womens-waves-top10",
            "template": "top_10_carousel",
            "params": {"score_type": "Wave", "sex": "Women", "event": 124},
            "caption": "A new caption.",
            "category": "seasonal",
            "scheduled_date": "2026-09-02T09:00:00",
        })
        assert "The best women's waves of Tenerife 2026." in result["replaced"]["caption"]
        assert result["replaced"]["scheduled_date"] == "2026-08-18T08:00:00"
        assert result["replaced"]["published"] is True

    def test_fields_it_does_not_manage_are_left_alone(self, backlog):
        upsert_entry(str(backlog), {
            "id": "tenerife2026-womens-waves-top10",
            "template": "top_10_carousel",
            "params": {"score_type": "Wave", "sex": "Women", "event": 124},
            "caption": "A new caption.",
            "category": "seasonal",
            "scheduled_date": "2026-09-02T09:00:00",
        })
        entry = find_entry(str(backlog), "tenerife2026-womens-waves-top10")
        assert "A note that carries a real decision" in entry["notes"]

    def test_the_neighbouring_entry_and_its_comment_survive(self, backlog):
        upsert_entry(str(backlog), {
            "id": "tenerife2026-womens-waves-top10",
            "template": "top_10_carousel",
            "params": {"score_type": "Wave", "sex": "Women", "event": 124},
            "caption": "Short.",
            "category": "seasonal",
            "scheduled_date": "2026-09-02T09:00:00",
        })
        text = backlog.read_text(encoding="utf-8")
        assert "-- DRAFT (no scheduled_date" in text
        assert find_entry(str(backlog), "fiji2026-wave-count")["params"][
            "event"] == 490099

    def test_an_entry_with_no_scheduled_date_gains_one(self, backlog):
        upsert_entry(str(backlog), {
            "id": "fiji2026-wave-count", "template": "wave_count",
            "params": {"event": 490099}, "caption": "Cloudbreak.",
            "category": "seasonal",
            "scheduled_date": "2026-09-05T08:00:00",
        })
        entry = find_entry(str(backlog), "fiji2026-wave-count")
        assert entry["scheduled_date"] == "2026-09-05T08:00:00"
        assert entry["caption"] == "Cloudbreak."
        assert "Needs photos" in entry["notes"]

    def test_updating_a_published_entry_is_flagged(self, backlog):
        """Re-dating a published post publishes nothing: the poller skips it."""
        result = upsert_entry(str(backlog), {
            "id": "tenerife2026-womens-waves-top10",
            "template": "top_10_carousel",
            "params": {"score_type": "Wave", "sex": "Women", "event": 124},
            "caption": "x", "category": "seasonal",
            "scheduled_date": "2026-09-02T09:00:00",
        })
        assert result["was_published"] is True

    def test_an_unpublished_update_is_not_flagged(self, backlog):
        result = upsert_entry(str(backlog), {
            "id": "fiji2026-wave-count", "template": "wave_count",
            "params": {"event": 490099}, "caption": "x", "category": "seasonal",
            "scheduled_date": "2026-09-05T08:00:00",
        })
        assert result["was_published"] is False


class TestLineEndings:
    """The real file is CRLF. Writing LF would show up as a 753-line diff, and
    "do not reformat the file" is the whole point of writing it by hand."""

    def test_a_crlf_file_stays_crlf(self, tmp_path):
        path = tmp_path / "crlf.yaml"
        path.write_bytes(SAMPLE.replace("\n", "\r\n").encode("utf-8"))
        upsert_entry(str(path), {
            "id": "new-post", "template": "top_10_carousel",
            "params": {"event": 124}, "caption": "One.\nTwo.",
            "category": "seasonal", "scheduled_date": "2026-09-01T08:00:00",
        })
        raw = path.read_bytes()
        assert b"\n" in raw
        assert raw.count(b"\r\n") == raw.count(b"\n")

    def test_only_the_new_entry_shows_up_in_the_diff(self, tmp_path):
        path = tmp_path / "crlf.yaml"
        before = SAMPLE.replace("\n", "\r\n")
        path.write_bytes(before.encode("utf-8"))
        upsert_entry(str(path), {
            "id": "new-post", "template": "top_10_carousel",
            "params": {"event": 124}, "caption": "x",
            "category": "seasonal", "scheduled_date": "2026-09-01T08:00:00",
        })
        after = path.read_text(encoding="utf-8", newline="")
        assert after.startswith(before[:before.index("  - id: fiji")])


class TestAgainstTheRealBacklog:
    """Every comment in the shipped file is a decision recorded nowhere else."""

    @pytest.fixture
    def real(self, tmp_path):
        import pathlib
        src = pathlib.Path(__file__).resolve().parent.parent / "content_backlog.yaml"
        dest = tmp_path / "content_backlog.yaml"
        dest.write_bytes(src.read_bytes())
        return dest

    def test_appending_leaves_every_comment_line_intact(self, real):
        before = real.read_text(encoding="utf-8").splitlines()
        before_count = len(_posts(real))
        upsert_entry(str(real), {
            "id": "a-brand-new-post", "template": "top_10_carousel",
            "params": {"score_type": "Wave", "sex": "Men", "event": 124,
                       "photos": True},
            "caption": "Body.\n\nMore body.", "category": "seasonal",
            "scheduled_date": "2026-12-01T08:00:00",
        })
        after = real.read_text(encoding="utf-8").splitlines()
        comments = [ln for ln in before if ln.strip().startswith("#")]
        assert comments == [ln for ln in after if ln.strip().startswith("#")]
        assert len(_posts(real)) == before_count + 1

    def test_updating_the_published_tenerife_entry_keeps_its_neighbours(self, real):
        before_posts = _posts(real)
        result = upsert_entry(str(real), {
            "id": "tenerife2026-womens-waves-top10",
            "template": "top_10_carousel",
            "params": {"score_type": "Wave", "sex": "Women", "event": 124,
                       "photos": True},
            "caption": "Rewritten.", "category": "seasonal",
            "scheduled_date": "2026-12-01T08:00:00",
        })
        assert result["action"] == "updated"
        assert result["was_published"] is True
        after_posts = _posts(real)
        assert len(after_posts) == len(before_posts)
        assert [p["id"] for p in after_posts] == [p["id"] for p in before_posts]
        # Everything except the one entry is untouched.
        for before, after in zip(before_posts, after_posts):
            if before["id"] != "tenerife2026-womens-waves-top10":
                assert before == after


class TestEntryText:
    def test_it_indents_to_the_files_own_shape(self):
        text = entry_text({
            "id": "x", "template": "top_10_carousel",
            "params": {"event": 124, "photos": True},
            "caption": "One.\nTwo.", "category": "seasonal",
            "scheduled_date": "2026-09-01T08:00:00",
        })
        assert text.startswith("  - id: x\n")
        assert "    params:\n      event: 124\n      photos: true\n" in text
        assert "    caption: |-\n      One.\n      Two.\n" in text
        assert '    scheduled_date: "2026-09-01T08:00:00"\n' in text

    def test_a_blank_line_inside_a_caption_stays_blank(self):
        text = entry_text({
            "id": "x", "template": "t", "params": {}, "caption": "One.\n\nTwo.",
            "category": "seasonal", "scheduled_date": "2026-09-01T08:00:00",
        })
        # A literal block keeps blank lines unindented; trailing spaces on an
        # empty line are what a naive indenter leaves behind.
        assert "      One.\n\n      Two.\n" in text


class TestProposeId:
    def test_it_follows_the_files_own_convention(self):
        assert propose_id("Tenerife Grand Slam", 2026, "Women", "Wave") == \
            "tenerife2026-womens-waves-top10"

    def test_the_apis_own_event_names_lead_with_the_year(self):
        """The API calls it "2026 Tenerife Grand Slam *****", which naively
        sliced gives 20262026-womens-waves-top10."""
        assert propose_id("2026 Tenerife Grand Slam *****", 2026, "Women",
                          "Wave") == "tenerife2026-womens-waves-top10"

    def test_a_star_rating_is_not_part_of_the_name(self):
        assert propose_id("***** Fiji Pro", 2026, "Men", "Wave") == \
            "fiji2026-mens-waves-top10"

    def test_men_and_jumps(self):
        assert propose_id("Gran Canaria Wind and Waves Festival", 2026,
                          "Men", "Jump").endswith("-mens-jumps-top10")

    def test_no_division_leaves_the_fleet_out(self):
        assert propose_id("Fiji Pro", 2026, None, "Wave") == \
            "fiji2026-waves-top10"
