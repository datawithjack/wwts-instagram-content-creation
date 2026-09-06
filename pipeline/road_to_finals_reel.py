"""Road to Finals promo reel — content builder.

A short reel promoting the title-race predictor at
windsurfworldtourstats.com/road-to-finals. Branded explainer cards
(templates/road_to_finals_reel.html) intercut with live screen-record footage of
the predictor itself (pipeline/screen_record_rtf.py), stitched by
pipeline/rtf_reel_edit.py.

Three cards open the reel and one closes it: the race is heating up, here is the
podium in both fleets, who do you think wins -- then the footage answers it, and the
CTA sends you to go and answer it yourself.

Nothing on the podium card is typed in. The riders, their points and their faces all
come from the same endpoint the predictor page uses, so a card and the footage behind
it cannot disagree, and a month from now the card is a different podium rather than a
stale one asserted as today's.
"""
import os

import requests

from pipeline.api import API_BASE_URL

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FACES_DIR = os.path.join(_REPO_ROOT, "assets", "photos", "faces")

# Accents mirror the app + sibling reels.
ACCENT_TOUR = "#22d3ee"
ACCENT_WARN = "#facc15"

PODIUM_SIZE = 3


def _face_url(athlete_id, fallback: str | None) -> str:
    """The best available headshot for one rider.

    Prefers the repo's own curated face crop, which is squared and tightly framed;
    falls back to the ranking feed's picture, which every ranked rider has. The card
    renders both as circles, so the two sources sit together without reading as two
    sources.
    """
    for ext in ("jpg", "jpeg", "png", "webp"):
        path = os.path.join(_FACES_DIR, f"{athlete_id}.{ext}")
        if os.path.exists(path):
            return "file:///" + os.path.abspath(path).replace(os.sep, "/")
    return fallback or ""


def _podium(rows: list) -> list:
    """The top three of one fleet, shaped for the card."""
    return [
        {
            "rank": row.get("rank") or i + 1,
            "name": row.get("athlete_name") or "Unknown",
            "points": f"{int(row.get('total_points') or 0):,}",
            "face": _face_url(row.get("athlete_id"), row.get("image_url")),
        }
        for i, row in enumerate(rows[:PODIUM_SIZE])
    ]


def fetch_title_race(year: int, timeout: int = 30) -> dict:
    """Both fleets' podiums and the events still to come.

    Uses the same endpoint the predictor page does (`/rankings/season/{year}`).
    """
    resp = requests.get(
        f"{API_BASE_URL}/rankings/season/{year}",
        params={"discipline": "wave", "top": 20},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    standings = data.get("standings", {})
    return {
        "men": _podium(standings.get("Men", [])),
        "women": _podium(standings.get("Women", [])),
        "events_left": len([e for e in data.get("events", []) if e.get("predictable")]),
        "year": data.get("year", year),
    }


# Small counts read better as words in a headline. Mirrors the page's own rule.
_COUNT_WORDS = [
    "No", "One", "Two", "Three", "Four", "Five", "Six",
    "Seven", "Eight", "Nine", "Ten",
]


def build_road_to_finals_reel_data(year: int = 2026) -> dict:
    """Build the content dict for the Road to Finals promo reel cards."""
    try:
        race = fetch_title_race(year)
    except Exception as exc:  # network, shape change, anything
        print(f"Standings fetch failed ({exc}); building the podium-free cards.")
        race = None

    if race:
        left = race["events_left"]
        word = _COUNT_WORDS[left] if left < len(_COUNT_WORDS) else str(left)
        # No numeral in the hook: the card is a mood, and the count belongs on the
        # podium card where there are numbers to read anyway.
        podium_sub = f"{word} 4 and 5-star events still to sail"
        men, women = race["men"], race["women"]
        season_year = race["year"]
    else:
        podium_sub = "Events still to sail"
        men, women = [], []
        season_year = year

    return {
        "accent_tour": ACCENT_TOUR,
        "accent_warn": ACCENT_WARN,

        # Screen 1 — the mood. No numbers, no names: this is the "stop scrolling" beat.
        "hook_eyebrow": f"{season_year} Wave World Tour",
        "hook_title": "THE WORLD\nTITLE RACE",
        "hook_kicker": "is heating up...",

        # Screen 2 — where both fleets actually stand.
        "podium_title": "AS IT STANDS",
        "podium_men_label": "Men",
        "podium_women_label": "Women",
        "podium_men": men,
        "podium_women": women,
        "podium_sub": podium_sub,

        # Screen 3 — the question the footage then answers.
        "question_title": "WHO DO\nYOU THINK\nWILL WIN?",
        "question_sub": "Predict every event left and see who it crowns.",

        # Screen 4 — CTA. The frictionless bit is the sell.
        "cta_eyebrow": "Play it out yourself",
        "cta_url_big": "ROAD TO\nFINALS",
        "cta_sub": "No account. No email. Just pick.",
        "cta_footnote": "A fun predictor, not official rankings. Points for events "
        "that have not happened yet are estimated.",
        "handle": "@windsurfworldtourstats",
        "url": "windsurfworldtourstats.com/road-to-finals",
    }
