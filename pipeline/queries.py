"""SQL query builders for templates not covered by the API."""


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
    params = [score_type]

    where_clauses = ["s.type = %s", "s.counting = 1"]

    if sex:
        where_clauses.append("s.sex = %s")
        params.append(sex)

    if year:
        where_clauses.append("s.pwa_year = %s")
        params.append(year)

    if event_id:
        where_clauses.append("s.pwa_event_id = %s")
        params.append(event_id)

    where = " AND ".join(where_clauses)

    sql = f"""
        SELECT
            a.primary_name AS athlete,
            a.nationality AS country,
            s.score,
            e.event_name AS event,
            hp.round_name AS round
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
