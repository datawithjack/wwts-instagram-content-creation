"""Planning the publish of approved headshots to the stats site (#33).

The plan is the part that decides what happens to a production row, so it is
pure and tested: every write the script makes comes from here, and --dry-run
prints exactly this list.
"""

from pipeline.headshot_publish import PUBLIC_HOST, plan_changes, plan_rollback

NOW = 1790000000
LIVEHEATS = "https://liveheats.com/images/abc.jpg"


def _manifest(**entries):
    return {"_comment": "ignored", **entries}


def _one(plan, athlete_id):
    return next(p for p in plan if p["athlete_id"] == athlete_id)


class TestApprove:
    def test_empty_row_gets_an_upload_and_an_update(self):
        plan = plan_changes(_manifest(**{"892": {"name": "Yentel Caers", "action": "approve"}}),
                            {892: None}, NOW)
        p = _one(plan, 892)
        assert p["op"] == "publish"
        assert p["key"] == f"athlete-photos/892_{NOW}.jpg"
        assert p["new"] == f"{PUBLIC_HOST}/athlete-photos/892_{NOW}.jpg"
        assert p["old"] is None
        assert p["file"].endswith("faces/892.jpg")

    def test_the_host_is_the_custom_domain_whatever_the_env_says(self, monkeypatch):
        """This repo's .env still names pub-*.r2.dev, which Telefonica blocks:
        a URL on it is a photo that silently fails for a whole ISP."""
        monkeypatch.setenv("R2_PUBLIC_URL", "https://pub-315dcf15c071471a8f60b02108fa.r2.dev")
        plan = plan_changes(_manifest(**{"892": {"action": "approve"}}), {892: None}, NOW)
        assert _one(plan, 892)["new"].startswith("https://img.windsurfworldtourstats.com/")

    def test_a_suppressed_row_can_be_given_a_photo(self):
        plan = plan_changes(_manifest(**{"892": {"action": "approve"}}), {892: ""}, NOW)
        assert _one(plan, 892)["op"] == "publish"

    def test_a_real_photo_is_never_overwritten(self):
        plan = plan_changes(_manifest(**{"5": {"action": "approve"}}), {5: LIVEHEATS}, NOW)
        p = _one(plan, 5)
        assert p["op"] == "refuse"
        assert "real photo" in p["reason"]

    def test_force_overwrites_a_real_photo(self):
        plan = plan_changes(_manifest(**{"5": {"action": "approve"}}), {5: LIVEHEATS},
                            NOW, force=True)
        assert _one(plan, 5)["op"] == "publish"

    def test_already_published_is_skipped(self):
        url = f"{PUBLIC_HOST}/athlete-photos/892_1.jpg"
        plan = plan_changes(
            _manifest(**{"892": {"action": "approve", "published_url": url}}), {892: url}, NOW)
        assert _one(plan, 892)["op"] == "skip"

    def test_a_row_we_published_before_is_ours_to_replace(self):
        """A re-pick after publishing replaces our own earlier headshot."""
        old = f"{PUBLIC_HOST}/athlete-photos/892_1.jpg"
        plan = plan_changes(_manifest(**{"892": {"action": "approve"}}), {892: old}, NOW)
        assert _one(plan, 892)["op"] == "publish"

    def test_an_athlete_missing_from_the_db_is_refused(self):
        plan = plan_changes(_manifest(**{"99999": {"action": "approve"}}), {}, NOW)
        assert _one(plan, 99999)["op"] == "refuse"


class TestSuppress:
    def test_hides_the_sail_number_guess(self):
        plan = plan_changes(_manifest(**{"110": {"action": "suppress"}}), {110: None}, NOW)
        p = _one(plan, 110)
        assert p["op"] == "update" and p["new"] == "" and "key" not in p

    def test_already_suppressed_is_skipped(self):
        plan = plan_changes(_manifest(**{"110": {"action": "suppress"}}), {110: ""}, NOW)
        assert _one(plan, 110)["op"] == "skip"

    def test_never_hides_a_real_photo(self):
        plan = plan_changes(_manifest(**{"5": {"action": "suppress"}}), {5: LIVEHEATS}, NOW)
        assert _one(plan, 5)["op"] == "refuse"


class TestRollback:
    def test_puts_each_old_value_back_where_the_row_still_holds_ours(self):
        records = [{"athlete_id": 892, "old": None, "new": "https://img/x.jpg"},
                   {"athlete_id": 110, "old": None, "new": ""}]
        plan = plan_rollback(records, {892: "https://img/x.jpg", 110: "changed-since"})
        assert _one(plan, 892) == {"athlete_id": 892, "op": "update",
                                   "old": "https://img/x.jpg", "new": None}
        assert _one(plan, 110)["op"] == "refuse"
