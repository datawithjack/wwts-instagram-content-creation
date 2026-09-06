"""Intercut the Road to Finals promo reel: branded cards + live predictor footage.

Stitches the explainer-card clips (rendered from templates/road_to_finals_reel.html,
one screen per clip) together with slices of the predictor screen-record footage
(pipeline/screen_record_rtf.py) into one portrait MP4:

    HOOK card -> [rankings + season chart] -> PREDICT card -> [placing riders]
    -> [the recomputed race] -> COUNTS card -> CTA card

Footage slices come from the markers screen_record_rtf.py writes alongside its video,
so page load and dead time are trimmed automatically. Falls back to a card-only reel
if no footage is supplied.

The ffmpeg primitives are shared with the picks reel (pipeline/reel_edit.py) rather
than reimplemented; only the spine, the pacing and the card renderer differ.

Usage:
    python -m pipeline.rtf_reel_edit \
        --footage output/mp4/rtf_raw.mp4 \
        --out output/mp4/road_to_finals_reel.mp4
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile

from pipeline.reel_edit import (
    DEFAULT_H,
    DEFAULT_W,
    concat_clips_cmd,
    trim_clip_cmd,
)

# Per-card hold (ms) as a standalone clip. The counts card holds longest: it carries
# three staggered bullets and the caveat line, and it is the one people screenshot.
CARD_HOLD_MS = {
    "hook": 3400,
    "predict": 2400,
    "counts": 4400,
    "cta": 2800,
}

# The reel spine: ("card", screen_id) or ("footage", segment_key), in order.
# Narrative: the race is level -> here is the real standings and how it got there ->
# now predict what is left -> watch it recompute -> only the best four count -> go.
REEL_SPINE = [
    ("card", "hook"),
    ("footage", "race"),
    ("card", "predict"),
    ("footage", "predict"),
    ("footage", "outcome"),
    ("card", "counts"),
    ("card", "cta"),
]

# Footage playback speed per segment. The predict segment is twenty taps' worth of
# scrolling and reads as a montage sped up; the outcome stays closest to real time
# because the numbers on it are the payoff and have to be legible.
FOOTAGE_SPEED = {
    "race": 1.8,
    "predict": 2.4,
    "outcome": 1.4,
}

SEGMENT_KEYS = ("race", "predict", "outcome")


def footage_segments(markers: dict) -> dict:
    """Plan which footage windows to cut in, from screen_record_rtf markers.

    Every segment is optional except `race`: without the standings the reel has no
    evidence that the thing it is promoting exists.
    """
    if "race_start" not in markers or "race_end" not in markers:
        raise ValueError("markers must define race_start and race_end")

    segs = {}
    for key in SEGMENT_KEYS:
        start, end = markers.get(f"{key}_start"), markers.get(f"{key}_end")
        if start is not None and end is not None:
            segs[key] = (start, end)
    return segs


def _load_markers(footage_path: str) -> dict:
    """Read the sidecar markers JSON screen_record_rtf.py writes next to the video."""
    sidecar = footage_path + ".markers.json"
    if os.path.exists(sidecar):
        with open(sidecar, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _render_card_clip(screen: str, out_path: str) -> str:
    """Render a single explainer-card screen to a standalone clip (solo mode)."""
    from pipeline.renderer import render_to_video
    from pipeline.templates import render_template
    from pipeline.road_to_finals_reel import build_road_to_finals_reel_data

    hold = CARD_HOLD_MS[screen]
    data = {
        **build_road_to_finals_reel_data(),
        "width": DEFAULT_W,
        "height": DEFAULT_H,
        "solo": screen,
        "solo_hold_ms": hold,
    }
    html = render_template("road_to_finals_reel", data)
    # fade-in + hold + fade-out, plus a little head/tail margin for recording.
    duration_ms = hold + 1600
    render_to_video(html, out_path, width=DEFAULT_W, height=DEFAULT_H, dpr=1,
                    duration_ms=duration_ms)
    return out_path


def build_road_to_finals_reel(
    out_path: str,
    footage_path: str | None = None,
    markers: dict | None = None,
) -> str:
    """Assemble the reel: explainer cards intercut with predictor footage."""
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
            else:
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
    parser = argparse.ArgumentParser(description="Build the Road to Finals promo reel")
    parser.add_argument("--footage", help="Path to rtf_raw.mp4 screen-record footage")
    parser.add_argument(
        "--out", default="output/mp4/road_to_finals_reel.mp4", help="Output mp4 path"
    )
    args = parser.parse_args()
    build_road_to_finals_reel(args.out, footage_path=args.footage)


if __name__ == "__main__":
    main()


