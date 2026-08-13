"""Tests for the how-to-make-picks reel editor (ffmpeg intercut).

reel_edit.py stitches branded explainer-card clips together with live picks
screen-record footage into the post-3 reel. These tests cover the pure logic:
building the ffmpeg trim/concat commands and planning which slices of the footage
to cut in (derived from the markers screen_record.py writes alongside the video).
The actual rendering/ffmpeg execution is integration, verified by running.
"""
from pipeline.reel_edit import (
    trim_clip_cmd,
    concat_clips_cmd,
    footage_segments,
    DEFAULT_W,
    DEFAULT_H,
    FPS,
)


class TestTrimClipCmd:
    def setup_method(self):
        self.cmd = trim_clip_cmd("in.mp4", 2.0, 6.5, "out.mp4")

    def test_is_ffmpeg(self):
        assert self.cmd[0] == "ffmpeg"
        assert "-y" in self.cmd

    def test_inputs_and_output(self):
        assert "in.mp4" in self.cmd
        assert self.cmd[-1] == "out.mp4"

    def test_seeks_to_start_and_limits_duration(self):
        # start = 2.0, end = 6.5 -> duration 4.5
        assert "2.0" in self.cmd
        i = self.cmd.index("-t")
        assert float(self.cmd[i + 1]) == 4.5

    def test_normalises_size_and_fps(self):
        joined = " ".join(self.cmd)
        assert f"{DEFAULT_W}" in joined and f"{DEFAULT_H}" in joined
        assert str(FPS) in joined

    def test_rejects_non_positive_duration(self):
        import pytest
        with pytest.raises(ValueError):
            trim_clip_cmd("in.mp4", 5.0, 5.0, "out.mp4")

    def test_speed_applies_setpts_divisor(self):
        cmd = trim_clip_cmd("in.mp4", 0.0, 10.0, "out.mp4", speed=2.5)
        joined = " ".join(cmd)
        assert "setpts=(PTS-STARTPTS)/2.5" in joined

    def test_default_speed_is_realtime(self):
        joined = " ".join(trim_clip_cmd("in.mp4", 0.0, 10.0, "out.mp4"))
        assert "setpts=(PTS-STARTPTS)/1.0" in joined


class TestConcatClipsCmd:
    def setup_method(self):
        self.clips = ["a.mp4", "b.mp4", "c.mp4"]
        self.cmd = concat_clips_cmd(self.clips, "final.mp4")

    def test_is_ffmpeg_with_output_last(self):
        assert self.cmd[0] == "ffmpeg"
        assert self.cmd[-1] == "final.mp4"

    def test_each_clip_is_an_input(self):
        # every clip should appear after a -i flag
        for clip in self.clips:
            idx = self.cmd.index(clip)
            assert self.cmd[idx - 1] == "-i"

    def test_concat_filter_covers_all_clips(self):
        joined = " ".join(self.cmd)
        assert "concat=n=3" in joined

    def test_requires_at_least_one_clip(self):
        import pytest
        with pytest.raises(ValueError):
            concat_clips_cmd([], "final.mp4")


class TestFootageSegments:
    def test_returns_build_and_confirm_windows(self):
        markers = {
            "build_start": 5.0,
            "build_end": 18.0,
            "confirm_start": 20.0,
            "confirm_end": 24.0,
        }
        segs = footage_segments(markers)
        assert segs["build"] == (5.0, 18.0)
        assert segs["confirm"] == (20.0, 24.0)

    def test_confirm_optional_when_markers_absent(self):
        markers = {"build_start": 5.0, "build_end": 18.0}
        segs = footage_segments(markers)
        assert "build" in segs
        assert "confirm" not in segs

    def test_raises_when_build_window_missing(self):
        import pytest
        with pytest.raises(ValueError):
            footage_segments({"confirm_start": 1.0, "confirm_end": 2.0})
