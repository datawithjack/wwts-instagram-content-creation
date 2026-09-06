"""Screen-record the live Road to Finals predictor as portrait reel footage.

Drives the production web app with Playwright and records four beats of the
predictor: placing riders for an upcoming event, scoring the prediction, the title
chart redrawing itself from those placings, and the counting matrix being edited.
Output is B-roll intercut with rendered explainer cards by pipeline/rtf_reel_edit.py.

Unlike pipeline/screen_record.py there is NO LOGIN: the predictor takes no account
and no email, which is one of the things the reel is selling. Nothing is written
anywhere -- predictions live in React state and die with the browser.

⚠️ Playwright's video capture is CSS-PIXEL BOUND. `device_scale_factor` is ignored
for video, and a `record_video_size` bigger than the viewport PADS the frame rather
than scaling into it (measured both, 2026-09-06). A wider viewport buys real pixels
but costs the phone layout: past Tailwind's `sm` (640) the rider pool goes to two
columns and the counting matrix becomes a wide table, so everything is sharper and
smaller, which is the wrong trade on a phone-sized reel.

So the frame stays 540x960 and the sharpness is bought back downstream instead: this
writes its mp4 at NATIVE size, and the single upscale to 1080x1920 happens once, in
the trim pass in rtf_reel_edit.py. It used to happen here as well, which meant the
footage was upscaled, encoded, re-encoded and encoded again.

⚠️ The chart's draw animation is the payoff beat and it fires ON MOUNT, 1.5s long.
On a phone the chart sits BELOW a ten-rider matrix, so a human-speed scroll arrives
after it has finished. `_jump_to` snaps there instead, inside the cut between the
score and chart segments, so the animation is still running when the frame lands.

This is screen-capture of the REAL app, NOT an HTML render, so it is inherently
side-effectful (live site, real browser) and verified by running, not unit tests.

Writes a sidecar <out>.markers.json (predict/score/chart/matrix _start and _end) so
pipeline/rtf_reel_edit.py can cut the footage into slices.

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
    SETTLE,
    _force_dark_bg,
    _install_cursor,
    _slow_scroll_into_view,
    _tap,
)

PAGE_URL = "https://www.windsurfworldtourstats.com/road-to-finals"

# The phone frame, kept deliberately -- see the module docstring.
VIDEO_SIZE = {"width": 540, "height": 960}
HD_CONTEXT = {**MOBILE_CONTEXT, "viewport": dict(VIDEO_SIZE)}

# Near-lossless for the raw capture: this file is an intermediate that gets scaled and
# re-encoded downstream, so anything it throws away is gone before the reel is cut.
CRF = "14"
PRESET = "slow"

# Pacing (ms). Every beat here is something to READ, so these run slower than the
# picks reel's.
BEAT = 900            # between rider taps
HOLD_CHART = 5200     # the line-drawing animation is 1.5s; the rest is reading it
HOLD_MATRIX = 3600    # the counting grid, before and after an edit
HOLD_SCORE = 1400     # the tap that turns a prediction into a title race

# Who to place, in predicted finishing order, at the event keyed by its SHORT chip
# label. Names must match the pool's aria-labels. Kept here rather than argparse'd:
# the prediction is an editorial choice about what the reel argues, not a knob.
#
# Men: Koster and Pare are tied at the top on 22,400 (2026-09-06), so the reel's
# claim is "this is level, one event decides it". Pare wins Sylt, Koster is 3rd.
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

# The matrix edit shown at the end: (rider, event chip label, new place).
#
# ⚠️ A cell only offers the places that EXIST at that event -- one more than are
# already filled -- so a four-rider prediction offers 1st to 4th and nothing beyond.
# Asking for "6th" there fails, and Playwright spends 30s retrying before it says so,
# which lands as half a minute of dead footage in the middle of the beat.
#
# Demoting the rider placed 3rd to 4th swaps them with whoever held 4th, so two rows
# move and two totals change: enough to read as "you can edit this".
MATRIX_EDIT = {
    "Men": ("Philip Köster", "Sylt", "4th"),
    "Women": ("Marine Hunter", "Sylt", "4th"),
}


def _select_fleet(page, fleet: str) -> None:
    """Switch the Men/Women dropdown. Men is the default, so this is a no-op there."""
    if fleet == "Men":
        return
    _tap(page, page.get_by_role("button", name="Fleet"))
    page.wait_for_timeout(SETTLE)
    _tap(page, page.get_by_role("option", name=fleet))
    page.wait_for_timeout(1200)


def _jump_to(page, locator) -> None:
    """Snap an element to the top of the frame, with no scroll animation.

    The slow human scroll is right everywhere else and wrong here: it is the only
    way to be looking at the chart while it is still drawing itself.
    """
    handle = locator.element_handle()
    if handle is None:
        return
    page.evaluate(
        """(el) => {
            const r = el.getBoundingClientRect();
            window.scrollTo(0, Math.max(0, window.scrollY + r.top - 90));
        }""",
        handle,
    )


def _pool_button(page, athlete_name: str):
    """The pool row for one rider.

    Matched on the aria-label rather than the visible name: the label carries the tap
    affordance ("... Tap to predict."), which is what distinguishes an unplaced row
    from a placed one.
    """
    exact = page.get_by_role("button", name=f"{athlete_name}. Tap to predict.")
    if exact.count() > 0:
        return exact.first
    surname = athlete_name.split()[-1]
    return page.get_by_role("button", name=f"{surname}. Tap to").first


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


def _edit_matrix(page, fleet: str) -> bool:
    """Enter the matrix's edit mode, change one placing, and submit it.

    Returns False if any control is missing, so a page change costs the reel this
    beat rather than the whole take. The edit is made with `select_option` rather
    than a click: a native <select> opens an OS-level list that the recorder cannot
    film anyway, and the value change is the part worth showing.
    """
    change = page.get_by_role("button", name="Change my prediction")
    if change.count() == 0:
        print("  matrix edit control not found, skipping the edit beat")
        return False
    _tap(page, change)
    page.wait_for_timeout(1000)

    athlete, event_label, place = MATRIX_EDIT[fleet]
    # One cell per (rider, event), so both halves are needed to name it: matching on
    # the surname alone finds the rider's FIRST event, which is not this one.
    surname = athlete.split()[-1]
    selects = page.get_by_role("combobox")
    target = None
    for i in range(selects.count()):
        label = selects.nth(i).get_attribute("aria-label") or ""
        if surname in label and event_label in label:
            target = selects.nth(i)
            break
    if target is None:
        print("  no place control matched, holding on the edit controls only")
        page.wait_for_timeout(HOLD_MATRIX)
        return True

    _slow_scroll_into_view(page, target)
    page.wait_for_timeout(SETTLE)
    try:
        # Short timeout on purpose: the default 30s of retries would be filmed.
        target.select_option(label=place, timeout=5000)
    except Exception as exc:
        print(f"  could not set the place ({exc}); holding on the controls")
        page.wait_for_timeout(HOLD_MATRIX)
        return True
    page.wait_for_timeout(1200)

    submit = page.get_by_role("button", name="Submit")
    if submit.count() > 0:
        _tap(page, submit)
        page.wait_for_timeout(1600)
    return True


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
                **HD_CONTEXT,
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

            # Into the predict step. The landing step is told by the cards, so none
            # of this is filmed.
            _tap(page, page.get_by_role("button", name="Predict what happens next"))
            page.wait_for_timeout(1600)

            # --- Beat 1: place the riders -------------------------------------
            markers["predict_start"] = round(time.monotonic() - t0, 2)
            for event_label, athletes in PREDICTIONS[fleet]:
                chip = page.get_by_role("button", name=event_label).first
                if chip.count() > 0:
                    _slow_scroll_into_view(page, chip)
                    _tap(page, chip)
                    page.wait_for_timeout(SETTLE)
                placed += _place_riders(page, athletes)
            page.wait_for_timeout(SETTLE)
            markers["predict_end"] = round(time.monotonic() - t0, 2)

            # --- Beat 2: score it ---------------------------------------------
            markers["score_start"] = round(time.monotonic() - t0, 2)
            _tap(page, page.get_by_role("button", name="Score my prediction").first)
            page.wait_for_timeout(HOLD_SCORE)
            markers["score_end"] = round(time.monotonic() - t0, 2)

            # --- Beat 3: the chart redraws itself from the prediction ----------
            # Snapped to, not scrolled to: see _jump_to. The cut between the score
            # and chart segments lands on the jump, so the viewer never sees it.
            chart_heading = page.get_by_role("heading", name="HOW THE RACE MOVES")
            chart_heading.wait_for(state="attached", timeout=15000)
            _jump_to(page, chart_heading)
            # Park the pointer in the top-left gutter first. Left where the Score
            # tap put it, the scroll lands it over the plot, and Recharts opens a
            # tooltip that then sits across the chart for the whole hold -- the one
            # beat that has to be unobstructed.
            #
            # ⚠️ `page.mouse`, not the drawn cursor. The fake cursor is a
            # pointer-events:none overlay, so moving it changes what the footage
            # SHOWS and not what the page thinks the pointer is doing.
            page.mouse.move(20, 20)
            page.evaluate("window.__cursor_move && window.__cursor_move(20, 20)")
            page.wait_for_timeout(400)
            markers["chart_start"] = round(time.monotonic() - t0, 2)
            page.wait_for_timeout(HOLD_CHART)
            markers["chart_end"] = round(time.monotonic() - t0, 2)

            # --- Beat 4: the matrix, and editing it ---------------------------
            markers["matrix_start"] = round(time.monotonic() - t0, 2)
            _slow_scroll_into_view(page, page.get_by_role("heading", name="WHAT COUNTS"))
            page.wait_for_timeout(HOLD_MATRIX)
            _edit_matrix(page, fleet)
            page.wait_for_timeout(HOLD_MATRIX)
            markers["matrix_end"] = round(time.monotonic() - t0, 2)

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
                    # No scale filter: the one upscale to 1080x1920 belongs in the
                    # trim pass, so the footage is only ever resampled once.
                    "-c:v", "libx264",
                    "-crf", CRF,
                    "-preset", PRESET,
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
