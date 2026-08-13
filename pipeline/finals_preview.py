"""Finals preview carousel — "the road to the final", 2 slides (men, women).

Posted the night before a final. Each slide is a 2x2 grid of the four
finalists: headshot, name, and their event so far in three numbers — best
heat score (hero), average counting wave, average counting jump.

Deliberately NOT shown: heat wins and average heat score. Both are distorted
by the draw at this point in an event. A rider seeded into the quarters has
sailed once (so their average equals their best), while a rider who came up
through the losers' route has sailed five times against weaker opposition.
Side by side in a grid those numbers read as a ranking when they are really
an artefact of the ladder. Best heat and the counting averages are
comparable regardless of how many heats a rider has had.
"""

from pipeline.helpers import nationality_to_iso, ordinal
from pipeline.templates import resolve_thumb_url

ACCENT_COLOR = "#5AB4CC"

SOURCE_NOTE = "Averages from counting scores at this event so far"

ROUTE_PREFIX = "QUALIFIED FROM:"

NO_VALUE = "-"


def build_slides(data: dict) -> list[dict]:
    """Build a finals preview carousel. Two shapes, picked by the input.

    Heats mode (``heats`` key) — a cover plus one 2x2 grid per drawn heat,
    used for a full round: "Men's Road to the Final" then "Quarter Final 1",
    "Quarter Final 2"... Each heat's numbers are compared within that heat,
    because that is the comparison the viewer is about to watch.

    Finals mode (``men`` / ``women`` keys) — one grid per division, no cover.

    Every athlete dict has athlete_id, name, nationality, photo_url,
    best_heat, avg_wave and avg_jump.
    """
    meta = data.get("event_meta") or {}
    common = {
        "accent_color": ACCENT_COLOR,
        "event_name": meta.get("event_name", ""),
        "event_year": meta.get("year", ""),
        "event_country": meta.get("country", ""),
        "event_tier": meta.get("stars", 0),
        "event_date_start": meta.get("start_date", ""),
        "event_date_end": meta.get("end_date", ""),
    }

    # Bars scale against one denominator for the whole carousel, so a number
    # on slide 4 is directly comparable with one on slide 1.
    common["bar_max"] = _carousel_maxima(data)

    if data.get("heats") is not None:
        slides = _heat_slides(data, common)
    else:
        slides = _division_slides(data, common)

    for slide in slides:
        slide.pop("bar_max", None)

    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = len(slides)

    return slides


def _heat_slides(data: dict, common: dict) -> list[dict]:
    """Cover plus one grid per drawn heat.

    Titles are white with only the final word in the accent colour, the same
    treatment the other cover and data slides use.
    """
    division = data.get("division_label", "")

    slides = [{
        "type": "finals_cover",
        "title_lines": [line for line in (division, "ROAD TO THE") if line],
        "title_accent": "FINAL",
        **common,
    }]

    # "MEN'S" -> "MEN", so the heat line reads "MEN QUARTER FINAL 4".
    division_word = division.replace("'S", "").strip()

    for heat in data["heats"]:
        lead, accent = _split_title(f"{division_word} {heat.get('label', '')}".strip())
        slides.append({
            "type": "finals_grid",
            "division_label": heat.get("label", ""),
            "title_lines": ["ROAD TO THE FINALS"],
            "title_lead": lead,
            "title_accent": accent,
            "subtitle": "Form at this event",
            "source_note": SOURCE_NOTE,
            "athletes": _build_grid(heat.get("athletes") or [], common.get("bar_max")),
            **common,
        })

    return slides


def _split_title(label: str) -> tuple:
    """Split a heat label into a white lead and an accented last word.

    "QUARTER FINAL 1" -> ("QUARTER FINAL", "1"). A one-word label keeps all of
    it white rather than turning the whole title accent.
    """
    parts = (label or "").rsplit(" ", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (label or "", "")


def _division_slides(data: dict, common: dict) -> list[dict]:
    """One grid per division (the men's final, then the women's final)."""
    slides = []
    for key, label in (("men", "MEN'S FINAL"), ("women", "WOMEN'S FINAL")):
        slides.append({
            "type": "finals_grid",
            "division_label": label,
            "title_lead": "ROAD TO THE",
            "title_accent": label,
            "subtitle": "How the four finalists got here",
            "source_note": SOURCE_NOTE,
            "athletes": _build_grid(data.get(key) or [], common.get("bar_max")),
            **common,
        })
    return slides


def _all_athletes(data: dict) -> list[dict]:
    """Every athlete in the carousel, whichever shape the input takes."""
    if data.get("heats") is not None:
        return [a for heat in data["heats"] for a in (heat.get("athletes") or [])]
    return (data.get("men") or []) + (data.get("women") or [])


def _carousel_maxima(data: dict) -> dict:
    """Highest value per stat across every athlete, for bar scaling."""
    everyone = _all_athletes(data)
    return {key: _leaders(everyone, key) for key in ("best_heat", "avg_wave", "avg_jump")}


def _build_grid(finalists: list[dict], bar_max: dict = None) -> list[dict]:
    """Build the athlete entries for one division's 2x2 grid."""
    if not finalists:
        return []

    bar_max = bar_max or {}
    finalists = _by_qualifying_round(finalists)

    # Jumps are a per-division call: a division with no jump scores at this
    # event drops the row entirely rather than printing a column of dashes.
    show_jumps = any(_num(f.get("avg_jump")) > 0 for f in finalists)

    leaders = {
        "best_heat": _leaders(finalists, "best_heat"),
        "avg_wave": _leaders(finalists, "avg_wave"),
        "avg_jump": _leaders(finalists, "avg_jump"),
    }

    grid = []
    for f in finalists:
        athlete_id = f.get("athlete_id")
        name = f.get("name", "")
        parts = name.split(None, 1) if name else [""]

        stats = [_stat("AVG WAVE", f.get("avg_wave"), leaders["avg_wave"], bar_max.get("avg_wave"))]
        if show_jumps:
            stats.append(_stat("AVG JUMP", f.get("avg_jump"), leaders["avg_jump"], bar_max.get("avg_jump")))

        last_name = parts[1].upper() if len(parts) > 1 else ""

        grid.append({
            "athlete_id": athlete_id,
            "name": name,
            "first_name": parts[0].upper(),
            "last_name": last_name,
            "name_class": _name_class(last_name),
            "route": _route(f.get("route_round"), f.get("route_place")),
            "country": nationality_to_iso(f.get("nationality", "")),
            "photo_url": resolve_thumb_url(athlete_id, f.get("photo_url") or ""),
            "hero": _stat("BEST HEAT", f.get("best_heat"), leaders["best_heat"], bar_max.get("best_heat")),
            "stats": stats,
        })

    return grid


def _by_qualifying_round(finalists: list[dict]) -> list[dict]:
    """Seeded riders first, then whoever came up through the ladder.

    Sorted by the round each rider qualified from, so riders who won the
    seeding round and have been waiting lead the card, and the ones who
    fought through later rounds follow. Python's sort is stable, so the heat
    sheet order survives within each group. Riders with no route data keep
    their position at the end.
    """
    if not any(f.get("route_order") for f in finalists):
        return finalists
    return sorted(finalists, key=lambda f: f.get("route_order") or float("inf"))


def _name_class(last_name: str) -> str:
    """Step the surname size down so long names stay inside the card.

    ``last_name`` is everything after the forename, so multi-word surnames
    ("VAN DER EYKEN", "ELLEFSON RIEMENSCHNEIDER") are the long cases, not
    long single words. The widest in the athlete DB is 24 characters.
    """
    length = len(last_name)
    if length >= 18:
        return "xlong"  # wraps to two lines
    if length >= 13:
        return "long"
    return ""


def _route(round_name, place) -> str:
    """How the rider reached this heat, from their last sailed heat.

    Every round is named the same way, including the seeding round, so the
    line reads consistently across all four cards.
    """
    if not round_name:
        return ""
    label = str(round_name).upper()
    if place:
        label = f"{label} · {ordinal(int(place)).upper()}"
    return f"{ROUTE_PREFIX} {label}"


def _num(value) -> float:
    """Coerce a score to a float, treating None/blank as 0."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _leaders(finalists: list[dict], key: str) -> float:
    """Return the value to beat for a stat (0 if nobody has one)."""
    return max((_num(f.get(key)) for f in finalists), default=0.0)


def _stat(label: str, value, best: float, bar_max: float = None) -> dict:
    """Format one stat cell, flagging it when it leads the division.

    A rider with no score yet shows a dash and never leads, so a division
    where nobody has scored has no highlight at all.
    """
    raw = _num(value)
    has_value = raw > 0
    ceiling = _num(bar_max)
    return {
        "label": label,
        "value": f"{raw:.2f}" if has_value else NO_VALUE,
        "raw": raw,
        "is_leader": has_value and raw >= best,
        "bar_pct": round(raw / ceiling * 100) if has_value and ceiling > 0 else 0,
    }
