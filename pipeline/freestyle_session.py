"""Freestyle Session launch carousel slide builder — 6 hardcoded slides.

Announces that The Session now runs for freestyle (Fuerteventura 2026) and
explains how its pick structure differs from the wave Session: more wildcard
slots, so squads vary more from player to player. Ends by teasing the Slalom
Session, which drops next.

Copy is distilled from the in-app rules (frontend FantasyRules.tsx "Freestyle
Session" section + utils/sessionSlotLabels.ts). Freestyle plays The Session
only, up to 9 picks:
  - Men: 1 Top 5, 2 mid (6-15), 3 wildcards      → 3 wildcards (wave has 1)
  - Women: 1 Top 3, 2 wildcards (fleet-permitting) → 2 wildcards (wave has 1)
So freestyle hands you 5 wildcard slots vs the wave Session's 2. Wildcards draw
from riders outside the seeded tiers and still score 1.25x, so they are the
variation lever. Reuses the fantasy_rules_* slide templates for a cohesive look.
"""

# Session teal, lifted from the web app's @theme tokens (session-400), so the
# post matches the mode's colour everywhere the Session appears in-app.
SESSION_COLOR = "#2dd4bf"

# One content slide per beat: what dropped, the squad shape, the wildcard change,
# and the slalom teaser. Each maps to the shared fantasy_rules_game template.
CONTENT_SLIDES = [
    {
        "eyebrow": "NOW LIVE",
        "name": "The Session",
        "tagline": "Freestyle fantasy, one event at a time.",
        "points": [
            "Pick a freestyle squad for Fuerteventura 2026",
            "Score points on every single heat they surf",
            "No captains, no season commitment",
            "A fresh, standalone leaderboard for this event",
        ],
    },
    {
        "eyebrow": "YOUR SQUAD",
        "name": "6 to 9 Picks",
        "tagline": "Six men, plus three women when the fleet is big enough.",
        "points": [
            "Men: 1 Top 5, 2 from the 6-15 tier, 3 wildcards",
            "Women: 1 Top 3, plus 2 wildcards",
            "Tiers seeded on last season's freestyle rankings",
            "Re-use any rider, at every freestyle event",
        ],
    },
    {
        "eyebrow": "WHAT'S CHANGED",
        "name": "More Wildcards",
        "tagline": "Freestyle hands you 5 wildcard slots, not 2.",
        "points": [
            "The wave Session gives 2 wildcards. Freestyle gives 5",
            "3 men's wildcards and 2 women's wildcards",
            "Wildcards pick from riders outside the seeded tiers",
            "More room to gamble, and every squad looks different",
        ],
    },
    {
        "eyebrow": "UP NEXT",
        "name": "Slalom",
        "tagline": "The Session for racing is dropping soon.",
        "points": [
            "Slalom X and Foil, picked as separate squads",
            "Same 6 men plus 3 women shape, 3 wildcards",
            "Scored on finish place: 1st = 10 down to 10th = 1",
            "The winners' final counts double",
        ],
    },
]


def build_freestyle_session_slides() -> list[dict]:
    """Build 6 slide dicts: cover, 4 content slides, cta."""
    slides = []

    # Cover
    slides.append({
        "type": "fantasy_rules_cover",
        "eyebrow": "WINDSURF FANTASY LEAGUE",
        "title": "Freestyle",
        "subtitle": "The Session is now live for Fuerteventura 2026.",
        "accent_color": SESSION_COLOR,
    })

    # Content slides (what dropped, squad shape, wildcards, slalom teaser)
    for slide in CONTENT_SLIDES:
        slides.append({
            "type": "fantasy_rules_game",
            "eyebrow": slide["eyebrow"],
            "name": slide["name"],
            "tagline": slide["tagline"],
            "points": slide["points"],
            "accent_color": SESSION_COLOR,
        })

    # CTA
    slides.append({
        "type": "fantasy_rules_cta",
        "headline": "PLAY NOW",
        "subtitle": "Get your Fuerteventura freestyle squad in before lock.",
        "cta_line": "Play free. Link in bio",
        "handle": "@windsurfworldtourstats",
        "accent_color": SESSION_COLOR,
    })

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
