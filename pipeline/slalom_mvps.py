"""Slalom Session Fantasy MVPs — carousel builder.

The slalom counterpart to pipeline/fuerte_fantasy_mvps.py. Slalom has NO judged
heat scores (the finish PLACE is the result), so it is scored by a different
engine from freestyle and the freestyle single/double elimination split does not
exist — a slalom event runs many eliminations (Fuerteventura 2026: 11 for the
men, 15 for the women). The table therefore reports wins / best / avg instead.

SCORING IS A PORT, NOT AN INVENTION. The rules below mirror
``backend/src/api/slalom_session_scoring.py`` in the windsurf-world-tour-stats-app
repo, which is what actually scores the live fantasy leaderboard:

  - Per heat: top-10 descending — 1st = 10, 2nd = 9, … 10th = 1, 11th+ = 0.
  - Result-code penalties are FLAT and replace the place points: DQ/PMS/DNE = -5,
    DNF/RAF = -1, DNS = 0 (a neutral non-start, overriding the finish place).
  - A ladder's championship final scores ×2.0; the losers'/petit final does not.

Keeping the rules here rather than importing across repos means they can drift,
so tests/test_slalom_mvps.py pins each rule, and generate.py cross-checks the
computed totals against the app's own stored per-athlete values before rendering
(see verify_against_app_scores) — a mismatch fails loudly instead of publishing a
post that disagrees with the leaderboard players can see.

Unlike the app's engine, which only scores PICKED athletes, this module scores
every competitor: an MVP board that silently omitted an unpicked rider who
outscored the field would be wrong.
"""

from collections import defaultdict
from decimal import Decimal
import re

from pipeline.helpers import (
    country_code_to_iso2,
    nationality_to_iso,
    ordinal,
    sail_prefix_to_iso2,
)

# Slalom X discipline colour, matching the Slalom X Event Picks launch carousel.
SLALOM_COLOR = "#5ab4cc"

# Finish place -> points within a single heat. Absent keys fall through to 0.
HEAT_PLACE_POINTS = {1: 10, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1}

DQ_PENALTY = -5.0
DNF_PENALTY = -1.0
DNS_NEUTRAL = 0.0
RESULT_CODE_PENALTY = {
    "PMS": DQ_PENALTY,   # premature start — the DQ
    "DNE": DQ_PENALTY,   # disqualification not excludable
    "OCS": DQ_PENALTY,   # on course side at the start
    "DSQ": DQ_PENALTY,
    "DQ": DQ_PENALTY,
    "DNF": DNF_PENALTY,  # did not finish
    "RAF": DNF_PENALTY,  # retired after finishing
    "DNS": DNS_NEUTRAL,  # did not start — neutral 0, overrides the finish place
}

WINNERS_FINAL_MULTIPLIER = 2.0

# Round names for the worked example, counted BACK from a ladder's last round so
# the labels track the real bracket depth: a 4-round ladder reads Qualifying ->
# Quarter Finals -> Semi Finals -> Final, while a straight final is just "Final".
# Anything deeper than the quarters is qualifying.
ROUNDS_FROM_FINAL = {0: "Final", 1: "Semi Finals", 2: "Quarter Finals"}
EARLY_ROUND_LABEL = "Qualifying"

_ROUND_RE = re.compile(r"_r(\d+)_")


def penalty_for_code(code):
    """Flat points for a slalom result code, or None if it doesn't override the
    finish place (a normal finish / an unknown code).

    NB ``DNS`` returns 0.0, not None — a non-start scores nothing regardless of
    the rank the source gave it (HeatScoringPRO ranks non-starters at the back
    of the heat, which the top-10 curve would otherwise read as a real place).
    """
    if not code:
        return None
    return RESULT_CODE_PENALTY.get(str(code).strip().upper())


def heat_points(place, *, penalty=None, final_multiplier: float = 1.0):
    """Points for one slalom heat finish.

    ``penalty``, when set, REPLACES the place points and is returned flat — it is
    never scaled by the final multiplier (a DQ in the final still costs -5).
    """
    if penalty is not None:
        return penalty
    return HEAT_PLACE_POINTS.get(place, 0) * final_multiplier


def athlete_event_points(heats: list[dict]):
    """Sum :func:`heat_points` over one athlete's heats. 0 for no heats."""
    total = 0.0
    for h in heats:
        penalty = h.get("penalty")
        if penalty is None:
            penalty = penalty_for_code(h.get("result_code"))
        total += heat_points(
            h.get("place"),
            penalty=penalty,
            final_multiplier=float(h.get("final_multiplier", 1.0)),
        )
    return total


def _parse_ladder_and_round(heat_id):
    """``(ladder, round)`` for a slalom heat_id ``{ladder}_r{round}_h{n}``."""
    m = _ROUND_RE.search(heat_id or "")
    if not m:
        return None, None
    return heat_id.split("_r")[0], int(m.group(1))


def final_multipliers_for_event(rows) -> dict:
    """Classify each ladder's finals, returning ``{heat_id: multiplier}``.

    ``rows`` is one entry per athlete-heat (``heat_id``, ``overall_place``) for
    ALL of the event's slalom heats. Within a ladder's max round, the heat whose
    members hold the best overall places is the winners' final. A straight final
    (one round, one heat) is itself the championship final. Anything ambiguous
    or unclassifiable gets no entry, i.e. ×1.
    """
    heat_round: dict = {}
    heat_places: dict = defaultdict(list)
    ladder_rounds: dict = defaultdict(set)
    ladder_heats: dict = defaultdict(set)

    for r in rows:
        heat_id = r.get("heat_id")
        ladder, rnd = _parse_ladder_and_round(heat_id)
        if ladder is None:
            continue
        heat_round[heat_id] = rnd
        ladder_rounds[ladder].add(rnd)
        ladder_heats[ladder].add(heat_id)
        place = r.get("overall_place")
        if place is not None:
            heat_places[heat_id].append(place)

    out: dict = {}
    for ladder, rounds in ladder_rounds.items():
        if len(rounds) < 2:
            # One round, ONE heat = a straight final -> x2. One round split over
            # several heats is a qualifying fleet, not a final -> no entry.
            heats = ladder_heats[ladder]
            if len(heats) == 1:
                hid = next(iter(heats))
                if heat_places.get(hid):
                    out[hid] = WINNERS_FINAL_MULTIPLIER
            continue
        max_round = max(rounds)
        finals = [
            (hid, min(heat_places[hid]))
            for hid in ladder_heats[ladder]
            if heat_round[hid] == max_round and heat_places.get(hid)
        ]
        if not finals:
            continue
        finals.sort(key=lambda x: x[1])
        if len(finals) >= 2 and finals[0][1] == finals[1][1]:
            continue  # ambiguous — can't identify the winners' final
        out[finals[0][0]] = WINNERS_FINAL_MULTIPLIER
    return out


def parse_fleet(elimination_name: str):
    """Fleet ("Men"/"Women") from a slalom elimination_name, or None.

    Slalom names look like "Men's Slalom X - Elimination 1". The source holds
    both straight and curly apostrophes, and "women" contains the substring
    "men", so the women test MUST run first.
    """
    s = (elimination_name or "").lower()
    if "women" in s:
        return "Women"
    if "men" in s:
        return "Men"
    return None


def _num(v) -> float:
    """Coerce a DB numeric (Decimal / int / str / None) to float."""
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def resolve_country_iso(country_code, nationality, sail_number=None) -> str:
    """Best-effort ISO2 for the flag column; empty string renders blank.

    Order: ATHLETES.country_code → nationality as a word ("Greece" → gr) →
    nationality as a code ("IT" → it) → the sail number's national prefix. The
    sail fallback carries most of the field here: 35 of the 52 riders at
    Fuerteventura 2026 had every country column NULL.
    """
    return (
        country_code_to_iso2(country_code or "")
        or nationality_to_iso(nationality or "")
        or country_code_to_iso2(nationality or "")
        or sail_prefix_to_iso2(sail_number or "")
        or ""
    )


def athlete_points_by_ladder(heat_rows, classify_rows) -> dict:
    """``{athlete_id: {ladder_id: points}}`` for every athlete in ``heat_rows``.

    Points are RAW (pre-wildcard): the ×1.25 wildcard bonus is a per-picker slot
    multiplier, not something the athlete earned, so it never belongs on an MVP
    board.
    """
    finals = final_multipliers_for_event(classify_rows or [])
    out: dict = defaultdict(lambda: defaultdict(float))
    for row in heat_rows:
        ladder, _rnd = _parse_ladder_and_round(row.get("heat_id"))
        if ladder is None:
            continue  # not a slalom heat
        pts = heat_points(
            row.get("place"),
            penalty=penalty_for_code(row.get("result_code")),
            final_multiplier=finals.get(row["heat_id"], 1.0),
        )
        out[int(row["athlete_id"])][ladder] += pts
    return {aid: dict(ladders) for aid, ladders in out.items()}


def best_elimination_example(heat_rows, classify_rows, elim_rows) -> dict | None:
    """The single biggest one-elimination haul at the event, heat by heat.

    Slalom totals only make sense once you can see a rider accumulating through
    the rounds, so the key slide shows a real worked example rather than an
    invented one: the actual best run at this event, which is also the number a
    reader is most likely to query.

    Returns ``{athlete, country, elimination, steps: [{label, detail, points}],
    total}`` ordered by round, or None when there are no heats.
    """
    finals = final_multipliers_for_event(classify_rows or [])

    # A ladder's last round is its final. Taken from ALL heats, not just the
    # example rider's, so a rider knocked out early is still labelled correctly.
    ladder_max_round: dict = defaultdict(int)
    for row in heat_rows or []:
        ladder, rnd = _parse_ladder_and_round(row.get("heat_id"))
        if ladder is not None:
            ladder_max_round[ladder] = max(ladder_max_round[ladder], rnd)

    runs: dict = defaultdict(list)
    meta: dict = {}
    for row in heat_rows or []:
        ladder, rnd = _parse_ladder_and_round(row.get("heat_id"))
        if ladder is None:
            continue
        aid = int(row["athlete_id"])
        mult = finals.get(row["heat_id"], 1.0)
        runs[(aid, ladder)].append({
            "round": rnd,
            "place": row.get("place"),
            "result_code": row.get("result_code"),
            "points": heat_points(
                row.get("place"),
                penalty=penalty_for_code(row.get("result_code")),
                final_multiplier=mult,
            ),
            "is_final": mult > 1.0,
        })
        meta.setdefault(aid, {
            "athlete": row.get("athlete", ""),
            "country_code": row.get("country_code", ""),
            "nationality": row.get("country", ""),
            "sail_number": row.get("sail_number", ""),
        })

    if not runs:
        return None

    (aid, ladder), heats = max(
        runs.items(), key=lambda kv: sum(h["points"] for h in kv[1])
    )

    elim_name = ""
    for r in elim_rows or []:
        if str(r.get("ladder_id")) == str(ladder):
            elim_name = r.get("elimination_name", "") or ""
            break
    # "Men's Slalom X - Elimination 9" -> "Elimination 9"
    if " - " in elim_name:
        elim_name = elim_name.split(" - ", 1)[1]

    max_round = ladder_max_round.get(ladder, 0)
    steps = []
    for h in sorted(heats, key=lambda h: h["round"]):
        code = (h.get("result_code") or "").strip().upper()
        if code and penalty_for_code(code) is not None:
            detail = code
        else:
            detail = ordinal(h["place"]) if h.get("place") else "-"
        if h["is_final"]:
            label = "Final"
        else:
            label = ROUNDS_FROM_FINAL.get(
                max_round - h["round"], EARLY_ROUND_LABEL
            )
            # The max round holds BOTH finals; without the x2 this is the
            # consolation, not the championship decider.
            if h["round"] == max_round:
                label = "Losers' Final"
        steps.append({
            "label": label,
            "detail": detail,
            "points": round(h["points"], 2),
        })

    info = meta.get(aid, {})
    return {
        "athlete": info.get("athlete", ""),
        "country": resolve_country_iso(
            info.get("country_code"), info.get("nationality"), info.get("sail_number")
        ),
        "elimination": elim_name,
        "steps": steps,
        "total": round(sum(s["points"] for s in steps), 2),
    }


def assemble_slalom_mvp_data(
    heat_rows: list[dict],
    classify_rows: list[dict],
    elim_rows: list[dict],
    pct_rows: list[dict],
    event_meta: dict,
    top_n: int = 10,
) -> dict:
    """Pivot the raw query rows into a ``{"event", "men", "women"}`` view model.

    Args:
        heat_rows: per athlete-heat — athlete_id, athlete, country, country_code,
            heat_id, place, result_code.
        classify_rows: per athlete-heat — heat_id, overall_place — for ALL of the
            event's slalom heats, used to find each ladder's final.
        elim_rows: SLALOM_ELIMINATION_VIEW rows — athlete_id, ladder_id,
            elimination_no, elimination_name, place. Supplies the fleet (via the
            elimination name) and the win count (overall place 1).
        pct_rows: athlete_id (VARCHAR), pick_count, total_entries.
        event_meta: dict describing the event (location, year, ...).
        top_n: max rows per fleet.

    Returns:
        Rows of {rank, athlete, country, athlete_id, wins, best_pts, avg_pts,
        total_pts, pct_picked}, best first.
    """
    pct_map: dict[int, int] = {}
    for r in pct_rows or []:
        total = r.get("total_entries") or 0
        if not total:
            continue
        pct_map[int(r["athlete_id"])] = round(
            _num(r["pick_count"]) / _num(total) * 100
        )

    points = athlete_points_by_ladder(heat_rows, classify_rows)

    # Fleet + wins come from the elimination view: place 1 is a TRUE elimination
    # win (won the championship final), distinct from winning the consolation.
    fleet_of: dict[int, str] = {}
    wins: dict[int, int] = defaultdict(int)
    for r in elim_rows or []:
        aid = int(r["athlete_id"])
        fleet = parse_fleet(r.get("elimination_name", ""))
        if fleet and aid not in fleet_of:
            fleet_of[aid] = fleet
        try:
            if int(r.get("place")) == 1:
                wins[aid] += 1
        except (TypeError, ValueError):
            pass  # NULL / non-numeric place (DNS) is never a win

    # A DNS/DNF is decisive in slalom (0 or -1 against a possible 20), so the
    # codes are kept for the caption to cite.
    non_finishes: dict[int, list] = defaultdict(list)
    names: dict[int, dict] = {}
    for r in heat_rows:
        aid = int(r["athlete_id"])
        code = (r.get("result_code") or "").strip().upper()
        if code and penalty_for_code(code) is not None:
            non_finishes[aid].append(code)
        names.setdefault(aid, {
            "athlete": r.get("athlete", ""),
            "country_code": r.get("country_code", ""),
            "nationality": r.get("country", ""),
            "sail_number": r.get("sail_number", ""),
        })

    def _fleet_rows(fleet: str) -> list[dict]:
        rows = []
        for aid, ladders in points.items():
            if fleet_of.get(aid) != fleet:
                continue
            per_elim = list(ladders.values())
            total = round(sum(per_elim), 2)
            # An MVP board lists point-scorers — drop anyone who scored nothing.
            if total <= 0 or not per_elim:
                continue
            meta = names.get(aid, {})
            rows.append({
                "athlete": meta.get("athlete", ""),
                "country": resolve_country_iso(
                    meta.get("country_code"),
                    meta.get("nationality"),
                    meta.get("sail_number"),
                ),
                "athlete_id": aid,
                "wins": wins.get(aid, 0),
                "elims": len(per_elim),
                "non_finishes": sorted(non_finishes.get(aid, [])),
                "best_pts": round(max(per_elim), 2),
                "avg_pts": round(total / len(per_elim), 2),
                "total_pts": total,
                "pct_picked": pct_map.get(aid, 0),
            })
            # Preformatted for the shared mvp_table template, which prints these
            # verbatim. Wins is a count, and slalom totals are always whole
            # numbers (the place curve, the penalties and the x2 final are all
            # integers), so only the average carries a decimal place. best_pts
            # stays on the row for captions even though the table omits it.
            rows[-1].update({
                "col_1": str(rows[-1]["wins"]),
                "col_2": f"{rows[-1]['avg_pts']:.1f}",
                "col_3": f"{rows[-1]['total_pts']:.0f}",
            })
        rows.sort(key=lambda r: r["total_pts"], reverse=True)
        for i, r in enumerate(rows[:top_n], 1):
            r["rank"] = i
        return rows[:top_n]

    return {
        "event": event_meta,
        "men": _fleet_rows("Men"),
        "women": _fleet_rows("Women"),
        # A real worked example for the key slide — see best_elimination_example.
        "example": best_elimination_example(heat_rows, classify_rows, elim_rows),
    }


def verify_against_app_scores(data: dict, breakdown_rows: list[dict]) -> list[str]:
    """Cross-check computed totals against the app's own stored per-athlete points.

    ``breakdown_rows`` are FANTASY_SESSION_SCORES rows for the event; each slot in
    a user's ``breakdown_json`` carries the athlete's ``heat_aggregate`` — the raw
    pre-wildcard event points the live leaderboard was built from. Every athlete
    the app scored should match this module's total exactly.

    Returns a list of human-readable mismatch descriptions (empty when the port
    agrees with the app). Athletes nobody picked are absent from the breakdowns
    and are silently skipped — they are exactly why this module scores the whole
    fleet rather than reading these rows directly.
    """
    import json

    expected: dict[int, float] = {}
    for row in breakdown_rows or []:
        raw = row.get("breakdown_json")
        if not raw:
            continue
        try:
            slots = json.loads(raw).get("slots", [])
        except (ValueError, TypeError):
            continue
        for slot in slots:
            aid = slot.get("athlete_id")
            agg = slot.get("heat_aggregate")
            if aid is not None and agg is not None:
                expected[int(aid)] = round(float(agg), 2)

    problems = []
    for fleet in ("men", "women"):
        for row in data.get(fleet, []):
            want = expected.get(row["athlete_id"])
            if want is None:
                continue
            if abs(want - row["total_pts"]) > 0.01:
                problems.append(
                    f"{row['athlete']} (id {row['athlete_id']}): "
                    f"computed {row['total_pts']}, app says {want}"
                )
    return problems


def build_slides(data: dict) -> list[dict]:
    """Build the MVP carousel: cover → men table → [women table] → cta.

    The women's table is dropped when that fleet has no scoring rows, so a
    men-only event doesn't publish an empty slide.
    """
    # discipline_label rides on every slide: the cover eyebrow and the table
    # eyebrow both default to "Freestyle" for the original MVP carousel.
    common = {"accent_color": SLALOM_COLOR, "discipline_label": "Slalom X"}
    event = data.get("event", {})
    # Slalom has no single/double split — see the module docstring. These
    # override the mvp_table template's freestyle defaults.
    columns = {
        "col_1_label": "Wins",
        "col_2_label": "Avg",
        "col_3_label": "Total",
        "footnote": (
            "Wins = eliminations won outright &middot; Avg / Total = points per "
            "elimination and across the event &middot; Picked = % of players who "
            "had them"
        ),
    }

    slides = [{"type": "mvp_cover", "event": event, **common}]

    # The key comes BEFORE the tables: slalom points are unreadable without it. A
    # men's rider can bank ~46 in ONE elimination (four heats plus a doubled
    # final) while a woman tops out at 20 (a single straight final), so the raw
    # numbers look arbitrary unless the accumulation and the x2 final are spelled
    # out first.
    slides.append({
        "type": "mvp_key",
        "event": event,
        "rules": [
            {"label": "Each heat",
             "text": "1st = 10 points, 2nd = 9, down to 10th = 1"},
            {"label": "The final",
             "text": "Points in an elimination's final count double"},
        ],
        # A real run from this event, not an invented one.
        "example": data.get("example"),
        **common,
    })

    for label, key in (("MEN", "men"), ("WOMEN", "women")):
        rows = data.get(key, [])
        if not rows:
            continue
        slides.append({
            "type": "mvp_table",
            "sex_label": label,
            "event": event,
            "rows": rows,
            **columns,
            **common,
        })
    slides.append({"type": "mvp_cta", "event": event, **common})

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
