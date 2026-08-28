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
