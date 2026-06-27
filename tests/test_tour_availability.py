"""Tests for the Tour availability infographic reel.

A single animated 1080x1920 reel illustrating The Tour's one-pick-per-season rule
across two events (Gran Canaria -> Tenerife, 2025 practice data): athletes "spent"
at GC become unavailable at Tenerife, so the available pool shrinks.
"""
import os

import yaml

from pipeline.templates import get_dummy_data, render_template
from pipeline.tour_availability import build_tour_availability_reel_data, select_roster


def _fake_startlist():
    """Mimic the /events/{id}/startlist payload (StartListAthlete[])."""
    athletes = []
    for i in range(6):
        athletes.append({
            "athlete_id": 100 + i, "athlete_name": f"Man {i}", "country_code": "ES",
            "sex": "Men", "tier": "top5", "on_start_list": True,
            "profile_picture_url": f"https://img/m{i}.webp",
            "world_rank": i + 1, "prev_year_result": f"{i + 1}th '24",
        })
    for i in range(6):
        athletes.append({
            "athlete_id": 200 + i, "athlete_name": f"Woman {i}", "country_code": "DE",
            "sex": "Women", "tier": "top5", "on_start_list": True,
            "profile_picture_url": f"https://img/w{i}.webp",
            "world_rank": i + 1, "prev_year_result": f"{i + 1}th '24",
        })
    # one with no photo + no rank — must be excluded
    athletes.append({
        "athlete_id": 999, "athlete_name": "No Photo", "country_code": "FR",
        "sex": "Men", "tier": "outside", "on_start_list": True,
        "profile_picture_url": None, "world_rank": None, "prev_year_result": None,
    })
    return athletes


class TestSelectRoster:
    def setup_method(self):
        self.pick_stats = {"athletes": [{"athlete_id": 100, "pick_pct": 42.4}]}
        self.roster = select_roster(_fake_startlist(), self.pick_stats)

    def test_returns_ten_with_five_used(self):
        assert len(self.roster) == 10
        assert sum(1 for a in self.roster if a["used"]) == 5

    def test_excludes_athletes_without_photo_or_rank(self):
        assert all(a["photo"] for a in self.roster)
        assert "No Photo" not in [a["name"] for a in self.roster]

    def test_top_ranked_are_the_used_picks(self):
        used_names = {a["name"] for a in self.roster if a["used"]}
        assert "Man 0" in used_names  # world_rank 1
        assert "Woman 0" in used_names

    def test_merges_pick_pct_and_normalises_sex(self):
        man0 = next(a for a in self.roster if a["name"] == "Man 0")
        assert man0["pct"] == "42%"
        assert man0["sex"] == "M"
        woman0 = next(a for a in self.roster if a["name"] == "Woman 0")
        assert woman0["sex"] == "F"
        assert woman0["pct"] is None  # not in pick_stats


# ── Data Builder ────────────────────────────────────────────────────────────

class TestBuildTourAvailabilityData:
    def setup_method(self):
        self.data = build_tour_availability_reel_data()

    def test_has_brand_intro(self):
        assert "TOUR" in self.data["intro_title"].upper()
        assert self.data["intro_sub"]

    def test_has_hook_copy(self):
        assert self.data["hook_title"]
        assert self.data["hook_sub"]
        assert "season" in self.data["hook_sub"].lower()

    def test_captain_exception_note(self):
        # The captain rule is the one exception to one-pick-per-season.
        assert "twice" in self.data["captain_text"].lower()
        assert self.data["captain_title"]

    def test_captains_are_two_athletes(self):
        caps = self.data["captains"]
        assert len(caps) == 2
        for c in caps:
            assert c["name"]

    def test_two_events_gc_then_tenerife(self):
        assert self.data["event1"]["name"]
        assert self.data["event2"]["name"]
        assert "canaria" in self.data["event1"]["name"].lower()
        assert "tenerife" in self.data["event2"]["name"].lower()

    def test_roster_is_pool_of_athletes(self):
        roster = self.data["roster"]
        assert isinstance(roster, list)
        assert len(roster) >= 8
        for a in roster:
            assert a["name"]
            assert isinstance(a["used"], bool)

    def test_five_athletes_spent_at_gc(self):
        # The squad spends exactly 5 picks at the first event.
        used = [a for a in self.data["roster"] if a["used"]]
        available = [a for a in self.data["roster"] if not a["used"]]
        assert len(used) == 5
        assert len(available) >= 3  # someone must remain available at Tenerife

    def test_event_captions(self):
        assert self.data["event1_caption"]
        assert self.data["event2_caption"]
        # The Tenerife caption sells the "unavailable / who's left" idea.
        e2 = self.data["event2_caption"].lower()
        assert "unavailable" in e2 or "left" in e2 or "gone" in e2

    def test_cta_has_handle_and_url(self):
        assert "@windsurfworldtourstats" in self.data["handle"]
        assert "windsurfworldtourstats.com" in self.data["url"]


# ── Dummy Data wiring ───────────────────────────────────────────────────────

class TestDummyData:
    def test_tour_availability_reel_dummy_data(self):
        data = get_dummy_data("tour_availability_reel")
        assert data["hook_title"]
        assert len(data["roster"]) >= 8


# ── Template Rendering ──────────────────────────────────────────────────────

class TestTourAvailabilityRendering:
    def setup_method(self):
        self.data = get_dummy_data("tour_availability_reel")
        self.html = render_template("tour_availability_reel", self.data)

    def test_returns_html_string(self):
        assert isinstance(self.html, str)
        assert "<html" in self.html

    def test_configured_as_vertical_reel(self):
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)
        reel = config["templates"]["tour_availability_reel"]
        assert reel["width"] == 1080
        assert reel["height"] == 1920

    def test_contains_event_names(self):
        upper = self.html.upper()
        assert "GRAN CANARIA" in upper
        assert "TENERIFE" in upper

    def test_contains_brand_and_captain_note(self):
        upper = self.html.upper()
        assert "THE TOUR" in upper
        assert "TWICE" in upper  # captain exception

    def test_contains_an_athlete_name(self):
        # At least one roster athlete should render into the markup.
        names = [a["name"] for a in self.data["roster"]]
        assert any(n in self.html for n in names)

    def test_contains_animation_script(self):
        assert "runAnimation" in self.html or "animate" in self.html

    def test_contains_brand_fonts_and_url(self):
        assert "Bebas Neue" in self.html
        assert "Inter" in self.html
        assert "windsurfworldtourstats.com" in self.html
