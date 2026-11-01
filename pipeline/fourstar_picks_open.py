"""Wissant "picks are open" carousel — 6 hardcoded slides.

The follow-up to pipeline/fourstar_session.py, which announced the event and
explained the two conditions gating it. Both have now moved: the start list has
cleared the 20-rider threshold, so the event is live for picks, and the slot
tiers are unlocking one category at a time as riders enter.

So this post says three things and stops: picks are open, go and draft a team,
and more slots will appear as the start list grows.

**Scoped to Wissant alone**, same as the announcement, and for the same reason:
Tiree is the other 2026 4-star on the fantasy season and is still unconfirmed.

The screenshots are shot fresh rather than reused. The announcement's shots are
of the *locked* state at 12 riders, so putting either on a post that says picks
are open would have the picture contradict the copy. They are committed under
their own names (``wissant_open_*``) rather than overwriting the originals: the
announcement's state is gone for good and cannot be re-shot.

Reuses the announcement's cover template and the Session teal, so the two read
as one story rather than two unrelated posts.
"""
from pipeline.fourstar_session import (
    SESSION_COLOR,
    logo_url,
    screenshot_url,
)

# The entry threshold the event had to clear, not the current start list. The
# app stops displaying a total once the gate is passed (the hub card swaps its
# counter for a countdown), so a live count cannot be read back off the
# screenshots the way the announcement's "12" could, and a hand-set one would
# be stale by the time the post lands. The threshold is a fixed fact and says
# the same thing: the event is open.
ENTRY_THRESHOLD = 20

# Slide 5 — the reason nobody has to sit refreshing the page. Same slot in the
# carousel as the announcement's version, but the promise has moved on: the
# thing worth being told about is no longer "picks open", it is "your locked
# slots opened".
#
# Email and Instagram are one point, not two: they are the same promise sent
# down two pipes, and splitting them spent a line saying "we will tell you"
# twice.
#
# The last point is the one piece of advice in the post: with tiers still
# unlocking, Confirm & Lock freezes a part-built team, and a saved draft
# auto-confirms at the deadline anyway. Drafting costs nothing and confirming
# early costs slots, so every slide that mentions picking says draft.
MORE_TO_COME = {
    "eyebrow": "MORE TO COME",
    "name": "Slots Keep Opening",
    "tagline": "Your team is not finished. More entries mean more slots to fill.",
    "points": [
        "Each new entry can unlock another slot",
        "Updates via email and Instagram when new slots open",
        "So save a draft, do not confirm yet",
    ],
}


def build_fourstar_picks_open_slides() -> list[dict]:
    """Build 6 slide dicts: cover, 3 screenshots, more-to-come, cta."""
    slides = [
        {
            "type": "fourstar_cover",
            "eyebrow": "THE SESSION",
            # The news is the big type, same rule as the announcement cover.
            "lede_lines": ["Wissant Wave Classic"],
            "lede_accent": "Picks Are Open",
            "event_name": "Wissant Wave Classic",
            "discipline": "Wave",
            "stars": 4,
            "dates": "12 to 20 Sept 2026",
            # The one fact nothing else on the slide carries: the gate that
            # held this event back has been cleared, and by how much.
            "subtitle": (
                f"The start list has passed the {ENTRY_THRESHOLD} riders it "
                "needed. Log in and start drafting your team."
            ),
            "cta_line": "Draft your team · windsurfworldtourstats.com",
            # The CTA carries the URL, so the shared watermark would print the
            # same address twice on one slide.
            "hide_footer": True,
            "logo_url": logo_url("wissant-wave-classic.png"),
            "logo_alt": "Wissant Wave Classic 2026 event poster",
            "logo_width": 260,
            "accent_color": SESSION_COLOR,
        },
        # The hub card in its open state. It is the cleanest single proof that
        # the gate is gone: the entry counter it used to carry is replaced by a
        # countdown and a button into the team builder.
        #
        # The card shows the green "Pick Session Team" CTA, which is what a
        # reader who has not drafted yet will meet. The credentialed account
        # used for the capture already holds a partial Wissant draft, so its
        # own card renders the amber "Finish Session Team" instead: a state no
        # new player can see, and misleading on a post inviting them to start.
        # See scratchpad shoot_pick_cta.py; the button was re-rendered into the
        # app's own no-picks markup (fantasySessionLink.ts:92) before the shot.
        {
            "type": "screenshot",
            "eyebrow": "IT IS LIVE",
            "title": "Open Now",
            "image_url": screenshot_url("wissant_open_hub_card.png"),
            "alt": "Wissant Wave Classic card showing picks closing in six days and a Pick Session Team button",
            "lead": "Picks close 12 September, 06:00.",
            "caption": "Tap it and the team builder opens on the slots you can fill today.",
            "max_height": 560,
            "accent_color": SESSION_COLOR,
        },
        # Wildcards open, ranked tiers still locked. Shown rather than
        # described, because the slot rows spell out their own conditions and
        # that is the whole of slide 4's promise in one picture.
        {
            "type": "screenshot",
            "eyebrow": "NOT ALL OF THEM",
            "title": "Some Still Locked",
            "tagline": "Wildcard slots are open. The ranked ones are still filling.",
            "image_url": screenshot_url("wissant_open_slots.png"),
            "alt": "Men's picks with three wildcard slots filled and three ranked slots locked",
            "lead": "Fill what is open, leave the rest.",
            "caption": "Every locked slot names what it is waiting for, so draft now and let confirming wait.",
            "max_height": 640,
            "accent_color": SESSION_COLOR,
        },
        # The action bar, shot on the live site. While the start list is
        # provisional the product gives Save Draft the filled teal and demotes
        # Confirm & Lock to an outline (#190), so the button treatment argues
        # the post's case before a word is read, and the reader recognises the
        # bar when they reach the bottom of the picks page.
        #
        # Two other shots were tried in this slot and dropped. The draft-saved
        # dialog ("not locked in yet") says it in words but arrives a step
        # later, after a click this slide is still asking for. The confirm
        # dialog carries an amber warning to the same effect, but it lists the
        # account's own unconfirmed team, and the app keeps a draft private
        # until it is confirmed.
        {
            "type": "screenshot",
            "eyebrow": "ONE PIECE OF ADVICE",
            "title": "Save The Draft",
            "tagline": "The app leads with it, and so should you.",
            "image_url": screenshot_url("wissant_open_action_bar.png"),
            "alt": "The picks action bar with Save Draft as the filled primary button and Confirm & Lock demoted to an outline",
            "lead": "Save Draft, not Confirm & Lock.",
            "caption": "A draft stays editable and enters you automatically when picks close.",
            "max_height": 320,
            "accent_color": SESSION_COLOR,
        },
        {
            "type": "fantasy_rules_game",
            "eyebrow": MORE_TO_COME["eyebrow"],
            "name": MORE_TO_COME["name"],
            "tagline": MORE_TO_COME["tagline"],
            "points": MORE_TO_COME["points"],
            "accent_color": SESSION_COLOR,
        },
        {
            "type": "fantasy_rules_cta",
            "headline": "GET DRAFTING",
            "subtitle": "Log in, fill the open slots, save a draft. Come back for the rest.",
            "deadline": "Picks close 06:00 local, 12 September 2026",
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
