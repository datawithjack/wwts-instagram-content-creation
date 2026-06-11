"""Wave-count carousel slide builder — "who made the most of Cloudbreak?".

A single-event spotlight on the riders who caught the most waves:
cover → top woman (hero shot) → top man (hero shot) → cta (4 slides)

Each hero slide is a full-bleed action photo of the rider who caught the most
waves at the event, name lower-left, with three stats beneath: waves caught,
heats sailed, and waves per heat (raw count partly reflects how far a rider
advanced — more heats means more waves — so the per-heat figure is shown too).
"""

from pipeline.helpers import nationality_to_iso
from pipeline.templates import resolve_action_url

ACCENT_COLOR = "#9478B5"  # muted violet — editorial accent
BAR_COLOR = "#9478B5"  # editorial violet — one-off editorial post (was ocean blue)


def build_wave_count_slides(
    men_data: list[dict],
    women_data: list[dict],
    event_meta: dict = None,
) -> list[dict]:
    """Build the 4-slide wave-count carousel.

    Args:
        men_data: List of dicts with keys: athlete, nationality, athlete_id,
                  photo_url, wave_count, heats (ordered by wave_count desc)
        women_data: Same format as men_data
        event_meta: Optional dict with cover/photo context — location,
                    event_name, year, event_id

    Returns:
        List of 4 slide dicts (cover, woman hero, man hero, cta).
    """
    meta = event_meta or {}
    common = {
        "accent_color": ACCENT_COLOR,
        "bar_color": BAR_COLOR,
    }

    cover = {
        "type": "wavecount_cover",
        "event_location": meta.get("location", "CLOUDBREAK"),
        "event_name": meta.get("event_name", "FIJI 2026"),
        "event_year": meta.get("year", ""),
        "event_country": meta.get("country", ""),
        "event_date_start": meta.get("start_date", ""),
        "event_date_end": meta.get("end_date", ""),
        "event_tier": meta.get("stars", 0),
        **common,
    }

    slides = [cover]
    # One hero slide per top wave-catcher. If riders tie for the most in a
    # division, every tied rider gets their own slide (women first, then men).
    for data, label in ((women_data, "WOMEN"), (men_data, "MEN")):
        tied = _top_tied(data)
        is_tie = len(tied) > 1
        for row in (tied or [None]):
            slides.append(_hero_slide(row, label, meta, tied=is_tie, **common))
    slides.append({"type": "wavecount_cta", **common})

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides


def _top_tied(data: list[dict]) -> list[dict]:
    """Return every rider tied for the most waves caught (empty list if no data)."""
    if not data:
        return []
    top_count = max(int(r["wave_count"]) for r in data)
    return [r for r in data if int(r["wave_count"]) == top_count]


def _hero_slide(top: dict, division_label: str, meta: dict, tied: bool = False, **common) -> dict:
    """Build a single hero slide for one top wave-catcher (or a placeholder)."""
    if top is None:
        return {
            "type": "wavecount_hero",
            "division_label": division_label,
            "tied": tied,
            "athlete_name": "",
            "country": "",
            "athlete_id": None,
            "photo_url": "",
            "wave_count": 0,
            "heats": 0,
            "waves_per_heat": 0,
            "stats": [],
            "event_name": meta.get("event_name", "FIJI 2026"),
            "event_year": meta.get("year", ""),
            "event_location": meta.get("location", "CLOUDBREAK"),
            **common,
        }

    wave_count = int(top["wave_count"])
    heats = int(top.get("heats") or 0)
    waves_per_heat = round(wave_count / heats, 1) if heats > 0 else 0
    athlete_id = top.get("athlete_id")
    photo_url = resolve_action_url(
        athlete_id, meta.get("event_id"), top.get("photo_url") or ""
    )

    stats = [
        {"value": str(wave_count), "label": "Waves Caught"},
        {"value": str(heats), "label": "Heats Sailed"},
        {"value": str(waves_per_heat), "label": "Per Heat"},
    ]

    return {
        "type": "wavecount_hero",
        "division_label": division_label,
        "tied": tied,
        "athlete_name": top["athlete"],
        "country": nationality_to_iso(top.get("nationality", "")),
        "athlete_id": athlete_id,
        "photo_url": photo_url,
        "wave_count": wave_count,
        "heats": heats,
        "waves_per_heat": waves_per_heat,
        "stats": stats,
        "event_name": meta.get("event_name", "FIJI 2026"),
        "event_year": meta.get("year", ""),
        "event_location": meta.get("location", "CLOUDBREAK"),
        **common,
    }
