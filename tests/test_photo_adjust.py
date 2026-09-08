"""Tests for the crop maths behind the photo adjuster."""

import pytest

from pipeline.photo_adjust import CropBox, cover_scale, crop_box, fits_frame


FRAME = (1080, 1350)  # the slide, 4:5


class TestCoverScale:
    def test_a_landscape_photo_is_bound_by_its_height(self):
        """3:2 into 4:5 scales to fit the height, which is why the vertical
        half of object-position is inert on these: there is no slack to pan."""
        assert cover_scale((1920, 1280), FRAME) == pytest.approx(1350 / 1280)

    def test_a_tall_photo_is_bound_by_its_width(self):
        assert cover_scale((1000, 2000), FRAME) == pytest.approx(1080 / 1000)


class TestCropBox:
    def test_unzoomed_landscape_takes_the_full_height(self):
        """At zoom 1 the box is the whole height and a slice of the width."""
        box = crop_box((1920, 1280), FRAME, zoom=1.0, offset=(0.0, 0.0))
        assert box.height == pytest.approx(1280)
        assert box.width == pytest.approx(1280 * 0.8)

    def test_zooming_in_takes_a_smaller_box(self):
        """Zoom 2 means the frame covers half as much of the source."""
        box = crop_box((1920, 1280), FRAME, zoom=2.0, offset=(0.0, 0.0))
        assert box.height == pytest.approx(640)
        assert box.width == pytest.approx(512)

    def test_offset_moves_the_box_not_the_subject(self):
        """A positive offset drags the photo right, so the box moves left:
        the viewer sees content further to the left of the source."""
        centred = crop_box((1920, 1280), FRAME, zoom=1.0, offset=(0.0, 0.0))
        dragged = crop_box((1920, 1280), FRAME, zoom=1.0, offset=(0.1, 0.0))
        assert dragged.left < centred.left

    def test_the_box_never_leaves_the_source(self):
        """Dragging past the edge would crop transparent pixels into the post."""
        box = crop_box((1920, 1280), FRAME, zoom=1.0, offset=(-5.0, -5.0))
        assert box.left >= 0 and box.top >= 0
        assert box.left + box.width <= 1920
        assert box.top + box.height <= 1280

    def test_zoom_below_one_is_clamped(self):
        """Under 1 the box would be bigger than the photo, so the crop would
        need padding. The full frame is as far out as a photo can go."""
        box = crop_box((1920, 1280), FRAME, zoom=0.4, offset=(0.0, 0.0))
        assert box.height == pytest.approx(1280)

    def test_the_box_keeps_the_frame_aspect(self):
        """Any other ratio would be squashed when it is resized to the slide."""
        for zoom in (1.0, 1.5, 2.5):
            box = crop_box((4994, 3329), FRAME, zoom=zoom, offset=(0.2, -0.1))
            assert box.width / box.height == pytest.approx(1080 / 1350)


class TestFitsFrame:
    def test_a_subject_wider_than_the_window_is_reported(self):
        """Tonky Frans' boom-to-board spans the whole visible width, so one end
        is always cut. Saying so beats the user hunting for a value that does
        not exist."""
        assert not fits_frame(subject_width=0.55, natural=(1920, 1280), frame=FRAME)

    def test_a_subject_that_fits_is_not_reported(self):
        assert fits_frame(subject_width=0.30, natural=(1920, 1280), frame=FRAME)


class TestSaveCrop:
    def _rider(self, tmp_path, size=(1920, 1280), kind="hero"):
        from PIL import Image
        src = tmp_path / "SRC_fs_V10_0001.jpg"
        im = Image.new("RGB", size)
        # A gradient, so a crop from a different offset is provably different.
        for x in range(size[0]):
            for y in range(0, size[1], 64):
                im.putpixel((x, y), (x % 256, 0, 0))
        im.save(src, "JPEG", quality=95)
        installed = tmp_path / "74.jpg"
        im.save(installed, "JPEG", quality=95)
        return {"id": 74, "kind": kind, "installed": str(installed),
                "display": str(src), "nw": size[0], "nh": size[1]}

    def test_the_saved_file_is_the_slide_size(self, tmp_path):
        """Anything else would be resized again at render, losing sharpness."""
        from PIL import Image
        import adjust_photos
        rider = self._rider(tmp_path)
        adjust_photos.save_crop(rider, zoom=1.0, dx=0.0, dy=0.0)
        with Image.open(rider["installed"]) as out:
            assert out.size == (1080, 1350)

    def test_dragging_changes_what_is_saved(self, tmp_path):
        """The whole point of the tool: a different position writes a
        different crop, not the same file with different metadata."""
        from PIL import Image
        import adjust_photos
        rider = self._rider(tmp_path)
        adjust_photos.save_crop(rider, zoom=1.0, dx=0.0, dy=0.0)
        with Image.open(rider["installed"]) as out:
            centred = list(out.convert("RGB").getdata())[:64]
        adjust_photos.save_crop(rider, zoom=1.0, dx=0.4, dy=0.0)
        with Image.open(rider["installed"]) as out:
            dragged = list(out.convert("RGB").getdata())[:64]
        assert centred != dragged

    def test_zooming_writes_a_tighter_crop(self, tmp_path):
        """Zoom has to reach the file: it is the adjustment focus.json cannot
        make at all."""
        import adjust_photos
        from pipeline.photo_adjust import crop_box
        rider = self._rider(tmp_path)
        wide = crop_box((rider["nw"], rider["nh"]), (1080, 1350), zoom=1.0)
        tight = crop_box((rider["nw"], rider["nh"]), (1080, 1350), zoom=2.0)
        assert tight.width < wide.width
        adjust_photos.save_crop(rider, zoom=2.0, dx=0.0, dy=0.0)  # must not raise


    def test_a_headshot_is_saved_square(self, tmp_path):
        """The table sets the thumbnail in a circle, so a hero-shaped crop
        would be squashed into it. The kind picks the frame.
        """
        from PIL import Image
        import adjust_photos
        rider = self._rider(tmp_path, kind="face")
        adjust_photos.save_crop(rider, zoom=1.0, dx=0.0, dy=0.0)
        with Image.open(rider["installed"]) as out:
            assert out.size == (600, 600)


    def test_a_crop_can_be_dragged_past_the_edge_of_the_photo(self, tmp_path):
        """At the widest framing a landscape shot has no vertical slack, so a
        clamped box cannot be nudged up or down at all. The tool has to let go
        of the edge for "move him up" to mean anything.
        """
        from PIL import Image
        import adjust_photos
        rider = self._rider(tmp_path)
        adjust_photos.save_crop(rider, zoom=1.0, dx=0.0, dy=0.0)
        with Image.open(rider["installed"]) as out:
            centred = list(out.convert("RGB").getdata())[:64]
        adjust_photos.save_crop(rider, zoom=1.0, dx=0.0, dy=0.5)
        with Image.open(rider["installed"]) as out:
            assert out.size == (1080, 1350)
            assert list(out.convert("RGB").getdata())[:64] != centred

    def test_what_falls_outside_is_filled_not_left_black(self, tmp_path):
        """A hard band on a published slide reads as a mistake. The overflow
        takes a blurred cover of the same photo instead.
        """
        from PIL import Image
        import adjust_photos
        rider = self._rider(tmp_path)
        # Far enough that the top of the frame is entirely off the photo.
        adjust_photos.save_crop(rider, zoom=1.0, dx=0.0, dy=0.9)
        with Image.open(rider["installed"]) as out:
            top_row = list(out.convert("RGB").crop((0, 0, 1080, 1)).getdata())
        assert any(px != (0, 0, 0) for px in top_row)


class TestOriginalLookup:
    """Finding the high-res file a photo was installed from."""

    def _adjust(self):
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "adjust_photos", pathlib.Path(__file__).parent.parent / "adjust_photos.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_a_flat_source_folder_resolves_directly(self, tmp_path):
        (tmp_path / "SY16_wv_E63_0269.jpg").write_bytes(b"x")
        found = self._adjust()._original_for(
            {"source_file": "SY16_wv_E63_0269.jpg"}, tmp_path)
        assert found == tmp_path / "SY16_wv_E63_0269.jpg"

    def test_a_nested_source_folder_is_searched(self, tmp_path):
        """The PWA Drive is <event>/wave/WOMEN/<frame>.jpg, and the heroes and
        the headshots sit in two different subtrees of one event folder. A
        flat lookup found neither, so every card opened with its zoom limited
        to the downscaled copy already in the repo.
        """
        deep = tmp_path / "wave" / "WOMEN"
        deep.mkdir(parents=True)
        (deep / "SY16_wv_H87_0261.jpg").write_bytes(b"x")
        found = self._adjust()._original_for(
            {"source_file": "SY16_wv_H87_0261.jpg"}, tmp_path)
        assert found == deep / "SY16_wv_H87_0261.jpg"

    def test_a_missing_original_is_still_none(self, tmp_path):
        assert self._adjust()._original_for(
            {"source_file": "nope.jpg"}, tmp_path) is None
