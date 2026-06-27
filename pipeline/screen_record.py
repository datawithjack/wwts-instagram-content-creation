"""Screen-record the live fantasy picks flow as a portrait video.

Drives the production web app with Playwright — logs in with the FANTASY_EMAIL /
FANTASY_PASSWORD creds from .env, opens the picks builder for an event, and clicks
through filling a squad while recording the session. Output is B-roll footage to be
intercut with the rendered tour-rules reel cards (see pipeline/reel_edit.py, TBD).

This is screen-capture of the REAL app, NOT an HTML render — so it's inherently
side-effectful (live site, real browser) and verified by running, not unit tests.

Stops BEFORE "Confirm & Lock Team" — picks are left as an unsaved draft, nothing is
committed to the account.

Usage:
    python -m pipeline.screen_record                 # default event 122 (Gran Canaria)
    python -m pipeline.screen_record --event 122 --out output/mp4/picks_raw.mp4
"""
import argparse
import os
import re
import shutil
import subprocess
import tempfile

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

    The auth endpoint is occasionally slow (>30s), so we treat the redirect to the
    picks page as the success signal with a generous timeout rather than blocking
    on the response event. A 401 (bad creds) surfaces as an inline alert.
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
        page.wait_for_url("**/fantasy/picks/**", timeout=45000)
    except Exception:
        code = status.get("code")
        raise RuntimeError(
            f"Login did not reach the picks page (auth status={code}). "
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


def record_picks_flow(event_id: int, out_path: str) -> str:
    """Record the picks flow for one event to a portrait mp4. Returns the path."""
    email = os.getenv("FANTASY_EMAIL")
    password = os.getenv("FANTASY_PASSWORD")
    if not email or not password:
        raise RuntimeError("FANTASY_EMAIL / FANTASY_PASSWORD must be set in .env")

    next_path = f"%2Ffantasy%2Fpicks%2F{event_id}"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    video_dir = tempfile.mkdtemp()

    picked: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(
                record_video_dir=video_dir,
                record_video_size=VIDEO_SIZE,
                **MOBILE_CONTEXT,
            )
            page = context.new_page()
            page.add_init_script(CURSOR_JS)  # cursor helpers on every document

            _login(page, email, password, next_path)
            _force_dark_bg(page)
            _install_cursor(page)
            _dismiss_captains_dialog(page)
            page.wait_for_timeout(HOLD_START)

            for _ in range(5):  # Man 1, Man 2, Woman 1, Woman 2, Wildcard
                name = _pick_next_slot(page)
                picked.append(name)
                page.wait_for_timeout(BEAT)

            # Slow-scroll back to the top to reveal the whole completed squad.
            _slow_scroll_into_view(page, page.get_by_role("heading", name="MEN'S PICKS", exact=True))
            page.wait_for_timeout(HOLD_END)

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

    print("Picked squad:", ", ".join(picked) if picked else "(none)")
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
