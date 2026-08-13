"""Tour-rules explainer reel — content builder for a single animated page.

Unlike the fantasy_rules carousel (swipeable static slides covering Tour + Session
at a high level), this is a vertical 1080x1920 video reel that explains ONE game —
"The Tour" — in animated screens (cover -> picks -> one-pick rule -> captains ->
scoring -> best-4 -> CTA). Copy is distilled from the in-app rules page
(frontend/src/pages/fantasy/FantasyRules.tsx — "The Tour" tab).

Returns a flat dict consumed directly by templates/tour_rules_reel.html — NOT a list
of carousel slide dicts.
"""

# Tour accent — the canonical muted IG cyan (base.html --color-accent). Kept as a
# constant so the data builder can hand it to the template if ever themed.
TOUR_ACCENT = "#5AB4CC"


def build_tour_rules_reel_data() -> dict:
    """Build the content dict for the Tour-rules reel."""
    return {
        "title": "THE TOUR",
        "tagline": "One squad. The full season. Every pick matters.",
        "accent_color": TOUR_ACCENT,

        # Screen 2 — pick structure (5 per event)
        "picks_title": "5 PICKS PER EVENT",
        "picks": [
            {"slot": "Man 1", "tier": "Top 5 ranked men", "kind": "men"},
            {"slot": "Man 2", "tier": "Men ranked 6–15", "kind": "men"},
            {"slot": "Woman 1", "tier": "Top 5 ranked women", "kind": "women"},
            {"slot": "Woman 2", "tier": "Women ranked 6–15", "kind": "women"},
            {"slot": "Wildcard", "tier": "Anyone outside the top 15", "kind": "wildcard"},
        ],

        # Screen 3 — one-pick rule
        "one_pick_title": "ONE-PICK RULE",
        "one_pick_text": "Each athlete can be picked once per season. Use them and they’re gone.",

        # Screen 4 — captains
        "captains_title": "TEAM CAPTAINS",
        "captains_points": [
            "1 men’s & 1 women’s captain from the Top 5",
            "Captains can be picked twice",
            "Locked once set, no scoring bonus",
        ],

        # Screen 5 — scoring (position-based). Trimmed to 6 rows for phone legibility.
        "scoring_title": "SCORING",
        "scoring_subtitle": "Points are based on where your riders finish.",
        "scoring_rows": [
            {"place": "1st", "points": "10,000"},
            {"place": "2nd", "points": "8,500"},
            {"place": "3rd", "points": "7,650"},
            {"place": "5th=", "points": "6,130"},
            {"place": "9th=", "points": "4,441"},
            {"place": "17th=", "points": "2,673"},
        ],

        # Screen 6 — counting events
        "counting_title": "BEST 4 EVENTS",
        "counting_text": "Your best 4 event scores build your season total.",

        # Screen 7 — CTA + brand reveal
        "cta_headline": "PLAY NOW",
        "cta_subtitle": "Build your team before the next event.",
        "handle": "@windsurfworldtourstats",
        "url": "windsurfworldtourstats.com",
    }
