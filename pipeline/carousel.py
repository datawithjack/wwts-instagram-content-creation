"""Top 10 carousel slide builder — splits 10 rows into 5 slide dicts."""

PODIUM_COLOURS = {
    1: {"bg": "rgba(240,192,64,0.08)", "accent": "#F0C040"},   # gold
    2: {"bg": "rgba(192,200,212,0.08)", "accent": "#C0C8D4"},  # silver
    3: {"bg": "rgba(205,127,50,0.08)", "accent": "#CD7F32"},   # bronze
}


def build_slides(data: dict) -> list[dict]:
    """Split top-10 data into 5 carousel slide dicts.

    Expects data with keys: title_gender, title_metric, title_year, entries (list of 10).
    Returns list of 5 slide dicts, each with 'type' and shared context fields.
    """
    rows = data["entries"]
    discipline = data["title_metric"].lower().rstrip("s")  # "Waves" -> "wave"
    # Normalise: "wave" -> "waves", "jump" -> "jumps" for consistency
    discipline = discipline + "s"  # "waves" or "jumps"
    title = f"{data['title_gender'].upper()} TOP 10 {data['title_metric'].upper()}"

    common = {
        "title": title,
        "discipline": discipline,
        "title_gender": data["title_gender"],
        "title_metric": data["title_metric"],
        "year": data.get("title_year"),
    }

    return [
        {
            "type": "cover",
            **common,
        },
        {
            "type": "hero",
            "row": rows[0],
            "podium_colour": PODIUM_COLOURS[1],
            **common,
        },
        {
            "type": "podium",
            "rows": rows[1:3],
            "podium_colours": [PODIUM_COLOURS[2], PODIUM_COLOURS[3]],
            **common,
        },
        {
            "type": "table",
            "rows": rows[3:7],
            "label": "Positions 4\u20137",
            **common,
        },
        {
            "type": "table_cta",
            "rows": rows[7:10],
            "label": "Positions 8\u201310",
            **common,
        },
    ]
