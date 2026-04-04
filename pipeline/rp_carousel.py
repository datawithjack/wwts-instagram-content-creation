"""Rider profile carousel slide builder — splits rider data into 4-5 slide dicts.

Slides: cover → hero (with stats) → waves → [jumps] → cta
"""

from pipeline.helpers import ordinal

ACCENT_WAVES = "#5AB4CC"
ACCENT_JUMPS = "#4DA89E"

PLACEMENT_COLORS = {
    1: "#F0C040",  # gold
    2: "#B0C4DE",  # silver — light steel blue
    3: "#CD7F32",  # bronze
}
PLACEMENT_DEFAULT = "#4DA89E"  # muted jade


def _has_jump(data: dict) -> bool:
    """Detect wave+jump event by presence of best_jump."""
    return bool(data.get("best_jump"))


def _fmt_score(val: float) -> str:
    return f"{val:.2f}"


def _build_common(data: dict) -> dict:
    """Extract shared context fields passed to every slide."""
    is_jump = _has_jump(data)
    name = data.get("athlete_name", "")
    parts = name.split() if name else []
    return {
        "accent_color": ACCENT_JUMPS if is_jump else ACCENT_WAVES,
        "event_name": data.get("event_name", ""),
        "event_country": data.get("event_country", ""),
        "event_date_start": data.get("event_date_start", ""),
        "event_date_end": data.get("event_date_end", ""),
        "event_tier": data.get("event_tier", 0),
        "athlete_name": name,
        "athlete_firstname": parts[0].upper() if parts else "",
        "athlete_surname": parts[-1].upper() if parts else "",
        "athlete_id": data.get("athlete_id"),
        "athlete_photo_url": data.get("athlete_photo_url", ""),
        "athlete_country": data.get("athlete_country", ""),
        "athlete_sail_number": data.get("athlete_sail_number", ""),
    }


def _build_stats(data: dict) -> list[dict]:
    """Build the stats list for the overview slide."""
    placement = data.get("placement", 0)

    # Get round for best wave (rank 1 in top_waves)
    top_waves = data.get("top_waves", [])
    best_wave_round = top_waves[0].get("round", "") if top_waves else ""

    # Get round for best jump (rank 1 in top_jumps)
    top_jumps = data.get("top_jumps") or []
    best_jump_round = top_jumps[0].get("round", "") if top_jumps else ""

    stats = [
        {
            "label": "Placing",
            "value": ordinal(placement),
            "detail": "",
            "is_placing": True,
        },
        {
            "label": "Best Heat",
            "value": _fmt_score(data.get("best_heat", 0)),
            "detail": data.get("best_heat_round", ""),
            "is_placing": False,
        },
        {
            "label": "Best Wave",
            "value": _fmt_score(data.get("best_wave", 0)),
            "detail": best_wave_round,
            "is_placing": False,
        },
    ]
    if _has_jump(data):
        stats.append({
            "label": "Best Jump",
            "value": _fmt_score(data.get("best_jump", 0)),
            "detail": best_jump_round,
            "is_placing": False,
        })
    else:
        stats.append({
            "label": "Average Wave",
            "value": _fmt_score(data.get("avg_wave", 0)),
            "detail": "",
            "is_placing": False,
        })
    return stats


def build_slides(data: dict) -> list[dict]:
    """Split rider profile data into 4-5 carousel slide dicts."""
    common = _build_common(data)
    is_jump = _has_jump(data)

    slides = []

    # Slide 1: Cover — use photo variant when athlete photo is available
    placement = data.get("placement", 0)
    has_photo = bool(common.get("athlete_photo_url"))
    slides.append({
        "type": "rp_cover_photo" if has_photo else "rp_cover",
        "hide_footer": False,
        "placement": placement,
        "placement_ordinal": ordinal(placement),
        "placement_color": PLACEMENT_COLORS.get(placement, PLACEMENT_DEFAULT),
        **common,
    })

    # Slide 2: Hero + Stats (merged)
    slides.append({
        "type": "rp_hero",
        "placement": data.get("placement", 0),
        "placement_ordinal": ordinal(data.get("placement", 0)),
        "stats": _build_stats(data),
        **common,
    })

    # Slide 3: Top Waves
    top_waves = []
    for wave in data.get("top_waves", []):
        top_waves.append({
            "rank": wave["rank"],
            "score": _fmt_score(wave["score"]),
            "round": wave["round"],
        })
    slides.append({
        "type": "rp_waves",
        "top_waves": top_waves,
        **common,
    })

    # Slide 4 (optional): Top Jumps — only for wave+jump events
    if is_jump and data.get("top_jumps"):
        top_jumps = []
        for jump in data.get("top_jumps", []):
            top_jumps.append({
                "rank": jump["rank"],
                "score": _fmt_score(jump["score"]),
                "round": jump["round"],
                "move": jump.get("move", ""),
            })
        slides.append({
            "type": "rp_jumps",
            "top_jumps": top_jumps,
            **common,
        })

    # Final slide: CTA
    slides.append({"type": "cta", "hide_footer": True, **common})

    # Add slide numbers
    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
