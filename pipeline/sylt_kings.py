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
from pipeline.templates import (
    resolve_face_credit,
    resolve_hero_focus,
    resolve_hero_url,
    resolve_photo_credit,
    resolve_thumb_url,
)

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
    # Freestyle ran at Sylt alongside the wave event, and the freestyle riders
    # are a mostly separate cast who never appear in the wave folders above.
    # Kept in one folder rather than per year because the shots span 2018 to
    # 2022 and no freestyle rider has more than one.
    #
    # Last, so a rider who sails both disciplines keeps the wave shot the wave
    # post already uses. Nobody on either list is currently in both, so the
    # order is not yet load-bearing; the day someone is, this wants to be
    # searched first for a freestyle post rather than last for every post.
    "syltfreestyle",
)


# Riders the ATHLETES table does not carry cleanly. The freestyle list is old
# enough to reach names the scrape stored as a nickname in brackets, as a bare
# surname, or with no nationality at all, and a card is 1080px of one rider's
# name and flag. Fixing it here rather than in the DB keeps a content change
# out of the app's data, but the DB is the better home if this grows.
NAME_OVERRIDES = {
    202: "Gollito Estredo",          # stored as: Jose "Gollito" Estredo
    722: "Taty Frans",               # stored as: Elton (Taty) Frans
    723: "Tonky Frans",              # stored as: Everon (Tonky) Frans
    890: "Steven Van Broeckhoven",   # stored as: Van Broeckhoven, no first name
}

NATIONALITY_OVERRIDES = {
    722: "Bonaire",   # NULL in ATHLETES
    723: "Bonaire",
    888: "Bonaire",   # Kiri Thode
    890: "Belgium",
    892: "Belgium",   # Yentel Caers
}


# The table cell is nowrap with an ellipsis at 36px, and the longest name that
# fits is about this many characters. Past it the surname gets cut mid-word,
# which is worse than losing the first name.
TABLE_NAME_MAX = 18


def _table_name(name: str) -> str:
    """A rider's name, shortened to fit the table's one line.

    Drops the first name to an initial rather than truncating, because the
    surname is what identifies the rider: "S. Van Broeckhoven" reads, where
    "Steven Van Broeck..." does not. A single-word name is left alone, having
    nothing to give up.
    """
    if len(name) <= TABLE_NAME_MAX:
        return name
    first, _, rest = name.partition(" ")
    if not rest:
        return name
    return f"{first[0]}. {rest}"


def _athlete_name(row: dict) -> str:
    """The rider's name as it should read on a slide."""
    return NAME_OVERRIDES.get(row.get("athlete_id")) or row.get("athlete") or ""


def _nationality(row: dict) -> str:
    """The rider's nationality, filled in where the DB has none."""
    return row.get("nationality") or NATIONALITY_OVERRIDES.get(row.get("athlete_id"), "")


def _title_lines(sex: str) -> tuple:
    """The cover headline, as the three lines it is set on.

    Every discipline gets the same headline for now; the eyebrow carries the
    discipline. Set as lines rather than one string because the autofit only
    shrinks on overflow, and a line long enough to wrap grows the block by a
    whole line instead: "MOST STYLISH" took the cover from 898px to 1197px.
    """
    return ("KINGS" if sex == "Men" else "QUEENS", "OF", "SYLT")


VENUE = "Sylt, Germany"

# How a discipline is named on the slides, where that differs from the name the
# query is built on. Sylt's slalom splits at 2023: fin to 2023, foil from 2024,
# and the post ranks the fin era only. Labelling it "Slalom" would read as the
# whole record and leave a reader asking why Johan Soe, who won 2024 and 2025,
# is missing. Riders on this list sailed both, so the ambiguity is real: Amado
# Vrieswijk and Matteo Iachino are here for fin titles and raced the foil
# editions too.
DISCIPLINE_LABELS = {"Slalom": "Fin Slalom"}

# Said on the fine print of a post whose discipline has an era the ranking
# leaves out, so the omission is stated rather than left to be noticed.
DISCIPLINE_NOTES = {"Slalom": "Foil slalom, from 2024, is a separate record"}


def _eyebrow(discipline: str) -> str:
    """Venue and discipline. Sylt runs wave and freestyle at the same event,
    so a post that names only the venue does not say which record it ranks."""
    return f"{VENUE} · {_discipline_label(discipline)}"


def _discipline_label(discipline: str) -> str:
    """The discipline as it should read on a slide."""
    return DISCIPLINE_LABELS.get(discipline, discipline)


def build_sylt_kings_slides(rows: list[dict], sex: str, editions: dict = None,
                            discipline: str = "Wave") -> list[dict]:
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
    title_lines = _title_lines(sex)
    eyebrow = _eyebrow(discipline)
    common = {"accent_color": ACCENT_COLOR}
    sample = _sample_line(editions)
    shared = _shared_years(rows)
    criteria = _criteria_note(shared, discipline)

    slides = [{
        "type": "sylt_cover",
        "title_word": title_word,
        "title_lines": title_lines,
        "division_label": sex.upper(),
        "eyebrow": eyebrow,
        # The cover styles the discipline on its own, so it gets the two parts
        # separately as well as the joined line.
        "eyebrow_venue": VENUE,
        "eyebrow_discipline": _discipline_label(discipline),
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
        "slide_title": " ".join(title_lines),
        "division_label": sex.upper(),
        "eyebrow": eyebrow,
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


def _criteria_note(shared: set, discipline: str = "Wave") -> str:
    """The fine print, with the asterisk explained when one is in play."""
    note = CRITERIA_NOTE
    era = DISCIPLINE_NOTES.get(discipline)
    if era:
        note = f"{note} · {era}"
    if not shared:
        return note
    return f"{note} · {_shared_phrase(shared)}"


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
    name = _athlete_name(row)
    first_name, _, last_name = name.partition(" ")

    hero_url, focus, _ = _hero(athlete_id)
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
        "country": nationality_to_iso(_nationality(row)),
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


def _hero(athlete_id) -> tuple[str, str, object]:
    """A rider's action shot, its crop anchor, and the folder both came from.

    Returns ("", "", None) when nothing landscape resolves, which is the signal
    for the portrait layout. The crop anchor comes from the same folder as the
    photo, so a shot picked at Sylt 2022 keeps the anchor it was cropped with.

    The folder is returned because the photographer is recorded beside the
    photo, not beside the rider: ``sylt_photo_credits`` needs to read the same
    ``credits.json`` this shot was chosen from, and searching again from the
    newest folder would credit whoever shot the most recent edition.
    """
    if not athlete_id:
        return "", "", None
    for event_id in SYLT_PHOTO_EVENTS:
        url = resolve_hero_url(athlete_id, event_id)
        # ``resolve_hero_url`` runs its own chain to h2h and the legacy flat
        # photo, so a url that is not inside this event's folder means this
        # event had nothing. Accepting it would end the search at the newest
        # folder for every rider who has any photo at all, and the older Sylt
        # folders would never be read: the Ruano Moreno twins last sailed the
        # venue in 2017 and 2019, and both have a flat photo.
        if url and f"/events/{event_id}/" in url.replace("\\", "/"):
            return url, resolve_hero_focus(athlete_id, event_id, DEFAULT_FOCUS), event_id
    # Nothing at Sylt: a shot cropped for a head-to-head or the legacy flat
    # photo still beats dropping the rider to a headshot.
    # No folder to return: a fallback shot was not taken at Sylt, so this
    # post has no record of who took it and credits nobody for it.
    return resolve_hero_url(athlete_id, None), DEFAULT_FOCUS, None


# Every Sylt folder is filled from the PWA library, so the tour is owed a
# credit on any post built from those photos, including one where no individual
# photographer is tagged.
TOUR_HANDLE = "@pwaworldtour"


def sylt_photo_credits(rows: list[dict]) -> list[str]:
    """Photographer handles for the rider cards, in slide order.

    Every rider on the list gets a card, so slide order is row order and every
    photograph on the post is accounted for.

    The credit is read from the folder each photo actually came from. A venue
    post spans nearly twenty years, so two riders' shots can be nine years and
    two photographers apart, and reading one folder for everyone would put the
    wrong name under half the post.

    An untagged photo contributes nothing: a caption missing a credit is a
    smaller problem than one carrying a guessed attribution. The tour handle
    still closes the line, because the library the shot came from is known even
    when the photographer is not.
    """
    credits = []
    used_sylt_photo = False
    for row in rows:
        athlete_id = row.get("athlete_id")
        _, _, event_id = _hero(athlete_id)
        if not event_id:
            continue
        used_sylt_photo = True
        handle = resolve_photo_credit(athlete_id, event_id)
        if handle and handle not in credits:
            credits.append(handle)

    # The table slide is built from headshots, so those are photographs on the
    # post too. They come second because the cards are what a reader swipes
    # through first, and a photographer who shot both is named once.
    for row in rows:
        handle = resolve_face_credit(row.get("athlete_id"))
        if handle:
            used_sylt_photo = True
            if handle not in credits:
                credits.append(handle)

    if used_sylt_photo and TOUR_HANDLE not in credits:
        credits.append(TOUR_HANDLE)
    return credits


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
            "athlete": _table_name(_athlete_name(row)),
            "country": nationality_to_iso(_nationality(row)),
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
