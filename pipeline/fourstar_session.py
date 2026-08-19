"""Wissant Session announcement carousel — 5 hardcoded slides.

Announces that Wissant Wave Classic, a 4-star wave event, plays the Fantasy
League in Session mode only, and explains the two conditions that gate it: the
event opens once 20 riders have entered, and pick slots then unlock in stages as
more riders enter.

**Scoped to Wissant alone** (12-20 Sep 2026, API id 278). Tiree Wave Classic is
the other 2026 4-star on the fantasy season and works the same way, but it is
not confirmed, so it is deliberately left out rather than announced early. Brazil
was a third 4-star and is cancelled. If Tiree is confirmed later, this is a copy
change to the event slide plus a second card screenshot, not a new template.

Wissant is not Tour-eligible: the season config carries ``tour_eligible: false``
on it and ``true`` on every 5-star, which is the machine-readable form of
"Session only".

Two slides carry real screenshots of the live app rather than drawn mockups,
because the states they show are perishable — once the start list fills, the
locked view is gone. See pipeline/screen_shots.py, which captured them while
Wissant sat at 9 riders of the 20 needed.

Slot copy is quoted from the app itself, so the post and the product say the
same thing. Note the rule is not a flat "two riders opens a tier": two opens a
band's first slot, four opens its second.

The body slides reuse the fantasy_rules_* templates and the Session teal, so this
reads as one series with the Freestyle and Slalom Session posts. The cover is its
own template: an event announcement wants the event's name, stars and dates on it,
which the shared cover has nowhere to put.
"""
import os

# Session teal, lifted from the web app's @theme token (session-400), shared
# with the Freestyle and Slalom Session posts.
SESSION_COLOR = "#2dd4bf"

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(_REPO_ROOT, "assets", "screenshots")
LOGOS_DIR = os.path.join(_REPO_ROOT, "assets", "logos")


def _file_url(directory: str, name: str) -> str:
    """file:// URL for a local asset, or "" when it is missing.

    Returning "" rather than raising keeps a dry-run preview renderable on a
    checkout that has not pulled the images: the slide frames an empty image
    instead of blowing up the whole carousel.
    """
    path = os.path.join(directory, name)
    if not os.path.exists(path):
        return ""
    return "file:///" + os.path.abspath(path).replace(os.sep, "/")


def screenshot_url(name: str) -> str:
    return _file_url(SCREENSHOTS_DIR, name)


def logo_url(name: str) -> str:
    return _file_url(LOGOS_DIR, name)


# Slide 5 — the part that means nobody has to sit refreshing the page.
YOU_WILL_KNOW = {
    "eyebrow": "NO NEED TO WATCH",
    "name": "We'll Tell You",
    "tagline": "The start list moves on its own schedule, so we'll do the watching.",
    "points": [
        "An email the moment picks open",
        "A nudge as the start list grows and slots unlock",
        "Practice Mode is open in the meantime",
    ],
}


def build_fourstar_session_slides() -> list[dict]:
    """Build 5 slide dicts: cover, 2 screenshots, notifications, cta.

    The squad-shape slide that used to sit at position 2 is gone. The cover
    now states the news in full, and the two conditions are what the post is
    actually for, so an eleven-slot breakdown in between was a detour.
    """
    slides = [
        # Bottom-anchored cover borrowed from event_picks, the house language
        # for an event-specific announcement. The poster sits as a corner mark
        # rather than the hero: it is supplied artwork with a loud palette and
        # a light background it cannot shed, so at hero size it fights the
        # brand and buries the news under a name it already shouts.
        {
            "type": "fourstar_cover",
            "eyebrow": "NEW SESSION EVENT",
            # No separate headline any more. Two attempts at one ("IT'S ON",
            # then "FOUR STARS") both put the slide's biggest type on the part
            # carrying the least information, with the actual news shrunk to a
            # line underneath. The news is the headline now.
            #
            # Two lines, not three: the event on one, what happened to it on
            # the other. The earlier three-line split ("Wissant Wave Classic /
            # Added To / Windsurf Fantasy League") stair-stepped down the slide
            # and put a two-word orphan in the middle.
            "lede_lines": ["Wissant Wave Classic"],
            "lede_accent": "Joins The Fantasy League",
            "event_name": "Wissant Wave Classic",
            "discipline": "Wave",
            "stars": 4,
            "dates": "12 to 20 Sept 2026",
            # One fact the rest of the slide does not already carry, and the
            # one that sets up slide 2. The star rating is in the meta strip
            # and the mode is in the eyebrow, so restating either here just
            # spent two lines saying nothing new.
            "subtitle": (
                "Picks open once 20 riders have entered the event. "
                "Twelve are in."
            ),
            # Not "picks open now": they do not, and will not until the start
            # list fills. This is the one thing a reader can act on today.
            "cta_line": "Sign up free \u00b7 windsurfworldtourstats.com",
            # The CTA carries the URL now, so the shared bottom-right watermark
            # would be the same address twice on one slide. Cover only; every
            # other slide in the carousel keeps it.
            "hide_footer": True,
            "logo_url": logo_url("wissant-wave-classic.png"),
            "logo_alt": "Wissant Wave Classic 2026 event poster",
            "logo_width": 260,
            "accent_color": SESSION_COLOR,
        },
        # The card carries both halves of the first condition in one shot: the
        # 20 needed, and how far along the event is. Re-shot 2026-08-19 after
        # the app's card was redesigned: the entry line now reads "12 riders
        # entered / Min. 20 required to play" on one row, and the "Stay tuned"
        # status next to the dates is gone.
        {
            "type": "screenshot",
            "eyebrow": "CONDITION ONE",
            "title": "20 Riders",
            "tagline": "The event opens for picks once 20 riders have entered.",
            "image_url": screenshot_url("hub_card_wissant.png"),
            "alt": "Wissant Wave Classic card showing 12 riders entered of the 20 required to play",
            "lead": "Wissant is at 12.",
            "caption": "Eight to go. The bar fills as entries land on the WWT site.",
            "max_height": 560,
            "accent_color": SESSION_COLOR,
        },
        # The rule in the app's own words: a slot is gated on its own ranking
        # category, not on the total. Two riders in a category opens that
        # category's first slot, four opens its second. The screenshot is the
        # women's column because every slot in it is still locked, so each row
        # is legible as "this is what I am waiting for" rather than a mix of
        # open and locked rows the reader has to sort out.
        {
            "type": "screenshot",
            "eyebrow": "CONDITION TWO",
            "title": "Slots Unlock",
            "tagline": "Slots open by category, not all at once.",
            "image_url": screenshot_url("wissant_womens_locked.png"),
            "alt": "Locked women's pick slots, each naming the riders needed to open it",
            "lead": "Two riders in a category opens its slot.",
            "caption": "Four opens the next one. Every slot tells you what it is waiting for.",
            "max_height": 640,
            "accent_color": SESSION_COLOR,
        },
        {
            "type": "fantasy_rules_game",
            "eyebrow": YOU_WILL_KNOW["eyebrow"],
            "name": YOU_WILL_KNOW["name"],
            "tagline": YOU_WILL_KNOW["tagline"],
            "points": YOU_WILL_KNOW["points"],
            "accent_color": SESSION_COLOR,
        },
        {
            "type": "fantasy_rules_cta",
            "headline": "GET READY",
            "subtitle": "Sign up now and get notified when picks open.",
            "deadline": "Entries close 06:00 local, 12 September 2026",
            "cta_line": "Play free. Link in bio",
            "handle": "@windsurfworldtourstats",
            "accent_color": SESSION_COLOR,
        },
    ]

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
