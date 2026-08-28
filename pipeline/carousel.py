"""Top 10 carousel slide builder — splits 10 rows into 5 slide dicts.

Unified flow (ties and no-ties handled by the same hero card):
cover → hero(all #1s) → table(next chunk) → table(remainder) → cta

Photo mode (--photos) trades the hero + two tables for a longer, slower read:
cover → 5 photo slides → one table of all 10 → cta
"""

from pipeline.helpers import ordinal
from pipeline.templates import (
    resolve_hero_focus,
    resolve_hero_url,
    resolve_thumb_url,
)

MEDAL_COLOURS = {
    "gold": "#F0C040",
    "silver": "#C0C8D4",
    "bronze": "#CD7F32",
}

ACCENT_WAVES = "#5AB4CC"
ACCENT_JUMPS = "#4DA89E"


def _detect_top_ties(entries: list[dict]) -> list[dict]:
    """Return entries sharing the top score, or [] if only one at the top."""
    if len(entries) < 2:
        return []
    top_score = entries[0]["score"]
    tied = [e for e in entries if e["score"] == top_score]
    return tied if len(tied) >= 2 else []


def _build_common(data: dict) -> dict:
    """Extract shared context fields from data."""
    discipline = data["title_metric"].lower().rstrip("s") + "s"  # "Waves" -> "waves"
    title = data.get("custom_title") or f"{data['title_gender'].upper()} TOP 10 {data['title_metric'].upper()}"
    accent = ACCENT_JUMPS if discipline == "jumps" else ACCENT_WAVES
    return {
        "title": title,
        "discipline": discipline,
        "accent_color": accent,
        "title_gender": data["title_gender"],
        "title_metric": data["title_metric"],
        "year": data.get("title_year"),
        "is_per_event": data.get("is_per_event", False),
        "event_name": data.get("event_name", ""),
        "event_country": data.get("event_country", ""),
        "event_date_start": data.get("event_date_start", ""),
        "event_date_end": data.get("event_date_end", ""),
        "event_stars": data.get("event_stars", 0),
        "show_trick_type": data.get("show_trick_type", False),
        "day": data.get("day"),
        "finals_day": data.get("finals_day", False),
        "so_far": data.get("so_far", False),
        "show_round": bool(data.get("day")) or data.get("finals_day", False) or data.get("so_far", False),
        "perfect_10s_mode": data.get("perfect_10s_mode", False),
        "show_year_sex": data.get("perfect_10s_mode", False),
        "custom_title": data.get("custom_title", ""),
        "custom_subtitle": data.get("custom_subtitle", ""),
    }


def _build_perfect_10s_slides(common: dict, rows: list[dict]) -> list[dict]:
    """Build the table slides for the 'every perfect 10' one-off post.

    Splits N rows into chunks of 5 (e.g. 12 → 5 + 5 + 2). No hero slide.
    """
    chunk_size = 5
    chunks = [rows[i:i + chunk_size] for i in range(0, len(rows), chunk_size)]
    slides = []
    for chunk in chunks:
        slides.append({
            "type": "table",
            "rows": chunk,
            "label": f"Positions {chunk[0]['rank']}\u2013{chunk[-1]['rank']}",
            **common,
        })
    return slides


def _name_class(last_name: str) -> str:
    """Step the surname size down so long names stay inside the slide.

    Same thresholds as the finals carousels: ``last_name`` is everything after
    the forename, so multi-word surnames are the long cases.
    """
    length = len(last_name)
    if length >= 18:
        return "xlong"
    if length >= 13:
        return "long"
    return ""


def _build_photo_slides(common: dict, rows: list[dict], event_id=None) -> list[dict]:
    """Photo mode: the top 5 scores as full-bleed slides, then one table of 10.

    The five slides are the literal top 5 rows, not five distinct riders. A
    rider who puts two waves in the top five gets two slides, which is the
    point: the post ranks waves, and one rider owning several of the best is
    itself the story.

    Countdown order (5th first, #1 last) so the carousel builds rather than
    opening on its own punchline.
    """
    slides = []
    for row in reversed(rows[:5]):
        name = row.get("athlete", "")
        parts = name.split(None, 1) if name else [""]
        first_name = parts[0].upper()
        last_name = parts[1].upper() if len(parts) > 1 else ""
        athlete_id = row.get("athlete_id")

        # Landscape only. A face crop blown up to 1080x1350 looks broken, so
        # with nothing landscape the slide switches layout rather than
        # stretching a headshot into the same footprint.
        action_url = resolve_hero_url(athlete_id, event_id)
        rank = row.get("rank")

        slides.append({
            "type": "wave_photo",
            "rank": rank,
            "rank_label": ordinal(int(rank)).upper() if rank else "",
            "athlete_id": athlete_id,
            "name": name,
            "first_name": first_name,
            "last_name": last_name,
            "name_class": _name_class(last_name),
            "country": row.get("country", ""),
            "score": row.get("score"),
            "round": row.get("round", ""),
            "heat": row.get("heat", ""),
            "counting": row.get("counting", 1),
            "trick_type": row.get("trick_type", ""),
            "modifier": row.get("modifier", ""),
            "photo_mode": "action" if action_url else "portrait",
            "photo_url": action_url or resolve_thumb_url(athlete_id, ""),
            "photo_focus": resolve_hero_focus(athlete_id, event_id),
            **common,
        })

    # All ten on one card. The five above have already been read one at a
    # time, so this is the recap, not the reveal.
    slides.append({
        "type": "table",
        "rows": rows,
        "label": f"Positions {rows[0]['rank']}–{rows[-1]['rank']}",
        "compact": True,
        **common,
    })
    return slides


def _build_content_slides(common: dict, rows: list[dict]) -> list[dict]:
    """Build the 3 content slides: hero + 2 tables (or table + cta)."""
    tied = _detect_top_ties(rows)

    if tied:
        # Group a rider's tied scores together — an eight-way tie with the same
        # name scattered down the card reads as a jumble. Sort is stable, so
        # each rider's own rows keep their leaderboard order.
        hero_rows = sorted(tied, key=lambda r: r["athlete"])
        remaining = [r for r in rows if r not in tied]
    else:
        hero_rows = [rows[0]]
        remaining = rows[1:]

    top_score = hero_rows[0]["score"]
    tie_count = len(hero_rows) if len(hero_rows) >= 2 else 0

    slides = [
        {
            "type": "hero",
            "rows": hero_rows,
            "top_score": top_score,
            "tie_count": tie_count,
            **common,
        },
    ]

    # Split remaining into chunks of max 5
    max_chunk = 5
    chunk1 = remaining[:max_chunk]
    chunk2 = remaining[max_chunk:]

    if chunk1:
        slides.append({
            "type": "table",
            "rows": chunk1,
            "label": f"Positions {chunk1[0]['rank']}\u2013{chunk1[-1]['rank']}",
            **common,
        })

    if chunk2:
        slides.append({
            "type": "table",
            "rows": chunk2,
            "label": f"Positions {chunk2[0]['rank']}\u2013{chunk2[-1]['rank']}",
            **common,
        })

    return slides


def build_slides(data: dict) -> list[dict]:
    """Split top-10 data into carousel slide dicts.

    Expects data with keys: title_gender, title_metric, title_year, entries (list of 10).
    Returns list of 5 slide dicts: cover → hero → table → table → cta.

    The hero slide handles both ties and no-ties with a unified score-first card.
    """
    rows = data["entries"]
    common = _build_common(data)
    # Footnote flag: surface the "dimmed = didn't count" note only when at
    # least one row actually didn't count toward its heat total.
    common["has_non_counting"] = any(not r.get("counting", 1) for r in rows)

    slides = [{"type": "cover", **common}]
    if common["perfect_10s_mode"]:
        slides.extend(_build_perfect_10s_slides(common, rows))
    elif data.get("photo_mode"):
        slides.extend(_build_photo_slides(common, rows, data.get("photo_event_id")))
    else:
        slides.extend(_build_content_slides(common, rows))
    slides.append({"type": "cta", **common})

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
