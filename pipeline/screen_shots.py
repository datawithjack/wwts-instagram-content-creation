"""Capture stills of the live fantasy app for use inside carousel slides.

Sibling to pipeline/screen_record.py, which records *video* of the picks flow.
This grabs *stills*, and reuses that module's login and mobile emulation so the
shots show the app exactly as a phone user sees it.

The shots this exists for are perishable. The Session gates an event behind a
20-rider start list, and unlocks pick slots in stages as riders enter, so the
locked state only exists while the start list is thin. Once an event fills up
that state is gone and cannot be re-shot. Capture early, commit the PNGs.

Like screen_record.py this drives the real site with real credentials, so it is
inherently side-effectful and verified by running, not by unit tests. It only
ever reads: no pick is chosen, no draft saved, "Confirm & Lock" never clicked.

Usage:
    python -m pipeline.screen_shots                      # hub + Wissant + Tiree
    python -m pipeline.screen_shots --event 278
    python -m pipeline.screen_shots --out assets/screenshots
"""
import argparse
import os
import re

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from pipeline.screen_record import BASE_URL, MOBILE_CONTEXT, _force_dark_bg, _login

load_dotenv()

OUT_DIR = "assets/screenshots"

# The 4-star wave events that play the Session only. Both are gated on the
# 20-rider threshold, so both show the locked state until their start lists fill.
FOUR_STAR_EVENTS = [
    {"id": 278, "slug": "wissant"},
    {"id": 279, "slug": "tiree"},
]

# App chrome that floats over the page. Fine on a real screen, but in a
# full-page screenshot a fixed/sticky element is painted at its viewport
# position, so it lands in the middle of the image over whatever it overlaps.
FLOATING_CHROME = "nav.fixed, .sticky.bottom-0"

# Wait for the picks grid to settle. The page renders its shell before the
# start list lands, so the slot rows change from placeholder to locked/open.
SETTLE_MS = 4000


def _hide_floating_chrome(page) -> None:
    page.add_style_tag(content=f"{FLOATING_CHROME} {{ display: none !important; }}")


def _dismiss_tips(page) -> None:
    """Close the dismissible tip banner so it doesn't cover a slot row."""
    for button in page.locator('button[aria-label*="ismiss"], button[aria-label*="lose"]').all():
        try:
            if button.is_visible():
                button.click()
                page.wait_for_timeout(250)
        except Exception:
            pass


def _clip_between(page, top, bottom, pad: int = 16) -> dict | None:
    """Document-space box spanning two locators, for a full-page clipped shot.

    Element screenshots are the obvious tool here, but the section containers
    are unlabelled wrappers — anchoring on the visible headings and rows is far
    less brittle than guessing at a class name that Tailwind may re-emit.
    """
    top_box = top.bounding_box()
    bottom_box = bottom.bounding_box()
    if not top_box or not bottom_box:
        return None
    scroll_y = page.evaluate("window.scrollY")
    y = top_box["y"] + scroll_y - pad
    height = (bottom_box["y"] + bottom_box["height"] + scroll_y) - y + pad
    width = page.evaluate("document.documentElement.clientWidth")
    return {"x": 0, "y": max(0, y), "width": width, "height": height}


def _surface_box(page, locator, pad: int = 12, pad_bottom: int | None = None) -> dict | None:
    """Document-space box of the nearest enclosing card surface.

    `surface-N` is the app's own card token rather than a Tailwind utility, so
    it marks a real card boundary. That matters here: climbing by text stops at
    the first wrapper holding the copy, which on an event card is the inner text
    column — it cuts off the star-rating badge and the image above it.

    `pad_bottom` is separate because the event card's entry progress bar is
    painted on the card's own bottom edge: growing the box evenly to catch it
    also drags in a slice of the card above.
    """
    handle = locator.element_handle()
    if handle is None:
        return None
    if pad_bottom is None:
        pad_bottom = pad
    return page.evaluate(
        """([el, pad, padBottom]) => {
            const card = el.closest('[class*="surface-"]');
            if (!card) return null;
            const r = card.getBoundingClientRect();
            return {
                x: Math.max(0, r.left - pad),
                y: Math.max(0, r.top + window.scrollY - pad),
                width: Math.min(document.documentElement.clientWidth, r.width + pad * 2),
                height: r.height + pad + padBottom,
            };
        }""",
        [handle, pad, pad_bottom],
    )


def _enclosing_box(page, locator, must_contain: str, pad: int = 12) -> dict | None:
    """Document-space box of the nearest ancestor whose text contains a phrase.

    For regions with no card surface to anchor on. Cards are unlabelled Tailwind
    divs of unpredictable depth, so "go up N parents" is a guess that breaks on
    the next markup change; climbing until the wanted copy is in scope does not.
    """
    handle = locator.element_handle()
    if handle is None:
        return None
    return page.evaluate(
        """([el, phrase, pad]) => {
            let node = el;
            while (node && node !== document.body) {
                if ((node.innerText || '').includes(phrase)) {
                    const r = node.getBoundingClientRect();
                    return {
                        x: Math.max(0, r.left - pad),
                        y: Math.max(0, r.top + window.scrollY - pad),
                        width: Math.min(document.documentElement.clientWidth, r.width + pad * 2),
                        height: r.height + pad * 2,
                    };
                }
                node = node.parentElement;
            }
            return null;
        }""",
        [handle, must_contain, pad],
    )


def _shoot(page, path: str, clip: dict | None = None) -> None:
    page.screenshot(path=path, full_page=True, clip=clip)
    print(f"  wrote {path}")


def _capture_hub(page, out_dir: str) -> None:
    """The hub: the 20-rider gate stated in the app's own words, plus each
    event card carrying its live entry count."""
    page.goto(f"{BASE_URL}/fantasy")
    page.wait_for_timeout(SETTLE_MS)
    _dismiss_tips(page)
    _hide_floating_chrome(page)
    _force_dark_bg(page)
    _shoot(page, f"{out_dir}/hub_full.png")

    # The gate card states the 20-rider rule and the email promise in the app's
    # own words. Take the whole card, so the Practice Mode button isn't halved.
    status = page.get_by_text("No picks open yet", exact=False).first
    if status.count():
        box = _enclosing_box(page, status, "Practice Mode", pad=20)
        _shoot(page, f"{out_dir}/hub_gate.png", box)

    # Shoot the whole card surface: discipline and star-rating badge, event
    # image, title, dates, and the "N riders entered / Picks open at 20" line
    # with its progress bar. The entry count is the point, but the badge and
    # image are what make it read as the event's card rather than a stray row.
    for event in FOUR_STAR_EVENTS:
        title = page.get_by_text(re.compile(event["slug"], re.I)).first
        if not title.count():
            print(f"  no hub card for {event['slug']}")
            continue
        box = _surface_box(page, title, pad=8, pad_bottom=10) or _enclosing_box(
            page, title, "required to play", pad=28
        )
        if not box:
            print(f"  could not locate the {event['slug']} card")
            continue
        _shoot(page, f"{out_dir}/hub_card_{event['slug']}.png", box)


def _capture_session(page, event_id: int, slug: str, out_dir: str) -> None:
    """The picks builder: open men's slots above, locked women's slots below,
    each spelling out the rider count that unlocks it."""
    page.goto(f"{BASE_URL}/fantasy/session/{event_id}")
    page.wait_for_timeout(SETTLE_MS)
    _dismiss_tips(page)
    _hide_floating_chrome(page)
    _force_dark_bg(page)
    _shoot(page, f"{out_dir}/{slug}_session_full.png")

    entered = page.get_by_text(re.compile(r"\d+ women entered")).first
    if entered.count():
        note = page.get_by_text("Men-only for now", exact=False).first
        _shoot(page, f"{out_dir}/{slug}_entries_banner.png",
               _clip_between(page, entered, note if note.count() else entered, pad=20))

    mens = page.get_by_role("heading", name="MEN'S PICKS").first
    womens = page.get_by_role("heading", name="WOMEN'S PICKS").first
    if mens.count() and womens.count():
        _shoot(page, f"{out_dir}/{slug}_mens_picks.png",
               _clip_between(page, mens, womens, pad=12))

    if womens.count():
        last_locked = page.get_by_text(re.compile(r"Opens when \d+ women outside")).last
        _shoot(page, f"{out_dir}/{slug}_womens_locked.png",
               _clip_between(page, womens, last_locked if last_locked.count() else womens, pad=20))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=int, action="append",
                        help="Fantasy event id (repeatable). Default: the 4-star wave events.")
    parser.add_argument("--out", default=OUT_DIR, help=f"Output directory (default {OUT_DIR})")
    parser.add_argument("--skip-hub", action="store_true", help="Only shoot the session pages")
    args = parser.parse_args()

    events = FOUR_STAR_EVENTS
    if args.event:
        known = {e["id"]: e for e in FOUR_STAR_EVENTS}
        events = [known.get(i, {"id": i, "slug": f"event{i}"}) for i in args.event]

    os.makedirs(args.out, exist_ok=True)
    email, password = os.getenv("FANTASY_EMAIL"), os.getenv("FANTASY_PASSWORD")
    if not email or not password:
        raise SystemExit("FANTASY_EMAIL / FANTASY_PASSWORD missing from .env")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(**MOBILE_CONTEXT)
        page = context.new_page()
        _login(page, email, password, "/fantasy")
        page.wait_for_timeout(2000)

        if not args.skip_hub:
            print("hub:")
            _capture_hub(page, args.out)

        for event in events:
            print(f"session {event['id']} ({event['slug']}):")
            _capture_session(page, event["id"], event["slug"], args.out)

        browser.close()


if __name__ == "__main__":
    main()
