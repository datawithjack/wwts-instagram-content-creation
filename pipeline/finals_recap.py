"""Finals recap carousel — how the final unfolded, counted down 4th to 1st.

The post-event companion to ``finals_preview``. The preview hides the result
and equalises the four riders because the draw makes their event-so-far
numbers incomparable. Once the final has sailed, the result *is* the story,
so this carousel inverts the premise: a cover, one slide per rider counting
down to the winner, then a card comparing all four.

Three rules fall out of that inversion.

First, the summary card splits its stats into two labelled groups rather than
one table. The final's own scores are the only strictly like-for-like numbers
available: one heat, four riders, the same conditions. Event aggregates still
carry the shape of each rider's ladder, so they are worth showing but are not
the same kind of number, and pooling the two would invite reading one rider's
event average against another's final score.

Second, the rider cards carry no final score and no qualifying route. The card
is one rider's event; the final is the summary card's job. Putting a single
final-score cell among seven event stats needed a footnote explaining that one
cell meant something different from the rest, which is a sign the structure is
wrong rather than the label. The final result is still on the card, as the
placing. The route goes for a related reason: ``finals_preview`` shows how a
rider reached the final because it has not been sailed, but here the ladder is
history and the result is the story.

Third, the countdown only pays off if the last slide is the strongest, which
makes this template photo-dependent in a way the grid templates are not. With
no landscape shot the same slide keeps its hero footprint and sizes a headshot
inside it, rather than stretching a face crop to full bleed.
"""

from pipeline.commentator_brief import _best_jump_move, _history_line, heats_sailed
from pipeline.finals_preview import (
    ACCENT_COLOR,
    NO_VALUE,
    _leaders,
    _name_class,
    _num,
    _stat,
)
from pipeline.helpers import nationality_to_iso, ordinal
from pipeline.templates import resolve_thumb_url

RIDER_NOTE = "At this event"

# Scoped to the averages on purpose: avg_wave and avg_jump come from the API's
# counting aggregates, but best_wave and best_jump are the highest scored,
# counting or not. Saying "counting scores only" of the whole strip would be
# wrong.
COUNTING_NOTE = "Wave and jump averages use counting scores only"

FINAL_GROUP = "IN THE FINAL"

# Where the final was man-on-man the same rows still carry the winner's and
# runner-up's scores, and third and fourth show a dash. Naming the heat is
# what stops that dash reading as "scored nothing".
SPLIT_FINAL_GROUP = "IN THE FINAL (1ST V 2ND)"

EVENT_GROUP = "AT THIS EVENT"

DEFAULT_FOCUS = "center 35%"

# The commentator brief's full set. Avg heat and heats won are the two the
# preview deliberately withholds, because mid-event the draw decides them: a
# seeded rider has sailed once, so their average is their best and their win
# rate is 1/1. A recap runs after the whole ladder, where both are earned.
STAT_FIELDS = (
    ("BEST HEAT", "best_heat", "score"),
    ("AVG HEAT", "avg_heat", "score"),
    ("HEATS WON", "heat_wins", "fraction"),
    ("BEST WAVE", "best_wave", "score"),
    ("AVG WAVE", "avg_wave", "score"),
    ("BEST JUMP", "best_jump", "score"),
    ("AVG JUMP", "avg_jump", "score"),
)

JUMP_FIELDS = ("best_jump", "avg_jump")

# Freestyle scores one thing, a move, so the wave set's four score stats
# collapse to two. The heat stats above them are unchanged: a freestyle heat
# has a total, a winner and a place, exactly as a wave heat does.
FREESTYLE_STAT_FIELDS = (
    ("BEST HEAT", "best_heat", "score"),
    ("AVG HEAT", "avg_heat", "score"),
    ("HEATS WON", "heat_wins", "fraction"),
    ("BEST MOVE", "best_move", "score"),
    ("AVG MOVE", "avg_move", "score"),
)

FREESTYLE_COUNTING_NOTE = "Move averages use counting scores only"

WAVE_ONLY_COUNTING_NOTE = "Wave averages use counting scores only"

# The strip breaks into two groups: heat-level stats, then the score-level ones.
# Best wave starts the second row, so waves and jumps read together rather than
# best wave hanging off the end of the heat row.
SCORE_ROW_START = "best_wave"

FREESTYLE_SCORE_ROW_START = "best_move"


def build_slides(data: dict) -> list[dict]:
    """Build the recap carousel: cover, 4th->1st, then the comparison card.

    Every rider dict carries the result (``place``, ``final_total``,
    ``final_waves``, ``final_jumps``) plus their event-wide aggregates
    (``best_heat``, ``best_wave``, ``best_jump``, ``avg_wave``, ``avg_jump``).

    A freestyle event (``discipline``) swaps the four wave-and-jump stats for
    the two a move has, and reads ``final_moves`` where the wave carousel
    reads ``final_waves``. Everything else is shared, because everything else
    is about heats: the countdown, the photo treatment, the two-group summary
    and the man-on-man handling all hold whatever was being scored.
    """
    riders = _by_place(data.get("riders") or [])
    if not riders:
        return []

    freestyle = (data.get("discipline") or "").strip().lower() == "freestyle"

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

    # A Grand Slam runs several disciplines, and the same rider can appear in
    # more than one of them: Lennart Neubauer won the Sylt 2025 freestyle and
    # came 25th in the wave. So wherever the event is named, the discipline is
    # named with it, and only a wave event leaves it off (wave is the default
    # everything else in the pipeline assumes).
    discipline = "FREESTYLE" if freestyle else ""
    event_label = _event_label(meta, discipline)

    slides = [_cover(division, riders, common, discipline)]
    slides.extend(_rider_slides(riders, common, event_label, freestyle))
    slides.append(_compare_slide(riders, common, event_label, freestyle))

    # The shared CTA the other carousels close on. hide_footer because the
    # slide carries the URL itself, so the watermark would say it twice.
    slides.append({"type": "cta", "hide_footer": True, **common})

    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = len(slides)

    return slides


def _event_label(meta: dict, discipline: str = "") -> str:
    """"TENERIFE GRAND SLAM 2026" -- the event, for a rider sharing the slide.

    A rider reposting their own card takes it out of the carousel, away from
    the cover that names the event, so the card has to carry that itself. At a
    Grand Slam that means naming the discipline too, or the card claims a
    rider's freestyle numbers were their week.
    """
    name = (meta.get("event_name") or "").strip()
    year = meta.get("year") or ""
    label = f"{name} {year}".strip().upper()
    return f"{label} · {discipline}" if discipline and label else label or discipline


def _cover(division: str, riders: list, common: dict, discipline: str = "") -> dict:
    """Cover slide, backed by a grid of the four riders' own hero shots.

    Only riders with a real landscape shot count towards the grid: a headshot
    dropped into a quarter of a full-bleed background reads as a mistake, and
    a half-filled grid is worse than none. With nothing to show the template
    falls back to the plain cover.
    """
    # "Finalists" is only true where they all sailed the final. Elsewhere the
    # carousel is a placings countdown and has to say so.
    subject = "FINALISTS" if _shared_final(riders) else f"TOP {len(riders)}"
    hero_photos = [
        {
            "place": r.get("place"),
            "url": r.get("action_url"),
            "focus": r.get("hero_focus") or DEFAULT_FOCUS,
        }
        for r in riders
        if r.get("action_url")
    ]
    # Three short lines, the same shape finals_preview uses ("MEN'S / ROAD TO
    # THE / FINAL"). One long line renders at a different size to every other
    # cover in the set, which is what breaks the family resemblance, so the
    # discipline takes a line of its own rather than lengthening the first.
    title_lines = ([f"{division}'S {discipline}".strip(), subject] if discipline
                   else [f"{division}'S {subject}".strip()])
    return {
        "type": "recap_cover",
        "title_lines": title_lines,
        "title_accent": "THE STATS",
        "hero_photos": hero_photos,
        **common,
    }


def _stat_fields(riders: list, freestyle: bool) -> tuple:
    """The stats this division's cards carry.

    A wave division that never jumped drops the two jump stats rather than
    printing a column of dashes on every slide; a freestyle one has its own
    set, because a move is the only thing it scores.
    """
    if freestyle:
        return FREESTYLE_STAT_FIELDS
    if _division_has_jumps(riders):
        return STAT_FIELDS
    return tuple(f for f in STAT_FIELDS if f[1] not in JUMP_FIELDS)


def _counting_note(riders: list, freestyle: bool) -> str:
    """Which averages the counting caveat applies to on this carousel."""
    if freestyle:
        return FREESTYLE_COUNTING_NOTE
    return COUNTING_NOTE if _division_has_jumps(riders) else WAVE_ONLY_COUNTING_NOTE


def _rider_slides(riders: list, common: dict, event_label: str = "",
                  freestyle: bool = False) -> list:
    """One slide per rider, counting down so the winner lands last."""
    fields = _stat_fields(riders, freestyle)
    move_label = "BEST MOVE" if freestyle else "BEST JUMP"
    row_start = FREESTYLE_SCORE_ROW_START if freestyle else SCORE_ROW_START

    # Bars scale against the whole division, so a bar on the 4th-place slide
    # is directly comparable with the winner's four slides later.
    bar_max = {key: _leaders(riders, key) for _, key, _ in fields}
    bar_max["final_total"] = _leaders(riders, "final_total")
    leaders = dict(bar_max)
    best_win_rate = _best_win_rate(riders)

    slides = []
    for rider in reversed(riders):
        place = rider.get("place")
        name = rider.get("name", "")
        parts = name.split(None, 1) if name else [""]
        first_name = parts[0].upper()
        last_name = parts[1].upper() if len(parts) > 1 else ""
        athlete_id = rider.get("athlete_id")
        history = rider.get("history") or []
        sail_number = rider.get("sail_number") or ""

        stats = []
        for label, key, fmt in fields:
            best = best_win_rate if fmt == "fraction" else leaders.get(key)
            cell = _recap_stat(label, rider.get(key), best, bar_max.get(key),
                               fmt, heats_sailed(history))
            cell["row_break"] = key == row_start
            stats.append(cell)
        _attach_move_name(stats, move_label, _best_jump_move(history))

        action_url = rider.get("action_url") or ""
        slides.append({
            "type": "recap_rider",
            "place": place,
            "place_label": ordinal(int(place)).upper() if place else "",
            "is_winner": place == 1,
            "athlete_id": athlete_id,
            "name": name,
            "first_name": first_name,
            "last_name": last_name,
            "name_class": _name_class(last_name),
            "sail_number": sail_number,
            "photo_mode": "action" if action_url else "portrait",
            # Landscape sources crop hard to 4:5. Where the rider sits in the
            # frame varies per shot, so the crop anchor is per photo.
            "photo_focus": rider.get("hero_focus") or DEFAULT_FOCUS,
            "photo_url": action_url or resolve_thumb_url(athlete_id, rider.get("photo_url") or ""),
            "stats": stats,
            "history": [_history_line(h) for h in history],
            "source_note": f"AT {event_label}" if event_label else RIDER_NOTE,
            "counting_note": _counting_note(riders, freestyle),
            **common,
        })

    return slides


def _recap_stat(label, value, best, bar_max, fmt: str, heats_sailed: int) -> dict:
    """One stat cell, scored or as a fraction of heats sailed.

    Wins print as a fraction, never a rate, and are never highlighted: each
    rider has their own denominator, so 5/5 and 1/1 are not comparable and a
    highlight would assert a ranking the numbers do not support. Same call the
    commentator brief makes, and it survives the event ending.
    """
    if fmt == "fraction":
        raw = _num(value)
        missing = value is None or value == "" or not heats_sailed
        rate = 0.0 if missing else raw / heats_sailed
        return {
            "label": label,
            "value": NO_VALUE if missing else f"{int(raw)}/{heats_sailed}",
            "raw": raw,
            # Ranked on rate, not raw wins: the denominators still differ, so
            # 3/3 is a better return than 4/6 even though it is fewer wins.
            "is_leader": bool(not missing and rate > 0 and rate >= _num(best)),
            "bar_pct": round(rate * 100) if rate > 0 else 0,
            "note": "",
        }

    cell = _stat(label, value, best, bar_max)
    cell["note"] = ""
    return cell


def _attach_move_name(stats: list, label: str, move: str) -> None:
    """Hang the move name off the cell holding the score it belongs to.

    A jump score and a freestyle score are both half a story without the move
    that earned them, so both carry it. Only the label differs.
    """
    if not move:
        return
    for stat in stats:
        if stat["label"] == label:
            stat["note"] = move


def _compare_slide(riders: list, common: dict, event_label: str = "",
                   freestyle: bool = False) -> dict:
    """All four riders across every stat, grouped by what the stat measures.

    Two groups, not one table. The final's own scores are the only truly
    like-for-like numbers (one heat, four riders, same conditions); the event
    aggregates carry the shape of each rider's ladder. Both are worth showing,
    but pooling them into one undifferentiated list would invite reading a
    rider's event average against another's final score as if they were the
    same kind of number.
    """
    fields = _stat_fields(riders, freestyle)
    shared_final = _shared_final(riders)
    any_final = any(r.get("final_total") is not None for r in riders)
    final_group = FINAL_GROUP if shared_final else SPLIT_FINAL_GROUP
    move_key = "best_move" if freestyle else "best_jump"

    # The final's own scores are the like-for-like half of this card. Where the
    # final was man-on-man they cover the top two only, which is still the
    # sharpest comparison on the page -- the same heat, the same conditions --
    # so the rows stay and the group header says who they belong to.
    rows = []
    if any_final:
        rows = [_compare_row("FINAL SCORE", riders, final_group,
                             lambda r: r.get("final_total"))]
        if freestyle:
            rows.append(_compare_row(
                "BEST MOVE", riders, final_group,
                lambda r: _best(r.get("final_moves")),
                note=lambda r: r.get("final_best_move") or "",
            ))
        else:
            rows.append(_compare_row("BEST WAVE", riders, final_group,
                                     lambda r: _best(r.get("final_waves"))))
            if any(r.get("final_jumps") for r in riders):
                rows.append(_compare_row(
                    "BEST JUMP", riders, final_group,
                    lambda r: _best(r.get("final_jumps")),
                    # The move is half the story of a jump score, so it travels
                    # with the number onto the summary as well as the rider slide.
                    note=lambda r: r.get("final_best_jump_move") or "",
                ))

    for label, key, fmt in fields:
        note = (lambda r: _best_jump_move(r.get("history") or "")) if key == move_key else None
        rows.append(_compare_row(label, riders, EVENT_GROUP,
                                 lambda r, k=key: r.get(k), fmt=fmt, note=note))

    return {
        "type": "recap_compare",
        "title_lead": "THE FINALISTS" if shared_final else f"THE TOP {len(riders)}",
        "title_accent": "COMPARED",
        "subtitle": event_label,
        "counting_note": _counting_note(riders, freestyle),
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


def _compare_row(label: str, riders: list, group: str, getter, fmt: str = "score",
                 note=None) -> dict:
    """One stat across all four riders, with every leader flagged.

    Ties mark both riders rather than picking the first: two riders on the
    same score in the final genuinely shared that stat.

    Heats won is a fraction over each rider's own heats sailed and is never
    highlighted, for the same reason it is not on the rider slides: the
    denominators differ, so the values do not rank against each other.
    """
    raw_values = [_num(getter(r)) for r in riders]

    if fmt == "fraction":
        best_rate = _best_win_rate(riders)
        cells = []
        for rider, raw in zip(riders, raw_values):
            sailed = heats_sailed(rider.get("history"))
            missing = getter(rider) is None or not sailed
            rate = 0.0 if missing else raw / sailed
            cells.append({
                "value": NO_VALUE if missing else f"{int(raw)}/{sailed}",
                "raw": raw,
                "is_leader": bool(not missing and rate > 0 and rate >= best_rate),
                "bar_pct": round(rate * 100) if rate > 0 else 0,
                "note": "",
            })
        return {"label": label, "group": group, "cells": cells}

    best = max(raw_values, default=0.0)
    return {
        "label": label,
        "group": group,
        # Named "cells", not "values": Jinja resolves row.values to dict.values
        # (the built-in method) before it ever looks for the key.
        "cells": [
            {
                "value": f"{v:.2f}" if v > 0 else NO_VALUE,
                "raw": v,
                "is_leader": v > 0 and v >= best,
                "bar_pct": round(v / best * 100) if v > 0 and best > 0 else 0,
                "note": (note(rider) if note and v > 0 else "") or "",
            }
            for rider, v in zip(riders, raw_values)
        ],
    }


def _best_win_rate(riders: list) -> float:
    """Highest wins-per-heat-sailed in the division, 0 if nobody has sailed.

    Rate rather than raw wins, because riders reach the final by different
    routes and so sail different numbers of heats. Mid-event that gap makes
    the comparison worthless (a seeded rider is 1/1); across a completed
    ladder it is small enough that the rate is a fair ranking.
    """
    rates = [
        _num(r.get("heat_wins")) / heats_sailed(r.get("history"))
        for r in riders
        if heats_sailed(r.get("history")) and r.get("heat_wins") is not None
    ]
    return max(rates, default=0.0)


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


def _shared_final(riders: list) -> bool:
    """Did every rider on the carousel sail the same final heat?

    At a man-on-man event they did not: the final holds two riders and third
    and fourth were settled in a heat of their own. That makes the final's own
    scores useless as a comparison and "finalists" the wrong word for the set,
    so both follow from this one question.
    """
    return bool(riders) and all(r.get("final_total") is not None for r in riders)


def _by_place(riders: list) -> list:
    """Sort 1st to 4th. Riders with no place recorded keep to the back."""
    return sorted(riders, key=lambda r: r.get("place") or float("inf"))
