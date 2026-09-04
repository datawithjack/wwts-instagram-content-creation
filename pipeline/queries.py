"""SQL query builders for templates not covered by the API."""


def build_canary_kings_query(sex: str) -> tuple[str, tuple]:
    """Build query for WAVE event winners at Tenerife/Gran Canaria since 2006.

    Returns athlete name, nationality, unified athlete ID, total wins,
    and per-location breakdown (gc_wins, tf_wins).

    Filters on division_label ('Wave Men' / 'Wave Women') so that
    multi-discipline "Grand Slam" events (which crown separate wave, slalom
    and foil champions) contribute only their wave winner — rather than being
    dropped entirely as apparent joint winners.

    Args:
        sex: "Men" or "Women"

    Returns:
        (sql, params) tuple ready for db.run_query()
    """
    sql = """
        SELECT a.primary_name AS athlete,
               a.nationality,
               a.id AS athlete_id,
               a.liveheats_image_url AS photo_url,
               SUM(CASE WHEN e.event_name LIKE '%%Gran Canaria%%' THEN 1 ELSE 0 END) AS gc_wins,
               SUM(CASE WHEN e.event_name LIKE '%%Tenerife%%' THEN 1 ELSE 0 END) AS tf_wins,
               COUNT(*) AS wins
        FROM PWA_IWT_RESULTS r
        JOIN ATHLETE_SOURCE_IDS asi
            ON asi.source = 'PWA' AND asi.source_id = r.athlete_id
        JOIN ATHLETES a
            ON a.id = asi.athlete_id
        JOIN PWA_IWT_EVENTS e
            ON e.event_id = r.event_id AND e.source = 'PWA'
        WHERE r.place = '1'
          AND r.source = 'PWA'
          AND r.division_label = %s
          AND r.event_id IN (
              SELECT ev.event_id
              FROM PWA_IWT_EVENTS ev
              WHERE (ev.event_name LIKE '%%Tenerife%%'
                  OR ev.event_name LIKE '%%Gran Canaria%%')
                AND ev.year >= 2006
                AND ev.source = 'PWA'
          )
        GROUP BY a.id, a.primary_name, a.nationality
        ORDER BY wins DESC, a.primary_name
    """
    return sql, (f"Wave {sex}",)


def build_athlete_rise_query(
    athlete_id: int, event_pattern: str, sex: str
) -> tuple[str, tuple]:
    """Build query for an athlete's progression at a location over years.

    Returns year, placement, best heat score (sum of counting scores per heat),
    best wave score, and best jump score for each year the athlete competed
    at matching events.

    Args:
        athlete_id: Unified athlete ID from ATHLETES table
        event_pattern: SQL LIKE pattern for event name (e.g. '%%Gran Canaria%%')
        sex: "Men" or "Women"

    Returns:
        (sql, params) tuple ready for db.run_query()
    """
    sql = """
        SELECT sub.year,
               sub.placement,
               sub.best_wave,
               sub.best_jump,
               sub.best_jump_type,
               sub.best_heat
        FROM (
            SELECT r.year,
                   CAST(r.place AS UNSIGNED) AS placement,
                   (
                       SELECT MAX(s.score)
                       FROM PWA_IWT_HEAT_SCORES s
                       JOIN ATHLETE_SOURCE_IDS asi2
                           ON asi2.source = s.source AND asi2.source_id = s.athlete_id
                       WHERE asi2.athlete_id = %s
                         AND s.source = 'PWA'
                         AND s.type = 'Wave'
                         AND s.counting = 1
                         AND s.pwa_event_id = r.event_id
                   ) AS best_wave,
                   (
                       SELECT MAX(s.score)
                       FROM PWA_IWT_HEAT_SCORES s
                       JOIN ATHLETE_SOURCE_IDS asi2
                           ON asi2.source = s.source AND asi2.source_id = s.athlete_id
                       WHERE asi2.athlete_id = %s
                         AND s.source = 'PWA'
                         AND s.type <> 'Wave'
                         AND s.counting = 1
                         AND s.pwa_event_id = r.event_id
                   ) AS best_jump,
                   (
                       SELECT s.type
                       FROM PWA_IWT_HEAT_SCORES s
                       JOIN ATHLETE_SOURCE_IDS asi2
                           ON asi2.source = s.source AND asi2.source_id = s.athlete_id
                       WHERE asi2.athlete_id = %s
                         AND s.source = 'PWA'
                         AND s.type <> 'Wave'
                         AND s.counting = 1
                         AND s.pwa_event_id = r.event_id
                       ORDER BY s.score DESC
                       LIMIT 1
                   ) AS best_jump_type,
                   (
                       SELECT MAX(ht.heat_total)
                       FROM (
                           SELECT s.heat_id,
                                  SUM(s.score) AS heat_total
                           FROM PWA_IWT_HEAT_SCORES s
                           JOIN ATHLETE_SOURCE_IDS asi2
                               ON asi2.source = s.source AND asi2.source_id = s.athlete_id
                           WHERE asi2.athlete_id = %s
                             AND s.source = 'PWA'
                             AND s.counting = 1
                             AND s.pwa_event_id = r.event_id
                           GROUP BY s.heat_id
                       ) ht
                   ) AS best_heat
            FROM PWA_IWT_RESULTS r
            JOIN ATHLETE_SOURCE_IDS asi
                ON r.source = asi.source AND r.athlete_id = asi.source_id
            JOIN PWA_IWT_EVENTS e
                ON e.event_id = r.event_id AND e.source = 'PWA'
            WHERE asi.athlete_id = %s
              AND r.source = 'PWA'
              AND e.event_name LIKE %s
              AND r.sex = %s
              AND r.place REGEXP '^[0-9]+$'
        ) sub
        ORDER BY sub.year ASC
    """
    return sql, (athlete_id, athlete_id, athlete_id, athlete_id, athlete_id, event_pattern, sex)


def build_top10_query(
    score_type: str,
    sex: str = None,
    year: int = None,
    event_id: int = None,
    rounds: list[str] = None,
    include_non_counting: bool = False,
) -> tuple[str, tuple]:
    """Build a top 10 scores query with optional filters.

    Args:
        score_type: "Wave" or "Jump"
        sex: "Men" or "Women" (optional)
        year: Filter to a specific year (optional)
        event_id: Filter to a specific event (optional)
        rounds: Filter to specific round names (optional, e.g. ["Final", "R5 B-Final"])
        include_non_counting: Include scores that didn't count toward the heat
            total (default False — only counting scores). Use to surface a fuller
            top 10 from a small heat/round where few scores counted.

    Returns:
        (sql, params) tuple ready for db.run_query()
    """
    params = []

    where_clauses = [] if include_non_counting else ["s.counting = 1"]

    if score_type == "Jump":
        # "Jump" means everything that isn't a Wave score — includes
        # the generic "Jump" type and individual trick types (F, B, P, etc.)
        where_clauses.append("s.type <> %s")
        params.append("Wave")
    else:
        where_clauses.append("s.type = %s")
        params.append(score_type)

    if sex:
        # Some events store trick scores with empty sex — include those too
        if score_type == "Jump":
            where_clauses.append("(s.sex = %s OR s.sex = '')")
            params.append(sex)
        else:
            where_clauses.append("s.sex = %s")
            params.append(sex)

    if year:
        where_clauses.append("s.pwa_year = %s")
        params.append(year)

    if event_id:
        where_clauses.append("s.pwa_event_id = %s")
        params.append(event_id)

    if rounds:
        placeholders = ", ".join(["%s"] * len(rounds))
        where_clauses.append(f"hp.round_name IN ({placeholders})")
        params.extend(rounds)

    where = " AND ".join(where_clauses)

    # Include trick type + modifier in select for jump queries
    type_col = "s.type AS trick_type, s.modifier AS modifier," if score_type == "Jump" else ""

    sql = f"""
        SELECT
            a.primary_name AS athlete,
            a.id AS athlete_id,
            a.nationality AS country,
            s.score,
            s.counting AS counting,
            {type_col}
            e.event_name AS event,
            hp.round_name AS round,
            hp.heat_id AS heat_id
        FROM PWA_IWT_HEAT_SCORES s
        JOIN ATHLETE_SOURCE_IDS asi
            ON asi.source = s.source AND asi.source_id = s.athlete_id
        JOIN ATHLETES a
            ON a.id = asi.athlete_id
        JOIN PWA_IWT_EVENTS e
            ON e.source = s.source AND e.event_id = s.pwa_event_id
        JOIN PWA_IWT_HEAT_PROGRESSION hp
            ON hp.heat_id = s.heat_id AND hp.source = s.source
        WHERE {where}
        ORDER BY s.score DESC
        LIMIT 10
    """

    return sql, tuple(params)


def build_freestyle_top10_query(
    sex: str = None,
    year: int = None,
    event_id: int = None,
    counting_only: bool = False,
    exclude_placeholders: bool = False,
    limit: int = 10,
) -> tuple[str, tuple]:
    """Build a top N highest-scoring freestyle moves query.

    Freestyle scores live in their own table (``PWA_IWT_FREESTYLE_HEAT_SCORES``),
    one row per move attempted, so this cannot share ``build_top10_query``. Each
    row is joined to ``MOVE_DICTIONARY`` for the move's difficulty rating, which
    the table slide renders as a sub-line beneath the move name.

    Args:
        sex: "Men" or "Women" (optional).
        year: Filter to a specific ``pwa_year`` (optional).
        event_id: Filter to a specific ``pwa_event_id`` (optional). Note this is
            the PWA event id, not the app event id — Fuerteventura 2026 is 389,
            not 123.
        counting_only: Only scores that counted toward the heat total. Defaults
            to False to match the wave/jump top 10.
        exclude_placeholders: Drop unnamed "New Move" slots. They are real
            tricks that were landed but not yet named in the dictionary, so a
            highest-scoring list keeps them by default; a *difficulty* list
            should not, since all the high tier sit at a flat 10.00.
        limit: Number of rows (default 10).

    Returns:
        (sql, params) tuple ready for db.run_query().

    Notes:
        ``score = 0`` means attempted and not landed, so bails are excluded
        here. ``Crash`` (slug ``CRSH``) is a dictionary entry at difficulty
        0.00 and is always excluded.
    """
    params = []

    # A bail is a real row at score 0. Never show one on a top-scores list.
    where_clauses = ["f.score > 0", "f.abbreviation <> %s"]
    params.append("CRSH")

    if counting_only:
        where_clauses.append("f.counting = 1")

    if exclude_placeholders:
        where_clauses.append("COALESCE(m.is_placeholder, 0) = 0")

    if sex:
        where_clauses.append("f.sex = %s")
        params.append(sex)

    if year:
        where_clauses.append("f.pwa_year = %s")
        params.append(year)

    if event_id:
        where_clauses.append("f.pwa_event_id = %s")
        params.append(event_id)

    where = " AND ".join(where_clauses)

    # LEFT JOIN throughout: one Fuerte 2026 row has a null abbreviation, and a
    # missing dictionary entry should cost the difficulty sub-line, not the row.
    sql = f"""
        SELECT
            a.primary_name AS athlete,
            a.nationality AS country,
            a.country_code AS country_code,
            asi.athlete_id AS athlete_id,
            f.score,
            f.counting AS counting,
            COALESCE(m.name, f.move_name) AS move,
            f.abbreviation AS move_slug,
            m.difficulty AS difficulty,
            m.family_name AS move_family,
            COALESCE(m.is_placeholder, 0) AS is_placeholder,
            e.event_name AS event,
            hp.round_name AS round,
            hp.heat_id AS heat_id
        FROM PWA_IWT_FREESTYLE_HEAT_SCORES f
        JOIN ATHLETE_SOURCE_IDS asi
            ON asi.source = f.source AND asi.source_id = f.athlete_id
        JOIN ATHLETES a
            ON a.id = asi.athlete_id
        JOIN PWA_IWT_EVENTS e
            ON e.source = f.source AND e.event_id = f.pwa_event_id
        JOIN PWA_IWT_HEAT_PROGRESSION hp
            ON hp.heat_id = f.heat_id AND hp.source = f.source
        LEFT JOIN MOVE_DICTIONARY m
            ON m.slug = f.abbreviation
        WHERE {where}
        ORDER BY f.score DESC
        LIMIT {int(limit)}
    """

    return sql, tuple(params)


def build_wave_count_query(
    sex: str,
    event_id: int,
    include_non_counting: bool = True,
) -> tuple[str, tuple]:
    """Build a per-athlete wave-count query for a single event.

    Counts how many waves each athlete caught (scored by the judges) at one
    event — a pure volume / work-rate stat, distinct from placement. Also
    returns the number of distinct heats sailed so the caller can derive a
    waves-per-heat figure.

    Args:
        sex: "Men" or "Women"
        event_id: DB pwa_event_id to filter to
        include_non_counting: Count every wave scored, including those that
            didn't count toward the heat total (default True — "most waves
            caught" means total volume). Set False to count only counting waves.

    Returns:
        (sql, params) tuple ready for db.run_query(). Rows carry: athlete,
        nationality, athlete_id, photo_url, wave_count, heats — ordered by
        wave_count DESC.
    """
    counting_clause = "" if include_non_counting else "\n          AND s.counting = 1"

    sql = f"""
        SELECT a.primary_name AS athlete,
               a.nationality,
               a.id AS athlete_id,
               a.liveheats_image_url AS photo_url,
               COUNT(*) AS wave_count,
               COUNT(DISTINCT s.heat_id) AS heats
        FROM PWA_IWT_HEAT_SCORES s
        JOIN ATHLETE_SOURCE_IDS asi
            ON asi.source = s.source AND asi.source_id = s.athlete_id
        JOIN ATHLETES a
            ON a.id = asi.athlete_id
        WHERE s.type = 'Wave'
          AND s.pwa_event_id = %s
          AND s.sex = %s{counting_clause}
        GROUP BY a.id, a.primary_name, a.nationality, a.liveheats_image_url
        ORDER BY wave_count DESC, a.primary_name
    """
    return sql, (event_id, sex)


def build_perfect_10s_wave_query() -> tuple[str, tuple]:
    """Build query for every perfect 10.00 wave score ever scored.

    Returns rows ordered by year DESC (latest first). Includes
    elimination_name so the caller can derive sex (Mens/Womens) for
    historical rows where PWA_IWT_HEAT_SCORES.sex is empty.

    Returns:
        (sql, params) tuple ready for db.run_query()
    """
    sql = """
        SELECT a.primary_name AS athlete,
               a.nationality AS country,
               s.score,
               e.year,
               e.event_name AS event,
               hp.round_name AS round,
               s.heat_id,
               hp.elimination_name
        FROM PWA_IWT_HEAT_SCORES s
        JOIN ATHLETE_SOURCE_IDS asi
            ON asi.source = s.source AND asi.source_id = s.athlete_id
        JOIN ATHLETES a
            ON a.id = asi.athlete_id
        JOIN PWA_IWT_EVENTS e
            ON e.source = s.source AND e.event_id = s.pwa_event_id
        JOIN PWA_IWT_HEAT_PROGRESSION hp
            ON hp.heat_id = s.heat_id AND hp.source = s.source
        WHERE s.counting = 1
          AND s.type = 'Wave'
          AND s.score = 10.00
        ORDER BY e.year DESC, e.event_name, a.primary_name
    """
    return sql, ()


def build_fantasy_mvp_points_query(event_id: int) -> tuple[str, tuple]:
    """Fantasy points per athlete at a freestyle Session event, split by elimination.

    An athlete's fantasy points = the "heat aggregate" the Session scoring engine
    uses: the sum of ``PWA_IWT_HEAT_RESULTS.result_total`` across every freestyle
    heat they competed in at the event (the raw pre-wildcard-multiplier score —
    the ×1.25 wildcard bonus is applied per-picker, not to the athlete). Grouping
    by ``hp.elimination_name`` returns one row per (athlete, elimination): the
    field encodes both the elimination ("Single"/"Double") and the gender
    ("Mens"/"Womens"), which the caller parses in Python.

    The freestyle scoping (``EXISTS ... PWA_IWT_FREESTYLE_HEAT_SCORES``) mirrors
    the backend scoring engine so a dual-discipline rider's slalom heats at the
    same multi-discipline event (e.g. Fuerteventura hosts freestyle + slalom)
    never leak in.

    Args:
        event_id: App/DB event id (``PWA_IWT_EVENTS.id``).

    Returns:
        (sql, params) tuple ready for db.run_query().
    """
    sql = """
        SELECT a.primary_name AS athlete,
               a.nationality AS country,
               a.country_code AS country_code,
               asi.athlete_id AS athlete_id,
               hp.elimination_name,
               SUM(hr.result_total) AS points
        FROM PWA_IWT_HEAT_RESULTS hr
        JOIN PWA_IWT_EVENTS e
            ON e.event_id = hr.pwa_event_id
           AND e.year = hr.pwa_year
           AND e.source = hr.source
        JOIN ATHLETE_SOURCE_IDS asi
            ON asi.source = hr.source AND asi.source_id = hr.athlete_id
        JOIN ATHLETES a
            ON a.id = asi.athlete_id
        JOIN PWA_IWT_HEAT_PROGRESSION hp
            ON hp.heat_id = hr.heat_id AND hp.source = hr.source
        WHERE e.id = %s
          AND hr.result_total IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM PWA_IWT_FREESTYLE_HEAT_SCORES f
              WHERE f.pwa_event_id = hr.pwa_event_id
                AND f.heat_id = hr.heat_id
          )
        GROUP BY asi.athlete_id, a.primary_name, a.nationality, a.country_code, hp.elimination_name
        ORDER BY points DESC
    """
    return sql, (event_id,)


def build_fantasy_session_pick_pct_query(
    event_id: int, discipline: str = "freestyle"
) -> tuple[str, tuple]:
    """Per-athlete % picked (ownership) for a Session event + discipline.

    Mirrors the fantasy backend's ``compute_session_pick_stats``: confirmed picks
    only, keyed on the same ``event_id`` (``PWA_IWT_EVENTS.id``). Each row carries
    the event-wide ``total_entries`` (distinct confirmed entrants) so the caller
    can compute the percentage without a second round-trip. ``athlete_id`` is a
    VARCHAR in ``FANTASY_SESSION_PICKS`` — coerce to int on the Python side to
    match the numeric ids the points query returns.

    Returns:
        (sql, params) tuple ready for db.run_query().
    """
    sql = """
        SELECT athlete_id,
               COUNT(DISTINCT user_id) AS pick_count,
               (SELECT COUNT(DISTINCT user_id)
                  FROM FANTASY_SESSION_PICKS
                 WHERE event_id = %s AND discipline = %s AND confirmed = TRUE
               ) AS total_entries
        FROM FANTASY_SESSION_PICKS
        WHERE event_id = %s AND discipline = %s AND confirmed = TRUE
        GROUP BY athlete_id
    """
    return sql, (event_id, discipline, event_id, discipline)


# A slalom heat_id is ``{ladder}_r{round}_h{name}``. This MySQL REGEXP isolates
# slalom heats and excludes wave/freestyle heats (which use a ``{n}_{round}{a/b}``
# format with no ``_r..._h``). Mirrors SLALOM_HEAT_REGEX in the app's
# slalom_session_db_scoring engine, verified 100% on prod.
SLALOM_HEAT_REGEX = r"_r[0-9]+_h"


def build_slalom_mvp_heats_query(event_id: int) -> tuple[str, tuple]:
    """Per-heat finish places for EVERY slalom competitor at an event.

    Slalom has no judged scores — the finish place is the result — so the MVP
    board is built from places (see pipeline/slalom_mvps.py for the curve). One
    row per (athlete, heat) carrying the place and the PWA result code
    (PMS/DNF/RAF/DNS), which maps to a flat penalty.

    Deliberately NOT restricted to picked athletes: the app's own engine only
    scores picks, but an MVP board that omitted an unpicked rider who outscored
    the field would be wrong.

    Args:
        event_id: App/DB event id (``PWA_IWT_EVENTS.id``).

    Returns:
        (sql, params) tuple ready for db.run_query().
    """
    sql = """
        SELECT asi.athlete_id AS athlete_id,
               a.primary_name AS athlete,
               a.nationality  AS country,
               a.country_code AS country_code,
               a.pwa_sail_number AS sail_number,
               hr.heat_id,
               hr.place,
               hr.result_code
        FROM PWA_IWT_HEAT_RESULTS hr
        JOIN PWA_IWT_EVENTS e
            ON hr.pwa_event_id = e.event_id
           AND hr.pwa_year     = e.year
           AND hr.source       = e.source
        JOIN ATHLETE_SOURCE_IDS asi
            ON hr.athlete_id = asi.source_id
           AND hr.source     = asi.source
        JOIN ATHLETES a
            ON a.id = asi.athlete_id
        WHERE e.id = %s AND hr.heat_id REGEXP %s
    """
    return sql, (event_id, SLALOM_HEAT_REGEX)


def build_slalom_mvp_classify_query(event_id: int) -> tuple[str, tuple]:
    """Every slalom heat at an event with each member's OVERALL elimination place.

    Feeds ``final_multipliers_for_event``, which uses it to tell a ladder's
    championship final (scores x2) from its consolation final (x1). Covers ALL
    heats, not just picked athletes', so a ladder's finals are still identified
    when a pick was knocked out early.

    Returns:
        (sql, params) tuple ready for db.run_query().
    """
    sql = """
        SELECT hr.heat_id, ser.place AS overall_place
        FROM PWA_IWT_HEAT_RESULTS hr
        JOIN PWA_IWT_EVENTS e
            ON hr.pwa_event_id = e.event_id
           AND hr.pwa_year     = e.year
           AND hr.source       = e.source
        LEFT JOIN PWA_IWT_SLALOM_ELIMINATION_RESULTS ser
            ON ser.ladder_id  = SUBSTRING_INDEX(hr.heat_id, '_r', 1)
           AND ser.athlete_id = hr.athlete_id
           AND ser.source     = hr.source
        WHERE e.id = %s AND hr.heat_id REGEXP %s
    """
    return sql, (event_id, SLALOM_HEAT_REGEX)


def build_slalom_elimination_view_query(event_id: int) -> tuple[str, tuple]:
    """Per-(athlete, elimination) overall placings for an event.

    Supplies two things the heat rows can't: the fleet (parsed from
    ``elimination_name``, e.g. "Men's Slalom X - Elimination 1") and the win
    count — ``place = 1`` is a TRUE elimination win, distinct from winning the
    consolation final.

    Returns:
        (sql, params) tuple ready for db.run_query().
    """
    sql = """
        SELECT athlete_id, ladder_id, elimination_no, elimination_name, place
        FROM SLALOM_ELIMINATION_VIEW
        WHERE event_id = %s
    """
    return sql, (event_id,)


def build_sylt_kings_query(sex: str, discipline: str = "Wave") -> tuple[str, tuple]:
    """Build the venue-record query behind the Kings/Queens of Sylt carousels.

    One row per rider who has either won Sylt or stood on the podium twice,
    ordered by titles descending, then podiums. Carries the year lists so a
    slide can name the editions rather than only counting them.

    ``wins`` and ``podiums`` do not overlap: a podium here is a 2nd or a 3rd.
    Counting firsts in both made the pair unreadable side by side, because
    "2 titles, 5 podiums" gives no way to tell whether the rider won twice and
    placed five more times or won twice and placed three more. It does not
    move anyone on the list: every rider with a win is on it for the win, and
    a rider with none has no first place to subtract.

    An edition counts if it has one or two recorded winners. Six Sylt editions
    have no results in the DB at all (2006, 2010, 2011, 2015, 2020, 2021), and
    two more are recorded with the whole fleet tied at the top because the
    contest never produced a result: 2005 lists 8 men and all 12 women first,
    and 2023 Wave Men lists 16 riders first and 16 seventeenth, one round
    having been sailed. Counting those would hand Victor Fernandez, Marc Pare
    and Thomas Traversa a phantom title each.

    Two riders tied at the top is a different thing and must be counted. Sylt
    2008 Wave Women ended with Daida and Iballa Ruano Moreno joint first, no
    second, and Junko Nagoshi and Nayra Alonso joint third. That is an
    official shared title, not a broken scrape: the PWA awarded both women
    2084 ranking points for it, and Sylt was one of only two events in that
    season's world ranking. Demanding a single winner dropped the edition and
    cost Iballa the fifth title that makes her the most decorated rider at the
    venue. No men's edition is shared, so the wider test changes nothing there.

    Testing the winner count rather than listing the good years keeps the
    filter honest as the scrape is fixed or extended.

    Args:
        sex: "Men" or "Women"
        discipline: "Wave" or "Freestyle". Sylt has run both for most of its
            history and the two records are different lengths and different
            stories, so a post takes one at a time.

    Returns:
        (sql, params) tuple ready for db.run_query(). Rows carry: athlete,
        nationality, athlete_id, photo_url, wins, podiums, starts, best_finish,
        avg_finish and placings — ordered by wins DESC, then podiums DESC.

        ``placings`` is every year the rider finished, as "2008:1,2012:3".
        One column rather than a win-years and a best-years column: the years
        behind any placing are a slice of the same list, and deriving them in
        the builder keeps the query from growing a column per slide element.
    """
    sql = """
        SELECT a.primary_name AS athlete,
               a.nationality,
               a.id AS athlete_id,
               a.liveheats_image_url AS photo_url,
               SUM(r.place = '1') AS wins,
               SUM(CAST(r.place AS UNSIGNED) BETWEEN 2 AND 3) AS podiums,
               COUNT(*) AS starts,
               MIN(CAST(r.place AS UNSIGNED)) AS best_finish,
               ROUND(AVG(CAST(r.place AS UNSIGNED)), 1) AS avg_finish,
               GROUP_CONCAT(DISTINCT CONCAT(e.year, ':', CAST(r.place AS UNSIGNED))
                            ORDER BY e.year) AS placings
        FROM PWA_IWT_RESULTS r
        JOIN PWA_IWT_EVENTS e
            ON e.event_id = r.event_id AND e.source = r.source
        JOIN ATHLETE_SOURCE_IDS asi
            ON asi.source = 'PWA' AND asi.source_id = r.athlete_id
        JOIN ATHLETES a
            ON a.id = asi.athlete_id
        WHERE r.source = 'PWA'
          AND r.division_label = %s
          AND e.event_name LIKE '%%Sylt%%'
          AND r.event_id IN (
              SELECT r2.event_id
              FROM PWA_IWT_RESULTS r2
              JOIN PWA_IWT_EVENTS e2
                  ON e2.event_id = r2.event_id AND e2.source = r2.source
              WHERE r2.source = 'PWA'
                AND r2.division_label = %s
                AND e2.event_name LIKE '%%Sylt%%'
              GROUP BY r2.event_id
              HAVING SUM(r2.place = '1') BETWEEN 1 AND 2
          )
        GROUP BY a.id, a.primary_name, a.nationality, a.liveheats_image_url
        HAVING wins >= 1 OR podiums >= 2
        ORDER BY wins DESC, podiums DESC, avg_finish ASC, a.primary_name
    """
    division = f"{discipline} {sex}"
    return sql, (division, division)


def build_sylt_editions_query(sex: str, discipline: str = "Wave") -> tuple[str, tuple]:
    """Count the Sylt editions that feed ``build_sylt_kings_query``.

    The slides state the sample ("10 editions, 2008-2025"), and stating it
    wrong is worse than not stating it, so the count comes from the same
    winner-count test as the rows rather than being written down beside it.

    Returns:
        (sql, params) tuple. One row: editions, first_year, last_year.
    """
    sql = """
        SELECT COUNT(*) AS editions,
               MIN(t.year) AS first_year,
               MAX(t.year) AS last_year
        FROM (
            SELECT e.year
            FROM PWA_IWT_RESULTS r
            JOIN PWA_IWT_EVENTS e
                ON e.event_id = r.event_id AND e.source = r.source
            WHERE r.source = 'PWA'
              AND r.division_label = %s
              AND e.event_name LIKE '%%Sylt%%'
            GROUP BY r.event_id, e.year
            HAVING SUM(r.place = '1') BETWEEN 1 AND 2
        ) t
    """
    return sql, (f"{discipline} {sex}",)


# Riders on the Sylt slalom list who are in ATHLETES but have no PWA row in
# ATHLETE_SOURCE_IDS, so the join finds nothing. Both won the event, and an
# unjoined rider loses their nationality and their photo as well as their name.
# Mapped here rather than by inserting the missing source ids, which would be a
# content change reaching into the app's own data; the insert is the better fix
# if this list grows past a handful.
SLALOM_ATHLETE_ID_FALLBACK = {
    642: 1085,   # Pierre Mortefon, won 2018
    1108: 1120,  # Marco Lang, won 2017
}


def build_sylt_slalom_query(sex: str = "Men") -> tuple[str, tuple]:
    """Build the Sylt slalom venue record, from ``PWA_RANKINGS``.

    A separate builder from ``build_sylt_kings_query`` because it reads a
    different table. That one reads ``PWA_IWT_RESULTS``, whose slalom rows
    start at 2016: Sylt gets three editions, three different winners and
    nobody with a second title, which is not a ranking. ``PWA_RANKINGS``
    carries the venue every year from 2006 and turns the same post into a
    fourteen-edition record with Antoine Albeau four times a champion.

    **Fin era only.** Sylt ran ``Slalom Men`` from 2006 to 2023 and
    ``Foil Slalom Men`` in 2024-25; no year ran both, so the discipline string
    is the whole test. The two are left apart because merging them distorts
    exactly the part of the list the post is about: Johan Soe won both foil
    editions from two starts, which on a combined count ranks him level with
    Bjorn Dunkerbeck, who won two from eight against fleets of 120-132 with
    Albeau in them. The foil fields were also the smallest in the run, 72 and
    73 against 87-152. Same column, nothing like the same achievement.

    A zero-point row is not a start. The rankings list the whole season
    fleet against every event, so a rider who skipped Sylt still gets a row
    there scoring nothing: 54 to 94 of each edition's 87-152 "riders" never
    sailed it. Counting them inflated the appearances column and put phantom
    placings on the cards, all of them tied at the bottom of the fleet. Micah
    Buzianis was shown as 54th in 2008, an edition he did not enter.

    Places are ranked from ``event_points`` rather than read from
    ``event_position``, which is NULL for every 2006-2009 row. The points are
    an exact ladder (2100, 2067, 2034, step 33), so the finishing order is
    fully recoverable, and deriving it for all years keeps one code path
    instead of two. ``DENSE_RANK`` so a genuine tie on points shares a place.

    The name falls back to ``PWA_RANKINGS.athlete_name`` because 548 of the 615
    riders in this data have no ``ATHLETE_SOURCE_IDS`` row, and two of them,
    Pierre Mortefon and Marco Lang, won the event. Grouping is on
    ``pwa_athlete_id`` rather than the athlete id for the same reason: every
    unmapped rider has a NULL athlete id, and grouping on that would collapse
    them into a single row.

    Two riders are joined through ``SLALOM_ATHLETE_ID_FALLBACK`` because the
    source-id table has no PWA row for them. The name fallback below still
    matters: it covers everyone else the table misses.

    The fallback name is aggregated, not grouped on. ``athlete_name`` is not
    stable across years for one rider: the scrape marks a youth entry with a
    "(Y)" suffix, so Amado Vrieswijk is stored under two spellings and grouping
    on the column split him into a 3-start row and a 4-start row that each
    counted a title. ``MIN`` also picks the unsuffixed spelling, the suffix
    sorting after the bare name.

    Args:
        sex: "Men". Sylt has never run a women's slalom event, only one Foil
            Slalom Women edition in 2024, so there is no women's record to
            rank. The argument exists to match the wave and freestyle
            builders' signature.

    Returns:
        (sql, params) for db.run_query(), in the same column shape as
        ``build_sylt_kings_query`` so ``build_sylt_kings_slides`` needs no
        change: athlete, nationality, athlete_id, photo_url, wins, podiums,
        starts, best_finish, avg_finish, placings.
    """
    sql = """
        WITH placed AS (
            SELECT r.year,
                   r.pwa_athlete_id,
                   r.athlete_name,
                   DENSE_RANK() OVER (PARTITION BY r.year
                                      ORDER BY r.event_points DESC) AS place
            FROM PWA_RANKINGS r
            WHERE r.discipline = %s
              AND r.event_name LIKE '%%Sylt%%'
              AND r.event_points > 0
        )
        SELECT COALESCE(a.primary_name, MIN(p.athlete_name)) AS athlete,
               a.nationality,
               a.id AS athlete_id,
               a.liveheats_image_url AS photo_url,
               SUM(p.place = 1) AS wins,
               SUM(p.place BETWEEN 2 AND 3) AS podiums,
               COUNT(*) AS starts,
               MIN(p.place) AS best_finish,
               ROUND(AVG(p.place), 1) AS avg_finish,
               GROUP_CONCAT(DISTINCT CONCAT(p.year, ':', p.place)
                            ORDER BY p.year) AS placings
        FROM placed p
        LEFT JOIN ATHLETE_SOURCE_IDS asi
            ON asi.source = 'PWA' AND asi.source_id = p.pwa_athlete_id
        LEFT JOIN ATHLETES a
            ON a.id = COALESCE(asi.athlete_id, %s)
        GROUP BY p.pwa_athlete_id, a.id, a.primary_name,
                 a.nationality, a.liveheats_image_url
        HAVING wins >= 1 OR podiums >= 2
        ORDER BY wins DESC, podiums DESC, avg_finish ASC, athlete
    """
    # One CASE rather than a placeholder per rider, so the params stay two.
    cases = " ".join(f"WHEN {pwa} THEN {aid}"
                     for pwa, aid in SLALOM_ATHLETE_ID_FALLBACK.items())
    fallback = f"CASE p.pwa_athlete_id {cases} END"
    return sql.replace("COALESCE(asi.athlete_id, %s)",
                       f"COALESCE(asi.athlete_id, {fallback})"), (f"Slalom {sex}",)


def build_sylt_slalom_editions_query(sex: str = "Men") -> tuple[str, tuple]:
    """Count the Sylt slalom editions behind ``build_sylt_slalom_query``.

    Same filter as the rows, so the sample line on the slides cannot drift
    from the record it describes. Sylt ran no slalom in 2011 or 2019 and the
    2020 and 2021 events were cancelled, so the span is not the count.

    Returns:
        (sql, params) tuple. One row: editions, first_year, last_year.
    """
    sql = """
        SELECT COUNT(DISTINCT year) AS editions,
               MIN(year) AS first_year,
               MAX(year) AS last_year
        FROM PWA_RANKINGS
        WHERE discipline = %s
          AND event_name LIKE '%%Sylt%%'
          AND event_points > 0
    """
    return sql, (f"Slalom {sex}",)
