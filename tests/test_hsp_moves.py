"""Tests for the HeatScoringPRO move dictionary snapshot."""
import json

from pipeline.hsp_moves import difficulty_by_slug, is_placeholder, load_snapshot


def _snap():
    return {
        "as_at": "2026-08-16",
        "categories": {
            "FREESTYLE": {
                "count": 4,
                "placeholders": ["NEW"],
                "moves": [
                    {"slug": "VW", "name": "Volwater", "difficulty": 9.9},
                    {"slug": "FKA", "name": "Air Flaka", "difficulty": 6.1},
                    {"slug": "NEW", "name": "New Move", "difficulty": 10},
                    {"slug": "XX", "name": "Unrated", "difficulty": None},
                ],
            }
        },
    }


class TestPlaceholders:
    def test_new_move_rows_are_placeholders(self):
        """Judges pick these for an unnamed new trick. They score 10, so left
        in they top any 'hardest move' ranking without being a real trick."""
        for slug in ("NEW", "NEW2", "NEW-H2", "NEW-H3"):
            assert is_placeholder({"slug": slug})

    def test_real_moves_are_not(self):
        assert not is_placeholder({"slug": "VW"})
        assert not is_placeholder({"slug": "FKA"})

    def test_placeholders_excluded_by_default(self):
        d = difficulty_by_slug(_snap())
        assert "NEW" not in d
        assert max(d.values()) == 9.9

    def test_can_be_opted_back_in(self):
        d = difficulty_by_slug(_snap(), include_placeholders=True)
        assert d["NEW"] == 10


class TestDifficultyMap:
    def test_maps_slug_to_difficulty(self):
        d = difficulty_by_slug(_snap())
        assert d["VW"] == 9.9
        assert d["FKA"] == 6.1

    def test_unrated_moves_are_dropped(self):
        assert "XX" not in difficulty_by_slug(_snap())


class TestSnapshotOnDisk:
    def test_the_committed_snapshot_loads_and_is_dated(self):
        s = load_snapshot()
        assert s["as_at"]
        assert s["source"] == "heatscoringpro"
        assert s["categories"]["FREESTYLE"]["count"] > 100

    def test_committed_snapshot_has_the_known_placeholders(self):
        s = load_snapshot()
        assert set(s["categories"]["FREESTYLE"]["placeholders"]) == {
            "NEW", "NEW2", "NEW-H2", "NEW-H3"
        }
