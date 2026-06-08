"""Event picks carousel slide builder.

Turns a small picks data file (data/picks/<event>.json) into a list of slide
dicts for a pre-event "Our picks" editorial carousel:

    cover -> rank 4 -> rank 3 -> rank 2 -> rank 1   (suspense reveal)

Data model (input)::

    {
      "event": {"name", "venue", "dates", "stars", "tour", "mode", "cover_sub"},
      "picks": [{"rank", "label", "name", "sail", "nation", "brand", "photo", "why"}]
    }

Conventions:
- ``{{...}}`` inside a ``why`` string marks the one phrase to highlight; it is
  rendered as ``<b>...</b>``.
- ``rank == 1`` is the winner: the slide carries ``is_winner`` so the template
  can apply the gold accent.
- ``photo: null`` (or a path that does not exist) -> ``has_photo`` False, so the
  template renders the dashed placeholder.
"""
import json
import os
import re

from pipeline.helpers import nationality_to_iso

# Single-event fan picks ("my top 4") are editorial/opinion content, so they use
# the editorial violet accent; multi-event Tour-mode picks use the muted cyan.
# Per repo brand the winner highlight is the existing gold (not orange).
ACCENT_PICKS = "#9478B5"
ACCENT_TOUR = "#5AB4CC"
WINNER_COLOR = "#F0C040"

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_HIGHLIGHT_RE = re.compile(r"\{\{(.+?)\}\}")


def parse_highlight(text: str) -> str:
    """Replace ``{{phrase}}`` markers with ``<b>phrase</b>``."""
    if not text:
        return ""
    return _HIGHLIGHT_RE.sub(r"<b>\1</b>", text)


def strip_markers(text: str) -> str:
    """Return the plain text with ``{{...}}`` markers removed (braces only)."""
    if not text:
        return ""
    return _HIGHLIGHT_RE.sub(r"\1", text)


def _resolve_pick_photo(photo: str) -> str:
    """Resolve a pick photo path to a ``file://`` URL, or "" if it doesn't exist.

    Relative paths are resolved against the repo root. A missing file (or None)
    returns "" so the caller renders the dashed placeholder.
    """
    if not photo:
        return ""
    path = photo if os.path.isabs(photo) else os.path.join(REPO_ROOT, photo)
    if os.path.exists(path):
        return "file:///" + os.path.abspath(path).replace(os.sep, "/")
    return ""


def load_picks_data(path: str) -> dict:
    """Load a picks data file (JSON) from disk."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_slides(data: dict) -> list[dict]:
    """Split picks data into carousel slide dicts (cover + one per pick)."""
    event = data.get("event", {})
    mode = event.get("mode", "picks")
    accent = ACCENT_TOUR if mode == "tour" else ACCENT_PICKS

    common = {
        "accent_color": accent,
        "event_name": event.get("name", ""),
        "venue": event.get("venue", ""),
        "dates": event.get("dates", ""),
        "stars": event.get("stars", 0),
        "tour": event.get("tour", ""),
        "category": event.get("category", ""),
        "mode": mode,
    }

    slides = [{
        "type": "picks_cover",
        "cover_sub": event.get("cover_sub", ""),
        **common,
    }]

    # Reveal in descending rank order (4 -> 1) regardless of input order.
    picks = sorted(data.get("picks", []), key=lambda p: p.get("rank", 0), reverse=True)
    for pick in picks:
        rank = pick.get("rank", 0)
        photo_url = _resolve_pick_photo(pick.get("photo"))
        nation = pick.get("nation", "")
        slides.append({
            "type": "picks_rider",
            "rank": rank,
            "label": pick.get("label") or "",
            "name": pick.get("name", ""),
            "sail": pick.get("sail", ""),
            "nation": nation,
            "nation_iso": nationality_to_iso(nation),
            "brand": pick.get("brand") or "",
            "photo_url": photo_url,
            "has_photo": bool(photo_url),
            "why_html": parse_highlight(pick.get("why", "")),
            "is_winner": rank == 1,
            "winner_color": WINNER_COLOR,
            **common,
        })

    # Closing CTA — matches every other series (reuses shared slide_cta.html).
    slides.append({"type": "cta", "hide_footer": True, **common})

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
