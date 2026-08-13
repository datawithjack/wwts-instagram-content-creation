"""Slalom Session launch carousel slide builder — 6 hardcoded slides.

Announces that The Session now runs for Slalom X and explains how racing
scores differently from the wave/freestyle Session: points come from finish
place, not judged heat scores, and racing carries penalties the wave heats
don't. Scoped to Slalom X only (Foil is a separate squad, covered elsewhere).

Copy is distilled from the in-app rules (frontend FantasyRules.tsx "Slalom
Session" section + utils/sessionSlotLabels.ts). Slalom plays The Session only,
up to 9 picks, same 6-men + 3-women shape as freestyle:
  - Men: 1 Top 5, 2 mid (6-15), 3 wildcards
  - Women: 1 Top 3, 2 wildcards (fleet-permitting)
Scoring is place-based: 1st = 10 down to 10th = 1, 11th+ = 0. The championship
final counts double. Penalties: DQ (premature start) -5, DNF -1, DNS neutral.
The x2 final never scales a penalty, but the 1.25x wildcard applies to a
wildcard slot's whole total. Reuses the fantasy_rules_* slide templates for a
cohesive look with the Freestyle Session post.
"""

# Session teal, lifted from the web app's @theme tokens (session-400), so the
# post matches the mode's colour everywhere the Session appears in-app. Shared
# with the Freestyle Session post so the two read as one series.
SESSION_COLOR = "#2dd4bf"

# One content slide per beat: what dropped, the squad shape, how racing scores,
# and the racing penalties. Each maps to the shared fantasy_rules_game template.
CONTENT_SLIDES = [
    {
        "eyebrow": "NOW LIVE",
        "name": "Event Picks",
        "tagline": "Slalom X fantasy for Fuerteventura, one event at a time.",
        "points": [
            "Pick a Slalom X squad for Fuerteventura",
            "Score points on every single heat they race",
            "No captains, no season commitment",
            "A fresh, standalone leaderboard for this event",
        ],
    },
    {
        "eyebrow": "YOUR SQUAD",
        "name": "9 Picks",
        "tagline": "Six men and three women, nine riders in all.",
        "points": [
            "Men: 1 Top 5, 2 from the 6-15 tier, 3 wildcards",
            "Women: 1 Top 3, plus 2 wildcards",
            "Tiers seeded on last season's Slalom X rankings",
            "Re-use any rider, at every Slalom X event",
        ],
    },
    {
        "eyebrow": "HOW IT SCORES",
        "name": "Finish Place",
        "tagline": "It's a race, so points come from where you cross the line.",
        "points": [
            "1st = 10 points, 2nd = 9, down to 10th = 1",
            "11th and below scores 0",
            "The elimination final counts double",
            "Wildcards still score 1.25x, and swing both ways",
        ],
    },
    {
        "eyebrow": "WATCH OUT",
        "name": "Penalties",
        "tagline": "Racing carries risk the wave heats don't.",
        "points": [
            "A DQ (premature start) costs 5 points",
            "A DNF (did not finish) costs 1 point",
            "A DNS (did not start) is neutral, zero",
            "Wildcards score 1.25x, so a penalty there stings more",
        ],
    },
]


def build_slalom_session_slides() -> list[dict]:
    """Build 6 slide dicts: cover, 4 content slides, cta."""
    slides = []

    # Cover
    slides.append({
        "type": "fantasy_rules_cover",
        "eyebrow": "WINDSURF FANTASY LEAGUE",
        "title": "Slalom X",
        "subtitle": "Fuerteventura Event Picks are now live.",
        "accent_color": SESSION_COLOR,
    })

    # Content slides (what dropped, squad shape, place scoring, penalties)
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
        "subtitle": "Get your Slalom X squad in before picks lock.",
        "deadline": "Picks lock 06:00 local, Wednesday 22 July",
        "cta_line": "Play free. Link in bio",
        "handle": "@windsurfworldtourstats",
        "accent_color": SESSION_COLOR,
    })

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
