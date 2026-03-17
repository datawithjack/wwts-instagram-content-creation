"""Athlete rise carousel slide builder — progression charts over years.

Cover → Explanation → Dual chart (placement + heat) → Dual chart (jump + wave) → CTA
"""

from pipeline.helpers import trick_type_label

ACCENT_COLOR = "#9478B5"  # muted violet — editorial accent for analysis posts
COLOR_OVERVIEW = "#9478B5"  # muted violet — editorial accent
COLOR_WAVE = "#5AB4CC"      # muted cyan — consistent wave color across feed
COLOR_JUMP = "#4DA89E"      # muted jade — consistent jump color across feed


def build_athlete_rise_slides(data: dict) -> list[dict]:
    """Build 5-slide carousel for athlete rise analysis.

    Args:
        data: Dict with keys: title, subtitle, athlete_name, location,
              accent_color, yearly_data (list of {year, placement, best_heat,
              best_wave, best_jump, best_jump_type?})

    Returns:
        List of 5 slide dicts.
    """
    accent = data.get("accent_color", ACCENT_COLOR)
    yearly = data["yearly_data"]
    years = [r["year"] for r in yearly]
    year_range = f"{min(years)}\u2013{max(years)}" if years else ""

    common = {"accent_color": accent}

    # Build charts
    podium_colors = {1: "#F0C040", 2: "#C0C8D4", 3: "#CD7F32"}
    placements = [
        {"year": r["year"], "value": r["placement"], "dot_color": podium_colors.get(r["placement"])}
        for r in yearly
    ]
    heats = [{"year": r["year"], "value": r.get("best_heat")} for r in yearly]
    jumps = [
        {
            "year": r["year"],
            "value": r.get("best_jump"),
            "label": trick_type_label(r["best_jump_type"]) if r.get("best_jump_type") else None,
        }
        for r in yearly
    ]
    waves = [{"year": r["year"], "value": r.get("best_wave")} for r in yearly]

    # Cover: split into name line + location line
    athlete_name = data.get("athlete_name", "")
    location = data.get("location", "")

    # Header info for chart slides
    header = {
        "header_eyebrow": f"ATHLETE PROGRESSION \u00b7 {location.upper()} \u00b7 {year_range}",
        "header_athlete": athlete_name.upper(),
        "athlete_photo_url": data.get("athlete_photo_url", ""),
        "athlete_initial": athlete_name[0] if athlete_name else "",
    }

    slides = [
        {
            "type": "rise_cover",
            "title": data["title"],
            "cover_name": athlete_name.upper(),
            "cover_location": f"AT THE {location.upper()} WORLD CUP",
            "eyebrow": f"{location} \u00b7 {year_range}",
            "athlete_photo_url": data.get("athlete_photo_url", ""),
            **common,
        },
        {
            "type": "rise_explanation",
            "body_text": data["subtitle"],
            **common,
        },
        {
            "type": "rise_dual_chart",
            "header_pill": "OVERVIEW",
            "top_chart": _build_chart("EVENT PLACEMENT", "line", placements, invert=True, color=COLOR_OVERVIEW),
            "bottom_chart": _build_chart("BEST HEAT SCORE", "column", heats, color=COLOR_OVERVIEW),
            **header,
            **common,
        },
        {
            "type": "rise_dual_chart",
            "header_pill": "BEST SCORES",
            "top_chart": _build_chart("BEST JUMP SCORE", "column", jumps, color=COLOR_JUMP, show_labels=True),
            "bottom_chart": _build_chart("BEST WAVE SCORE", "column", waves, color=COLOR_WAVE),
            **header,
            **common,
        },
        {
            "type": "analysis_cta",
            **common,
        },
    ]

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides


def _build_chart(
    title: str,
    chart_type: str,
    raw_points: list[dict],
    invert: bool = False,
    color: str = ACCENT_COLOR,
    show_labels: bool = False,
) -> dict:
    """Build chart data with pre-computed height percentages.

    Args:
        title: Chart title (e.g. "EVENT PLACEMENT")
        chart_type: "line" or "column"
        raw_points: List of {year, value, label?} dicts (value may be None)
        invert: If True, lower values get higher height_pct (for placement)
        color: Bar/line color for this specific chart
        show_labels: If True, include bar labels (e.g. trick type inside bars)

    Returns:
        Dict with chart_title, chart_type, color, show_labels, points
    """
    values = [p["value"] for p in raw_points if p["value"] is not None]

    if not values:
        points = [
            {"year": p["year"], "value": p["value"], "height_pct": 0, "label": p.get("label")}
            for p in raw_points
        ]
        return {"chart_title": title, "chart_type": chart_type, "color": color, "show_labels": show_labels, "points": points}

    max_val = max(values)
    min_val = min(values)

    points = []
    for p in raw_points:
        v = p["value"]
        if v is None:
            pct = 0
        elif invert:
            if max_val == min_val:
                pct = 100
            else:
                pct = round((max_val - v) / (max_val - min_val) * 100)
        else:
            if max_val == 0:
                pct = 0
            else:
                pct = round(v / max_val * 100)
        points.append({
            "year": p["year"],
            "value": v,
            "height_pct": pct,
            "label": p.get("label"),
            "dot_color": p.get("dot_color"),
        })

    return {"chart_title": title, "chart_type": chart_type, "color": color, "show_labels": show_labels, "points": points}
