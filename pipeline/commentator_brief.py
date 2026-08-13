"""Commentator brief — one detailed sheet per drawn heat.

Same photo-card layout as the finals carousel, but built for the booth rather
than for Instagram: a taller canvas, every stat rather than three, each
rider's heat-by-heat run through the event, world ranking and sail number,
and a generated-at stamp so nobody reads out stale numbers.

Heat wins and average heat score appear here even though the carousel leaves
them out. On a public graphic they mislead, because both scale with how many
heats a rider has sailed. Read aloud with context they are useful.
"""

from pipeline.finals_preview import (
    ACCENT_COLOR,
    NO_VALUE,
    ROUTE_PREFIX,
    _by_qualifying_round,
    _name_class,
    _num,
    _route,
)
from pipeline.helpers import nationality_to_iso, ordinal, trick_type_label
from pipeline.templates import resolve_thumb_url

# (label, source key, formatter) in the order they read on the sheet.
STAT_FIELDS = (
    ("BEST HEAT", "best_heat", "score"),
    ("AVG HEAT", "avg_heat", "score"),
    ("HEATS WON", "heat_wins", "fraction"),
    ("BEST WAVE", "best_wave", "score"),
    ("AVG WAVE", "avg_wave", "score"),
    ("BEST JUMP", "best_jump", "score"),
    ("AVG JUMP", "avg_jump", "score"),
)


def build_pages(data: dict) -> list[dict]:
    """Build one sheet per heat.

    Args:
        data: ``division_label``, ``heats`` (each ``label`` + ``athletes``),
            ``event_meta`` and ``generated_at``.
    """
    meta = data.get("event_meta") or {}
    division = (data.get("division_label") or "").replace("'S", "").strip()

    common = {
        "accent_color": ACCENT_COLOR,
        "event_name": meta.get("event_name", ""),
        "event_year": meta.get("year", ""),
        "event_tier": meta.get("stars", 0),
        "generated_at": data.get("generated_at", ""),
    }

    heats = data.get("heats") or []
    strongest = _strongest_heat(heats)

    pages = []
    for i, heat in enumerate(heats):
        label = heat.get("label", "")
        pages.append({
            "type": "brief_heat",
            "title": f"{division} {label}".strip(),
            "draw_note": _draw_note(heat.get("athletes") or []),
            "is_strongest": i == strongest,
            "riders": _build_riders(heat.get("athletes") or []),
            **common,
        })

    for i, page in enumerate(pages, 1):
        page["page_number"] = i
        page["total_pages"] = len(pages)

    return pages


def _ranks(riders: list[dict]) -> list[int]:
    """World ranks present in a heat, best first."""
    return sorted(int(r["world_rank"]) for r in riders if r.get("world_rank"))


def _draw_note(riders: list[dict]) -> str:
    """The world ranks in this heat, which is how a commentator sizes it up."""
    ranks = _ranks(riders)
    return "World ranks " + ", ".join(f"#{r}" for r in ranks) if ranks else ""


def _strongest_heat(heats: list[dict]) -> int:
    """Index of the heat holding the best-ranked field, or -1.

    Needs at least two heats to compare, ranks on every heat, and a single
    outright answer: a tie is not worth calling out.
    """
    if len(heats) < 2:
        return -1

    means = []
    for heat in heats:
        ranks = _ranks(heat.get("athletes") or [])
        if not ranks:
            return -1
        means.append(sum(ranks) / len(ranks))

    best = min(means)
    return means.index(best) if means.count(best) == 1 else -1


def _build_riders(riders: list[dict]) -> list[dict]:
    """Build the rider blocks for one heat, seeded riders first."""
    if not riders:
        return []

    riders = _by_qualifying_round(riders)
    leaders = {key: _best(riders, key) for _, key, _ in STAT_FIELDS}

    built = []
    for r in riders:
        athlete_id = r.get("athlete_id")
        name = r.get("name", "")
        parts = name.split(None, 1) if name else [""]
        last_name = parts[1].upper() if len(parts) > 1 else ""
        rank = r.get("world_rank")

        built.append({
            "athlete_id": athlete_id,
            "name": name,
            "first_name": parts[0].upper(),
            "last_name": last_name,
            "name_class": _name_class(last_name),
            "country": nationality_to_iso(r.get("nationality", "")),
            "sail_number": r.get("sail_number", "") or "",
            "meta_class": _meta_class(parts[0], r.get("sail_number") or ""),
            "rank_label": f"WR #{int(rank)}" if rank else "",
            "route": _route(r.get("route_round"), r.get("route_place")),
            "photo_url": resolve_thumb_url(athlete_id, r.get("photo_url") or ""),
            "stats": _with_jump_move(
                [
                    _stat(label, r.get(key), leaders.get(key), fmt, len(r.get("history") or []))
                    for label, key, fmt in STAT_FIELDS
                ],
                _best_jump_move(r.get("history") or []),
            ),
            "history": [_history_line(h) for h in (r.get("history") or [])],
        })

    return built


def _with_jump_move(stats: list[dict], move: str) -> list[dict]:
    """Hang the move name off the best-jump cell."""
    for stat in stats:
        if stat["label"] == "BEST JUMP":
            stat["note"] = move
    return stats


def _best_jump_move(history: list[dict]) -> str:
    """Name the move behind a rider's best jump at this event.

    Waves are typed "Wave"; a jump carries a short code in ``type`` and the
    full name in ``move_type``, so anything not typed Wave is a jump and the
    code is the fallback label.
    """
    best_score, best_move = 0.0, ""
    for entry in history:
        for score in entry.get("scores") or []:
            if (score.get("type") or "").strip().lower() == "wave":
                continue
            value = _num(score.get("score"))
            if value > best_score:
                best_score = value
                best_move = score.get("move_type") or trick_type_label(score.get("type", ""))
    return best_move


# Flag + forename + sail + "WR #10" has to fit one card width. Past this
# many characters the WR badge starts getting pushed off the card, so the
# whole row steps down a size (e.g. SARAH-QUITA ARU-91).
META_TIGHT_CHARS = 16


def _meta_class(first_name: str, sail_number: str) -> str:
    """Step the name row down when forename and sail together run long."""
    return "tight" if len(first_name) + len(sail_number) >= META_TIGHT_CHARS else ""


def _best(riders: list[dict], key: str) -> float:
    """Highest value for a stat within this heat."""
    return max((_num(r.get(key)) for r in riders), default=0.0)


def _stat(label: str, value, best, fmt: str, heats_sailed: int = 0) -> dict:
    """One stat cell.

    Wins print as a fraction of heats sailed rather than a rate. At this
    point in an event the denominators are one to five, so a percentage
    would read as precision that is not there: 1/1 is not "100%" in any
    sense comparable with 4/5. The fraction carries its own denominator and
    reads out loud naturally. Nothing on that column is ever highlighted,
    because the values are not comparable.
    """
    missing = value is None or value == ""
    raw = _num(value)

    if fmt == "fraction":
        shown = f"{int(raw)}/{heats_sailed}" if not missing and heats_sailed else NO_VALUE
        return {"label": label, "value": shown, "raw": raw, "is_leader": False, "note": ""}

    shown = NO_VALUE if missing or raw <= 0 else f"{raw:.2f}"

    return {
        "label": label,
        "value": shown,
        "raw": raw,
        "is_leader": not missing and raw > 0 and raw >= _num(best),
        "note": "",
    }


def _history_line(entry: dict) -> str:
    """One sailed heat, e.g. "Seeding R1 H8 · 20.01 · 1st"."""
    bits = [f"{entry.get('round', '')} H{entry.get('heat', '')}".strip()]
    if entry.get("total"):
        bits.append(f"{_num(entry['total']):.2f}")
    if entry.get("place"):
        bits.append(ordinal(int(entry["place"])))
    return " · ".join(b for b in bits if b)
