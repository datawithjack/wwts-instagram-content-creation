"""Top 10 carousel slide builder — splits 10 rows into 5 slide dicts.

Unified flow (ties and no-ties handled by the same hero card):
cover → hero(all #1s) → table(next chunk) → table(remainder) → cta
"""

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
    title = f"{data['title_gender'].upper()} TOP 10 {data['title_metric'].upper()}"
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
        "show_round": bool(data.get("day")),
    }


def _build_content_slides(common: dict, rows: list[dict]) -> list[dict]:
    """Build the 3 content slides: hero + 2 tables (or table + cta)."""
    tied = _detect_top_ties(rows)

    if tied:
        hero_rows = tied
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

    slides = [{"type": "cover", **common}]
    slides.extend(_build_content_slides(common, rows))
    slides.append({"type": "cta", **common})

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
