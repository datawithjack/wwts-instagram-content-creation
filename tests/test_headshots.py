"""Headshot matching: which lifestyle frame belongs to which athlete (#32).

The stats site shows a photo built from a rider's CURRENT sail number, and PWA
reassigns sail numbers -- Alice Arutkin renders a man (stats-app #230). So a
frame here is matched on the sail its rider held AT the event the frame was
shot at, taken from that event's own results.
"""

import pytest

from PIL import Image

from pipeline.headshots import (
    frames_for,
    holders_by_token,
    parse_frame,
    rank_frames,
    render_headshot,
    square_box,
)
from pipeline.photo_picker import credit_for


class TestParseFrame:
    def test_reads_event_year_kind_and_sail(self):
        assert parse_frame("SY25_ls_ARU91_00156 copy.jpg") == {
            "event_code": "SY", "year": 2025, "kind": "ls", "token": "ARU91"}

    def test_photographer_suffix_does_not_change_the_sail(self):
        frame = parse_frame("SY25_fl_ITA140_RAFASOULART_00240 copy.jpg")
        assert frame["token"] == "ITA140"
        assert frame["kind"] == "fl"

    def test_two_digit_event_year(self):
        assert parse_frame("FV26_ls_B16_00091 copy.jpg")["year"] == 2026

    def test_a_name_without_the_convention_is_not_a_frame(self):
        """Rafa's portrait day is _SA75108.jpg: no sail, so no rider. Skip it."""
        assert parse_frame("_SA75108.jpg") is None
        assert parse_frame("FUE25 Podium 27JulyLOW_I3A5189.jpg") is None


RESULTS_378 = [
    # (stats athlete id, sail at THIS event, nationality)
    (75, "GRE-734", "Greece"),
    (892, "B-16", "Belgium"),
    (16, "G-3", "Germany"),
]


class TestHoldersByToken:
    def test_maps_each_spelling_of_the_sail_to_the_athlete(self):
        holders = holders_by_token(RESULTS_378)
        assert holders["GRE734"] == 75
        assert holders["B16"] == 892
        assert holders["BEL16"] == 892

    def test_a_sail_two_athletes_held_at_the_event_matches_nobody(self):
        """G-3 is shared by two athletes in the stats DB. If both show up in
        one event's results, the filename cannot say which one is pictured."""
        holders = holders_by_token(RESULTS_378 + [(1462, "G-3", "Germany")])
        assert "G3" not in holders

    def test_the_same_athlete_twice_is_not_a_clash(self):
        """A rider in two divisions at one event appears twice in results."""
        holders = holders_by_token(RESULTS_378 + [(75, "GRE-734", "Greece")])
        assert holders["GRE734"] == 75


class TestFramesFor:
    FILES = [
        ("Rider Portraits", "SY25_ls_GRE734_00962.jpg"),
        ("SYLT HIGH RES/FREESTYLE", "SY25_fs_GRE734_01021.jpg"),
        ("Rider Portraits", "SY25_ls_B16_00026 copy.jpg"),
        ("Rider Portraits", "SY25_ls_GRE7340_00001.jpg"),
        ("Rider Portraits", "FV26_ls_GRE734_00059 copy.jpg"),
    ]

    def test_only_this_athletes_lifestyle_frames_from_this_event(self):
        got = frames_for(75, self.FILES, holders_by_token(RESULTS_378),
                         event_code="SY", year=2025)
        assert [name for _, name in got] == ["SY25_ls_GRE734_00962.jpg"]

    def test_a_sail_nobody_held_at_the_event_matches_nothing(self):
        """Today's sail is not evidence: only the event's own results are."""
        got = frames_for(999, self.FILES, holders_by_token(RESULTS_378),
                         event_code="SY", year=2025)
        assert got == []


class TestRankFrames:
    def test_posed_portraits_first_then_lifestyle_then_the_rest(self):
        frames = [
            ("27 SEPT - DAY 2", "SY25_ls_B16_3.jpg"),
            ("SYLT HIGH RES/LIFESTYLE", "SY25_ls_B16_2.jpg"),
            ("Rider Portraits", "SY25_ls_B16_1.jpg"),
        ]
        assert [f for f, _ in rank_frames(frames)] == [
            "Rider Portraits", "SYLT HIGH RES/LIFESTYLE", "27 SEPT - DAY 2"]

    def test_the_same_frame_in_two_folders_is_one_candidate(self):
        """The Drive keeps SY25_ls_GRE734_00036.jpg in HIGH RES and
        '..._00036 copy.jpg' in Rider Portraits: one frame, shown once."""
        frames = [
            ("SYLT HIGH RES/LIFESTYLE", "SY25_ls_GRE734_00036.jpg"),
            ("Rider Portraits", "SY25_ls_GRE734_00036 copy.jpg"),
            ("SYLT HIGH RES/LIFESTYLE", "SY25_ls_GRE734_00002.jpg"),
        ]
        assert rank_frames(frames) == [
            ("Rider Portraits", "SY25_ls_GRE734_00036 copy.jpg"),
            ("SYLT HIGH RES/LIFESTYLE", "SY25_ls_GRE734_00002.jpg"),
        ]

    def test_caps_the_number_of_candidates(self):
        frames = [("Rider Portraits", f"SY25_ls_B16_{i}.jpg") for i in range(20)]
        assert len(rank_frames(frames, limit=6)) == 6


class TestSquareBox:
    def test_is_square_and_contains_the_face(self):
        left, top, side = square_box(3000, 2000, (1400, 600, 200, 200))
        assert side > 200
        assert left <= 1400 and left + side >= 1600
        assert top <= 600 and top + side >= 800

    def test_never_leaves_the_frame(self):
        left, top, side = square_box(3000, 2000, (2900, 10, 90, 90))
        assert left >= 0 and top >= 0
        assert left + side <= 3000 and top + side <= 2000

    def test_a_face_bigger_than_the_frame_allows_takes_the_short_edge(self):
        left, top, side = square_box(1000, 800, (100, 100, 700, 700))
        assert side == 800 and top == 0

    @pytest.mark.parametrize("scale", [2.0, 3.0])
    def test_scale_sets_how_much_of_the_body_is_in(self, scale):
        _, _, side = square_box(4000, 4000, (1900, 1900, 200, 200), scale=scale)
        assert side == int(200 * scale)


class TestRenderHeadshot:
    def _src(self, tmp_path, size=(3000, 2000)):
        src = tmp_path / "SY25_ls_B16_00026.jpg"
        Image.new("RGB", size, (200, 120, 90)).save(src, "JPEG")
        return src

    def test_writes_a_640_square_jpeg(self, tmp_path):
        dest = render_headshot(self._src(tmp_path), (0.3, 0.1, 0.5),
                               tmp_path / "892.jpg")
        with Image.open(dest) as im:
            assert im.format == "JPEG"
            assert im.size == (640, 640)

    def test_box_is_a_fraction_of_the_frame_it_was_drawn_on(self, tmp_path):
        """The sheet draws on a 1000px thumbnail; the render reads a larger
        copy. Fractions of the short edge keep the box the same either way."""
        src = tmp_path / "src.jpg"
        im = Image.new("RGB", (2000, 1000), (0, 0, 0))
        im.paste((255, 255, 255), (1000, 0, 2000, 1000))  # right half white
        im.save(src, "JPEG")
        dest = render_headshot(src, (0.5, 0.0, 1.0), tmp_path / "1.jpg")
        with Image.open(dest) as out:
            assert min(out.convert("L").getextrema()) > 200

    def test_never_upscales_a_small_crop(self, tmp_path):
        dest = render_headshot(self._src(tmp_path, (800, 600)), (0, 0, 1.0),
                               tmp_path / "1.jpg")
        with Image.open(dest) as im:
            assert im.size == (600, 600)

    def test_credit_travels_in_the_file(self, tmp_path):
        credit = {"photographer": "Rafa Soulart", "handle": "@rafasoulart"}
        dest = render_headshot(self._src(tmp_path), (0.3, 0.1, 0.5),
                               tmp_path / "892.jpg", credit=credit)
        read = credit_for(dest)
        assert read["confirmed"] is True
        assert "Rafa Soulart" in read["photographer"]

    def test_an_unknown_credit_is_left_blank_not_guessed(self, tmp_path):
        dest = render_headshot(self._src(tmp_path), (0.3, 0.1, 0.5),
                               tmp_path / "892.jpg",
                               credit={"photographer": "", "handle": ""})
        assert credit_for(dest)["confirmed"] is False
