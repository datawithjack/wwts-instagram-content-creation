"""How-to-make-picks explainer reel — content builder.

The conversion-driver post in the Fantasy League launch series. A short reel that
intercuts live picks screen-record footage (pipeline/screen_record.py) with branded
explainer cards, hammering the one thing players get wrong: Save Draft keeps your
progress but does NOT enter you, Confirm & Lock is the step that actually does.

This module returns ONLY the card copy (static, no live data). The footage is spliced
between cards later by pipeline/reel_edit.py. Card styling mirrors the fantasy app
(tour-400 cyan, captain-400 amber warning, Bebas Neue) and the sibling reels. Consumed
by templates/how_to_pick_reel.html.

Deadline: GC 2026 picks lock at 6am Gran Canaria time on 4 Jul 2026 — the CTA drives
to that.
"""

# Accents mirror the app + sibling reels.
ACCENT_TOUR = "#22d3ee"     # confirm / "do this"
ACCENT_WARN = "#facc15"     # save-draft trap (captain-400 amber)


def build_how_to_pick_reel_data() -> dict:
    """Build the content dict for the how-to-make-picks explainer reel."""
    return {
        "accent_tour": ACCENT_TOUR,
        "accent_warn": ACCENT_WARN,

        # Screen 1 — hook
        "hook_eyebrow": "Windsurf Fantasy League",
        "hook_title": "MAKING\nYOUR PICKS",
        "hook_sub": "To draft, or to confirm?",

        # Screen 2 — build your squad (footage of tapping picks plays around this)
        "build_num": "1",
        "build_title": "BUILD YOUR SQUAD",
        "build_sub": "Tap to choose your riders: 2 men, 2 women, 1 wildcard.",

        # Screen 3 — the two options and their trade-offs
        "contrast_title": "SAVE DRAFT OR\nCONFIRM & LOCK",
        "save": {
            "label": "Save Draft",
            "points": [
                "Keep editing your picks until the deadline",
                "You can't see other people's teams yet",
            ],
        },
        "confirm": {
            "label": "Confirm & Lock",
            "points": [
                "Your team is confirmed and locked",
                "Now you can see everyone's confirmed teams",
            ],
            "warning": "Risky: if an athlete drops out, you lose that pick",
        },
        "contrast_footnote": "A saved draft auto-confirms at 6am on day one of the "
        "event, so you're always entered.",

        # Screen 4 — confirm & lock (footage of the Confirm & Lock button plays here)
        "lock_num": "2",
        "lock_title": "CONFIRM & LOCK",
        "lock_sub": "No confirm, no entry. Lock it in before picks close.",

        # Screen 5 — static "picks close" date/time (GC 2026 runs 4-12 Jul; picks lock
        # at 6am Gran Canaria time on day one).
        "countdown_eyebrow": "Gran Canaria · Picks close",
        "lock_time": "6AM",
        "lock_date": "SAT 4 JULY",
        "lock_tz": "Gran Canaria time",
        "countdown_sub": "Sign up and lock your team",
        "handle": "@windsurfworldtourstats",
        "url": "windsurfworldtourstats.com",
    }
