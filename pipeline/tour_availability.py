"""Tour availability infographic reel — content builder for a single animated page.

Illustrates The Tour's one-pick-per-season rule across two events (Gran Canaria ->
Tenerife). Each athlete can be picked once all season, so the five "spent" at Gran
Canaria are unavailable at Tenerife and the pool shrinks. Uses 2025 (completed /
practice) data so the line-up is real, not provisional.

Returns a flat dict consumed directly by templates/tour_availability_reel.html.
Athlete `used=True` means picked at GC (greyed out at Tenerife); `used=False` means
still available. `photo` is an absolute headshot URL (the app's profile_picture_url)
or None, which falls back to an initials avatar in the template.

`build_tour_availability_reel_data()` returns a curated offline pool (for --dry-run /
tests). `build_tour_availability_live()` fetches the real 2025 line-up from the
fantasy API (real photos, world ranks, last-year finishes, % picked).
"""

# Tour accent — the canonical muted IG cyan (base.html --color-accent).
TOUR_ACCENT = "#5AB4CC"

# 2025 fantasy event ids (resolved from /fantasy/seasons/2025).
GC_2025_EVENT_ID = 12
TENERIFE_2025_EVENT_ID = 14


def _roster() -> list[dict]:
    """Curated 2025 wave-tour pool. Five marked used (spent at Gran Canaria).

    Each athlete carries the same metadata the app's AthleteCard shows: world
    ranking (`wr`), last-season finish (`finish`), and % picked (`pct`). `face` is
    an optional headshot asset id (assets/photos/{face}.jpg); None falls back to an
    initials avatar, mirroring the app's Avatar fallback.
    """
    return [
        # Spent at Gran Canaria — unavailable at Tenerife.
        {"name": "Philip Köster", "country": "DE", "sex": "M", "wr": 1, "finish": "1st '25", "pct": "42%", "used": True, "photo": None},
        {"name": "Marcilio Browne", "country": "BR", "sex": "M", "wr": 2, "finish": "2nd '25", "pct": "31%", "used": True, "photo": None},
        {"name": "Marc Paré Rico", "country": "ES", "sex": "M", "wr": 4, "finish": "4th '25", "pct": "17%", "used": True, "photo": None},
        {"name": "Sarah-Quita Offringa", "country": "AW", "sex": "F", "wr": 1, "finish": "1st '25", "pct": "55%", "used": True, "photo": None},
        {"name": "Daida Ruano Moreno", "country": "ES", "sex": "F", "wr": 2, "finish": "2nd '25", "pct": "24%", "used": True, "photo": None},
        # Still available at Tenerife.
        {"name": "Ricardo Campello", "country": "BR", "sex": "M", "wr": 5, "finish": "5th '25", "pct": "19%", "used": False, "photo": None},
        {"name": "Víctor Fernández", "country": "ES", "sex": "M", "wr": 7, "finish": "7th '25", "pct": "12%", "used": False, "photo": None},
        {"name": "Iballa Ruano Moreno", "country": "ES", "sex": "F", "wr": 4, "finish": "4th '25", "pct": "15%", "used": False, "photo": None},
        {"name": "Lina Erpenstein", "country": "DE", "sex": "F", "wr": 3, "finish": "3rd '25", "pct": "21%", "used": False, "photo": None},
        {"name": "Alexia Kiefer Quintana", "country": "ES", "sex": "F", "wr": 6, "finish": "6th '25", "pct": "9%", "used": False, "photo": None},
    ]


def _captains(roster: list[dict]) -> list[dict]:
    """The illustrative captains: the top used man + top used woman."""
    men = [a for a in roster if a["sex"] == "M" and a["used"]]
    women = [a for a in roster if a["sex"] == "F" and a["used"]]
    caps = []
    if men:
        caps.append(men[0])
    if women:
        caps.append(women[0])
    return caps


def _base_data(roster: list[dict]) -> dict:
    """Shared copy + structure for the reel, given a roster."""
    return {
        "accent_color": TOUR_ACCENT,

        # Screen 1 — brand intro (THE TOUR, pronounced)
        "intro_eyebrow": "Windsurf Fantasy League",
        "intro_title": "THE TOUR",
        "intro_sub": "One squad. The whole season. Pick your riders, event by event.",

        # Screen 2 — the rule
        "hook_kicker": "The one rule",
        "hook_title": "ONE PICK\nPER SEASON",
        "hook_sub": "Pick a rider once. Use them and they’re gone for the rest of the season.",

        # The two events (2025 practice data)
        "event1": {"name": "GRAN CANARIA", "year": "2025", "label": "Event 1"},
        "event2": {"name": "TENERIFE", "year": "2025", "label": "Event 2"},

        # Shared pool — used=True were spent at GC (greyed at Tenerife)
        "roster": roster,

        "event1_caption": "Spend 5 of your stars at Gran Canaria.",
        "event2_caption": "Those 5 are gone — at Tenerife you pick from who’s left.",

        # Screen 5 — captain exception
        "captain_kicker": "The one exception",
        "captain_title": "YOUR CAPTAINS",
        "captain_text": "Name a men’s & women’s captain from the Top 5 — they’re the only riders you can pick twice.",
        "captains": _captains(roster),

        # Screen 6 — CTA
        "cta_headline": "CHOOSE WISELY",
        "cta_subtitle": "Every pick costs you a star for the whole season.",
        "handle": "@windsurfworldtourstats",
        "url": "windsurfworldtourstats.com",
    }


def build_tour_availability_reel_data() -> dict:
    """Build the content dict for the Tour-availability infographic reel (offline)."""
    return _base_data(_roster())


def select_roster(startlist: list, pick_stats: dict | None = None,
                  n_men: int = 5, n_women: int = 5,
                  used_men: int = 3, used_women: int = 2) -> list[dict]:
    """Pick a balanced roster from a fantasy start list and mark the GC "spend".

    Takes the top `n_men`/`n_women` by world rank (only athletes that have both a
    photo and a rank — so the cards render cleanly), marks the highest `used_men` +
    `used_women` as spent at Gran Canaria, and merges in % picked. Returns cards in
    display order: used first, then available.
    """
    pct_map = {}
    if pick_stats:
        for item in pick_stats.get("athletes", []):
            pct_map[item["athlete_id"]] = item.get("pick_pct")

    def usable(a):
        return a.get("profile_picture_url") and a.get("world_rank")

    cands = [a for a in startlist if usable(a)]
    men = sorted([a for a in cands if a.get("sex") == "Men"], key=lambda a: a["world_rank"])[:n_men]
    women = sorted([a for a in cands if a.get("sex") == "Women"], key=lambda a: a["world_rank"])[:n_women]
    used_ids = {a["athlete_id"] for a in men[:used_men]} | {a["athlete_id"] for a in women[:used_women]}

    def to_card(a):
        pct = pct_map.get(a["athlete_id"])
        return {
            "name": a["athlete_name"],
            "country": a.get("country_code") or "",
            "sex": "M" if a.get("sex") == "Men" else "F",
            "wr": a.get("world_rank"),
            "finish": a.get("prev_year_result"),
            "pct": f"{round(pct)}%" if pct is not None else None,
            "used": a["athlete_id"] in used_ids,
            "photo": a.get("profile_picture_url"),
        }

    # Used first (clusters the GC "picked" stamps at the top), then available.
    ordered = men[:used_men] + women[:used_women] + men[used_men:] + women[used_women:]
    return [to_card(a) for a in ordered]


def build_tour_availability_live(year: int = 2025) -> dict:
    """Build the reel dict from the live fantasy API (real 2025 line-up + photos)."""
    from pipeline import fantasy_api as fa

    token = fa.login()
    season = fa.get_season(year, token)
    gc = fa.find_event(season, "canaria") or fa.find_event(season, "gran")
    if gc is None:
        raise RuntimeError(f"Could not find a Gran Canaria event in season {year}")
    startlist = fa.get_startlist(gc["id"], token)
    try:
        pick_stats = fa.get_pick_stats(gc["id"], token)
    except Exception:
        pick_stats = None

    roster = select_roster(startlist, pick_stats)
    data = _base_data(roster)
    data["event1"] = {"name": "GRAN CANARIA", "year": str(year), "label": "Event 1"}
    data["event2"] = {"name": "TENERIFE", "year": str(year), "label": "Event 2"}
    return data
