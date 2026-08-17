"""4-star Session announcement carousel — 6 hardcoded slides.

Announces that the tour's 4-star wave events now play the Fantasy League in
Session mode only, and explains the two conditions that gate them: an event
opens once 20 riders have entered, and pick slots then unlock in stages as more
riders enter.

The two events are Wissant Wave Classic (12-20 Sep 2026) and Tiree Wave Classic
(10-16 Oct 2026). Brazil was the other 2026 4-star but is cancelled, so the post
names two. Neither is Tour-eligible: the season config carries
``tour_eligible: false`` on both and ``true`` on every 5-star, which is the
machine-readable form of "Session only".

Two slides carry real screenshots of the live app rather than drawn mockups,
because the states they show are perishable — once an event's start list fills,
the locked view is gone. See pipeline/screen_shots.py, which captured them while
Wissant sat at 9 riders of the 20 needed.

Slot copy is quoted from the app itself, so the post and the product say the
same thing. Note the rule is not a flat "two riders opens a tier": two opens a
band's first slot, four opens its second.

Reuses the fantasy_rules_* slide templates so this reads as one series with the
Freestyle and Slalom Session posts.
"""
import os

# Session teal, lifted from the web app's @theme token (session-400), shared
# with the Freestyle and Slalom Session posts.
SESSION_COLOR = "#2dd4bf"

SCREENSHOTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "screenshots"
)


def screenshot_url(name: str) -> str:
    """file:// URL for a committed screenshot, or "" when it is missing.

    Returning "" rather than raising keeps a dry-run preview renderable on a
    checkout that has not pulled the PNGs: the slide frames an empty image
    instead of blowing up the whole carousel.
    """
    path = os.path.join(SCREENSHOTS_DIR, name)
    if not os.path.exists(path):
        return ""
    return "file:///" + os.path.abspath(path).replace(os.sep, "/")


# Slide 2 — what actually changed, and for which events.
THE_CHANGE = {
    "eyebrow": "WHAT'S NEW",
    "name": "Session Only",
    "tagline": "Two more events to play, one event at a time.",
    "points": [
        "Wissant Wave Classic, 12 to 20 September",
        "Tiree Wave Classic, 10 to 16 October",
        "The Session only, so no Tour points ride on them",
        "Pick a squad, score on every heat they sail",
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
        {
            "type": "fantasy_rules_cover",
            "eyebrow": "WINDSURF FANTASY LEAGUE",
            "title": "4-Star Events",
            "subtitle": "Wissant and Tiree join The Session.",
            "accent_color": SESSION_COLOR,
        },
        {
            "type": "fantasy_rules_game",
            "eyebrow": THE_CHANGE["eyebrow"],
            "name": THE_CHANGE["name"],
            "tagline": THE_CHANGE["tagline"],
            "points": THE_CHANGE["points"],
            "accent_color": SESSION_COLOR,
        },
        # The card carries both halves of the first condition in one shot: the
        # 20 needed, and how far along this event is.
        {
            "type": "screenshot",
            "eyebrow": "CONDITION ONE",
            "title": "20 Riders",
            "tagline": "An event opens for picks once 20 riders have entered.",
            "image_url": screenshot_url("hub_card_wissant.png"),
            "alt": "Wissant Wave Classic card showing 9 riders entered of the 20 needed",
            "lead": "Wissant is at 9.",
            "caption": "Watch the bar fill.",
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
            "subtitle": "Sign up now and we'll email you the moment Wissant opens.",
            "deadline": "Wissant entries close 06:00 local, 12 September",
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
