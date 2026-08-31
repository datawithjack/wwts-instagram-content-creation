"""Kings / Queens of Sylt — one venue, one division, one carousel.

cover -> a photo card per rider, counted down -> summary table -> cta

The photo-led descendant of ``canary_kings``. That post answered its question
with a single stacked bar chart, which works when the whole story is "who has
the most" across two venues. Sylt is one venue, so the split that made the
stack informative does not exist, and a lone bar chart of a single number is a
thin post. Here the ranking is carried by a card per rider, full-bleed action
shot where one exists, and a table closes the post as a summary of what the
cards just walked through rather than as the whole argument.

The cards count down, so the most-decorated rider lands immediately before the
table that ranks them.

Ranked by podiums, not titles, because that is what the list is measuring.
The consequence is deliberate and visible on the chart: Marcilio Browne leads
three two-time champions on four podiums and no title, and Marine Hunter, a
Sylt champion, ranks last on one. Sorting by titles first would bury the most
consistent rider at the venue behind riders who won twice and finished nowhere
otherwise.

Inclusion is one win or two podiums. Every qualifying rider gets a card, with
or without a photo: cutting the riders whose shots the library happens to be
missing would drop Victor Fernandez, joint most-decorated man at Sylt, out of
his own ranking. Cards without an action shot fall back to a headshot sized
inside the same hero footprint, the way ``finals_recap`` does it.
"""

from pipeline.helpers import nationality_to_iso
from pipeline.templates import resolve_hero_focus, resolve_hero_url, resolve_thumb_url

# Sylt is side-on and waist-high: the rider sits low and central in most
# frames, so the default anchor sits higher than a jumping shot would want.
# Per-photo overrides live in each event folder's focus.json.
DEFAULT_FOCUS = "center 30%"

ACCENT_COLOR = "#9478B5"  # muted violet — the editorial accent, as canary_kings

CRITERIA_NOTE = "Riders with at least 1 win or 2 podiums"

# API event ids for Sylt, newest first, searched in order for a rider's action
# shot. A venue post spans nearly twenty years, so unlike a single-event
# carousel there is no one folder to read: Marc Pare last sailed Sylt in 2025
# and Alex Mussolini in 2019, and both need a photo. Newest first because a
# recent frame is the one that looks current, and ``pick_photos`` installs into
# these same folders keyed by API event id.
SYLT_PHOTO_EVENTS = (
    16,   # 2025
    27,   # 2024
    39,   # 2023
    48,   # 2022
    64,   # 2021
    75,   # 2020
)


def build_sylt_kings_slides(rows: list[dict], sex: str, editions: dict = None) -> list[dict]:
    """Build the carousel for one division.

    Args:
        rows: Output of ``build_sylt_kings_query``, already ordered by podiums
              descending. Keys used: athlete, nationality, athlete_id,
              photo_url, wins, podiums, starts, best_finish, win_years.
        sex: "Men" or "Women" — picks the KINGS/QUEENS wording.
        editions: Optional dict from ``build_sylt_editions_query`` with
                  editions, first_year, last_year. Drives the sample line.

    Returns:
        List of slide dicts: cover, one per rider, chart, cta.
    """
    title_word = "KINGS" if sex == "Men" else "QUEENS"
    common = {"accent_color": ACCENT_COLOR}
    sample = _sample_line(editions)

    slides = [{
        "type": "sylt_cover",
        "title_word": title_word,
        "division_label": sex.upper(),
        "sample_line": sample,
        "criteria_note": CRITERIA_NOTE,
        **common,
    }]

    # Counted down, so the cards build to the most-decorated rider and hand
    # straight over to the chart that ranks them. Leading with #1 spends the
    # payoff on slide two and leaves seven cards of diminishing interest after
    # it; ``rows`` stays in ranking order and only the walk is reversed.
    ranked = list(enumerate(rows, 1))
    for rank, row in reversed(ranked):
        slides.append(_rider_slide(row, rank, sample, **common))

    slides.append({
        "type": "sylt_table",
        "slide_title": f"{title_word} OF SYLT",
        "division_label": sex.upper(),
        "sample_line": sample,
        "criteria_note": CRITERIA_NOTE,
        "rows": _table_rows(rows),
        **common,
    })
    slides.append({"type": "analysis_cta", **common})

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides


def _sample_line(editions: dict) -> str:
    """State the sample the ranking is drawn from, e.g. "10 editions, 2008-2025".

    Six Sylt editions are missing from the data and three more are unusable,
    so a bare "since 2005" would claim a completeness the numbers do not have.
    """
    if not editions or not editions.get("editions"):
        return "Sylt, Germany"
    first, last = editions.get("first_year"), editions.get("last_year")
    span = f", {first}-{last}" if first and last else ""
    return f"{int(editions['editions'])} editions{span}"


def _rider_slide(row: dict, rank: int, sample: str, **common) -> dict:
    """One rider's card.

    ``photo_mode`` picks the layout: a landscape action shot goes full bleed,
    and anything else is a headshot sized inside the same footprint. The two
    are separate layouts on purpose — a face crop stretched to 1080x1350 looks
    broken, which is exactly what one shared layout would force.
    """
    athlete_id = row.get("athlete_id")
    name = row.get("athlete") or ""
    first_name, _, last_name = name.partition(" ")

    hero_url, focus = _hero(athlete_id)
    photo_mode = "action" if hero_url else "portrait"
    photo_url = hero_url or resolve_thumb_url(athlete_id, row.get("photo_url") or "")

    wins = int(row.get("wins") or 0)
    podiums = int(row.get("podiums") or 0)
    placings = _placings(row.get("placings"))
    best_place, best_years = _best(placings, row.get("best_finish"))

    return {
        "type": "sylt_rider",
        "rank": rank,
        "rank_label": f"#{rank}",
        "athlete_name": name,
        "first_name": first_name,
        "last_name": last_name,
        "name_class": _name_class(last_name),
        "country": nationality_to_iso(row.get("nationality") or ""),
        "athlete_id": athlete_id,
        "photo_url": photo_url,
        "photo_mode": photo_mode,
        "photo_focus": focus,
        "is_champion": wins > 0,
        "years_line": _years_line([y for y, p in placings if p == 1], podiums),
        "sample_line": sample,
        "stats": [
            {"value": str(podiums), "label": "Podiums", "note": ""},
            {"value": str(wins), "label": "Titles", "note": ""},
            {"value": str(int(row.get("starts") or 0)), "label": "Appearances", "note": ""},
            # A best finish is worth more with its date on it: 2nd in 2008 and
            # 2nd across 2017, 2019 and 2024 are the same cell otherwise.
            {"value": _place_label(best_place), "label": "Best",
             "note": ", ".join(str(y) for y in best_years)},
        ],
        **common,
    }


def _hero(athlete_id) -> tuple[str, str]:
    """A rider's action shot and its crop anchor, from the Sylt event folders.

    Returns ("", "") when nothing landscape resolves, which is the signal for
    the portrait layout. The crop anchor comes from the same folder as the
    photo, so a shot picked at Sylt 2022 keeps the anchor it was cropped with.
    """
    if not athlete_id:
        return "", ""
    for event_id in SYLT_PHOTO_EVENTS:
        url = resolve_hero_url(athlete_id, event_id)
        if url:
            return url, resolve_hero_focus(athlete_id, event_id, DEFAULT_FOCUS)
    # Nothing at Sylt: a shot cropped for a head-to-head or the legacy flat
    # photo still beats dropping the rider to a headshot.
    return resolve_hero_url(athlete_id, None), DEFAULT_FOCUS


def _placings(raw) -> list[tuple[int, int]]:
    """Parse the query's "2008:1,2012:3" column into (year, place) pairs.

    Anything malformed is dropped rather than raised on: a bad placing costs
    one line of a card, and failing the render costs the post.
    """
    pairs = []
    for chunk in str(raw or "").split(","):
        year, _, place = chunk.partition(":")
        if year.strip().isdigit() and place.strip().isdigit():
            pairs.append((int(year), int(place)))
    return sorted(pairs)


def _best(placings: list[tuple[int, int]], fallback) -> tuple[int, list[int]]:
    """The rider's best finish and every year they matched it."""
    if not placings:
        try:
            return int(fallback), []
        except (TypeError, ValueError):
            return 0, []
    best = min(place for _, place in placings)
    return best, [year for year, place in placings if place == best]


def _years_line(win_years: list[int], podiums: int) -> str:
    """The years won, or what the rider has instead.

    A rider on the list without a title is there on podiums, so saying nothing
    would leave their card looking like a champion's with the years missing.
    """
    if win_years:
        return "Won " + ", ".join(str(y) for y in win_years)
    return f"{podiums} podiums, no title yet"


def _place_label(place) -> str:
    """A finishing place as an ordinal chip: 1ST, 2ND, 3RD."""
    try:
        value = int(place)
    except (TypeError, ValueError):
        return "-"
    if not value:
        return "-"
    suffix = {1: "ST", 2: "ND", 3: "RD"}.get(value, "TH")
    return f"{value}{suffix}"


def _name_class(last_name: str) -> str:
    """Step the surname size down so long names stay inside the card."""
    length = len(last_name)
    if length >= 18:
        return "xlong"
    if length >= 13:
        return "long"
    return ""


def _table_rows(rows: list[dict]) -> list[dict]:
    """The closing summary, one line per rider, in ranking order.

    A table rather than the canary post's bar chart. Eight women qualify, and
    eight bar rows with a thumbnail each ran off the bottom of the slide,
    losing the last rider and the criteria note. The table fits them and
    carries podiums, titles and the best finish where the bar carried one
    number, which is worth more on the slide that closes the post.
    """
    table = []
    for rank, row in enumerate(rows, 1):
        athlete_id = row.get("athlete_id")
        placings = _placings(row.get("placings"))
        best_place, best_years = _best(placings, row.get("best_finish"))

        table.append({
            "rank": rank,
            "athlete": row.get("athlete") or "",
            "country": nationality_to_iso(row.get("nationality") or ""),
            "athlete_id": athlete_id,
            "photo_url": resolve_thumb_url(athlete_id, row.get("photo_url") or ""),
            "podiums": int(row.get("podiums") or 0),
            "wins": int(row.get("wins") or 0),
            "starts": int(row.get("starts") or 0),
            "best_label": _place_label(best_place),
            "best_years": ", ".join(str(y) for y in best_years),
        })

    return table
