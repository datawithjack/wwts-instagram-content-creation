"""Session-vs-Tour product infographic reel — content builder.

A single animated 1080x1920 reel contrasting the two fantasy game modes as products:
The Tour (one squad, whole season) vs The Session (one event, drop in any time). A
spotlight on each mode, then a head-to-head comparison. Static copy — no live data.

Copy is distilled from the in-app fantasy hub / rules (frontend FantasyHub +
FantasyRules). Returns a flat dict consumed by templates/session_vs_tour_reel.html.
"""

# Mode accents mirror the app: Tour = tour-400 (cyan), Session = session-400 (teal).
ACCENT_TOUR = "#22d3ee"
ACCENT_SESSION = "#2dd4bf"


def build_fantasy_modes_reel_data() -> dict:
    """Build the content dict for the Session-vs-Tour infographic reel."""
    return {
        "accent_tour": ACCENT_TOUR,
        "accent_session": ACCENT_SESSION,

        # Screen 1 — hook
        "hook_eyebrow": "Windsurf Fantasy League",
        "hook_sub": "One league. Two ways to play.",

        # Screen 2 — The Tour spotlight
        "tour": {
            "name": "THE TOUR",
            "eyebrow": "The season-long game",
            "points": [
                "5 picks every event: 2 men, 2 women, 1 wildcard",
                "Each athlete can be picked only once all season",
                "So your squad changes event to event",
                "Captains are the exception, pick them twice",
                "Your best 4 events make your season score",
            ],
        },

        # Screen 3 — The Session spotlight
        "session": {
            "name": "THE SESSION",
            "eyebrow": "The one-event game",
            "points": [
                "One event at a time",
                "8 picks per event: 4 men, 4 women",
                "Re-use any rider, every event",
                "No season commitment",
                "Scored on every single heat",
            ],
        },

        # Screen 4 — head-to-head
        "comparison": [
            {"label": "Commitment", "tour": "Whole season", "session": "One event"},
            {"label": "Picks / event", "tour": "5", "session": "8"},
            {"label": "Re-use a rider", "tour": "Once a season", "session": "Every event"},
            {"label": "Scored on", "tour": "Final results", "session": "Every heat"},
            {"label": "Best for", "tour": "Superfans", "session": "Casual fans"},
        ],

        # Screen 5 — CTA
        "cta_headline": "Sign up and get involved",
        "cta_subtitle": "Link in bio",
        "handle": "@windsurfworldtourstats",
        "url": "windsurfworldtourstats.com",
    }
