"""Tests for grouping a carousel's slides into a folder of their own."""

import os

from generate import group_into_post_folder, write_caption_file


def _slides(tmp_path, stem, count):
    paths = []
    for i in range(1, count + 1):
        p = tmp_path / f"{stem}_{i}.png"
        p.write_bytes(b"png")
        paths.append(str(p))
    return paths


class TestGroupIntoPostFolder:
    def test_slides_move_into_a_folder_named_for_the_post(self, tmp_path):
        """A flat output/png fills up fast: one carousel is a dozen files, and
        three runs of the same post are told apart only by a timestamp buried
        in the middle of every name."""
        paths = _slides(tmp_path, "sylt_kings_freestyle_men_20260904_120000", 3)
        moved = group_into_post_folder(paths)
        folder = tmp_path / "sylt_kings_freestyle_men_20260904_120000"
        assert folder.is_dir()
        assert [os.path.basename(m) for m in moved] == [
            "sylt_kings_freestyle_men_20260904_120000_1.png",
            "sylt_kings_freestyle_men_20260904_120000_2.png",
            "sylt_kings_freestyle_men_20260904_120000_3.png",
        ]
        assert all(os.path.exists(m) for m in moved)
        assert not (tmp_path / "sylt_kings_freestyle_men_20260904_120000_1.png").exists()

    def test_slide_order_is_preserved(self, tmp_path):
        """The returned paths are what gets published, and a carousel posted
        out of order is a re-upload, not an edit."""
        paths = _slides(tmp_path, "post_20260904_120000", 11)
        moved = group_into_post_folder(paths)
        numbers = [int(os.path.basename(m).rsplit("_", 1)[1].split(".")[0])
                   for m in moved]
        assert numbers == list(range(1, 12))

    def test_an_empty_render_is_left_alone(self, tmp_path):
        assert group_into_post_folder([]) == []

    def test_a_second_run_does_not_collide(self, tmp_path):
        """Two runs carry different timestamps, so they get different folders
        rather than one overwriting the other's slides."""
        first = group_into_post_folder(_slides(tmp_path, "post_20260904_120000", 2))
        second = group_into_post_folder(_slides(tmp_path, "post_20260904_130000", 2))
        assert os.path.dirname(first[0]) != os.path.dirname(second[0])
        assert all(os.path.exists(p) for p in first + second)


class TestWriteCaptionFile:
    def test_the_caption_lands_beside_the_slides(self, tmp_path):
        """Posting by hand means copying the caption from somewhere. Next to
        the images beats scrolling back through a terminal."""
        paths = _slides(tmp_path, "post_20260904_120000", 2)
        moved = group_into_post_folder(paths)
        written = write_caption_file(moved, "Who is the King of Sylt?\n\n\U0001f4f8 @jc")
        assert os.path.basename(written) == "caption.txt"
        assert os.path.dirname(written) == os.path.dirname(moved[0])
        with open(written, encoding="utf-8") as fh:
            assert fh.read() == "Who is the King of Sylt?\n\n\U0001f4f8 @jc"

    def test_no_slides_writes_nothing(self, tmp_path):
        assert write_caption_file([], "text") is None
