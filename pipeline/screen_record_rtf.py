"""Screen-record the live Road to Finals predictor as portrait reel footage.

Drives the production web app with Playwright and records four beats: finding the
predictor from the site's home page via the menu, placing riders across the events
still to sail, scoring the prediction, and the title chart redrawing itself from
those placings. Output is B-roll intercut with rendered explainer cards by
pipeline/rtf_reel_edit.py.

The counting matrix used to get a fifth beat, entering edit mode and changing a
placing. Cut 2026-09-07: it was the longest segment in the reel and the least of
it, and the matrix is on screen under the chart anyway.

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

⚠️ Two separate things put a beat's first frame in the wrong place, and both had to
be fixed before the cuts landed where the markers say:

1. A step swap or a client-side route change KEEPS the previous scroll position, so
   a beat can open halfway down a list with its heading off frame. `_scroll_to_top`
   guards the three places it matters: arriving at the predictor, entering the
   predict step, and leaving it -- the last one because the outcome step inherits
   the pool's scroll, which would put the chart below the frame at the exact moment
   it draws.
2. The marker clock and the video clock are NOT the same clock. See `_align_markers`.

Writes a sidecar <out>.markers.json (nav/predict/score/chart _start and _end) so
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
    SCROLL_PAUSE,
    SCROLL_STEPS,
    SETTLE,
    _force_dark_bg,
    _install_cursor,
    _slow_scroll_into_view,
    _tap,
)

# The shared cursor in pipeline/screen_record.py is a translucent touch circle. This
# reel wants a mouse pointer instead, so the arrow tip lands ON the thing being
# clicked rather than a disc sitting over it and hiding the label underneath.
#
# Added as a SECOND init script that wraps `__cursor_install` rather than editing the
# shared one: the picks reel is already published with the circle, and this should
# not silently restyle it. Both scripts run on every document, in the order added, so
# the wrap survives the route change from the home page into the predictor.
POINTER_CURSOR_JS = r"""
(() => {
  const install = window.__cursor_install;
  window.__cursor_install = () => {
    install();
    const c = document.getElementById('__fake_cursor');
    if (!c || c.dataset.pointer) return;
    c.dataset.pointer = '1';
    const s = document.createElement('style');
    s.textContent = `
      #__fake_cursor{width:28px;height:36px;margin:0;border:none;border-radius:0;
        background:transparent;box-shadow:none;
        filter:drop-shadow(0 2px 5px rgba(0,0,0,0.6));}
      #__fake_cursor.__press{background:transparent;}
      /* Ripple at the TIP, which is the top-left corner for an arrow, not the
         middle of its box the way it was for the circle. */
      #__fake_cursor.__tap::after{left:2px;top:2px;width:34px;height:34px;
        margin:-17px 0 0 -17px;}
    `;
    document.head.appendChild(s);
    c.innerHTML =
      '<svg viewBox="0 0 24 32" width="28" height="36" style="display:block">' +
      '<path d="M3 2 L3 25 L9.5 19 L13.5 28.5 L17.5 26.5 L13.5 17.5 L21 17.5 Z" ' +
      'fill="#ffffff" stroke="rgba(15,23,42,0.9)" stroke-width="1.6" ' +
      'stroke-linejoin="round"/></svg>';
  };
})();
"""

HOME_URL = "https://www.windsurfworldtourstats.com/"
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
BEAT = 800            # between rider taps; every one of them is a name to read
HOLD_CHART = 5200     # the line-drawing animation is 1.5s; the rest is reading it
HOLD_SCORE = 1400     # the finished order held before the tap that scores it
HOLD_HOME = 1500      # the home page, before the menu opens
HOLD_MENU = 1400      # the open menu, so ROAD TO FINALS is read before it is tapped
HOLD_ARRIVE = 3000    # the predictor's landing step, having just arrived
HOLD_STANDINGS = 3200  # reading the standings before tapping on into Predict

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
# Two events, the two 5-stars, top five each. The placings are FEASIBLE: the reel is
# arguing "this is close and it swings", which needs a prediction a viewer recognises
# as a real possibility. An outsider sweeping the season is funnier for about three
# seconds and then it is just noise, and the Score tap stops meaning anything.
#
# Koster takes Sylt and goes clear; Pare takes Aloha and claws it back. The two of
# them are level on 22,400 today, so both halves are arguable.
PREDICTIONS = {
    "Men": [
        [],  # Wissant, walked past
        ["Philip Köster", "Marc Paré Rico", "Marcilio Browne",
         "Bernd Roediger", "Antoine Martin"],
        [],  # Tiree, walked past
        ["Marc Paré Rico", "Marcilio Browne", "Philip Köster",
         "Morgan Noireaux", "Bernd Roediger"],
    ],
    "Women": [
        [],  # Wissant, walked past
        ["Lina Erpenstein", "Maria Behrens", "Sarah-Quita Offringa",
         "Marine Hunter", "Sol Degrieck"],
        [],  # Tiree, walked past
        ["Sarah-Quita Offringa", "Marine Hunter", "Lina Erpenstein",
         "Maria Behrens", "Pauline Katz"],
    ],
}

def _align_markers(markers: dict, video_path: str) -> dict:
    """Slide the marker timeline onto the video's, and return the corrected markers.

    ⚠️ Playwright's video does NOT start at t0. Recording begins when the page first
    has something to paint, so the page load and settle at the top of the flow are
    missing from the file and every marker sits roughly two seconds AHEAD of the
    frame it names. Measured 2026-09-07: a 76.35s marker timeline in a 74.44s file,
    which put the predict segment's first frame on a tap two beats later.

    The recorder closes the browser immediately after the last marker, so nothing is
    recorded past it: the gap between the file's duration and that marker IS the
    offset. Self-calibrating, so it stays right if the load time changes.
    """
    if not markers or not shutil.which("ffprobe"):
        return markers
    last = max(markers.values())
    try:
        probed = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", video_path],
            capture_output=True, text=True, check=True,
        )
        duration = float(probed.stdout.strip())
    except Exception as exc:
        print(f"  could not measure the footage ({exc}); markers left unaligned")
        return markers

    offset = last - duration
    if offset <= 0.05:
        return markers
    print(f"Video is {duration:.2f}s to the markers' {last:.2f}s; "
          f"sliding the timeline back {offset:.2f}s.")
    return {k: round(max(0.0, v - offset), 2) for k, v in markers.items()}


def _select_fleet(page, fleet: str) -> None:
    """Switch the Men/Women dropdown. Men is the default, so this is a no-op there."""
    if fleet == "Men":
        return
    _tap(page, page.get_by_role("button", name="Fleet"))
    page.wait_for_timeout(SETTLE)
    _tap(page, page.get_by_role("option", name=fleet))
    page.wait_for_timeout(1200)


def _scroll_to_top(page) -> None:
    """Human-speed scroll back to the top of the page, if it is not already there.

    Used before a beat that has to OPEN on a header rather than halfway down a list.
    A route change or a step swap keeps whatever scroll position the last one had,
    which lands the next segment mid-page with its heading off frame.
    """
    start = page.evaluate("window.scrollY")
    if start < 8:
        return
    for i in range(1, SCROLL_STEPS + 1):
        page.evaluate("(y) => window.scrollTo(0, y)", start * (1 - i / SCROLL_STEPS))
        page.wait_for_timeout(SCROLL_PAUSE)


def _navigate_from_home(page) -> None:
    """Arrive at the predictor the way a viewer would: home page, menu, ROAD TO FINALS.

    This is the beat that answers "where do I even find this", so it is filmed rather
    than skipped over with a direct goto. The menu is a real route change, so the
    predictor mounts fresh underneath it.
    """
    page.wait_for_timeout(HOLD_HOME)
    _tap(page, page.get_by_role("button", name="Open navigation menu").first)
    page.wait_for_timeout(SETTLE + HOLD_MENU)
    _tap(page, page.get_by_role("link", name="ROAD TO FINALS").first)
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    # A client-side route change carries the old scroll position across, so the
    # predictor can mount halfway down itself. Land on its heading, not its middle.
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(HOLD_ARRIVE)


def _current_event(page) -> str:
    """The event being predicted, read off the phone's bottom bar.

    The bar's aria-label is "Predicting {event}, {n} of 10 placed. Choose a
    different event." -- the only place the page names the event now that the chip
    rail is gone. Printed as the take runs, so a calendar that has moved on shows up
    in the log rather than in the footage.
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
            page.add_init_script(POINTER_CURSOR_JS)  # must come after CURSOR_JS

            page.goto(HOME_URL, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2500)
            _force_dark_bg(page)
            _install_cursor(page)

            # --- Beat 0: how you get there ------------------------------------
            # Home page -> hamburger -> ROAD TO FINALS. Filmed rather than skipped
            # with a direct goto: "where do I find this" is a real question and the
            # answer is three taps.
            markers["nav_start"] = round(time.monotonic() - t0, 2)
            _navigate_from_home(page)
            _force_dark_bg(page)
            _select_fleet(page, fleet)

            # Into the predict step, and this tap is INSIDE the nav beat on purpose.
            # It used to fall in the cut between nav and predict, so the reel went
            # from "where it stands" straight to a list of riders with no visible
            # reason: the viewer never saw the button that moved them on. `.last`:
            # the phone's pinned bottom bar carries its own copy of this button and
            # it is the one on screen.
            _slow_scroll_into_view(
                page, page.get_by_role("button", name="Predict what happens next").last
            )
            page.wait_for_timeout(HOLD_STANDINGS)
            _tap(page, page.get_by_role("button", name="Predict what happens next").last)
            page.wait_for_timeout(1600)
            markers["nav_end"] = round(time.monotonic() - t0, 2)

            # The step swap keeps the landing step's scroll, so the predict beat can
            # open halfway down the rider pool with its heading off frame.
            _scroll_to_top(page)

            # --- Beat 1: place the riders, one event at a time -----------------
            # No event is chosen by name: the page opens on the first one still to
            # sail and the bottom bar walks forward from there.
            markers["predict_start"] = round(time.monotonic() - t0, 2)
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
                placed += _place_riders(page, athletes)
            page.wait_for_timeout(SETTLE)
            markers["predict_end"] = round(time.monotonic() - t0, 2)

            # --- Beat 2: score it ---------------------------------------------
            # "Score" in the phone's bottom bar (it read "Score my prediction" before
            # the bar existed). exact=True or it also matches the bar's sibling
            # controls; `.last` for the same reason as the button above.
            # Back to the top first. Five taps leave the pool scrolled down, and the
            # outcome step inherits that scroll -- which would put the chart, the one
            # shot the reel is for, off the bottom of the frame when it mounts.
            _scroll_to_top(page)
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

    markers = _align_markers(markers, out_path)

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
