"""Top 10 carousel slide builder — splits 10 rows into 5 slide dicts.

Supports two flows:
- Standard (no ties): cover → hero → table(2-6) → table(7-10) → cta
- Tied top scores: cover → tied_highlight → tied_grid → table → cta
"""

MEDAL_COLOURS = {
    "gold": "#F0C040",
    "silver": "#C0C8D4",
    "bronze": "#CD7F32",
}


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
    return {
        "title": title,
        "discipline": discipline,
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
    }


def _build_tied_slides(common: dict, tied: list[dict], remaining: list[dict]) -> list[dict]:
    """Build slides for the tied-top-score scenario."""
    tie_score = tied[0]["score"]
    metric_singular = common["title_metric"].upper().rstrip("S")

    max_table = 5
    table_rows = remaining[:max_table]
    cta_rows = remaining[max_table:]

    slides = [
        {"type": "cover", **common},
        {
            "type": "tied_highlight",
            "row": tied[0],
            "tie_count": len(tied),
            "tie_score": tie_score,
            "tie_accent": MEDAL_COLOURS["gold"],
            "tie_label": f"{metric_singular} POINT {common['title_metric'].upper()}",
            **common,
        },
        {
            "type": "tied_grid",
            "rows": tied,
            "tie_accent": MEDAL_COLOURS["gold"],
            **common,
        },
        {
            "type": "table",
            "rows": table_rows,
            "label": f"Positions {table_rows[0]['rank']}\u2013{table_rows[-1]['rank']}",
            **common,
        },
    ]

    if cta_rows:
        slides.append({
            "type": "table_cta",
            "rows": cta_rows,
            "label": f"Positions {cta_rows[0]['rank']}\u2013{cta_rows[-1]['rank']}",
            **common,
        })
    else:
        slides.append({"type": "cta", **common})

    return slides


def _build_standard_slides(common: dict, rows: list[dict]) -> list[dict]:
    """Build slides for the standard (no-tie) scenario."""
    return [
        {"type": "cover", **common},
        {
            "type": "hero",
            "row": rows[0],
            "podium_colour": {"bg": "rgba(240,192,64,0.08)", "accent": MEDAL_COLOURS["gold"]},
            **common,
        },
        {
            "type": "table",
            "rows": rows[1:6],
            "label": "Positions 2\u20136",
            **common,
        },
        {
            "type": "table",
            "rows": rows[6:10],
            "label": "Positions 7\u201310",
            **common,
        },
        {"type": "cta", **common},
    ]


def build_slides(data: dict) -> list[dict]:
    """Split top-10 data into carousel slide dicts.

    Expects data with keys: title_gender, title_metric, title_year, entries (list of 10).
    Returns list of slide dicts, each with 'type' and shared context fields.

    If 2+ entries share the top score, uses the tied flow instead of the standard flow.
    """
    rows = data["entries"]
    common = _build_common(data)
    tied = _detect_top_ties(rows)

    if tied:
        remaining = [e for e in rows if e not in tied]
        slides = _build_tied_slides(common, tied, remaining)
    else:
        slides = _build_standard_slides(common, rows)

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
