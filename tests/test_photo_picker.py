"""Sail-token matching, cheapest-copy resolution and credit reading."""

import json
import os

import pytest

from pipeline.photo_picker import (
    cheapest_copies,
    credit_for,
    matches_token,
    sail_tokens,
    token_of,
)


class TestSailTokens:
    """The Drive writes the same rider two ways, so a lookup must try both."""

    def test_strips_the_hyphen(self):
        assert "E334" in sail_tokens("E-334", "Spain")

    def test_adds_the_three_letter_form_from_the_athletes_country(self):
        """Takuma Sugi is J-7 in the API and JPN7 in the Drive.

        Searching only J7 finds 6 files; JPN7 finds 44. Miss this and a rider
        looks unphotographed when he is not.
        """
        tokens = sail_tokens("J-7", "Japan")
        assert "J7" in tokens
        assert "JPN7" in tokens

    def test_spanish_sail_gets_the_esp_form(self):
        tokens = sail_tokens("E-95", "Spain")
        assert "E95" in tokens
        assert "ESP95" in tokens

    def test_already_three_letter_sail_is_not_duplicated(self):
        tokens = sail_tokens("BRA-105", "Brazil")
        assert tokens.count("BRA105") == 1

    def test_unknown_country_still_yields_the_literal_form(self):
        assert sail_tokens("X-12", "Ruritania") == ["X12"]

    def test_missing_sail_yields_nothing(self):
        assert sail_tokens("", "Spain") == []
        assert sail_tokens(None, "Spain") == []

    def test_literal_form_comes_first(self):
        """The sail as registered is the better guess; the alias is a fallback."""
        assert sail_tokens("J-7", "Japan")[0] == "J7"


class TestTokenMatching:
    """Prefix matching would merge riders who have nothing to do with each other."""

    def test_reads_the_sail_field_out_of_the_filename(self):
        assert token_of("TF26_wv_G21_1317.jpg") == "G21"
        assert token_of("GC26_ls_BRA105_00347.jpg") == "BRA105"

    def test_filename_without_enough_fields_has_no_token(self):
        assert token_of("random.jpg") == ""
        assert token_of("TF26_wv.jpg") == ""

    @pytest.mark.parametrize("filename,token,expected", [
        ("GC26_wv_E95_0001.jpg", "E95", True),
        # E959 is Marino Gil Gherardi, not Alessio Stillrich
        ("GC26_wv_E959_0001.jpg", "E95", False),
        # E1111 is a different rider again
        ("GC26_wv_E1111_0001.jpg", "E11", False),
        ("GC26_wv_E11_0001.jpg", "E11", True),
        # 2025 puts the photographer between the sail and the sequence
        ("TF25_ls_E3_RAFASOULART_00013.jpg", "E3", True),
    ])
    def test_matches_whole_token_only(self, filename, token, expected):
        assert matches_token(filename, token) is expected

    def test_matching_is_case_insensitive(self):
        assert matches_token("gc26_wv_e95_0001.jpg", "E95") is True


class TestCheapestCopies:
    """The same frame exists twice: web size in the day folder, huge in HIGH RES."""

    def test_keeps_the_smallest_copy_of_each_frame(self, tmp_path):
        day = tmp_path / "DAY 6"
        hi = tmp_path / "HIGH RES"
        day.mkdir()
        hi.mkdir()
        (day / "TF26_wv_G21_1317.jpg").write_bytes(b"x" * 1_400_000)
        (hi / "TF26_wv_G21_1317.jpg").write_bytes(b"x" * 26_000_000)

        kept = cheapest_copies([day / "TF26_wv_G21_1317.jpg",
                                hi / "TF26_wv_G21_1317.jpg"])
        assert len(kept) == 1
        assert kept[0].parent.name == "DAY 6"

    def test_different_frames_are_all_kept(self, tmp_path):
        for name in ("a_b_G21_1.jpg", "a_b_G21_2.jpg"):
            (tmp_path / name).write_bytes(b"x" * 100)
        assert len(cheapest_copies(list(tmp_path.iterdir()))) == 2

    def test_result_is_stable_in_filename_order(self, tmp_path):
        for name in ("a_b_G21_3.jpg", "a_b_G21_1.jpg", "a_b_G21_2.jpg"):
            (tmp_path / name).write_bytes(b"x" * 100)
        names = [p.name for p in cheapest_copies(list(tmp_path.iterdir()))]
        assert names == sorted(names)


def _jpeg_with_xmp(path, creator=None, rights=None):
    """Minimal file carrying an XMP-ish packet, which is all credit_for reads."""
    xmp = b""
    if creator:
        xmp += (b"<dc:creator> <rdf:Seq> <rdf:li>" + creator.encode()
                + b"</rdf:li> </rdf:Seq> </dc:creator>")
    if rights:
        xmp += (b'<dc:rights> <rdf:Alt> <rdf:li xml:lang="x-default">'
                + rights.encode() + b"</rdf:li> </rdf:Alt> </dc:rights>")
    path.write_bytes(b"\xff\xd8\xff\xe1" + xmp + b"\x00" * 128)
    return path


class TestCreditFor:
    """Credit is per photo. One line per event is wrong: Tenerife 2025 is Rafa
    Soulart and Tenerife 2026 is John Carter, and 2025 mixes in Photo Medano."""

    def test_filename_marker_wins(self, tmp_path):
        p = _jpeg_with_xmp(tmp_path / "TF25_ls_E3_RAFASOULART_00013.jpg")
        credit = credit_for(p)
        assert credit["photographer"] == "Rafa Soulart"
        assert credit["handle"] == "@rafasoulart"
        assert credit["confirmed"] is True

    def test_filename_marker_beats_a_conflicting_xmp_tag(self, tmp_path):
        p = _jpeg_with_xmp(tmp_path / "TF25_ls_E3_RAFASOULART_1.jpg",
                           creator="john carter")
        assert credit_for(p)["photographer"] == "Rafa Soulart"

    def test_falls_back_to_the_xmp_creator(self, tmp_path):
        p = _jpeg_with_xmp(tmp_path / "TF26_wv_G21_1317.jpg",
                           creator="john carter", rights="john carter")
        credit = credit_for(p)
        assert credit["photographer"] == "john carter"
        assert credit["handle"] == "@jcwindsurf"
        assert credit["confirmed"] is True

    def test_untagged_is_unknown_not_guessed(self, tmp_path):
        """A third of Tenerife 2026 is untagged, and untagged frames appear even
        inside a folder named JOHN CARTER, so absence proves nothing."""
        p = _jpeg_with_xmp(tmp_path / "GC26_wv_G44_00825.jpg")
        credit = credit_for(p)
        assert credit["photographer"] == ""
        assert credit["confirmed"] is False

    def test_unknown_photographer_keeps_the_name_but_has_no_handle(self, tmp_path):
        p = _jpeg_with_xmp(tmp_path / "x_y_E1_1.jpg", creator="Someone New")
        credit = credit_for(p)
        assert credit["photographer"] == "Someone New"
        assert credit["handle"] == ""
        assert credit["confirmed"] is True

    def test_records_the_source_filename(self, tmp_path):
        p = _jpeg_with_xmp(tmp_path / "GC26_wv_G44_00825.jpg")
        assert credit_for(p)["source_file"] == "GC26_wv_G44_00825.jpg"


class TestInstallPhoto:
    """Picks land in the repo at the same size as every other athlete photo."""

    def _big(self, tmp_path, name="src.jpg", size=(4000, 2667)):
        from PIL import Image
        p = tmp_path / name
        Image.new("RGB", size, (40, 80, 120)).save(p, "JPEG")
        return p

    def test_downscales_to_the_repo_convention(self, tmp_path):
        from PIL import Image
        from pipeline.photo_picker import install_photo
        src = self._big(tmp_path)
        dest = install_photo(src, tmp_path / "out", 49)
        assert dest.name == "49.jpg"
        assert max(Image.open(dest).size) == 1920

    def test_leaves_an_already_small_photo_alone(self, tmp_path):
        from PIL import Image
        from pipeline.photo_picker import install_photo
        src = self._big(tmp_path, size=(1200, 800))
        dest = install_photo(src, tmp_path / "out", 7)
        assert Image.open(dest).size == (1200, 800)

    def test_creates_the_event_folder(self, tmp_path):
        from pipeline.photo_picker import install_photo
        out = tmp_path / "events" / "122"
        install_photo(self._big(tmp_path), out, 49)
        assert out.is_dir()

    def test_square_crop_for_a_face(self, tmp_path):
        from PIL import Image
        from pipeline.photo_picker import install_photo
        src = self._big(tmp_path)
        dest = install_photo(src, tmp_path / "faces", 19, square=600)
        assert Image.open(dest).size == (600, 600)


class TestMergeJsonEntry:
    """focus.json and credits.json are hand-editable, so a write must not
    trample the neighbouring riders or the explanatory comment."""

    def test_creates_the_file_with_a_comment(self, tmp_path):
        from pipeline.photo_picker import merge_json_entry
        p = tmp_path / "focus.json"
        merge_json_entry(p, "49", "50% 50%", comment="how to read this")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["49"] == "50% 50%"
        assert data["_comment"] == "how to read this"

    def test_keeps_existing_riders(self, tmp_path):
        from pipeline.photo_picker import merge_json_entry
        p = tmp_path / "focus.json"
        p.write_text(json.dumps({"_comment": "keep me", "68": "45% 50%"}),
                     encoding="utf-8")
        merge_json_entry(p, "49", "50% 50%")
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["68"] == "45% 50%"
        assert data["49"] == "50% 50%"
        assert data["_comment"] == "keep me"

    def test_overwrites_the_same_rider(self, tmp_path):
        from pipeline.photo_picker import merge_json_entry
        p = tmp_path / "focus.json"
        merge_json_entry(p, "49", "10% 50%")
        merge_json_entry(p, "49", "90% 50%")
        assert json.loads(p.read_text(encoding="utf-8"))["49"] == "90% 50%"

    def test_survives_a_corrupt_file_without_losing_the_new_entry(self, tmp_path):
        from pipeline.photo_picker import merge_json_entry
        p = tmp_path / "focus.json"
        p.write_text("{not json", encoding="utf-8")
        merge_json_entry(p, "49", "50% 50%")
        assert json.loads(p.read_text(encoding="utf-8"))["49"] == "50% 50%"
