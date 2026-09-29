"""The picker fills two slots, not one.

The hero photo is per event and the headshot is per athlete, and they live in
different folders. Picking only the hero is how a post reaches the summary card
with a blank thumbnail, so the sheet asks for both in one pass -- but only where
the headshot is actually missing, because a face does not go out of date.
"""

from pathlib import Path

from PIL import Image

import pick_photos
from pipeline.photo_sheet import render_sheet


def _frame(tmp_path, name="WI26_ls_F777_150.jpg"):
    path = tmp_path / name
    Image.new("RGB", (2000, 1333), (30, 90, 140)).save(path, "JPEG")
    return path


def _rider(athlete_id, candidates, faces=True):
    return {
        "athlete_id": athlete_id, "name": "Kilian Couedic", "score": 8.5,
        "rank_label": "1ST", "metric": "WAVE", "sail": "F-777",
        "tokens": ["F777"], "candidates": candidates,
        "face_candidates": candidates if faces else [],
    }


def _candidate(path, kind="ls"):
    return {"path": str(path), "name": path.name, "kind": kind, "thumb": "t.jpg",
            "score_label": "8.50",
            "credit": {"photographer": "olivier caenen", "handle": "",
                       "source_file": path.name, "confirmed": True, "via": "xmp"}}


class TestWhoGetsAsked:
    """A rider with a headshot already is not asked about one again."""

    def test_a_rider_with_no_headshot_is_asked(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pick_photos, "PHOTOS_DIR", tmp_path)
        assert pick_photos._face_missing(1725) is True

    def test_a_rider_who_has_one_is_not(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pick_photos, "PHOTOS_DIR", tmp_path)
        faces = tmp_path / "faces"
        faces.mkdir()
        (faces / "97.jpg").write_bytes(b"x")
        assert pick_photos._face_missing(97) is False

    def test_a_png_headshot_counts_too(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pick_photos, "PHOTOS_DIR", tmp_path)
        faces = tmp_path / "faces"
        faces.mkdir()
        (faces / "35.png").write_bytes(b"x")
        assert pick_photos._face_missing(35) is False


class TestTheSheet:
    """The headshot section only appears where there is something to fill."""

    def test_a_headshot_section_is_rendered(self, tmp_path):
        page = render_sheet([_rider(1725, [_candidate(_frame(tmp_path))])], "Wissant")
        assert 'id="rider-face-1725"' in page
        assert 'name="pick-face-1725"' in page

    def test_no_section_when_the_headshot_exists(self, tmp_path):
        rider = _rider(97, [_candidate(_frame(tmp_path))], faces=False)
        page = render_sheet([rider], "Wissant")
        assert 'id="rider-face-97"' not in page
        assert 'id="rider-97"' in page

    def test_the_headshot_card_offers_both_anchors(self, tmp_path):
        """A square cut from a 3:2 frame has slack in both directions."""
        page = render_sheet([_rider(1725, [_candidate(_frame(tmp_path))])], "Wissant")
        assert 'class="focusy"' in page


class TestTheHeadshotPool:
    """Faces are shot on the beach, and the beach shots carry no sail number."""

    def test_a_riders_own_lifestyle_frames_win(self, tmp_path):
        mine = [_candidate(_frame(tmp_path, "WI26_wv_F111_66.jpg"), "wv"),
                _candidate(_frame(tmp_path, "WI26_ls_F111_130.jpg"), "ls")]
        pool = pick_photos._face_pool(mine, lifestyle=[])
        assert pool[0]["name"] == "WI26_ls_F111_130.jpg"

    def test_water_shots_only_falls_back_to_the_folders_faces(self, tmp_path):
        """Alice at Wissant: four frames, all of her a hundred metres out."""
        mine = [_candidate(_frame(tmp_path, "WI26_wv_F111_66.jpg"), "wv")]
        podium = _candidate(_frame(tmp_path, "WI26_ls_PRIZE_WOMEN_154.jpg"), "ls")
        pool = pick_photos._face_pool(mine, lifestyle=[podium])
        assert [c["name"] for c in pool] == ["WI26_wv_F111_66.jpg",
                                             "WI26_ls_PRIZE_WOMEN_154.jpg"]

    def test_the_fallback_never_repeats_a_frame(self, tmp_path):
        shared = _candidate(_frame(tmp_path, "WI26_wv_F111_66.jpg"), "wv")
        pool = pick_photos._face_pool([shared], lifestyle=[shared])
        assert len(pool) == 1


class TestWhereThePicksLand:
    """The routing is the whole point: two slots, two folders."""

    def test_a_face_pick_goes_to_the_faces_folder(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pick_photos, "PHOTOS_DIR", tmp_path)
        src = _frame(tmp_path)
        pick_photos._install({"face-1725": {"file": str(src), "focus": "40% 20%"}}, 278)

        dest = tmp_path / "faces" / "1725.jpg"
        assert Image.open(dest).size == (pick_photos.FACE_PX, pick_photos.FACE_PX)
        assert not (tmp_path / "events" / "278" / "1725.jpg").exists()

    def test_a_hero_pick_still_goes_to_the_event(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pick_photos, "PHOTOS_DIR", tmp_path)
        src = _frame(tmp_path)
        pick_photos._install({"1725": {"file": str(src), "focus": "40% 50%"}}, 278)

        assert (tmp_path / "events" / "278" / "1725.jpg").exists()
        assert not (tmp_path / "faces" / "1725.jpg").exists()

    def test_a_face_pick_records_its_photographer(self, tmp_path, monkeypatch):
        """A headshot carries a slide, so its credit is owed like any other."""
        import json
        monkeypatch.setattr(pick_photos, "PHOTOS_DIR", tmp_path)
        monkeypatch.setattr(pick_photos, "credit_for", lambda src: {
            "photographer": "olivier caenen", "handle": "", "confirmed": True,
            "source_file": Path(src).name, "via": "xmp"})
        pick_photos._install({"face-1725": {"file": str(_frame(tmp_path))}}, 278)

        record = json.loads((tmp_path / "faces" / "credits.json").read_text())
        assert record["1725"]["photographer"] == "olivier caenen"

    def test_an_untagged_face_pick_is_flagged(self, tmp_path, monkeypatch):
        import json
        monkeypatch.setattr(pick_photos, "PHOTOS_DIR", tmp_path)
        monkeypatch.setattr(pick_photos, "credit_for", lambda src: {
            "photographer": "", "handle": "", "confirmed": False,
            "source_file": Path(src).name, "via": ""})
        pick_photos._install({"face-1725": {"file": str(_frame(tmp_path))}}, 278)

        record = json.loads((tmp_path / "faces" / "credits.json").read_text())
        assert "UNTAGGED" in record["1725"]["note"]

    def test_both_slots_in_one_save(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pick_photos, "PHOTOS_DIR", tmp_path)
        src = _frame(tmp_path)
        installed = pick_photos._install({
            "1725": {"file": str(src), "focus": "50% 50%"},
            "face-1725": {"file": str(src), "focus": "50% 30%"},
        }, 278)

        assert (tmp_path / "events" / "278" / "1725.jpg").exists()
        assert (tmp_path / "faces" / "1725.jpg").exists()
        assert len(installed) == 2


class TestTheAdjuster:
    """It opens on every save rather than being remembered as a second command."""

    def test_it_is_launched_with_the_event_and_its_source(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(pick_photos.subprocess, "Popen",
                            lambda cmd, **kw: seen.setdefault("cmd", cmd))
        pick_photos._open_adjuster(278, "G:/drive/2026/01 - WISSANT")

        assert "adjust_photos.py" in " ".join(seen["cmd"])
        assert "278" in seen["cmd"]
        assert "G:/drive/2026/01 - WISSANT" in seen["cmd"]

    def test_a_failure_to_start_does_not_lose_the_photos(self, monkeypatch, capsys):
        """The photos are already written by the time it runs."""
        def boom(cmd, **kw):
            raise OSError("no python here")

        monkeypatch.setattr(pick_photos.subprocess, "Popen", boom)
        pick_photos._open_adjuster(278, None)
        assert "adjust_photos.py yourself" in capsys.readouterr().out
