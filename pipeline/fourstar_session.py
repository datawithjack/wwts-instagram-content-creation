"""Wissant Session announcement carousel — 6 hardcoded slides.

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


# Slide 2 — the squad shape.
#
# This slide used to restate the cover: the event name, the dates, "pick a
# squad, score on every heat". With the cover carrying all of that it had
# nothing left to say, so it says the one thing the reader actually needs
# before slides 3 and 4 make sense: there are eleven slots, five of them
# women's, which is why a locked women's slot matters.
#
# Slot shape verified against the live Wissant picks page and
# frontend/src/utils/sessionSlotLabels.ts in the app repo.
THE_SQUAD = {
    "eyebrow": "YOUR SQUAD",
    "name": "11 Picks",
    "tagline": "Six men and five women.",
    "points": [
        "Men: 1 Top 5, 2 from 6-15, 3 wildcards",
        "Women: 1 Top 5, 2 from 6-15, 2 wildcards",
        "Every heat your riders sail scores",
        "No captain, no Tour points, no season to commit to",
    ],
}

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
    """Build 6 slide dicts: cover, the change, 2 screenshots, notifications, cta."""
    slides = [
        # Bottom-anchored cover borrowed from event_picks, the house language
        # for an event-specific announcement. The poster sits as a corner mark
        # rather than the hero: it is supplied artwork with a loud palette and
        # a light background it cannot shed, so at hero size it fights the
        # brand and buries the news under a name it already shouts.
        {
            "type": "fourstar_cover",
            # Eyebrow names the mode, not the league: the lede below carries
            # the league now, and having both say it wastes a line.
            "eyebrow": "THE SESSION",
            "headline": "It's On",
            # The line the slide exists to deliver, so it is sized to carry
            # weight rather than sit as a caption under the headline.
            "lede": "The 4-star Wissant Wave Classic joins",
            "lede_accent": "Windsurf Fantasy League",
            "event_name": "Wissant Wave Classic",
            "discipline": "Wave",
            "stars": 4,
            "dates": "12 to 20 Sept 2026",
            "subtitle": "Pick a squad for the event, score on every heat.",
            "logo_url": logo_url("wissant-wave-classic.png"),
            "logo_alt": "Wissant Wave Classic 2026 event poster",
            "logo_width": 300,
            "accent_color": SESSION_COLOR,
        },
        {
            "type": "fantasy_rules_game",
            "eyebrow": THE_SQUAD["eyebrow"],
            "name": THE_SQUAD["name"],
            "tagline": THE_SQUAD["tagline"],
            "points": THE_SQUAD["points"],
            "accent_color": SESSION_COLOR,
        },
        # The card carries both halves of the first condition in one shot: the
        # 20 needed, and how far along the event is.
        {
            "type": "screenshot",
            "eyebrow": "CONDITION ONE",
            "title": "20 Riders",
            "tagline": "The event opens for picks once 20 riders have entered.",
            "image_url": screenshot_url("hub_card_wissant.png"),
            "alt": "Wissant Wave Classic card showing 9 riders entered of the 20 needed",
            "lead": "Wissant is at 9.",
            "caption": "Watch the bar fill: it updates as entries land on the WWT site.",
            "max_height": 560,
            "accent_color": SESSION_COLOR,
        },
        {
            "type": "screenshot",
            "eyebrow": "CONDITION TWO",
            "title": "Slots Unlock",
            "tagline": "Each slot names the riders it is waiting on.",
            "image_url": screenshot_url("wissant_womens_locked.png"),
            "alt": "Locked women's pick slots, each naming the riders needed to open it",
            "lead": "Two in a tier opens its first slot.",
            "caption": "Four opens the second.",
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
