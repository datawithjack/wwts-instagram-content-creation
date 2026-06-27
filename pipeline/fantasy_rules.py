"""Fantasy Rules overview carousel slide builder — 4 hardcoded slides.

High-level explainer for the Windsurf Fantasy League. Copy distilled from the
in-app rules page (frontend FantasyRules.tsx / onboardingContent.ts).

There are two games per event — The Tour (season-long) and The Session
(one-off per-event). This overview gives each a single summary slide; the full
rules of each game are covered in their own follow-up posts.
"""

# Game accent colours, lifted from the web app's @theme tokens
# (frontend/src/index.css): Tour = cyan tour-400, Session = teal session-400.
# Tour cyan is the product's primary brand accent, so the cover + CTA use it.
TOUR_COLOR = "#22d3ee"
SESSION_COLOR = "#2dd4bf"
ACCENT_COLOR = TOUR_COLOR

# The two games, one summary slide each.
GAMES = [
    {
        "name": "The Tour",
        "tagline": "One squad. The full season.",
        "color": TOUR_COLOR,
        "points": [
            "Pick 5 riders each event — 2 men, 2 women & a wildcard",
            "Scored on where your riders finish on tour",
            "Your best events build a season-long total",
        ],
    },
    {
        "name": "The Session",
        "tagline": "One event. Every heat.",
        "color": SESSION_COLOR,
        "points": [
            "Pick 8 riders for a single event",
            "Score points every heat your riders surf",
            "A fresh, standalone leaderboard each time",
        ],
    },
]


def build_fantasy_rules_slides() -> list[dict]:
    """Build 4 slide dicts: cover → The Tour → The Session → cta."""
    slides = []

    # Cover
    slides.append({
        "type": "fantasy_rules_cover",
        "eyebrow": "WINDSURF FANTASY LEAGUE",
        "title": "How It Works",
        "subtitle": "Two ways to play. Same windsurfing action.",
        "accent_color": ACCENT_COLOR,
    })

    # One slide per game
    for i, game in enumerate(GAMES, 1):
        slides.append({
            "type": "fantasy_rules_game",
            "eyebrow": f"WAY {i} OF 2",
            "name": game["name"],
            "tagline": game["tagline"],
            "points": game["points"],
            "accent_color": game["color"],
        })

    # CTA
    slides.append({
        "type": "fantasy_rules_cta",
        "headline": "PLAY NOW",
        "subtitle": "Get your team in before the next event.",
        "cta_line": "Sign up — link in bio",
        "handle": "@windsurfworldtourstats",
        "accent_color": ACCENT_COLOR,
    })

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
