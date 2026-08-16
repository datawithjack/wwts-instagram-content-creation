"""Finals recap carousel — how the final unfolded, counted down 4th to 1st.

The post-event companion to ``finals_preview``. The preview hides the result
and equalises the four riders because the draw makes their event-so-far
numbers incomparable. Once the final has sailed, the result *is* the story,
so this carousel inverts the premise: a cover, one slide per rider counting
down to the winner, then a card comparing all four.

Two rules fall out of that inversion.

First, the comparison card uses the final heat's own scores, not event-wide
aggregates. After the event a rider's average still carries the shape of
their ladder, so putting event averages side by side would repeat exactly the
distortion ``finals_preview`` was written to avoid. The final is the one heat
all four sailed together, in the same conditions, so it is the only
like-for-like comparison available. Event-wide numbers still appear, but on
the individual rider slides where they are labelled as that rider's event.

Second, the countdown only pays off if the last slide is the strongest, which
makes this template photo-dependent in a way the grid templates are not. An
event with no action shots falls back to a framed portrait rather than
stretching a tight face crop to full bleed.
"""

from pipeline.finals_preview import (
    ACCENT_COLOR,
    NO_VALUE,
    _leaders,
    _name_class,
    _num,
    _route,
    _stat,
)
from pipeline.helpers import nationality_to_iso, ordinal
from pipeline.templates import resolve_thumb_url

COMPARE_NOTE = "Scores from the final itself, the one heat all four sailed together"

RIDER_NOTE = "This rider's event so far"


def build_slides(data: dict) -> list[dict]:
    """Build the recap carousel: cover, 4th->1st, then the comparison card.

    Every rider dict carries the result (``place``, ``final_total``,
    ``final_waves``, ``final_jumps``) plus their event-wide aggregates
    (``best_heat``, ``best_wave``, ``best_jump``, ``avg_wave``, ``avg_jump``).
    """
    riders = _by_place(data.get("riders") or [])
    if not riders:
        return []

    meta = data.get("event_meta") or {}
    division = (data.get("division") or "").upper()
    common = {
        "accent_color": ACCENT_COLOR,
        "event_name": meta.get("event_name", ""),
        "event_year": meta.get("year", ""),
        "event_country": meta.get("country", ""),
        "event_tier": meta.get("stars", 0),
        "event_date_start": meta.get("start_date", ""),
        "event_date_end": meta.get("end_date", ""),
    }

    slides = [_cover(division, common)]
    slides.extend(_rider_slides(riders, common))
    slides.append(_compare_slide(riders, common))

    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = len(slides)

    return slides


def _cover(division: str, common: dict) -> dict:
    """Cover slide. Reuses the finals cover so the two templates read as a set."""
    division_label = f"{division}'S" if division else ""
    return {
        "type": "finals_cover",
        "title_lines": [line for line in (division_label, "HOW THE FINAL") if line],
        "title_accent": "UNFOLDED",
        **common,
    }


def _rider_slides(riders: list, common: dict) -> list:
    """One slide per rider, counting down so the winner lands last."""
    show_jumps = _division_has_jumps(riders)

    # Bars scale against the whole division, so a bar on the 4th-place slide
    # is directly comparable with the winner's four slides later.
    bar_max = {
        key: _leaders(riders, key)
        for key in ("final_total", "best_heat", "best_wave", "best_jump", "avg_wave", "avg_jump")
    }
    leaders = dict(bar_max)

    slides = []
    for rider in reversed(riders):
        place = rider.get("place")
        name = rider.get("name", "")
        parts = name.split(None, 1) if name else [""]
        last_name = parts[1].upper() if len(parts) > 1 else ""
        athlete_id = rider.get("athlete_id")

        stats = [
            _stat("BEST HEAT", rider.get("best_heat"), leaders["best_heat"], bar_max["best_heat"]),
            _stat("BEST WAVE", rider.get("best_wave"), leaders["best_wave"], bar_max["best_wave"]),
            _stat("AVG WAVE", rider.get("avg_wave"), leaders["avg_wave"], bar_max["avg_wave"]),
        ]
        if show_jumps:
            stats.append(
                _stat("BEST JUMP", rider.get("best_jump"), leaders["best_jump"], bar_max["best_jump"])
            )
            stats.append(
                _stat("AVG JUMP", rider.get("avg_jump"), leaders["avg_jump"], bar_max["avg_jump"])
            )

        action_url = rider.get("action_url") or ""
        slides.append({
            "type": "recap_rider",
            "place": place,
            "place_label": ordinal(int(place)).upper() if place else "",
            "is_winner": place == 1,
            "athlete_id": athlete_id,
            "name": name,
            "first_name": parts[0].upper(),
            "last_name": last_name,
            "name_class": _name_class(last_name),
            "country": nationality_to_iso(rider.get("nationality", "")),
            "route": _route(rider.get("route_round"), rider.get("route_place")),
            "photo_mode": "action" if action_url else "portrait",
            "photo_url": action_url or resolve_thumb_url(athlete_id, rider.get("photo_url") or ""),
            "hero": _stat(
                "FINAL SCORE", rider.get("final_total"), leaders["final_total"], bar_max["final_total"]
            ),
            "stats": stats,
            "source_note": RIDER_NOTE,
            **common,
        })

    return slides


def _compare_slide(riders: list, common: dict) -> dict:
    """All four riders across each stat, from the final heat's own scores."""
    rows = [_compare_row("FINAL SCORE", riders, lambda r: r.get("final_total"))]
    rows.append(_compare_row("BEST WAVE", riders, lambda r: _best(r.get("final_waves"))))

    # The jump row is driven by the final itself, not the rider's event: a
    # wave-only final in a jumping event should not print four dashes.
    if any(r.get("final_jumps") for r in riders):
        rows.append(_compare_row("BEST JUMP", riders, lambda r: _best(r.get("final_jumps"))))

    return {
        "type": "recap_compare",
        "title_lead": "THE FINAL",
        "title_accent": "COMPARED",
        "subtitle": "Every rider, every score",
        "source_note": COMPARE_NOTE,
        "riders": [
            {
                "athlete_id": r.get("athlete_id"),
                "place": r.get("place"),
                "place_label": ordinal(int(r["place"])).upper() if r.get("place") else "",
                "name": r.get("name", ""),
                "last_name": (r.get("name", "").split(None, 1) + [""])[1].upper()
                or r.get("name", "").upper(),
                "country": nationality_to_iso(r.get("nationality", "")),
                "photo_url": resolve_thumb_url(r.get("athlete_id"), r.get("photo_url") or ""),
            }
            for r in riders
        ],
        "rows": rows,
        **common,
    }


def _compare_row(label: str, riders: list, getter) -> dict:
    """One stat across all four riders, with every leader flagged.

    Ties mark both riders rather than picking the first: two riders on the
    same score in the final genuinely shared that stat.
    """
    raw_values = [_num(getter(r)) for r in riders]
    best = max(raw_values, default=0.0)
    return {
        "label": label,
        "values": [
            {
                "value": f"{v:.2f}" if v > 0 else NO_VALUE,
                "raw": v,
                "is_leader": v > 0 and v >= best,
                "bar_pct": round(v / best * 100) if v > 0 and best > 0 else 0,
            }
            for v in raw_values
        ],
    }


def _best(scores) -> float:
    """Highest score in a list, 0 when there is nothing to read."""
    return max((_num(s) for s in (scores or [])), default=0.0)


def _division_has_jumps(riders: list) -> bool:
    """Whether this division jumped at all, across the whole event.

    A wave-only division drops the jump stats entirely rather than printing a
    column of dashes on every rider slide.
    """
    return any(
        _num(r.get("avg_jump")) > 0 or _num(r.get("best_jump")) > 0 or r.get("final_jumps")
        for r in riders
    )


def _by_place(riders: list) -> list:
    """Sort 1st to 4th. Riders with no place recorded keep to the back."""
    return sorted(riders, key=lambda r: r.get("place") or float("inf"))
