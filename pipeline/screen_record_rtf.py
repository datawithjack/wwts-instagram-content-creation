"""Screen-record the live Road to Finals predictor as portrait reel footage.

Drives the production web app with Playwright and records four beats of the
predictor: placing riders across the events still to sail, scoring the prediction,
the title chart redrawing itself from those placings, and the counting matrix being
edited.
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
The outcome step now LEADS with the chart on a phone (app commit dd33181), so the
Score tap and the chart reveal are the same moment: the chart is already in frame at
scroll 0 and the recorder holds still while it draws. It used to sit below a
ten-rider matrix and had to be snapped to mid-cut; that snap is gone, and so is the
`_jump_to` helper it needed. Do not reintroduce a scroll here -- any scroll during
the 1.5s is a scroll across the one shot the reel exists for.

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
import re
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
# 16 placements across four events, so the gap between taps is half what it was when
# the reel predicted one: the predict beat is a montage, and at 900 it ran to 40s of
# raw footage that no playback speed rescues.
BEAT = 450            # between rider taps
HOLD_CHART = 5200     # the line-drawing animation is 1.5s; the rest is reading it
HOLD_MATRIX = 3600    # the counting grid, before and after an edit
HOLD_SCORE = 1400     # the finished order held before the tap that scores it

# Who to place, in predicted finishing order: one list per event, in calendar order.
# An EMPTY list walks past that event without predicting it. Names must match the
# pool's aria-labels. Kept here rather than argparse'd: the prediction is an
# editorial choice about what the reel argues, not a knob.
#
# ⚠️ No event is NAMED here, only its position in the calendar. The event rail the
# recorder used to tap is gone from the phone layout: the first event is whichever
# the page opens on (the first still to sail), and the way forward is the bottom
# bar's "Predict {next} next" button. So this follows the calendar on its own and
# runs out gracefully when there are fewer events left than entries. The order as of
# 2026-09-07 is Wissant, Sylt, Tiree, Aloha, Chile -- Tiree is the skipped one.
#
# The prediction is deliberately ROGUE. A sensible one barely moves the table, which
# makes for a dull Score tap; this one has an outsider win the three 5-stars, so the
# board tears itself up and a name from mid-table ends the season on top. It is a
# predictor, not a forecast, and the reel is selling "go and play with it".
PREDICTIONS = {
    "Men": [
        # Wissant: the plausible opener, so there is a baseline to wreck.
        ["Marc Paré Rico", "Marcilio Browne", "Philip Köster", "Bernd Roediger"],
        ["Lennart Neubauer", "Takuma Sugi", "Morgan Noireaux", "Philip Köster"],
        [],  # Tiree, left unpredicted
        ["Lennart Neubauer", "Morgan Noireaux", "Marcilio Browne", "Marc Paré Rico"],
        ["Lennart Neubauer", "Antoine Martin", "Takuma Sugi", "Bernd Roediger"],
    ],
    "Women": [
        ["Maria Behrens", "Lina Erpenstein", "Marine Hunter", "Sol Degrieck"],
        ["Sarah-Quita Offringa", "Pauline Katz", "Lina Erpenstein", "Maria Behrens"],
        [],  # Tiree, left unpredicted
        ["Sarah-Quita Offringa", "Marine Hunter", "Sol Degrieck", "Lina Erpenstein"],
        ["Sarah-Quita Offringa", "Alexia Kiefer Quintana", "Pauline Katz", "Maria Behrens"],
    ],
}

# The matrix edit shown at the end demotes the winner of the LAST event predicted to
# this place. Both the rider and the event are taken from what actually got placed,
# so the edit cannot drift out of step with PREDICTIONS.
#
# ⚠️ A cell only offers the places that EXIST at that event -- one more than are
# already filled -- so a four-rider prediction offers 1st to 4th and nothing beyond.
# Asking for "6th" there fails, and Playwright spends 30s retrying before it says so,
# which lands as half a minute of dead footage in the middle of the beat. (The app
# has a fix for this on feat/sparse-prediction-places, unmerged as of 2026-09-07 --
# once it ships, any of the ten places is offered and this can open up.)
MATRIX_DEMOTE_TO = "4th"


def _select_fleet(page, fleet: str) -> None:
    """Switch the Men/Women dropdown. Men is the default, so this is a no-op there."""
    if fleet == "Men":
        return
    _tap(page, page.get_by_role("button", name="Fleet"))
    page.wait_for_timeout(SETTLE)
    _tap(page, page.get_by_role("option", name=fleet))
    page.wait_for_timeout(1200)


def _current_event(page) -> str:
    """The event being predicted, read off the phone's bottom bar.

    The bar's aria-label is "Predicting {event}, {n} of 10 placed. Choose a
    different event." -- the only place the page names the event now that the chip
    rail is gone. Returned so the matrix beat can find the right column without the
    recorder hardcoding a name that the calendar moves past.
    """
    match = re.compile(r"^Predicting (.+?), \d+ of \d+ placed")
    buttons = page.get_by_role("button")
    for i in range(buttons.count()):
        label = buttons.nth(i).get_attribute("aria-label") or ""
        found = match.match(label)
        if found:
            return found.group(1)
    return ""


def _next_event(page) -> bool:
    """Move on to the next event via the bottom bar. False if there is no next one.

    The bar's way-forward button reads "Pick Sylt" but is labelled "Predict {full
    event name} next." -- matched on the label because the visible text is a two-word
    shortening that collides with nothing useful. The trailing period is what keeps
    this off the landing step's "Predict what happens next".
    """
    button = page.get_by_role("button", name=re.compile(r"^Predict .+ next\.$"))
    if button.count() == 0:
        return False
    _slow_scroll_into_view(page, button.last)
    _tap(page, button.last)
    page.wait_for_timeout(SETTLE)
    return True


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


def _edit_matrix(page, athlete: str, place: str, event_label: str) -> bool:
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

    # One cell per (rider, event), so both halves are needed to name it: matching on
    # the surname alone finds the rider's FIRST event, which is not this one. The
    # labels read "{Name} at {Event}, predicted 3rd. Change place." -- matched on the
    # event's first word only, because the bottom bar and the cell are two different
    # shortenings of the same event name and nothing guarantees they stay identical.
    surname = athlete.split()[-1]
    event_key = event_label.split()[0] if event_label else ""
    selects = page.get_by_role("combobox")
    target = None
    for i in range(selects.count()):
        label = selects.nth(i).get_attribute("aria-label") or ""
        if surname in label and event_key in label:
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
            # of this is filmed. `.last`: the phone's pinned bottom bar carries its
            # own copy of this button and it is the one on screen.
            _tap(page, page.get_by_role("button", name="Predict what happens next").last)
            page.wait_for_timeout(1600)

            # --- Beat 1: place the riders, one event at a time -----------------
            # No event is chosen by name: the page opens on the first one still to
            # sail and the bottom bar walks forward from there.
            markers["predict_start"] = round(time.monotonic() - t0, 2)
            event_label, last_winner = "", ""
            for i, athletes in enumerate(PREDICTIONS[fleet]):
                if i and not _next_event(page):
                    print("  no further event to predict, stopping at", i)
                    break
                here = _current_event(page)
                if not athletes:
                    # Walked past on the way to the next one. Nothing is placed, so
                    # this event keeps whatever the page projects for it.
                    print("Skipping:", here)
                    continue
                print("Predicting:", here or "(event not named on the page)")
                event_label = here
                placed += _place_riders(page, athletes)
                last_winner = athletes[0]
            page.wait_for_timeout(SETTLE)
            markers["predict_end"] = round(time.monotonic() - t0, 2)

            # --- Beat 2: score it ---------------------------------------------
            # "Score" in the phone's bottom bar (it read "Score my prediction" before
            # the bar existed). exact=True or it also matches the bar's sibling
            # controls; `.last` for the same reason as the button above.
            markers["score_start"] = round(time.monotonic() - t0, 2)
            page.wait_for_timeout(HOLD_SCORE)
            _tap(page, page.get_by_role("button", name="Score", exact=True).last)

            # --- Beat 3: the chart redraws itself from the prediction ----------
            # The outcome step leads with the chart, so it is already in frame and
            # already drawing: hold still and film it. The cut between the score and
            # chart segments is the tap itself.
            #
            # Park the real pointer in the top-left gutter. Left where the Score tap
            # put it, it sits over the plot and Recharts opens a tooltip that then
            # covers the chart for the whole hold -- the one beat that has to be
            # unobstructed.
            #
            # ⚠️ `page.mouse`, not the drawn cursor. The fake cursor is a
            # pointer-events:none overlay, so moving it changes what the footage
            # SHOWS and not what the page thinks the pointer is doing.
            page.mouse.move(20, 20)
            page.evaluate("window.__cursor_move && window.__cursor_move(20, 20)")
            # The two markers meet ON the click, so the cut lands there and the whole
            # 1.5s draw falls inside the chart segment rather than being spent on the
            # tail of the score one.
            markers["score_end"] = round(time.monotonic() - t0, 2)
            markers["chart_start"] = round(time.monotonic() - t0, 2)
            page.wait_for_timeout(HOLD_CHART)
            markers["chart_end"] = round(time.monotonic() - t0, 2)

            # --- Beat 4: the matrix, and editing it ---------------------------
            markers["matrix_start"] = round(time.monotonic() - t0, 2)
            _slow_scroll_into_view(page, page.get_by_role("heading", name="WHAT COUNTS"))
            page.wait_for_timeout(HOLD_MATRIX)
            _edit_matrix(page, last_winner, MATRIX_DEMOTE_TO, event_label)
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
