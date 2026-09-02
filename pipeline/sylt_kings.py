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

Ranked by titles, then podiums as the tie-break. The consequence is
deliberate and visible on the chart: Marcilio Browne has four podiums at Sylt
and more than any two-time champion below him, but no title, so he ranks
behind all of them. Winning the event is the thing the list is measuring;
podiums separate riders who won it the same number of times.

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

CRITERIA_NOTE = ("Riders with at least 1 win or 2 podiums \u00b7 "
                 "Titles are wins, podiums are 2nd and 3rd places")

# Photo folders for Sylt, newest first, searched in order for a rider's action
# shot. A venue post spans nearly twenty years, so unlike a single-event
# carousel there is no one folder to read: Marc Pare last sailed Sylt in 2025
# and Alex Mussolini in 2019, and both need a photo. Newest first because a
# recent frame is the one that looks current, and ``pick_photos`` installs into
# these same folders keyed by API event id.
#
# The named folders are the exception: the API only goes back to 2020, so there
# is no id to key 2019 or 2016 by, but the DB has the results and riders on this
# list last sailed the venue in those years. Daida Ruano Moreno's last Sylt was
# 2017 and Iballa's 2019, so without a 2016 folder the twins fall through to the
# h2h fallback, which drops their per-photo crop anchor.
SYLT_PHOTO_EVENTS = (
    16,          # 2025
    27,          # 2024
    39,          # 2023
    48,          # 2022
    64,          # 2021
    75,          # 2020
    "sylt2019",  # 2019 -- not in the API, see above
    "sylt2016",  # 2016 -- not in the API, see above
)


def build_sylt_kings_slides(rows: list[dict], sex: str, editions: dict = None) -> list[dict]:
    """Build the carousel for one division.

    Args:
        rows: Output of ``build_sylt_kings_query``, already ordered by titles
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
    shared = _shared_years(rows)
    criteria = _criteria_note(shared)

    slides = [{
        "type": "sylt_cover",
        "title_word": title_word,
        "division_label": sex.upper(),
        "sample_line": sample,
        "criteria_note": criteria,
        **common,
    }]

    # Counted down, so the cards build to the most-decorated rider and hand
    # straight over to the chart that ranks them. Leading with #1 spends the
    # payoff on slide two and leaves seven cards of diminishing interest after
    # it; ``rows`` stays in ranking order and only the walk is reversed.
    ranked = list(zip(_ranks(rows), rows))
    for rank, row in reversed(ranked):
        slides.append(_rider_slide(row, rank, sample, shared, **common))

    slides.append({
        "type": "sylt_table",
        "slide_title": f"{title_word} OF SYLT",
        "division_label": sex.upper(),
        "sample_line": sample,
        "criteria_note": criteria,
        "rows": _table_rows(rows, shared),
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


def _shared_years(rows: list[dict]) -> set:
    """Years more than one rider on the list won, from the placings.

    Sylt 2008 Wave Women ended with Daida and Iballa Ruano Moreno joint first,
    so the titles on the slides add to one more than the editions counted. That
    looks like an arithmetic error unless the year is marked, and marking it
    from the data means the men's post, which has no shared edition, carries no
    asterisk it cannot explain.
    """
    won = {}
    for row in rows:
        for year, place in _placings(row.get("placings")):
            if place == 1:
                won[year] = won.get(year, 0) + 1
    return {year for year, n in won.items() if n > 1}


def _shared_phrase(years) -> str:
    """"* 2008 title shared", for the footnote and the cards that need it.

    One wording in one place: the card carrying the asterisk and the footnote
    explaining it are read seconds apart, and two phrasings of the same fact
    read as two facts.
    """
    years = sorted(years)
    if not years:
        return ""
    listed = ", ".join(str(y) for y in years)
    return f"* {listed} title{'s' if len(years) > 1 else ''} shared"


def _criteria_note(shared: set) -> str:
    """The fine print, with the asterisk explained when one is in play."""
    if not shared:
        return CRITERIA_NOTE
    return f"{CRITERIA_NOTE} · {_shared_phrase(shared)}"


def _mark(year, shared: set) -> str:
    """A year, asterisked if the title that year was shared."""
    return f"{year}*" if year in shared else str(year)


def _ranks(rows: list[dict]) -> list[int]:
    """Standard competition ranking on the two numbers the list is sorted by.

    Riders level on titles *and* podiums share a rank and the next rank skips
    (1, 1, 3, 3, 3, 6, 7). The sort has a third key, average finish, but it is
    a tie-break for the running order, not a claim that one rider did better
    at the venue: Fernandez and Koster have both won Sylt twice off five
    podiums, and numbering one of them second would invent a gap the record
    does not contain.
    """
    ranks = []
    for i, row in enumerate(rows):
        key = (int(row.get("wins") or 0), int(row.get("podiums") or 0))
        prev = rows[i - 1] if i else None
        if prev is not None and key == (int(prev.get("wins") or 0), int(prev.get("podiums") or 0)):
            ranks.append(ranks[-1])
        else:
            ranks.append(i + 1)
    return ranks


def _rider_slide(row: dict, rank: int, sample: str, shared: set, **common) -> dict:
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
        # A countdown does not need to number itself: the cards already run
        # last-to-first and every one carries the titles and podiums the order
        # is built on. Naming only the top spot makes the climax land instead
        # of arriving as one more number in a sequence.
        "rank_label": "MOST SUCCESSFUL RIDER" if rank == 1 else "",
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
        "years_line": _years_line([y for y, p in placings if p == 1], podiums,
                                  [y for y, _ in placings], shared),
        # Only the riders whose own years carry an asterisk explain it. A note
        # on all eight cards would raise a question seven of them do not answer.
        "shared_note": _shared_phrase([y for y, p in placings
                                       if p == 1 and y in shared]),
        "sample_line": sample,
        "stats": [
            {"value": str(wins), "label": "Titles", "note": ""},
            {"value": str(podiums), "label": "Podiums", "note": "2nd or 3rd"},
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
        # ``resolve_hero_url`` runs its own chain to h2h and the legacy flat
        # photo, so a url that is not inside this event's folder means this
        # event had nothing. Accepting it would end the search at the newest
        # folder for every rider who has any photo at all, and the older Sylt
        # folders would never be read: the Ruano Moreno twins last sailed the
        # venue in 2017 and 2019, and both have a flat photo.
        if url and f"/events/{event_id}/" in url.replace("\\", "/"):
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


def _years_line(win_years: list[int], podiums: int, years: list[int],
                shared: set = frozenset()) -> str:
    """The years won, or what the rider has instead, and the span behind it.

    A rider on the list without a title is there on podiums, so saying nothing
    would leave their card looking like a champion's with the years missing.

    Every card names the venue and the rider's own first and last Sylt, not the
    sample span: "3 podiums" over a decade of starts and "3 podiums" over three
    consecutive years are different records, and the card is the only place
    that distinction can be drawn. Champions get the same treatment, so the
    cards read as one series rather than two.
    """
    head = ("Won " + ", ".join(_mark(y, shared) for y in win_years)
            if win_years else f"{podiums} podiums")
    if not years:
        return f"{head} at Sylt World Cup"
    first, last = min(years), max(years)
    span = first if first == last else f"{first}-{last}"
    return f"{head} at Sylt World Cup, {span}"


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


def _table_rows(rows: list[dict], shared: set = frozenset()) -> list[dict]:
    """The closing summary, one line per rider, in ranking order.

    A table rather than the canary post's bar chart. Eight women qualify, and
    eight bar rows with a thumbnail each ran off the bottom of the slide,
    losing the last rider and the criteria note. The table fits them and
    carries titles, podiums, appearances and the best finish where the bar
    carried one number, which is worth more on the slide that closes the post.
    Appearances is the column that stops the rest being read as a rate: two
    titles from seven starts and two from ten are not the same record.

    Titles and podiums are exclusive, so the two columns add up rather than
    nest, and a rider's total top-three finishes is the sum of them.
    """
    table = []
    for rank, row in zip(_ranks(rows), rows):
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
            "best_years": ", ".join(
                _mark(y, shared) if best_place == 1 else str(y) for y in best_years),
        })

    return table
