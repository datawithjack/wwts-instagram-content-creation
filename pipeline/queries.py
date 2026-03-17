"""SQL query builders for templates not covered by the API."""


def build_canary_kings_query(sex: str) -> tuple[str, tuple]:
    """Build query for event winners at Tenerife/Gran Canaria since 2016.

    Returns athlete name, nationality, unified athlete ID, total wins,
    and per-location breakdown (gc_wins, tf_wins). Excludes events with
    joint winners (multiple 1st places in same event+sex).

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
          AND r.sex = %s
          AND r.event_id IN (
              SELECT ev.event_id
              FROM PWA_IWT_EVENTS ev
              WHERE (ev.event_name LIKE '%%Tenerife%%'
                  OR ev.event_name LIKE '%%Gran Canaria%%')
                AND ev.year >= 2016
                AND ev.source = 'PWA'
          )
          AND r.event_id NOT IN (
              SELECT sub.event_id
              FROM PWA_IWT_RESULTS sub
              WHERE sub.place = '1'
                AND sub.source = 'PWA'
                AND sub.sex = %s
              GROUP BY sub.event_id, sub.sex
              HAVING COUNT(*) > 1
          )
        GROUP BY a.id, a.primary_name, a.nationality
        ORDER BY wins DESC, a.primary_name
    """
    return sql, (sex, sex)


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
) -> tuple[str, tuple]:
    """Build a top 10 scores query with optional filters.

    Args:
        score_type: "Wave" or "Jump"
        sex: "Men" or "Women" (optional)
        year: Filter to a specific year (optional)
        event_id: Filter to a specific event (optional)

    Returns:
        (sql, params) tuple ready for db.run_query()
    """
    params = []

    where_clauses = ["s.counting = 1"]

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

    where = " AND ".join(where_clauses)

    # Include trick type in select for jump queries
    type_col = "s.type AS trick_type," if score_type == "Jump" else ""

    sql = f"""
        SELECT
            a.primary_name AS athlete,
            a.nationality AS country,
            s.score,
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
