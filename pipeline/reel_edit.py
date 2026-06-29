"""Intercut the how-to-make-picks reel: branded cards + live picks footage.

The conversion-driver post in the Fantasy League launch series (post 3). Stitches the
explainer-card clips (rendered from templates/how_to_pick_reel.html, one screen per
clip) together with slices of the live picks screen-record footage
(pipeline/screen_record.py) into one portrait MP4:

    HOOK card -> [build-squad footage] -> CONTRAST card -> [confirm-button footage]
    -> CTA card

The footage slices are derived from the markers screen_record.py writes alongside its
video (build_start/end, confirm_start/end), so the login screen and dead time are
trimmed out automatically. Falls back gracefully to a card-only reel if no footage is
supplied.

Pure helpers (trim/concat command building, segment planning) are unit-tested; the
render + ffmpeg execution is integration, verified by running.

Usage:
    python -m pipeline.reel_edit \
        --footage output/mp4/picks_raw.mp4 \
        --out output/mp4/how_to_pick_reel.mp4
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile

DEFAULT_W = 1080
DEFAULT_H = 1920
FPS = 30

# Per-card hold (ms) when rendered as a standalone clip. Tuned to read on a reel
# without dragging; the fade in/out is handled by the template JS.
CARD_HOLD_MS = {
    "hook": 2600,
    "contrast": 7400,
    "cta": 4000,
}

# The reel spine: cards in order, with footage cut in between. Each entry is either
# ("card", screen_id) or ("footage", segment_key). Narrative: hook -> watch a squad
# get built -> the confirm pop-out (team locks, becomes visible to others) -> the
# Save-vs-Confirm comparison that explains it -> deadline CTA.
REEL_SPINE = [
    ("card", "hook"),
    ("footage", "build"),
    ("footage", "confirm"),
    ("card", "contrast"),
    ("card", "cta"),
]

# Footage playback speed per segment. The build is a ~35s slog at 1x (5 picks via
# modals); sped up it reads as a snappy "watch the squad come together" montage. The
# confirm beat is short and stays at real time so the button registers.
FOOTAGE_SPEED = {
    "build": 2.4,
    "confirm": 1.0,
}


def _scale_pad_filter(width: int, height: int, fps: int, speed: float = 1.0) -> str:
    """A filter chain that fits any source into width x height (letterbox, no crop),
    normalises fps + SAR, optionally speeds it up, and resets PTS so clips concat
    cleanly. Speed is applied before the fps resample so the result is a clean
    constant-rate clip."""
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1,setpts=(PTS-STARTPTS)/{speed},fps={fps},format=yuv420p"
    )


def trim_clip_cmd(
    src: str,
    start: float,
    end: float,
    out_path: str,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    fps: int = FPS,
    speed: float = 1.0,
) -> list[str]:
    """Build the ffmpeg command to cut [start, end] from src, normalised to the reel
    frame (size + fps) and optionally sped up. -ss/-t are input options so the source
    window is selected first, then setpts compresses it (output = window / speed).
    Re-encodes (accurate seek) rather than stream-copy."""
    duration = round(end - start, 3)
    if duration <= 0:
        raise ValueError(f"non-positive trim duration: start={start} end={end}")
    return [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", src,
        "-vf", _scale_pad_filter(width, height, fps, speed),
        "-an",  # drop source audio; the reel gets its own track later
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        out_path,
    ]


def concat_clips_cmd(
    clips: list[str],
    out_path: str,
    width: int = DEFAULT_W,
    height: int = DEFAULT_H,
    fps: int = FPS,
) -> list[str]:
    """Build the ffmpeg command to concatenate clips via the concat filter, scaling +
    fps-normalising each so heterogeneous sources (card renders + screen-record
    footage) join without glitches."""
    if not clips:
        raise ValueError("concat needs at least one clip")

    cmd = ["ffmpeg", "-y"]
    for clip in clips:
        cmd += ["-i", clip]

    filt = _scale_pad_filter(width, height, fps)
    parts = []
    for i in range(len(clips)):
        parts.append(f"[{i}:v]{filt}[v{i}]")
    streams = "".join(f"[v{i}]" for i in range(len(clips)))
    parts.append(f"{streams}concat=n={len(clips)}:v=1:a=0[outv]")
    filter_complex = ";".join(parts)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        out_path,
    ]
    return cmd


def footage_segments(markers: dict) -> dict:
    """Plan which footage windows to cut in, from screen_record markers.

    Returns {"build": (start, end)} plus {"confirm": (start, end)} when those markers
    are present. The build window is required (it's the heart of the footage)."""
    if "build_start" not in markers or "build_end" not in markers:
        raise ValueError("markers must define build_start and build_end")

    segs = {"build": (markers["build_start"], markers["build_end"])}
    if "confirm_start" in markers and "confirm_end" in markers:
        segs["confirm"] = (markers["confirm_start"], markers["confirm_end"])
    return segs


def _load_markers(footage_path: str) -> dict:
    """Read the sidecar markers JSON screen_record.py writes next to the video."""
    sidecar = footage_path + ".markers.json"
    if os.path.exists(sidecar):
        with open(sidecar, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _render_card_clip(screen: str, out_path: str) -> str:
    """Render a single explainer-card screen to a standalone clip (solo mode)."""
    from pipeline.renderer import render_to_video
    from pipeline.templates import render_template
    from pipeline.how_to_pick import build_how_to_pick_reel_data

    hold = CARD_HOLD_MS[screen]
    data = {
        **build_how_to_pick_reel_data(),
        "width": DEFAULT_W,
        "height": DEFAULT_H,
        "solo": screen,
        "solo_hold_ms": hold,
    }
    html = render_template("how_to_pick_reel", data)
    # fade-in + hold + fade-out, plus a little head/tail margin for recording.
    duration_ms = hold + 1600
    render_to_video(html, out_path, width=DEFAULT_W, height=DEFAULT_H, dpr=1,
                    duration_ms=duration_ms)
    return out_path


def build_how_to_pick_reel(
    out_path: str,
    footage_path: str | None = None,
    markers: dict | None = None,
) -> str:
    """Assemble the post-3 reel: explainer cards intercut with picks footage.

    If footage_path is given, its markers sidecar (or the markers arg) decides which
    slices to cut in. With no footage, produces a card-only reel.
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to build the reel")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    work = tempfile.mkdtemp()

    if markers is None and footage_path:
        markers = _load_markers(footage_path)

    segs = {}
    if footage_path and markers:
        try:
            segs = footage_segments(markers)
        except ValueError:
            print("Footage markers incomplete, building a card-only reel.")

    try:
        clips: list[str] = []
        for kind, key in REEL_SPINE:
            if kind == "card":
                clip = os.path.join(work, f"card_{key}.mp4")
                print(f"Rendering card: {key} ...")
                _render_card_clip(key, clip)
                clips.append(clip)
            else:  # footage
                if key not in segs:
                    continue  # no footage for this slot, skip it
                start, end = segs[key]
                speed = FOOTAGE_SPEED.get(key, 1.0)
                clip = os.path.join(work, f"footage_{key}.mp4")
                print(f"Trimming footage [{key}] {start}-{end}s @ {speed}x ...")
                subprocess.run(
                    trim_clip_cmd(footage_path, start, end, clip, speed=speed),
                    capture_output=True, check=True,
                )
                clips.append(clip)

        print(f"Concatenating {len(clips)} clips ...")
        subprocess.run(concat_clips_cmd(clips, out_path), capture_output=True, check=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("Saved:", out_path)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the how-to-make-picks reel")
    parser.add_argument(
        "--footage", default="output/mp4/picks_raw.mp4",
        help="Picks screen-record footage (with a .markers.json sidecar)",
    )
    parser.add_argument(
        "--out", default="output/mp4/how_to_pick_reel.mp4", help="Output mp4 path",
    )
    parser.add_argument(
        "--cards-only", action="store_true", help="Build without footage (cards only)",
    )
    args = parser.parse_args()

    footage = None if args.cards_only else args.footage
    if footage and not os.path.exists(footage):
        print(f"Footage not found at {footage}; building a card-only reel.")
        footage = None
    build_how_to_pick_reel(args.out, footage_path=footage)


if __name__ == "__main__":
    main()
