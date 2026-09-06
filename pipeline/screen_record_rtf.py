"""Screen-record the live Road to Finals predictor as portrait reel footage.

Drives the production web app with Playwright through the predictor's three steps --
"Where it stands" (rankings + season bump chart), "Predict" (placing riders for a
remaining event) and "Outcome" (the recomputed title race) -- while recording.
Output is B-roll intercut with rendered explainer cards by pipeline/reel_edit.py.

Unlike pipeline/screen_record.py there is NO LOGIN: the predictor takes no account
and no email, which is one of the things the reel is selling. Nothing is written
anywhere -- predictions live in React state and die with the browser.

This is screen-capture of the REAL app, NOT an HTML render, so it is inherently
side-effectful (live site, real browser) and verified by running, not unit tests.

Writes a sidecar <out>.markers.json (race_start/end, predict_start/end,
outcome_start/end) so pipeline/reel_edit.py can cut the footage into slices.

Usage:
    python -m pipeline.screen_record_rtf
    python -m pipeline.screen_record_rtf --fleet Women --out output/mp4/rtf_raw.mp4
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time

from playwright.sync_api import sync_playwright

from pipeline.screen_record import (
    CURSOR_JS,
    MOBILE_CONTEXT,
    OUTPUT_SIZE,
    SETTLE,
    VIDEO_SIZE,
    _force_dark_bg,
    _install_cursor,
    _slow_scroll_into_view,
    _tap,
)

PAGE_URL = "https://www.windsurfworldtourstats.com/road-to-finals"

# Pacing (ms). Slower than the picks reel: every beat here is something to READ
# (a ranking, a chart, a matrix), not a tap to watch.
BEAT = 900           # between rider taps
HOLD_RANKINGS = 3200  # linger on the current world rankings
HOLD_CHART = 3400    # linger on the season-so-far bump chart
HOLD_EVENTS = 2800   # linger on the events still to come
HOLD_OUTCOME = 4200  # linger on the recomputed title race

# Who to place, in predicted finishing order, for the event named. Names must match
# the pool's aria-labels exactly. Kept here rather than argparse'd: the prediction is
# an editorial choice about what the reel argues, not a runtime knob.
#
# Men: Koster and Pare are tied at the top on 22,400 (2026-09-06), so the reel's
# claim is "this is level -- one event decides it". Pare wins Sylt, Koster is 3rd.
# The event key is the chip's SHORT label as the rail renders it (shortLabel()),
# not the feed's full name -- "Sylt Germany", not "2026 Sylt, Germany Grand Slam *****".
PREDICTIONS = {
    "Men": [
        (
            "Sylt",
            ["Marc Paré Rico", "Marcilio Browne", "Philip Köster", "Bernd Roediger"],
        ),
    ],
    "Women": [
        (
            "Sylt",
            ["Maria Behrens", "Lina Erpenstein", "Marine Hunter", "Sol Degrieck"],
        ),
    ],
}


def _select_fleet(page, fleet: str) -> None:
    """Switch the Men/Women dropdown. Men is the default, so this is a no-op there."""
    if fleet == "Men":
        return
    _tap(page, page.get_by_role("button", name="Fleet"))
    page.wait_for_timeout(SETTLE)
    _tap(page, page.get_by_role("option", name=fleet))
    page.wait_for_timeout(1200)


def _pool_button(page, athlete_name: str):
    """The pool row for one rider.

    Matched on the aria-label prefix rather than the visible name: the label carries
    the tap affordance ("... Tap to predict."), and it flips to "Tap to remove" once
    placed, so a prefix match is the stable half. Accents are matched loosely because
    the source-of-truth spelling ("Koster" vs "KOster") is easy to get wrong here.
    """
    exact = page.get_by_role("button", name=f"{athlete_name}. Tap to predict.")
    if exact.count() > 0:
        return exact.first
    surname = athlete_name.split()[-1]
    return page.get_by_role("button", name=f"{surname}. Tap to").first


def _open_event(page, event_name: str) -> None:
    """Select one event in the predict step's event rail."""
    chip = page.get_by_role("button", name=event_name).first
    if chip.count() == 0:
        return
    _slow_scroll_into_view(page, chip)
    _tap(page, chip)
    page.wait_for_timeout(SETTLE)


def _place_riders(page, athletes: list[str]) -> list[str]:
    """Tap each rider in turn; each tap takes the next finishing place."""
    placed = []
    for name in athletes:
        button = _pool_button(page, name)
        try:
            button.wait_for(state="visible", timeout=8000)
        except Exception:
            print(f"  pool row not found, skipping: {name}")
            continue
        _slow_scroll_into_view(page, button)
        _tap(page, button)
        placed.append(name)
        page.wait_for_timeout(BEAT)
    return placed


def record_rtf_flow(fleet: str, out_path: str) -> str:
    """Record the Road to Finals flow to a portrait mp4. Returns the path."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    video_dir = tempfile.mkdtemp()

    placed: list[str] = []
    markers: dict = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(
                record_video_dir=video_dir,
                record_video_size=VIDEO_SIZE,
                **MOBILE_CONTEXT,
            )
            page = context.new_page()
            # Recording starts with the context; mark times relative to here so the
            # offsets line up with the recorded timeline.
            t0 = time.monotonic()
            page.add_init_script(CURSOR_JS)

            page.goto(PAGE_URL, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2500)
            _force_dark_bg(page)
            _install_cursor(page)
            _select_fleet(page, fleet)

            # --- Step 1: where it stands -------------------------------------
            markers["race_start"] = round(time.monotonic() - t0, 2)
            page.wait_for_timeout(HOLD_RANKINGS)
            _slow_scroll_into_view(
                page, page.get_by_role("heading", name="THE SEASON SO FAR")
            )
            page.wait_for_timeout(HOLD_CHART)
            _slow_scroll_into_view(
                page, page.get_by_role("heading", name="STILL TO COME")
            )
            page.wait_for_timeout(HOLD_EVENTS)
            markers["race_end"] = round(time.monotonic() - t0, 2)

            # --- Step 2: predict ---------------------------------------------
            markers["predict_start"] = round(time.monotonic() - t0, 2)
            _tap(page, page.get_by_role("button", name="Predict what happens next"))
            page.wait_for_timeout(1600)

            for event_name, athletes in PREDICTIONS[fleet]:
                _open_event(page, event_name)
                placed += _place_riders(page, athletes)
            page.wait_for_timeout(SETTLE)
            markers["predict_end"] = round(time.monotonic() - t0, 2)

            # --- Step 3: outcome ---------------------------------------------
            markers["outcome_start"] = round(time.monotonic() - t0, 2)
            _tap(page, page.get_by_role("button", name="Score my prediction").first)
            page.wait_for_timeout(2200)
            _slow_scroll_into_view(
                page, page.get_by_role("heading", name="WHAT COUNTS")
            )
            page.wait_for_timeout(HOLD_OUTCOME)
            _slow_scroll_into_view(
                page, page.get_by_role("heading", name="HOW THE RACE MOVES")
            )
            page.wait_for_timeout(HOLD_OUTCOME)
            markers["outcome_end"] = round(time.monotonic() - t0, 2)

            page.close()
            context.close()
            browser.close()

        videos = [f for f in os.listdir(video_dir) if f.endswith(".webm")]
        if not videos:
            raise RuntimeError("Playwright did not produce a video file")
        recorded = os.path.join(video_dir, videos[0])

        if out_path.endswith(".mp4") and shutil.which("ffmpeg"):
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", recorded,
                    "-vf", f"scale={OUTPUT_SIZE}:flags=lanczos",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    out_path,
                ],
                capture_output=True,
                check=True,
            )
        else:
            if out_path.endswith(".mp4"):
                out_path = out_path.rsplit(".", 1)[0] + ".webm"
            shutil.copy2(recorded, out_path)
    finally:
        shutil.rmtree(video_dir, ignore_errors=True)

    markers_path = out_path + ".markers.json"
    with open(markers_path, "w", encoding="utf-8") as f:
        json.dump(markers, f, indent=2)

    print("Placed:", ", ".join(placed) if placed else "(none)")
    print("Markers:", markers)
    print("Saved:", out_path)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record the Road to Finals predictor to video"
    )
    parser.add_argument("--fleet", default="Men", choices=["Men", "Women"])
    parser.add_argument("--out", default="output/mp4/rtf_raw.mp4", help="Output mp4 path")
    args = parser.parse_args()
    record_rtf_flow(args.fleet, args.out)


if __name__ == "__main__":
    main()
