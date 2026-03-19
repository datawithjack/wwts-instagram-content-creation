"""Analysis carousel slide builder — custom analysis posts with bar charts.

Kings & Queens of the Canaries:
cover → men bars → women bars → cta (4 slides)
"""

from decimal import Decimal

from pipeline.helpers import nationality_to_iso
from pipeline.templates import resolve_photo_override

ACCENT_COLOR = "#9478B5"  # muted violet — editorial accent for analysis posts
COLOR_GC = "#2a8ab0"  # muted cyan — Gran Canaria
COLOR_TF = "#1e9485"  # muted teal — Tenerife
MIN_BAR_PCT = 20


def build_canary_kings_slides(men_data: list[dict], women_data: list[dict]) -> list[dict]:
    """Build 4-slide carousel for Kings & Queens of the Canaries.

    Args:
        men_data: List of dicts with keys: athlete, nationality, athlete_id,
                  wins, gc_wins, tf_wins
        women_data: Same format as men_data

    Returns:
        List of 4 slide dicts.
    """
    common = {
        "accent_color": ACCENT_COLOR,
        "color_gc": COLOR_GC,
        "color_tf": COLOR_TF,
    }

    men_bars = _build_bars(men_data)
    women_bars = _build_bars(women_data)

    slides = [
        {
            "type": "analysis_cover",
            **common,
        },
        {
            "type": "analysis_bars",
            "slide_title": "KING OF THE CANARIES",
            "bars": men_bars,
            **common,
        },
        {
            "type": "analysis_bars",
            "slide_title": "QUEEN OF THE CANARIES",
            "bars": women_bars,
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


def _build_bars(data: list[dict]) -> list[dict]:
    """Convert query results into stacked bar chart data."""
    if not data:
        return []

    max_wins = max(int(row["wins"]) for row in data)

    bars = []
    for row in data:
        country_iso = nationality_to_iso(row.get("nationality", ""))
        athlete_id = row.get("athlete_id")
        # Use DB photo URL, fall back to local file by athlete ID
        photo_url = resolve_photo_override(athlete_id, row.get("photo_url") or "")

        wins = int(row["wins"])
        gc_wins = int(row.get("gc_wins", 0))
        tf_wins = int(row.get("tf_wins", 0))

        # Total bar width as percentage of max
        bar_width = max(MIN_BAR_PCT, round(wins / max_wins * 100))

        # Segment widths as percentages within the bar
        if wins > 0:
            gc_pct = round(gc_wins / wins * 100)
            tf_pct = 100 - gc_pct
        else:
            gc_pct = 50
            tf_pct = 50

        bars.append({
            "athlete": row["athlete"],
            "country": country_iso,
            "athlete_id": athlete_id,
            "photo_url": photo_url,
            "wins": wins,
            "gc_wins": gc_wins,
            "tf_wins": tf_wins,
            "bar_width": bar_width,
            "gc_pct": gc_pct,
            "tf_pct": tf_pct,
            "has_both": gc_wins > 0 and tf_wins > 0,
        })

    return bars
