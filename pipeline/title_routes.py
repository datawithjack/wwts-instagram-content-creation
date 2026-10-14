"""Routes to the world title: the top 4 and what each needs from the last two events.

cover -> the race (where each starts, how far each can go) -> a route card per
rider, counted down to the leader -> cta to Road to Finals

Built from the same endpoint the Road to Finals page uses
(``/rankings/season/{year}``), with the same counting rule: a season counts each
rider's best ``min(5-star events sailed, 4)`` results. The post runs before the
first of the remaining 5-stars, so every number here is taken *after* the window
widens for it. That is the table a fan cannot see on the tour's own rankings,
and the reason a rider with a fourth result in hand starts further up than his
rank says.

A route is a pair of finishes, order-free ("1st + 2nd" means one of each). For
each route the card says either that it wins outright whatever the others do, or
the best each threatening rival may finish and still lose. Rival places exclude
the ones the rider on the card holds: if he wins an event nobody else can.

Limits, stated on the slides rather than hidden:
- Remaining events are priced on the API's baseline 5-star scale; the tour sets
  each event's real scale itself.
- Level on points is left to the tour's tie-break, so a rival "no better than"
  a pair also means not level with it.
- Only the four riders on the post are modelled. A rider further down who wins
  both events is not.
"""

import os
from itertools import product

import requests

from pipeline.api import API_BASE_URL
from pipeline.helpers import ordinal
from pipeline.templates import resolve_hero_focus, resolve_hero_url, resolve_photo_credit, resolve_thumb_url

ACCENT_COLOR = "#E0B04A"  # muted gold: the post is about a title

RIDERS = 4
MAX_COUNTING = 4
PREMIER_STAR = 5

# Routes shown on every card, best first. Order-free pairs.
ROUTES = ((1, 1), (1, 2), (2, 2))

# 2026 photo folders, searched in order. ``pick_photos --event <id> --athletes``
# installs into these, so a shot picked for this post lands where it is read.
# Tenerife leads: its frames came in at full quality (2-2.5MB) where the
# Wissant ones are visibly soft on a full-width band.
PHOTO_EVENTS = (124, 278, 122, 277, 134, 133)
DEFAULT_FOCUS = "center 35%"

# The tag over each rider's name, by current world ranking. Our read of the race.
RIDER_TAGS = {1: "Our title favourite", 2: "The main challenger", 3: "The outside bet", 4: "The dark horse"}

# The cover's own shot, chosen for the post rather than for a rider. Portrait
# framing wants a different frame from the landscape band on the rider cards.
# Missing, the cover falls back to the leader's card shot.
COVER_PHOTO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "assets", "photos", "title_routes", "cover.jpg")

# The names the feed sends are mis-decoded UTF-8 (Paré arrives as "ParÃ©").
def _fix_mojibake(name: str) -> str:
    try:
        return name.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def fetch_season(year: int, timeout: int = 30) -> dict:
    resp = requests.get(f"{API_BASE_URL}/rankings/season/{year}",
                        params={"discipline": "wave", "top": 10}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# ── The maths ──────────────────────────────────────────────────────────────

def _scale(season: dict) -> dict:
    """Place -> points on the 5-star scale, with 0 for not scoring at all."""
    raw = season["baseline_scales"][str(PREMIER_STAR)]
    return {0: 0, **{int(k): v for k, v in raw.items()}}


def _window_after_next(season: dict) -> int:
    """Results that count once the next 5-star has sailed."""
    sailed = sum(1 for e in season["events"]
                 if e.get("star", 0) >= PREMIER_STAR and e.get("status") == "completed")
    return min(sailed + 1, MAX_COUNTING)


def total(points: list, extra: tuple, window: int) -> float:
    return sum(sorted(list(points) + list(extra), reverse=True)[:window])


class Race:
    """The top riders' results and the two events left, ready to ask questions of."""

    def __init__(self, riders: list[dict], scale: dict, window: int):
        self.riders = riders          # [{id, name, rank, points: [...]}]
        self.scale = scale
        self.window = window
        self.places = sorted(p for p in scale if p)

    def score(self, rider: dict, a: int, c: int) -> float:
        return total(rider["points"], (self.scale[a], self.scale[c]), self.window)

    def counting(self, rider: dict) -> list[dict]:
        """The results behind ``start``: the best ``window`` the rider holds."""
        return sorted(rider["results"], key=lambda r: -r["points"])[:self.window]

    def start(self, rider: dict) -> float:
        return self.score(rider, 0, 0)

    def ceiling(self, rider: dict) -> float:
        return self.score(rider, 1, 1)

    def _rival_pairs(self, held: tuple):
        """Every (aloha, chile) a rival can finish, given the places 1-4 the
        rider on the card already holds. Below 4th places are shared."""
        options = self.places + [0]
        for a, c in product(options, options):
            if (a and a <= 4 and a == held[0]) or (c and c <= 4 and c == held[1]):
                continue
            yield a, c

    def conditions(self, rider: dict, route: tuple) -> list[dict]:
        """For each rival who could match this route, the best they may finish.

        Returns [{rival, limits: [(p, q), ...]}], empty when the route wins
        outright. Pairs are sorted best place first and only the maximal ones
        are kept, so "1st + 4th or 2nd + 2nd" rather than every pair below them.
        """
        target = self.score(rider, *route)
        out = []
        for rival in self.riders:
            if rival is rider:
                continue
            pairs = list(self._rival_pairs(route))
            if all(self.score(rival, a, c) < target for a, c in pairs):
                continue
            allowed = {tuple(sorted(p, key=lambda x: x or 999))
                       for p in pairs if self.score(rival, *p) < target}
            # Order-free domination: smaller place is better, 0 (no score) worst.
            key = lambda p: tuple(x or 999 for x in p)
            maximal = [p for p in allowed
                       if not any(q != p and all(qa <= pa for qa, pa in zip(key(q), key(p)))
                                  for q in allowed)]
            out.append({"rival": rival, "limits": sorted(maximal, key=key)})
        return out

    def settle_at_first(self, rider: dict) -> list[dict] | None:
        """Can a win at the first event settle it with one to go?

        Returns, per rival who needs holding back, the best place they may
        finish at the first event so that even a win at the last cannot catch
        up. None when no set of rival results makes it possible.
        """
        floor = self.score(rider, 1, 0)
        out = []
        for rival in self.riders:
            if rival is rider:
                continue
            ok = [p for p in self.places if p != 1 and self.score(rival, p, 1) < floor]
            if not ok:
                return None
            best = min(ok)
            if best > 2:  # 2nd is the best anyone can do once he has won it
                out.append({"rival": rival, "place": best})
        return out


def build_race(season: dict, top: int = RIDERS, sex: str = "Men") -> Race:
    standings = season["standings"][sex][:top]
    breakdown = {b["athlete_id"]: b["results"] for b in season["breakdown"][sex]}
    event_names = {e["event_id"]: short_event(e["name"]) for e in season["events"]}
    riders = [{
        "id": s["athlete_id"],
        "name": _fix_mojibake(s["athlete_name"]),
        "rank": s["rank"],
        "official": s.get("total_points") or 0,
        "country": (s.get("country_code") or "").lower(),
        "image_url": s.get("image_url") or "",
        "points": [r["points"] for r in breakdown.get(s["athlete_id"], [])],
        "results": [{"event": event_names.get(r["event_id"], ""), "place": r["place"], "points": r["points"]}
                    for r in breakdown.get(s["athlete_id"], [])],
    } for s in standings]
    return Race(riders, _scale(season), _window_after_next(season))


# ── Words ──────────────────────────────────────────────────────────────────

# Feed names are sponsor-heavy ("Quatro Maui Pro - USA"); the card wants the venue.
# Matanzas before Chile: it is a 3-star in Chile, and "Chile" on its own reads
# as the Chile World Cup still to come.
VENUES = ("Margaret River", "Gran Canaria", "Tenerife", "Maui", "Fiji", "Wissant",
          "Puerto Rico", "Israel", "Morocco", "Matanzas", "Chile", "Peru", "Cornwall", "Sylt",
          "Aloha", "Mar del Plata", "Pacasmayo", "Dominican Republic", "Brazil")


def short_event(name: str) -> str:
    low = name.lower()
    for venue in VENUES:
        if venue.lower() in low:
            return venue
    return name.split(" - ")[0]


def _surname(name: str) -> str:
    parts = name.split()
    # Two-part Spanish surnames read as one: Paré Rico, not Rico.
    if len(parts) >= 3:
        return " ".join(parts[1:])
    return parts[-1]


def _place(p: int) -> str:
    return ordinal(p) if p else "no score"


def route_label(route: tuple) -> str:
    a, c = route
    if a == c == 1:
        return "WIN BOTH"
    if a == 1:
        return f"WIN + {_place(c).upper()}"
    return f"{_place(a).upper()} + {_place(c).upper()}"


def _limits_text(limits: list[tuple]) -> str:
    if not limits:
        return "must not score"
    return "no better than " + " or ".join(f"{_place(a)} + {_place(b)}" for a, b in limits)


def _points(x: float) -> str:
    return f"{int(x):,}"


# ── Photos ─────────────────────────────────────────────────────────────────

def _hero(athlete_id) -> tuple[str, str, object]:
    """Action shot, crop anchor and folder, searched newest 2026 event first."""
    for event_id in PHOTO_EVENTS:
        url = resolve_hero_url(athlete_id, event_id)
        if url and f"/events/{event_id}/" in url.replace("\\", "/"):
            return url, resolve_hero_focus(athlete_id, event_id, DEFAULT_FOCUS), event_id
    return resolve_hero_url(athlete_id, None), DEFAULT_FOCUS, None


def photo_credits(race: Race) -> list[str]:
    credits = []
    for rider in race.riders:
        _, _, event_id = _hero(rider["id"])
        handle = resolve_photo_credit(rider["id"], event_id) if event_id else ""
        if handle and handle not in credits:
            credits.append(handle)
    return credits


def _screenshot(name: str) -> str:
    """file:// URL for a captured Road to Finals still, or "" when missing."""
    path = os.path.join(os.path.dirname(COVER_PHOTO), "..", "..", "screenshots", name)
    path = os.path.abspath(path)
    return "file:///" + path.replace(os.sep, "/") if os.path.exists(path) else ""


# ── The season so far ──────────────────────────────────────────────────────

# One colour per rider, in ranking order. Muted to sit with the gold accent.
RIDER_COLORS = ("#E0B04A", "#5AB4CC", "#4DA89E", "#C77D9B")

# Chart geometry, in px inside the slide's 960px content width.
CHART_W, CHART_H = 960, 560
X0, X1 = 92, 800          # first and last event column
Y0, Y1 = 26, CHART_H - 46 # rank 1 row and the bottom "6+" row
LEVELS = 6                # 1st..5th, then everything below


def _level(rank) -> int:
    """Row on the chart: 0 for 1st .. 4 for 5th, 5 for 6th or outside the top 10."""
    return rank - 1 if rank and rank <= 5 else LEVELS - 1


def _lead_line(name_ranks: list, events: list) -> str:
    """One fact about a rider's time at or near the top, from the chart ranks."""
    ranks = [r for r, _ in name_ranks]
    if ranks[-1] == 1:
        i = len(ranks) - 1
        while i > 0 and ranks[i - 1] == 1:
            i -= 1
        if name_ranks[i][1]:
            alone = next((events[k] for k in range(i, len(ranks)) if not name_ranks[k][1]), None)
            return f"Joint No.1 after {events[i]}" + (f", alone on top since {alone}" if alone else "")
        return f"World No.1 since {events[i]}"
    led = [(e, j) for e, (r, j) in zip(events, name_ranks) if r == 1]
    if led:
        return ("Joint No.1 after " if all(j for _, j in led) else "Led after ") + _and([e for e, _ in led])
    best = min((r for r in ranks if r), default=None)
    if not best:
        return ""
    return f"Up to {ordinal(best)} after " + _and([e for e, r in zip(events, ranks) if r == best])


def _and(items: list) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _season_slide(season: dict, race: Race, sex: str, common: dict) -> dict:
    """Bump chart of world ranking after each 4 and 5-star event, plus one line per rider."""
    steps = [e for e in season["progression"] if e.get("star", 0) >= 4 and e.get(sex)]
    events = [short_event(e["name"]) for e in steps]
    xs = [X0 + (X1 - X0) * i / max(len(steps) - 1, 1) for i in range(len(steps))]
    row = lambda lvl: Y0 + (Y1 - Y0) * lvl / (LEVELS - 1)

    # Rank per rider per step; a tie is two riders on one rank.
    table = []
    for e in steps:
        ranks = {x["athlete_id"]: x["rank"] for x in e[sex]}
        counts = {}
        for r in ranks.values():
            counts[r] = counts.get(r, 0) + 1
        table.append({aid: (rk, counts[rk] > 1) for aid, rk in ranks.items()})

    # Riders sharing a row at a step (a tie, or both below 5th) are spread a
    # few px apart so every line stays visible.
    all_ranks = [[t.get(r["id"], (None, False)) for t in table] for r in race.riders]
    spread = []
    for k in range(len(steps)):
        groups = {}
        for i, nr in enumerate(all_ranks):
            groups.setdefault(_level(nr[k][0]), []).append(i)
        offs = {}
        for members in groups.values():
            for j, i in enumerate(members):
                offs[i] = (j - (len(members) - 1) / 2) * 12
        spread.append(offs)

    lines, rows = [], []
    for i, rider in enumerate(race.riders):
        color = RIDER_COLORS[i % len(RIDER_COLORS)]
        name_ranks = all_ranks[i]
        points = [(round(x, 1), round(row(_level(rk)) + spread[k][i], 1))
                  for k, (x, (rk, _)) in enumerate(zip(xs, name_ranks))]
        lines.append({"color": color, "points": " ".join(f"{x},{y}" for x, y in points),
                      "dots": [{"x": x, "y": y} for x, y in points],
                      "face": resolve_thumb_url(rider["id"], rider["image_url"]),
                      "end_x": points[-1][0], "end_y": points[-1][1]})
        rows.append({
            "color": color,
            "name": _surname(rider["name"]),
            "rank": rider["rank"],
            "lead": _lead_line(name_ranks, events),
            "results": " · ".join(f"{r['event']} {ordinal(r['place'])}" for r in rider["results"]),
        })

    return {
        "type": "routes_season",
        "chart_w": CHART_W, "chart_h": CHART_H,
        "columns": [{"x": round(x, 1), "label": e} for x, e in zip(xs, events)],
        "levels": [{"y": round(row(l), 1), "label": ordinal(l + 1) if l < LEVELS - 1 else "6th+"}
                   for l in range(LEVELS)],
        "lines": lines,
        "rows": rows,
        **common,
    }


# ── Slides ─────────────────────────────────────────────────────────────────

def _rider_slide(race: Race, rider: dict, next_event: str) -> dict:
    hero_url, focus, _ = _hero(rider["id"])
    routes = []
    for route in ROUTES:
        conds = race.conditions(rider, route)
        routes.append({
            "label": route_label(route),
            "points": _points(race.score(rider, *route)),
            "outright": not conds,
            "conditions": [{"name": _surname(c["rival"]["name"]),
                            "text": _limits_text(c["limits"])} for c in conds],
        })

    settle = race.settle_at_first(rider)
    if settle is not None:
        needs = [f"{_surname(s['rival']['name'])} {ordinal(s['place'])} or worse" for s in settle]
        needs = " and ".join([", ".join(needs[:-1]), needs[-1]] if len(needs) > 1 else needs)
        settle_line = f"Can clinch it at {next_event}: win there" + (f", with {needs}." if needs else ".")
    else:
        settle_line = ""

    first, _, last = rider["name"].partition(" ")
    return {
        "type": "routes_rider",
        "accent_color": ACCENT_COLOR,
        "rank": rider["rank"],
        "tag": RIDER_TAGS.get(rider["rank"], f"World No.{rider['rank']}"),
        "official": _points(rider["official"]),
        "first_name": first,
        "last_name": last,
        "country": rider["country"],
        "photo_url": hero_url or resolve_thumb_url(rider["id"], rider["image_url"]),
        "photo_mode": "action" if hero_url else "portrait",
        "photo_focus": focus,
        "start": _points(race.start(rider)),
        # The results behind the official total, then the one that joins the
        # count at Aloha (or an empty slot), so the card's numbers add up.
        "counting": [{"place": ordinal(r["place"]), "event": r["event"], "points": _points(r["points"]),
                      "joins": i >= race.window - 1}
                     for i, r in enumerate(race.counting(rider))],
        "next_event": next_event,
        "empty_slots": race.window - len(race.counting(rider)),
        "ceiling": _points(race.ceiling(rider)),
        "routes": routes,
        "settle_line": settle_line,
    }


# ── On form: the remaining events priced from each rider's venue record ─────

# How an event's past editions are recognised in the results feed. Pro-Am and
# Cold Hawaii (Denmark) share words with these and are not the same event.
VENUE_EVENTS = {
    "Aloha": lambda name: "Aloha Classic" in name,
    "Chile": lambda name: "Chile World Cup" in name,
}
FORM_EDITIONS = 3


def fetch_results(athlete_id: int, timeout: int = 30) -> list[dict]:
    rows, page = [], 1
    while True:
        resp = requests.get(f"{API_BASE_URL}/athletes/results",
                            params={"athlete_id": athlete_id, "page": page, "page_size": 100}, timeout=timeout)
        resp.raise_for_status()
        batch = resp.json()["results"]
        rows += batch
        if len(batch) < 100:
            return rows
        page += 1


def venue_record(results: list[dict], venue: str, season_year: int, sex: str = "Men") -> list[tuple]:
    """(year, place) at the venue over its last three editions before this season."""
    years = range(season_year - FORM_EDITIONS, season_year)
    out = []
    for r in results:
        if (r.get("event_year") in years and VENUE_EVENTS[venue](r.get("event_name") or "")
                and r.get("division_label") == f"Wave {sex}" and str(r.get("placement")).isdigit()):
            out.append((r["event_year"], int(r["placement"])))
    return sorted(out)


def form_best(record: list[tuple], places: list[int]) -> int:
    """Best finish at the venue, snapped to the place it scores as."""
    return max(p for p in places if p <= min(pl for _, pl in record))


def form_place(record: list[tuple], places: list[int]) -> int:
    """Median finish, snapped to the scale place it shares points with (8th pays as 7th)."""
    vals = sorted(p for _, p in record)
    n = len(vals)
    median = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    return max(p for p in places if p <= round(median))


def _shift(form: dict, rider, place: int) -> dict:
    """One event's places once ``rider`` finishes ``place`` instead of his form one.

    1st-4th are single places, so the rivals between the two move: down one if
    he finishes higher than his form (he takes a place one of them held), up one
    if he finishes lower (he vacates one). Places below 4th are shared bands and
    unmodelled riders fill them, so nobody beyond 4th moves.
    """
    f = form[rider]
    out = {rider: place}
    at = place or 999  # no score finishes behind everyone
    for rid, q in form.items():
        if rid == rider:
            continue
        if at < f and at <= q < f and q <= 4:
            q += 1
        elif at > f and f < q <= at and q <= 4:
            q -= 1
        out[rid] = q
    return out


def needed(race: Race, rider: dict, form: dict, best: dict) -> tuple | None:
    """The most believable (aloha, chile) that wins the title, with every rival
    on their form finish.

    Believable = the smallest step beyond what the rider has already done at
    each venue (his best there over the last three editions), in points; then
    the fewest points overall. So a rider who has won Aloha is asked to win
    Aloha before he is asked to win in Chile, where his best is 7th.
    """
    found = None
    options = race.places + [0]  # 0: no points needed from that event at all
    for a, c in product(options, options):
        al = _shift({r["id"]: form[r["id"]]["Aloha"] for r in race.riders}, rider["id"], a)
        ch = _shift({r["id"]: form[r["id"]]["Chile"] for r in race.riders}, rider["id"], c)
        mine = race.score(rider, a, c)
        rivals = [(race.score(r, al[r["id"]], ch[r["id"]]), r) for r in race.riders if r is not rider]
        closest = max(rivals, key=lambda x: x[0])
        if mine > closest[0]:
            stretch = (max(0, race.scale[a] - race.scale[best["Aloha"]])
                       + max(0, race.scale[c] - race.scale[best["Chile"]]))
            key = (stretch, race.scale[a] + race.scale[c])
            if found is None or key < found[0]:
                found = (key, a, c, mine, closest[1], mine - closest[0])
    return found[1:] if found else None


def slips(race: Race, rider: dict, form: dict, need: tuple) -> list[str]:
    """Events where the closest rival finishing one place better than his
    projection would take the title off ``rider`` on the needed route."""
    a, c, mine, rival, _ = need
    al = _shift({k: v["Aloha"] for k, v in form.items()}, rider["id"], a)
    ch = _shift({k: v["Chile"] for k, v in form.items()}, rider["id"], c)
    better = lambda p: max((q for q in race.places if q < p), default=p)
    out = []
    for venue, places in (("Aloha", al), ("Chile", ch)):
        ra, rc = al[rival["id"]], ch[rival["id"]]
        if venue == "Aloha":
            ra = better(ra)
        else:
            rc = better(rc)
        if race.score(rival, ra, rc) >= mine:
            out.append(venue)
    return out


def needed_text(pair: tuple) -> tuple[str, str]:
    """Headline and sub-line for a required pair, e.g. ("5TH AT ALOHA", "Any result in Chile")."""
    a, c = pair
    if a == c == 1:
        return "WIN BOTH", ""
    at = lambda p, v: ("WIN " if p == 1 else f"{ordinal(p).upper()} ") + ("AT ALOHA" if v == "Aloha" else "IN CHILE")
    if not c:
        return at(a, "Aloha"), "Any result in Chile"
    if not a:
        return at(c, "Chile"), "Any result at Aloha"
    return f"{at(a, 'Aloha')} + {at(c, 'Chile')}", ""


def _edge_text(race: Race, rider: dict, form: dict, need: tuple | None) -> str:
    if not need:
        return ""
    who = _surname(need[3]["name"])
    head = f"Only {_points(need[4])} pts clear of {who}"
    flips = slips(race, rider, form, need)
    if len(flips) == 2:
        return f"{head}: one place better for {who} at either event and it slips away."
    if flips:
        return f"{head}: one place better for {who} {'at Aloha' if flips[0] == 'Aloha' else 'in Chile'} and it slips away."
    return f"{head}: {who} would need to finish more than one place above his projection."


def scenario(race: Race, rider: dict, form: dict, need: tuple) -> list[dict]:
    """Everyone's finishes and totals on ``rider``'s needed route, best first."""
    a, c = need[:2]
    al = _shift({k: v["Aloha"] for k, v in form.items()}, rider["id"], a)
    ch = _shift({k: v["Chile"] for k, v in form.items()}, rider["id"], c)
    rows = [{"name": _surname(r["name"]),
             "aloha": ordinal(al[r["id"]]) if al[r["id"]] else "Any",
             "chile": ordinal(ch[r["id"]]) if ch[r["id"]] else "Any",
             "total": race.score(r, al[r["id"]], ch[r["id"]]),
             "me": r is rider} for r in race.riders]
    rows.sort(key=lambda x: -x["total"])
    for r in rows:
        r["total"] = _points(r["total"])
    return rows


def form_paragraph(rider: dict, p: dict, leader: dict) -> str:
    """What the venue record suggests, in a sentence or two."""
    def leg(v):
        hist = ", ".join(f"{ordinal(pl)} in {y}" for y, pl in p["record"][v])
        where = "at Aloha" if v == "Aloha" else "in Chile"
        return f"{ordinal(p['finish'][v])} {where} ({hist})"
    name = _surname(rider["name"])
    outcome = (f"That makes {name} world champion on {_points(p['total'])} pts."
               if p["position"] == 1 else
               f"That puts {name} {ordinal(p['position'])}, "
               f"{_points(leader['total'] - p['total'])} pts behind {_surname(leader['name'])}.")
    return f"Previous results point to {leg('Aloha')} and {leg('Chile')}. {outcome}"


def _form_slides(season: dict, race: Race, sex: str, common: dict) -> tuple[list, dict]:
    """Rider cards and the projected table for the on-form version."""
    proj = {}
    for rider in race.riders:
        results = fetch_results(rider["id"])
        rec = {v: venue_record(results, v, season["year"], sex) for v in VENUE_EVENTS}
        fin = {v: form_place(rec[v], race.places) for v in VENUE_EVENTS}
        proj[rider["id"]] = {"record": rec, "finish": fin,
                             "total": race.score(rider, fin["Aloha"], fin["Chile"])}

    form = {rid: p["finish"] for rid, p in proj.items()}
    for rider in race.riders:
        best = {v: form_best(proj[rider["id"]]["record"][v], race.places) for v in VENUE_EVENTS}
        proj[rider["id"]]["needed"] = needed(race, rider, form, best)

    order = sorted(race.riders, key=lambda r: -proj[r["id"]]["total"])
    top = proj[order[0]["id"]]["total"]
    for pos, rider in enumerate(order, 1):
        p = proj[rider["id"]]
        p["position"] = pos
        p["verdict"] = ("World champion" if pos == 1
                        else f"{ordinal(pos)}, {_points(top - p['total'])} behind")

    years = list(range(season["year"] - FORM_EDITIONS, season["year"]))
    history = {
        "type": "routes_history",
        "years": years,
        "season_year": season["year"],
        "venues": [{
            "name": "Aloha Classic" if v == "Aloha" else "Chile World Cup",
            "rows": [{
                "name": _surname(r["name"]),
                "face": resolve_thumb_url(r["id"], r["image_url"]),
                "cells": [next((ordinal(pl) for y, pl in proj[r["id"]]["record"][v] if y == yr), "–")
                          for yr in years],
                "projected": ordinal(proj[r["id"]]["finish"][v]),
            } for r in race.riders],
        } for v in VENUE_EVENTS],
        **common,
    }

    table = {
        "type": "routes_form_table",
        "rows": [{
            "position": proj[r["id"]]["position"],
            "name": _surname(r["name"]),
            "face": resolve_thumb_url(r["id"], r["image_url"]),
            "aloha": ordinal(proj[r["id"]]["finish"]["Aloha"]),
            "chile": ordinal(proj[r["id"]]["finish"]["Chile"]),
            "total": _points(proj[r["id"]]["total"]),
            "gap": "" if proj[r["id"]]["position"] == 1 else "-" + _points(top - proj[r["id"]]["total"]),
        } for r in order],
        **common,
    }
    return proj, table, history


def build_title_routes_slides(season: dict, sex: str = "Men", mode: str = None) -> list[dict]:
    race = build_race(season, sex=sex)
    remaining = [e for e in season["events"] if e.get("predictable")]
    next_event = "Aloha" if remaining and "Aloha" in remaining[0]["name"] else "the next event"
    common = {"accent_color": ACCENT_COLOR}

    slides = [{
        "type": "routes_cover",
        "count": len(race.riders),
        "year": season["year"],
        "events_left": " + ".join("Aloha" if "Aloha" in e["name"] else "Chile" if "Chile" in e["name"] else e["name"]
                                  for e in remaining),
        "riders": [{"name": _surname(r["name"]), "face": resolve_thumb_url(r["id"], r["image_url"]),
                    "rank": r["rank"]} for r in race.riders],
        "photo_url": ("file:///" + COVER_PHOTO.replace(os.sep, "/")) if os.path.exists(COVER_PHOTO)
                     else _hero(race.riders[0]["id"])[0],
        "photo_focus": "center 30%" if os.path.exists(COVER_PHOTO) else _hero(race.riders[0]["id"])[1],
        **common,
    }, _season_slide(season, race, sex, common)]
    proj, table, history = _form_slides(season, race, sex, common) if mode == "form" else ({}, None, None)
    if proj:
        top = min(race.riders, key=lambda r: proj[r["id"]]["position"])
        leader = {"name": top["name"], "total": proj[top["id"]]["total"]}
    if history:
        slides.append(history)
    for rider in reversed(race.riders):
        slide = _rider_slide(race, rider, next_event)
        if mode == "form":
            p = proj[rider["id"]]
            need = p["needed"]
            head, sub = needed_text(need[:2]) if need else ("OUT OF REACH", "")
            slide["form"] = {
                "need_head": head,
                "need_sub": sub,
                "need_total": _points(need[2]) if need else "",
                # The minimum is just enough by construction: say by how much,
                # and over whom, so one rival beating his form reads as the risk.
                "need_edge": _edge_text(race, rider, {k: v["finish"] for k, v in proj.items()}, need),
                "table": scenario(race, rider, {k: v["finish"] for k, v in proj.items()}, need) if need else [],
                "paragraph": form_paragraph(rider, p, leader),
                "venues": [{"name": v,
                            "history": " · ".join(f"{y} {ordinal(pl)}" for y, pl in p["record"][v]),
                            "finish": ordinal(p["finish"][v])} for v in VENUE_EVENTS],
                "total": _points(p["total"]),
                "verdict": p["verdict"],
                "champion": p["position"] == 1,
            }
        slides.append(slide)
    if table:
        slides.append(table)
    slides.append({
        "type": "routes_app",
        "pick_url": _screenshot("rtf_pick.png"),
        "outcome_url": _screenshot("rtf_outcome.png"),
        **common,
    })
    slides.append({"type": "routes_cta", **common})
    return slides
