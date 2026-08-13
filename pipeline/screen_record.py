"""Screen-record the live fantasy picks flow as a portrait video.

Drives the production web app with Playwright — logs in with the FANTASY_EMAIL /
FANTASY_PASSWORD creds from .env, opens on the /fantasy hub, taps the event card to
enter the picks builder, then clicks through filling a squad while recording the
session. Output is B-roll footage intercut with the rendered explainer cards by
pipeline/reel_edit.py.

This is screen-capture of the REAL app, NOT an HTML render — so it's inherently
side-effectful (live site, real browser) and verified by running, not unit tests.

Scrolls to and highlights "Confirm & Lock Team" as the payoff beat but NEVER clicks it
— picks are left as an unsaved draft, nothing is committed to the account. Writes a
sidecar <out>.markers.json (build_start/end, confirm_start/end) so pipeline/reel_edit.py
can cut the footage into the right slices.

Usage:
    python -m pipeline.screen_record                 # default event 122 (Gran Canaria)
    python -m pipeline.screen_record --event 122 --out output/mp4/picks_raw.mp4
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

LOGIN_URL = "https://www.windsurfworldtourstats.com/fantasy/login"
BASE_URL = "https://www.windsurfworldtourstats.com"

# Mobile reel-style emulation: a real touch device at 9:16, rendered at 2x →
# crisp 1080x1920 footage AND the app's mobile layout (modal athlete picker,
# hamburger nav) — i.e. what a phone user actually sees.
MOBILE_CONTEXT = {
    "viewport": {"width": 540, "height": 960},
    "device_scale_factor": 2,
    "is_mobile": True,
    "has_touch": True,
    "user_agent": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
}
# Record at the CSS viewport size so the page fills the frame (setting a larger
# record size makes Playwright capture a taller region, leaving grey below the
# page). We upscale to a crisp 1080x1920 in the ffmpeg pass.
VIDEO_SIZE = {"width": 540, "height": 960}
OUTPUT_SIZE = "1080:1920"

# Pacing (ms) — tuned so the footage is watchable, not frantic.
BEAT = 1100          # between pick actions
SETTLE = 600         # let a modal animate in
HOLD_START = 2200    # linger on the empty squad
HOLD_END = 3200      # linger on the completed squad
POPUP_HOLD = 4400    # pause on the confirm pop-out (no button is pressed)
GLIDE = 650          # fake-cursor travel time (matches the CSS transition)
SCROLL_STEPS = 22    # increments per slow scroll
SCROLL_PAUSE = 40    # ms between scroll increments

# A fake touch/cursor overlay so the footage reads like a real person tapping —
# headless Chromium has no visible pointer. Defines window.__cursor_* helpers;
# installed as an init script so it survives navigations. The blob is appended to
# <body> (outside React's root) with a max z-index so it floats above modals, and
# pointer-events:none so it never blocks the real click.
CURSOR_JS = r"""
window.__cursor_install = () => {
  if (document.getElementById('__fake_cursor')) return;
  const s = document.createElement('style');
  s.textContent = `
    #__fake_cursor{position:fixed;left:0;top:0;width:38px;height:38px;margin:-19px 0 0 -19px;
      border-radius:50%;background:rgba(255,255,255,0.30);border:2px solid rgba(255,255,255,0.9);
      box-shadow:0 2px 10px rgba(0,0,0,0.45);z-index:2147483647;pointer-events:none;
      transform:translate(50vw,55vh);
      transition:transform 0.65s cubic-bezier(.22,.61,.36,1);}
    #__fake_cursor.__press{background:rgba(90,180,204,0.6);transform-origin:center;}
    #__fake_cursor.__tap::after{content:'';position:absolute;left:50%;top:50%;width:38px;height:38px;
      margin:-19px 0 0 -19px;border-radius:50%;border:2px solid rgba(90,180,204,0.7);
      animation:__ripple 0.5s ease-out forwards;}
    @keyframes __ripple{from{transform:scale(0.5);opacity:0.9}to{transform:scale(2.4);opacity:0}}
  `;
  document.head.appendChild(s);
  const c = document.createElement('div');
  c.id = '__fake_cursor';
  document.body.appendChild(c);
};
window.__cursor_move = (x, y) => {
  const c = document.getElementById('__fake_cursor');
  if (c) c.style.transform = `translate(${x}px, ${y}px)`;
};
window.__cursor_tap = () => {
  const c = document.getElementById('__fake_cursor');
  if (!c) return;
  c.classList.remove('__tap'); void c.offsetWidth;  // restart animation
  c.classList.add('__tap', '__press');
  setTimeout(() => c.classList.remove('__press'), 220);
};
"""


def _login(page, email: str, password: str, next_path: str) -> None:
    """Sign in via the native email/password form, redirecting to next_path.

    The auth endpoint is occasionally slow (>30s), so we treat leaving the login page
    as the success signal with a generous timeout rather than blocking on the response
    event. A 401 (bad creds) surfaces as an inline alert.
    """
    page.goto(f"{LOGIN_URL}?next={next_path}")
    page.get_by_role("button", name="Sign In", exact=True).first.click()
    page.wait_for_timeout(400)
    page.get_by_role("textbox", name="you@example.com").fill(email)
    page.get_by_role("textbox", name="Min 8 characters").fill(password)

    status: dict = {}
    page.on(
        "response",
        lambda r: status.update(code=r.status) if "auth/login" in r.url else None,
    )
    page.locator("form").get_by_role("button", name="Sign In").click()
    try:
        page.wait_for_url(lambda u: "/fantasy/login" not in u, timeout=45000)
    except Exception:
        code = status.get("code")
        raise RuntimeError(
            f"Login did not redirect off the login page (auth status={code}). "
            "Check FANTASY_EMAIL / FANTASY_PASSWORD in .env, or retry (the auth "
            "endpoint can be slow)."
        )


def _install_cursor(page) -> None:
    """Inject the fake-cursor blob (idempotent)."""
    page.evaluate("window.__cursor_install && window.__cursor_install()")


def _slow_scroll_into_view(page, locator) -> None:
    """Human-speed scroll bringing the element to the vertical middle, in small
    increments (Playwright's auto-scroll on click is an instant jump otherwise)."""
    handle = locator.element_handle()
    if handle is None:
        return
    target = page.evaluate(
        """(el) => {
            const r = el.getBoundingClientRect();
            const mid = window.scrollY + r.top - (window.innerHeight / 2 - r.height / 2);
            return Math.max(0, mid);
        }""",
        handle,
    )
    start = page.evaluate("window.scrollY")
    if abs(target - start) < 8:
        return
    for i in range(1, SCROLL_STEPS + 1):
        y = start + (target - start) * i / SCROLL_STEPS
        page.evaluate("(y) => window.scrollTo(0, y)", y)
        page.wait_for_timeout(SCROLL_PAUSE)


def _tap(page, locator) -> None:
    """Glide the fake cursor to the element, ripple, then perform the real click."""
    _install_cursor(page)
    box = locator.bounding_box()
    if box:
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        page.evaluate("([x, y]) => window.__cursor_move(x, y)", [cx, cy])
        page.wait_for_timeout(GLIDE)
        page.evaluate("window.__cursor_tap && window.__cursor_tap()")
        page.wait_for_timeout(180)
    locator.click()


def _force_dark_bg(page) -> None:
    """The mobile picks page is shorter than a 16:9 frame, leaving the page body
    (grey) visible below it. Paint html/body/#root the app's dark navy so the
    empty area blends into the app instead of reading as a grey letterbox."""
    page.add_style_tag(
        content="html, body, #root { background: #0a0d16 !important; }"
    )


def _event_card_pick_link(page, event_id: int):
    """The "Pick Tour Team" link ON THE EVENT CARD (not the reminder banner).

    Both the banner and the card link to /fantasy/picks/{id}, but only the card pairs
    it with a "Pick Session Team" link (/fantasy/session/{id}) in the same row. So we
    anchor on the session link (card-only) and grab the Tour link from its parent row,
    falling back to the last picks link (the card sits below the banner)."""
    tour_sel = f'a[href$="/fantasy/picks/{event_id}"]'
    session = page.locator(f'a[href$="/fantasy/session/{event_id}"]').first
    if session.count() > 0:
        row = session.locator("xpath=..")
        link = row.locator(tour_sel).first
        if link.count() > 0:
            return link
    return page.locator(tour_sel).last


def _click_through_event_card(page, event_id: int) -> None:
    """From the /fantasy hub, scroll to the event card's "Pick Tour Team" button and
    tap it to enter the picks builder — the natural way a real user starts."""
    link = _event_card_pick_link(page, event_id)
    link.wait_for(state="visible", timeout=12000)
    _slow_scroll_into_view(page, link)
    page.wait_for_timeout(SETTLE)
    _tap(page, link)
    page.wait_for_url(f"**/fantasy/picks/{event_id}", timeout=15000)
    page.wait_for_timeout(SETTLE)


def _dismiss_captains_dialog(page) -> None:
    """The "Choose your captains" modal auto-opens on load — close it via the X
    button (Escape only hides it visually; the app re-opens it on the next tap)."""
    dialog = page.get_by_role("dialog")
    try:
        dialog.wait_for(state="visible", timeout=6000)
    except Exception:
        return  # modal never appeared — nothing to dismiss
    _tap(page, dialog.get_by_role("button", name="Close"))
    page.wait_for_timeout(SETTLE)


_CHOOSE_RE = re.compile(r"choose your pick", re.I)


def _pick_next_slot(page) -> str:
    """Fill the next empty slot and return the picked athlete's name.

    On the mobile layout each slot opens an athlete-picker MODAL (not an inline
    list). We slow-scroll the topmost remaining "+ Tap to choose your pick" into
    view, tap it, then tap the first athlete card; the modal closes and the slot
    fills. Slots do not auto-advance here, so every slot gets its own tap.
    """
    slot = page.get_by_role("button", name=_CHOOSE_RE).first
    _slow_scroll_into_view(page, slot)
    _tap(page, slot)
    page.wait_for_timeout(SETTLE)

    dialog = page.get_by_role("dialog")
    dialog.wait_for(state="visible", timeout=6000)
    # Athlete cards are the dialog buttons that carry a photo (img); the X has none.
    option = dialog.locator("button").filter(has=page.locator("img")).first
    page.wait_for_timeout(SETTLE)
    name = option.locator("img").first.get_attribute("alt") or "?"
    _tap(page, option)
    page.wait_for_timeout(SETTLE)  # let the modal close + slot fill
    return name


_CONFIRM_RE = re.compile(r"confirm\s*(&|and)\s*lock", re.I)
_CONFIRM_PICKS_RE = re.compile(r"confirm picks", re.I)


def _open_confirm_popup(page) -> str:
    """Highlight + tap "Confirm & Lock Team" to open the confirmation pop-out, then
    pause on it (the payoff beat: it spells out that the team locks and becomes visible
    to other players). No button inside the modal is ever pressed — not Confirm Picks,
    not Save Draft, not Cancel — so nothing is committed; the modal is simply left open
    and discarded when the browser closes.

    Returns "popup" if the modal was captured, "button" if the confirm button was only
    highlighted (e.g. disabled because captains aren't set), or "" if not found."""
    btn = page.get_by_role("button", name=_CONFIRM_RE).first
    try:
        btn.wait_for(state="visible", timeout=6000)
    except Exception:
        print("Confirm & Lock button not found — skipping confirm footage.")
        return ""
    _slow_scroll_into_view(page, btn)
    page.wait_for_timeout(SETTLE)

    if not btn.is_enabled():
        # Captains not set → button disabled. Highlight it (no click) and move on.
        print("Confirm & Lock disabled (captains likely unset) — highlighting only.")
        _install_cursor(page)
        box = btn.bounding_box()
        if box:
            page.evaluate(
                "([x, y]) => window.__cursor_move(x, y)",
                [box["x"] + box["width"] / 2, box["y"] + box["height"] / 2],
            )
        page.wait_for_timeout(GLIDE)
        page.evaluate("window.__cursor_tap && window.__cursor_tap()")
        page.wait_for_timeout(HOLD_END)
        return "button"

    _tap(page, btn)  # opens the ConfirmPicksModal pop-out (does NOT commit)
    # Confirm the pop-out is up via its commit button — which we deliberately avoid.
    try:
        page.get_by_role("button", name=_CONFIRM_PICKS_RE).first.wait_for(
            state="visible", timeout=6000
        )
    except Exception:
        print("Confirm pop-out did not appear — showing button highlight only.")
        page.wait_for_timeout(HOLD_END)
        return "button"
    # Park the cursor on the modal body (away from its action buttons) and just hold,
    # so the footage reads as "here's the pop-out" rather than about to press anything.
    page.evaluate(
        "([x, y]) => window.__cursor_move(x, y)",
        [VIDEO_SIZE["width"] / 2, VIDEO_SIZE["height"] * 0.3],
    )
    page.wait_for_timeout(POPUP_HOLD)  # pause on the pop-out (this is the footage)
    return "popup"


def record_picks_flow(event_id: int, out_path: str) -> str:
    """Record the picks flow for one event to a portrait mp4. Returns the path."""
    email = os.getenv("FANTASY_EMAIL")
    password = os.getenv("FANTASY_PASSWORD")
    if not email or not password:
        raise RuntimeError("FANTASY_EMAIL / FANTASY_PASSWORD must be set in .env")

    # Start on the /fantasy hub so the footage opens on the event card, then clicks
    # through into picks (the natural user journey).
    next_path = "%2Ffantasy"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    video_dir = tempfile.mkdtemp()

    picked: list[str] = []
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
            # Video recording starts with the context; mark times relative to here so
            # the marker offsets line up with the recorded timeline (login + dead
            # time before build_start is trimmed out by reel_edit.py).
            t0 = time.monotonic()
            page.add_init_script(CURSOR_JS)  # cursor helpers on every document

            _login(page, email, password, next_path)
            _force_dark_bg(page)
            _install_cursor(page)

            # Open on the event card, linger, then click through into the picks builder.
            markers["build_start"] = round(time.monotonic() - t0, 2)
            page.wait_for_timeout(HOLD_START)
            _click_through_event_card(page, event_id)

            _dismiss_captains_dialog(page)
            page.wait_for_timeout(SETTLE)

            for _ in range(5):  # Man 1, Man 2, Woman 1, Woman 2, Wildcard
                name = _pick_next_slot(page)
                picked.append(name)
                page.wait_for_timeout(BEAT)

            # Slow-scroll back to the top to reveal the whole completed squad.
            _slow_scroll_into_view(page, page.get_by_role("heading", name="MEN'S PICKS", exact=True))
            page.wait_for_timeout(HOLD_END)
            markers["build_end"] = round(time.monotonic() - t0, 2)

            # Payoff beat: tap Confirm & Lock to surface the pop-out (locks team /
            # visible to others) and pause on it. No modal button is pressed, so
            # nothing is committed — the modal is just discarded when the browser closes.
            markers["confirm_start"] = round(time.monotonic() - t0, 2)
            if _open_confirm_popup(page):
                markers["confirm_end"] = round(time.monotonic() - t0, 2)
            else:
                markers.pop("confirm_start", None)

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

    # Sidecar markers: reel_edit.py reads these to cut the footage into the
    # build-squad and confirm-button slices (skipping login + dead time).
    markers_path = out_path + ".markers.json"
    with open(markers_path, "w", encoding="utf-8") as f:
        json.dump(markers, f, indent=2)

    print("Picked squad:", ", ".join(picked) if picked else "(none)")
    print("Markers:", markers)
    print("Saved:", out_path)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Record the fantasy picks flow to video")
    parser.add_argument("--event", type=int, default=122, help="Fantasy event id")
    parser.add_argument(
        "--out", default="output/mp4/picks_raw.mp4", help="Output mp4 path"
    )
    args = parser.parse_args()
    record_picks_flow(args.event, args.out)


if __name__ == "__main__":
    main()
