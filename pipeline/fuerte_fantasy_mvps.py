"""Fuerteventura Fantasy MVPs — freestyle-Session leaderboard carousel builder.

A post-event payoff for the freestyle Session (see pipeline/freestyle_session.py):
a top-10 of the pro riders who generated the most fantasy points at the event,
each rider's points split into single-elim / double-elim / total, plus % picked
(how many Session players had them on their team).

Data comes from two DB queries (pipeline/queries.py):
  - build_fantasy_mvp_points_query  → per-athlete points per elimination
  - build_fantasy_session_pick_pct_query → per-athlete confirmed-pick %
assembled here into a {"event", "men", "women"} dict, then into slides:
cover → men table → women table → cta.
"""

from decimal import Decimal

from pipeline.helpers import nationality_to_iso, country_code_to_iso2

# Session teal, matching the freestyle Session launch post (freestyle_session.py)
# and the mode's colour everywhere it appears in the web app.
SESSION_COLOR = "#2dd4bf"

# Freestyle-only riders whose ATHLETES row has EVERY country column NULL — an
# upstream data gap. Keyed on the unified ATHLETES.id (athlete_id), ISO2 values
# derived from each rider's PWA sail-number prefix (Ryoma Sugi has no sail → JP
# by relation). The durable fix is backfilling ATHLETES.country_code; until then
# this fills the flag column so the post is publishable. Remove an entry once its
# DB row is populated (the DB value takes precedence anyway).
COUNTRY_OVERRIDES = {
    985: "it", 884: "ch", 908: "bq", 957: "nl", 983: "it", 881: "nl", 722: "bq",
    982: "it", 951: "it", 967: "gb", 977: "at", 981: "cw", 966: "pl", 975: "gr",
    971: "it", 969: "se", 576: "jp", 896: "fr", 973: "de", 963: "nl", 974: "nl",
    890: "be", 892: "be", 882: "bq",
}


def resolve_country_iso(country_code, nationality, athlete_id=None) -> str:
    """Best-effort ISO2 country code for the flag column.

    Order: ATHLETES.country_code (2/3-letter) → nationality as a word
    ("Greece" → gr) → nationality as an ISO code ("IT" → it) → sail-derived
    override by athlete_id (for riders with every country column NULL in the DB).
    Empty string when nothing resolves (renders as a blank flag cell).
    """
    iso = country_code_to_iso2(country_code or "")
    if iso:
        return iso
    iso = nationality_to_iso(nationality or "")
    if iso:
        return iso
    iso = country_code_to_iso2(nationality or "")
    if iso:
        return iso
    return COUNTRY_OVERRIDES.get(athlete_id, "")


def parse_elimination(name: str) -> tuple[str | None, str | None]:
    """Split an elimination_name into (sex, elim).

    Freestyle ``PWA_IWT_HEAT_PROGRESSION.elimination_name`` values look like
    "Mens Single Elimination" / "Womens Double Elimination" — the field encodes
    both the fleet and the elimination. Returns sex in {"Men", "Women"} and elim
    in {"single", "double"}, or None for either part that can't be identified.

    "women" contains the substring "men", so the women test MUST run first.
    """
    s = (name or "").lower()

    if "women" in s:
        sex = "Women"
    elif "men" in s:
        sex = "Men"
    else:
        sex = None

    if "double" in s:
        elim = "double"
    elif "single" in s:
        elim = "single"
    else:
        elim = None

    return sex, elim


def _num(v) -> float:
    """Coerce a DB numeric (Decimal / int / str / None) to float."""
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def assemble_mvp_data(
    points_rows: list[dict],
    pct_rows: list[dict],
    event_meta: dict,
    top_n: int = 10,
) -> dict:
    """Pivot the raw query rows into a {"event", "men", "women"} view model.

    Args:
        points_rows: rows from build_fantasy_mvp_points_query — one per
            (athlete, elimination_name) with keys: athlete, country
            (nationality), athlete_id, elimination_name, points.
        pct_rows: rows from build_fantasy_session_pick_pct_query — keys:
            athlete_id (VARCHAR), pick_count, total_entries.
        event_meta: dict describing the event (name, location, year, ...).
        top_n: max rows per fleet.

    Returns:
        {"event": event_meta, "men": [...], "women": [...]} where each row is
        {rank, athlete, country (iso lc), athlete_id, single_pts, double_pts,
        total_pts, pct_picked}.
    """
    # % picked lookup keyed on int athlete id (VARCHAR in the picks table).
    pct_map: dict[int, int] = {}
    for r in pct_rows:
        total = r.get("total_entries") or 0
        if not total:
            continue
        aid = int(r["athlete_id"])
        pct_map[aid] = round(_num(r["pick_count"]) / _num(total) * 100)

    # Pivot points by athlete, summing per elimination.
    athletes: dict[int, dict] = {}
    for r in points_rows:
        aid = int(r["athlete_id"])
        sex, elim = parse_elimination(r.get("elimination_name", ""))
        if sex is None:
            continue  # skip rows we can't attribute to a fleet (e.g. slalom leak)
        entry = athletes.setdefault(
            aid,
            {
                "athlete_id": aid,
                "athlete": r["athlete"],
                "nationality": r.get("country", ""),
                "country_code": r.get("country_code", ""),
                "sex": sex,
                "single_pts": 0.0,
                "double_pts": 0.0,
            },
        )
        pts = round(_num(r.get("points")), 2)
        if elim == "double":
            entry["double_pts"] = round(entry["double_pts"] + pts, 2)
        else:  # single (or unknown elim → count as single so it isn't lost)
            entry["single_pts"] = round(entry["single_pts"] + pts, 2)

    def _fleet(sex: str) -> list[dict]:
        rows = [a for a in athletes.values() if a["sex"] == sex]
        for a in rows:
            a["total_pts"] = round(a["single_pts"] + a["double_pts"], 2)
        # An MVP board is a list of point-scorers — drop anyone who scored zero.
        rows = [a for a in rows if a["total_pts"] > 0]
        rows.sort(key=lambda a: a["total_pts"], reverse=True)
        out = []
        for i, a in enumerate(rows[:top_n], 1):
            out.append(
                {
                    "rank": i,
                    "athlete": a["athlete"],
                    "country": resolve_country_iso(a["country_code"], a["nationality"], a["athlete_id"]),
                    "athlete_id": a["athlete_id"],
                    "single_pts": a["single_pts"],
                    "double_pts": a["double_pts"],
                    "total_pts": a["total_pts"],
                    "pct_picked": pct_map.get(a["athlete_id"], 0),
                }
            )
        return out

    return {
        "event": event_meta,
        "men": _fleet("Men"),
        "women": _fleet("Women"),
    }


def build_slides(data: dict) -> list[dict]:
    """Build the 4-slide MVP carousel: cover → men table → women table → cta."""
    common = {"accent_color": SESSION_COLOR}
    event = data.get("event", {})

    slides = [
        {"type": "mvp_cover", "event": event, **common},
        {
            "type": "mvp_table",
            "sex_label": "MEN",
            "event": event,
            "rows": data.get("men", []),
            **common,
        },
        {
            "type": "mvp_table",
            "sex_label": "WOMEN",
            "event": event,
            "rows": data.get("women", []),
            **common,
        },
        {"type": "mvp_cta", "event": event, **common},
    ]

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
