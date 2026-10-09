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

# Events with a prize partner, keyed on app/DB event id. The CTA thanks them in
# place of the "next event" push. `logo` is a file in assets/logos/; until it is
# there the CTA sets the partner's name in type instead.
PRIZE_PARTNERS = {
    126: {"name": "SURF Magazin", "logo": "surf-magazin.svg", "scope": "Sylt"},
}

# What calling a rider's exact podium place was worth, from the app's
# fantasy_ranked_scoring.PODIUM_POINTS. Keep in step with it.
PODIUM_POINTS = {1: 25, 2: 15, 3: 10}

# Men's freestyle tiers, in slide order: FANTASY_TIERS value, then the slide
# title in two parts (white, accent), then the slot label on the optimal team. A man with no tier row is 'outside' and can only fill a wildcard
# slot, where the app multiplies his points by WILDCARD_MULTIPLIER.
MEN_TIERS = [
    ("top5", "TOP 5", "TIER", "Top 5"),
    ("6to15", "6-15", "TIER", "6-15"),
    ("outside", "WILD", "CARDS", "Wildcard"),
]
WILDCARD_MULTIPLIER = 1.25

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
    podium_rows: list[dict] | None = None,
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
        podium_rows: rows from build_event_podium_query (athlete_id, place).
            Only for events that ran podium picks; omitted, no rider gets one.

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

    podium_map = {int(r["athlete_id"]): PODIUM_POINTS[int(r["place"])] for r in podium_rows or []}

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
            a["podium_pts"] = podium_map.get(a["athlete_id"], 0)
            a["total_pts"] = round(a["single_pts"] + a["double_pts"] + a["podium_pts"], 2)
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
                    "podium_pts": a["podium_pts"],
                }
            )
        return out

    return {
        "event": event_meta,
        "men": _fleet("Men"),
        "women": _fleet("Women"),
    }


def assemble_tier_view(
    men: list[dict],
    tiers: dict[int, str],
    team_pct: dict[int, int],
    slot_counts: dict[str, int],
    top_n: int = 5,
) -> dict:
    """The men's field split by fantasy tier, plus the best team that could be picked.

    Args:
        men: every scoring man from assemble_mvp_data (podium_pts filled in).
        tiers: athlete_id -> FANTASY_TIERS tier for the event's season.
        team_pct: athlete_id -> % of players with him in a team slot (podium
            calls excluded, so the number means "had him on their team").
        slot_counts: tier -> how many team slots that tier had.

    Returns:
        {"tiers": [{tier, title, rows}], "optimal": {...}}. Wildcard rows carry
        their points with the multiplier applied, as the app scores them.
    """
    view, team = [], []
    for tier, title, accent, slot_label in MEN_TIERS:
        mult = WILDCARD_MULTIPLIER if tier == "outside" else 1.0
        rows = []
        for a in men:
            if tiers.get(a["athlete_id"], "outside") != tier:
                continue
            heat_pts = round(a["single_pts"] + a["double_pts"], 2)
            team_pts = round(heat_pts * mult, 2)
            rows.append({**a, "heat_pts": heat_pts, "team_pts": team_pts,
                         "total_pts": round(team_pts + a["podium_pts"], 2),
                         "pct_picked": team_pct.get(a["athlete_id"], 0)})
        # The optimal team fills each slot on team points; the podium is its own pick.
        for a in sorted(rows, key=lambda r: r["team_pts"], reverse=True)[: slot_counts.get(tier, 0)]:
            team.append({"athlete": a["athlete"], "country": a["country"], "thumb_url": a.get("thumb_url", ""), "tier": slot_label,
                         "multiplier": mult, "heat_pts": a["heat_pts"], "points": a["team_pts"]})
        rows.sort(key=lambda r: r["total_pts"], reverse=True)
        for i, r in enumerate(rows[:top_n], 1):
            r["rank"] = i
        view.append({"tier": tier, "title": title, "accent": accent, "rows": rows[:top_n]})

    podium = sorted((a for a in men if a["podium_pts"]), key=lambda a: -a["podium_pts"])
    team_total = round(sum(t["points"] for t in team), 2)
    podium_total = sum(a["podium_pts"] for a in podium)
    return {
        "tiers": view,
        "optimal": {
            "team": team,
            "podium": [{"athlete": a["athlete"], "country": a["country"], "thumb_url": a.get("thumb_url", ""),
                        "points": a["podium_pts"]} for a in podium],
            "team_total": team_total,
            "podium_total": podium_total,
            "total": round(team_total + podium_total, 2),
        },
    }


def _partner(partner: dict | None) -> dict | None:
    """Attach the logo's file URL, or leave it off while the file isn't in assets/logos/."""
    if not partner:
        return None
    import os
    from pipeline.fourstar_session import LOGOS_DIR, logo_url
    out = dict(partner)
    if os.path.exists(os.path.join(LOGOS_DIR, partner["logo"])):
        out["logo_url"] = logo_url(partner["logo"])
    return out


def _fleet_tables(data: dict, event: dict, common: dict) -> list[dict]:
    """One top-10 table per fleet that ran (the pre-tier layout)."""
    slides = []
    for sex_label, key in (("MEN", "men"), ("WOMEN", "women")):
        rows = data.get(key, [])
        if not rows:
            continue  # the event ran no fleet for this sex (Sylt: no women's freestyle)
        table = {"type": "mvp_table", "sex_label": sex_label, "event": event, "rows": rows, **common}
        if not any(r["double_pts"] for r in rows):
            # Single elimination only: the split would just repeat Total.
            table["col_1_label"] = ""
            table["col_2_label"] = ""
        slides.append(table)
    return slides


def build_slides(data: dict) -> list[dict]:
    """Build the MVP carousel.

    With a tier view: cover → one table per men's tier → optimal team → cta.
    Without: cover → men table → women table → cta (empty fleets dropped).
    """
    common = {"accent_color": SESSION_COLOR}
    event = data.get("event", {})

    partner = _partner(event.get("partner"))
    badge = {"partner_badge": partner} if partner else {}
    slides = [{"type": "mvp_cover", "event": event, "partner": partner, **common}]
    if data.get("tier_view"):
        slides += tier_slides(data["tier_view"], event, common, badge)
    else:
        slides += _fleet_tables(data, event, common)
    slides.append({"type": "mvp_cta", "event": event, "partner": partner, **common})

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides


def tier_slides(tier_view: dict, event: dict, common: dict, badge: dict) -> list[dict]:
    """One table per men's tier, then the optimal team. Shared with slalom_mvps."""
    slides = []
    for t in tier_view["tiers"]:
        wildcard = t["tier"] == "outside"
        table = {
            "type": "mvp_table", "event": event, "rows": t["rows"],
            "title": t["title"], "title_accent": t["accent"], "subtitle": "Top 5 riders in the tier, ranked by total",
            "col_1_label": "Points", "col_3_label": "Total", "show_thumbs": True,
            **badge, **common,
        }
        if wildcard:
            # Show what the rider scored, then the bonus the wildcard slot
            # added on top, so the x1.25 is visible rather than baked in.
            table["col_2_label"] = "x1.25"
            table["col_4_label"] = "Podium"
            table["footnote"] = ("Points = total heat scores &middot; x1.25 = wildcard bonus"
                                 " &middot; Podium = bonus for calling their exact place"
                                 " &middot; Picked = % who had them on their team")
        else:
            table["col_2_label"] = "Podium"
            table["footnote"] = ("Points = total heat scores &middot; Podium = bonus for calling"
                                 " their exact place &middot; Picked = % who had them on their team")
        for r in t["rows"]:
            r["col_1"] = "%.1f" % r["heat_pts"]
            podium = f"+{r['podium_pts']}" if r["podium_pts"] else ""
            if wildcard:
                r["col_2"] = "+%.1f" % (r["team_pts"] - r["heat_pts"])
                r["col_4"] = podium
            else:
                r["col_2"] = podium
            r["col_3"] = "%.1f" % r["total_pts"]
        slides.append(table)
    slides.append({"type": "mvp_optimal", "event": event,
                   "optimal": tier_view["optimal"], **badge, **common})
    return slides
