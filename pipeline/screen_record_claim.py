"""Screen-record the live profile-claim flows as portrait reel footage (#26, #27).

Three takes, each a separate file, cut together by pipeline/claim_reel_edit.py:

    pro          signed in: the profile's "Are you a pro rider?" form, then the Pros board
    coach-board  SIGNED OUT: the Coaches board, its coach's links boxed
    coach-form   signed in: the profile's "Run clinics? Get listed" form

The coach reel needs two takes because one account cannot show both halves: the
claim link is hidden from anyone already listed, and the board's only coach is the
owner's own account. The board is filmed signed out, so it reads as a player sees it
with no "(you)" highlight. ⚠️ `coach-form` needs the account's coach flag OFF and
`coach-board` needs it ON.

NOTHING IS SUBMITTED. Each form is opened, its fields pointed at, and closed with
Cancel. Nothing is typed either: the pro search box is highlighted, not searched, so
the footage never reads as a particular rider claiming a profile.

Reuses the Road to Finals recorder's arrow pointer, text-aimed taps and marker
alignment. Verified by running, not unit tests: it drives the production site.

Usage:
    python -m pipeline.screen_record_claim --flow pro
    python -m pipeline.screen_record_claim --flow coach-board
    python -m pipeline.screen_record_claim --flow coach-form
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
    BASE_URL,
    CURSOR_JS,
    SETTLE,
    _install_cursor,
    _login,
    _slow_scroll_into_view,
    _tap,
)
from pipeline.screen_record_rtf import (
    CRF,
    HD_CONTEXT,
    POINTER_CURSOR_JS,
    PRESET,
    VIDEO_SIZE,
    _align_markers,
    _scroll_to_top,
    _tap_text,
)

LEADERBOARD_PATH = "/fantasy/leaderboard"

# Pacing (ms).
HOLD_ARRIVE = 1800   # the board as it opens, before the filter is touched
HOLD_BOARD = 3200    # the filtered board, long enough to read who is on it
HOLD_FIELD = 1500    # each highlighted form field
HOLD_FORM = 1800     # the open form, read before the pointer moves into it
HOLD_BOX = 2600      # a highlight box, up

FLOWS = ("pro", "coach-board", "coach-form")

# The profile prints the signed-in account's email under its name. Hidden before it
# paints: a MutationObserver callback runs ahead of the next frame, so it never shows.
HIDE_TEXT_JS = r"""
(() => {
  const target = %s;
  const hide = (node) => {
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      if (walker.currentNode.nodeValue.trim() === target) {
        walker.currentNode.parentElement.style.visibility = 'hidden';
      }
    }
  };
  new MutationObserver((records) => records.forEach((r) => r.addedNodes.forEach((n) => {
    if (n.nodeType === 1) hide(n);
    else if (n.nodeType === 3 && n.parentElement) hide(n.parentElement);
  }))).observe(document, {childList: true, subtree: true});
})();
"""


def _mark(markers: dict, key: str, t0: float) -> None:
    markers[key] = round(time.monotonic() - t0, 2)


def _choose_players(page, option: str) -> None:
    """Switch the board's Everyone / Pros / Coaches dropdown.

    A dropdown on the phone layout, not pills. The button's accessible name is
    "Player filter" whatever it currently shows.
    """
    _tap(page, page.get_by_role("button", name="Player filter").first)
    page.wait_for_timeout(SETTLE + 400)
    _tap_text(page, page.get_by_role("option", name=option).first)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass


def _highlight(page, locator) -> None:
    """Point at a form field and focus it, so its border lights. Nothing is typed."""
    locator.wait_for(state="visible", timeout=10000)
    _tap(page, locator)
    page.wait_for_timeout(HOLD_FIELD)


def _box(page, locator, label: str = "") -> None:
    """Draw a highlight box around an element, with an optional label beneath it.
    Fixed to the viewport, so do not scroll while it is up."""
    locator.wait_for(state="visible", timeout=10000)
    page.evaluate(
        """([el, label]) => {
            const r = el.getBoundingClientRect(), pad = 8;
            const b = document.createElement('div');
            b.id = '__highlight_box';
            Object.assign(b.style, {
                position: 'fixed', left: (r.left - pad) + 'px', top: (r.top - pad) + 'px',
                width: (r.width + pad * 2) + 'px', height: (r.height + pad * 2) + 'px',
                border: '3px solid #facc15', borderRadius: '10px',
                boxShadow: '0 0 18px rgba(250, 204, 21, 0.55)',
                zIndex: 2147483646, pointerEvents: 'none',
                opacity: 0, transform: 'scale(1.35)',
                transition: 'opacity 0.35s ease, transform 0.35s cubic-bezier(.22,.61,.36,1)',
            });
            document.body.appendChild(b);
            if (label) {
                const t = document.createElement('div');
                t.id = '__highlight_label';
                t.textContent = label;
                Object.assign(t.style, {
                    // Under the box, right edges aligned: beside it, it covered the score.
                    position: 'fixed', right: (window.innerWidth - r.right - pad) + 'px',
                    top: (r.bottom + pad + 10) + 'px',
                    padding: '6px 12px', borderRadius: '8px',
                    background: '#facc15', color: '#0f172a',
                    font: '700 15px Inter, system-ui, sans-serif', whiteSpace: 'nowrap',
                    zIndex: 2147483646, pointerEvents: 'none',
                    opacity: 0, transition: 'opacity 0.35s ease 0.2s',
                });
                document.body.appendChild(t);
                requestAnimationFrame(() => requestAnimationFrame(() => { t.style.opacity = 1; }));
            }
            requestAnimationFrame(() => requestAnimationFrame(() => {
                b.style.opacity = 1; b.style.transform = 'scale(1)';
            }));
        }""",
        [locator.element_handle(), label],
    )


def _unbox(page) -> None:
    page.evaluate("""['__highlight_box', '__highlight_label']
        .forEach((id) => document.getElementById(id)?.remove())""")


def _cancel(page) -> None:
    _tap(page, page.get_by_role("button", name="Cancel").last)
    page.wait_for_timeout(900)


def _open_profile(page) -> None:
    """Menu, then the profile: a ring avatar labelled "{name}, profile ... complete".

    An incomplete profile opens a checklist first, whose "Complete profile" button
    opens the editor; a complete one opens the editor directly.
    """
    _tap(page, page.get_by_role("button", name="Open navigation menu").first)
    page.wait_for_timeout(SETTLE + 500)
    trigger = page.get_by_role("button", name=re.compile(r", profile .*complete$")).last
    _tap(page, trigger)
    page.wait_for_timeout(SETTLE)
    complete = page.get_by_role("button", name="Complete profile")
    if complete.count():
        page.wait_for_timeout(700)
        _tap_text(page, complete.first)
    page.wait_for_timeout(SETTLE + HOLD_FORM)


def _flow_pro(page, markers: dict, t0: float) -> None:
    # Step 1: claim, from the profile.
    _mark(markers, "profile_start", t0)
    page.wait_for_timeout(1000)
    _open_profile(page)
    _tap_text(page, page.get_by_text("Are you a pro rider? Claim your athlete profile").first)
    # The form prefills Instagram from the recording account's profile, which is the
    # brand's own handle: on camera it reads as the brand claiming to be a rider.
    page.locator('input[placeholder^="Instagram handle"]').fill("")
    page.wait_for_timeout(SETTLE + HOLD_FORM)
    _highlight(page, page.locator("#rider-claim-search"))
    page.wait_for_timeout(600)
    _cancel(page)
    _mark(markers, "profile_end", t0)

    # Step 2: the board it gets you onto. The route change happens between segments.
    page.goto(BASE_URL + LEADERBOARD_PATH, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)
    _install_cursor(page)
    _mark(markers, "board_start", t0)
    page.wait_for_timeout(HOLD_ARRIVE)
    # The main board: a verified rider's badge, boxed.
    badge = page.locator('button[title="Verified Rider"]').first
    _slow_scroll_into_view(page, badge)
    page.wait_for_timeout(500)
    _box(page, badge)
    page.wait_for_timeout(HOLD_BOX)
    _unbox(page)
    _scroll_to_top(page)
    # The Pros board: a rider's socials, boxed.
    _choose_players(page, "Pros")
    page.wait_for_timeout(1500)
    _box(page, page.locator('a[href*="instagram.com"]').first)
    page.wait_for_timeout(HOLD_BOX)
    _unbox(page)
    page.wait_for_timeout(600)
    _mark(markers, "board_end", t0)


def _flow_coach_board(page, markers: dict, t0: float) -> None:
    _mark(markers, "board_start", t0)
    page.wait_for_timeout(HOLD_ARRIVE)
    # The main board: a coach's badge, boxed.
    _box(page, page.locator('span[title="Coach"]').first)
    page.wait_for_timeout(HOLD_BOX)
    _unbox(page)
    # The Coaches board: the website link, boxed and named.
    _choose_players(page, "Coaches")
    page.wait_for_timeout(1500)
    _box(page, page.locator('a[title="Website"]').first, "Link to your website")
    page.wait_for_timeout(HOLD_BOX)
    _unbox(page)
    page.wait_for_timeout(600)
    _mark(markers, "board_end", t0)


def _flow_coach_form(page, markers: dict, t0: float) -> None:
    _mark(markers, "profile_start", t0)
    page.wait_for_timeout(1000)
    _open_profile(page)
    _tap_text(page, page.get_by_text("Run clinics? Get listed on the Coaches board").first)
    # Prefilled from the recording account's own links, the brand's. Cleared so the
    # fields show their placeholders instead.
    for field in ("#coach-claim-website", "#coach-claim-instagram"):
        page.locator(field).fill("")
    page.wait_for_timeout(SETTLE + HOLD_FORM)
    for field in ("#coach-claim-website", "#coach-claim-instagram"):
        _highlight(page, page.locator(field))
    _cancel(page)
    _mark(markers, "profile_end", t0)


def record_claim_flow(flow: str, out_path: str) -> str:
    """Record one claim take to a portrait mp4 with a markers sidecar. Returns the path."""
    if flow not in FLOWS:
        raise ValueError(f"flow must be one of {FLOWS}")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    video_dir = tempfile.mkdtemp()
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
            t0 = time.monotonic()
            page.add_init_script(CURSOR_JS)
            page.add_init_script(POINTER_CURSOR_JS)  # must come after CURSOR_JS

            if flow != "coach-board":
                page.add_init_script(HIDE_TEXT_JS % json.dumps(os.environ["FANTASY_EMAIL"]))
                _login(page, os.environ["FANTASY_EMAIL"], os.environ["FANTASY_PASSWORD"],
                       LEADERBOARD_PATH)
            start = LEADERBOARD_PATH if flow == "coach-board" else "/fantasy"
            page.goto(BASE_URL + start, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)
            _install_cursor(page)

            {"pro": _flow_pro, "coach-board": _flow_coach_board,
             "coach-form": _flow_coach_form}[flow](page, markers, t0)

            page.close()
            context.close()
            browser.close()

        videos = [f for f in os.listdir(video_dir) if f.endswith(".webm")]
        if not videos:
            raise RuntimeError("Playwright did not produce a video file")
        subprocess.run(
            ["ffmpeg", "-y", "-i", os.path.join(video_dir, videos[0]),
             "-c:v", "libx264", "-crf", CRF, "-preset", PRESET,
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path],
            capture_output=True, check=True,
        )
    finally:
        shutil.rmtree(video_dir, ignore_errors=True)

    markers = _align_markers(markers, out_path)
    with open(out_path + ".markers.json", "w", encoding="utf-8") as f:
        json.dump(markers, f, indent=2)
    print("Markers:", markers)
    print("Saved:", out_path)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a profile-claim take to video")
    parser.add_argument("--flow", required=True, choices=FLOWS)
    parser.add_argument("--out", help="Output mp4 (default output/mp4/claim_{flow}_raw.mp4)")
    args = parser.parse_args()
    record_claim_flow(args.flow, args.out or f"output/mp4/claim_{args.flow}_raw.mp4")


if __name__ == "__main__":
    main()
