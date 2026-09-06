"""Road to Finals promo reel — content builder.

A short reel promoting the title-race predictor at
windsurfworldtourstats.com/road-to-finals. Branded explainer cards
(templates/road_to_finals_reel.html) intercut with live screen-record footage of
the predictor itself (pipeline/screen_record_rtf.py), stitched by
pipeline/rtf_reel_edit.py.

The hook is whatever the season is actually doing, so the top two riders and their
points are READ OFF THE API rather than typed in. On 2026-09-06 the men's race was
tied -- Koster and Pare both on 22,400 -- which is the strongest hook the season has
offered; a month later it will be something else, and a card that quietly kept
claiming a tie would be worse than one that never named a number.

Card 3 carries the caveats. The predictor states four of them on the page; two go on
screen here (it is a fun predictor, not official rankings; future points are
estimated) and the rest belong in the caption -- a reel that stops to explain the
counting window loses the viewer.
"""
import requests

from pipeline.api import API_BASE_URL

# Accents mirror the app + sibling reels.
ACCENT_TOUR = "#22d3ee"
ACCENT_WARN = "#facc15"

# What the cards fall back to if the standings call fails. Deliberately a shape, not
# a stale scoreboard: no names, no numbers, so a failed fetch reads as a generic hook
# rather than as last month's race asserted as today's.
FALLBACK_HOOK = {
    "hook_rivals": [],
    "hook_sub": "Predict every event left and crown the World Champion.",
}


def fetch_title_race(year: int, fleet: str = "Men", timeout: int = 30) -> dict:
    """The top two of the season standings, and whether they are level.

    Uses the same endpoint the predictor page does (`/rankings/season/{year}`), so
    the card and the footage behind it cannot disagree.
    """
    resp = requests.get(
        f"{API_BASE_URL}/rankings/season/{year}",
        params={"discipline": "wave", "top": 20},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    rows = data.get("standings", {}).get(fleet, [])[:2]
    events = [e for e in data.get("events", []) if e.get("predictable")]
    return {
        "rivals": [
            {
                "name": (row.get("athlete_name") or "").upper(),
                "points": f"{int(row.get('total_points') or 0):,}",
            }
            for row in rows
        ],
        "level": len({row.get("total_points") for row in rows}) == 1 and len(rows) == 2,
        "events_left": len(events),
        "year": data.get("year", year),
    }


# Small counts read better as words in a headline. Mirrors the page's own rule.
_COUNT_WORDS = [
    "No", "One", "Two", "Three", "Four", "Five", "Six",
    "Seven", "Eight", "Nine", "Ten",
]


def build_road_to_finals_reel_data(year: int = 2026, fleet: str = "Men") -> dict:
    """Build the content dict for the Road to Finals promo reel cards."""
    try:
        race = fetch_title_race(year, fleet)
    except Exception as exc:  # network, shape change, anything
        print(f"Standings fetch failed ({exc}); building the generic hook.")
        race = None

    if race and race["rivals"]:
        left = race["events_left"]
        word = _COUNT_WORDS[left] if left < len(_COUNT_WORDS) else str(left)
        hook_title = "THE TITLE\nIS LEVEL" if race["level"] else "THE TITLE\nRACE"
        hook_sub = (
            f"{word} events left. Predict them and "
            f"crown the {race['year']} World Champion."
        )
        rivals = race["rivals"]
    else:
        hook_title = "THE TITLE\nRACE"
        hook_sub = FALLBACK_HOOK["hook_sub"]
        rivals = FALLBACK_HOOK["hook_rivals"]

    return {
        "accent_tour": ACCENT_TOUR,
        "accent_warn": ACCENT_WARN,

        # Screen 1 — hook. The two riders at the top and what separates them.
        "hook_eyebrow": "Wave World Title",
        "hook_title": hook_title,
        "hook_rivals": rivals,
        "hook_sub": hook_sub,

        # Screen 2 — the predict step (footage of placing riders plays around this)
        "predict_num": "1",
        "predict_title": "PREDICT\nTHE REST",
        "predict_sub": "Place the riders at every 4 and 5-star event still to come.",

        # Screen 3 — the counting rule, which is the thing nobody knows, plus the
        # two caveats that have to be on screen rather than only in the caption.
        "counts_title": "ONLY YOUR BEST\nFOUR COUNT",
        "counts_points": [
            "A season counts a rider's best four results",
            "Everything else is discarded, however good",
            "Predict the rest and watch who it crowns",
        ],
        "counts_footnote": "A fun predictor, not official rankings. Points for events "
        "that have not happened yet are estimated.",

        # Screen 4 — CTA. The frictionless bit is the sell.
        "cta_eyebrow": "Play it out yourself",
        "cta_url_big": "ROAD TO\nFINALS",
        "cta_sub": "No account. No email. Just pick.",
        "handle": "@windsurfworldtourstats",
        "url": "windsurfworldtourstats.com/road-to-finals",
    }
