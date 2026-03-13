"""H2H carousel slide builder — splits head-to-head data into 5 or 6 slide dicts.

Wave-only: cover → overview → heats → waves → cta (5 slides)
Wave+jump: cover → overview → heats → waves → jumps → cta (6 slides)
"""

from pipeline.helpers import ordinal

ACCENT_WAVES = "#38bdf8"
ACCENT_JUMPS = "#2dd4bf"


def _is_wave_jump(data: dict) -> bool:
    """Detect wave+jump event by presence of jump keys."""
    return "athlete_1_best_jump" in data


def _fmt_score(val: float) -> str:
    return f"{val:.2f}"


def _build_metric(
    label: str,
    raw1,
    raw2,
    fmt: str = "score",
    lower_is_better: bool = False,
) -> dict:
    """Build a single metric dict with formatted values, winner, and delta."""
    if fmt == "ordinal":
        val1 = ordinal(int(raw1))
        val2 = ordinal(int(raw2))
    elif fmt == "integer":
        val1 = str(int(raw1))
        val2 = str(int(raw2))
    else:
        val1 = _fmt_score(raw1)
        val2 = _fmt_score(raw2)

    # Determine winner
    if raw1 == raw2:
        winner = 0
    elif lower_is_better:
        winner = 1 if raw1 < raw2 else 2
    else:
        winner = 1 if raw1 > raw2 else 2

    # Compute delta string
    if winner == 0:
        delta = ""
    elif fmt in ("ordinal", "integer"):
        diff = abs(int(raw1) - int(raw2))
        delta = f"+{diff}"
    else:
        diff = abs(raw1 - raw2)
        delta = f"+{diff:.2f}"

    return {
        "label": label,
        "val1": val1,
        "val2": val2,
        "winner": winner,
        "delta": delta,
        "format": fmt,
    }


def _build_common(data: dict) -> dict:
    """Extract shared context fields passed to every slide."""
    is_jump = _is_wave_jump(data)
    return {
        "accent_color": ACCENT_JUMPS if is_jump else ACCENT_WAVES,
        "event_name": data.get("event_name", ""),
        "event_country": data.get("event_country", ""),
        "event_date_start": data.get("event_date_start", ""),
        "event_date_end": data.get("event_date_end", ""),
        "event_tier": data.get("event_tier", 0),
        "athlete_1_name": data.get("athlete_1_name", ""),
        "athlete_2_name": data.get("athlete_2_name", ""),
        "athlete_1_photo_url": data.get("athlete_1_photo_url", ""),
        "athlete_2_photo_url": data.get("athlete_2_photo_url", ""),
        "athlete_1_country": data.get("athlete_1_country", ""),
        "athlete_2_country": data.get("athlete_2_country", ""),
    }


def build_slides(data: dict) -> list[dict]:
    """Split H2H data into carousel slide dicts.

    Returns 5 slides for wave-only, 6 for wave+jump events.
    """
    common = _build_common(data)
    is_jump = _is_wave_jump(data)

    # Cover slide
    slides = [{"type": "h2h_cover", **common}]

    # Overview: placement + heat wins
    overview_metrics = [
        _build_metric(
            "FINAL PLACEMENT",
            data["athlete_1_placement"],
            data["athlete_2_placement"],
            fmt="ordinal",
            lower_is_better=True,
        ),
        _build_metric(
            "HEAT WINS",
            data["athlete_1_heat_wins"],
            data["athlete_2_heat_wins"],
            fmt="integer",
        ),
    ]
    slides.append({
        "type": "h2h_stat",
        "section": "OVERVIEW",
        "metrics": overview_metrics,
        **common,
    })

    # Heat scores: best + average
    heat_metrics = [
        _build_metric(
            "BEST HEAT SCORE",
            data["athlete_1_best_heat"],
            data["athlete_2_best_heat"],
        ),
        _build_metric(
            "AVERAGE HEAT SCORE",
            data["athlete_1_avg_heat"],
            data["athlete_2_avg_heat"],
        ),
    ]
    slides.append({
        "type": "h2h_stat",
        "section": "HEAT SCORES",
        "metrics": heat_metrics,
        **common,
    })

    # Wave scores: best + avg counting
    wave_metrics = [
        _build_metric(
            "BEST WAVE",
            data["athlete_1_best_wave"],
            data["athlete_2_best_wave"],
        ),
        _build_metric(
            "AVG. COUNTING WAVE",
            data["athlete_1_avg_wave"],
            data["athlete_2_avg_wave"],
        ),
    ]
    slides.append({
        "type": "h2h_stat",
        "section": "WAVE SCORES",
        "metrics": wave_metrics,
        **common,
    })

    # Jump scores (only for wave+jump events)
    if is_jump:
        jump_metrics = [
            _build_metric(
                "BEST JUMP",
                data["athlete_1_best_jump"],
                data["athlete_2_best_jump"],
            ),
            _build_metric(
                "AVG. COUNTING JUMP",
                data["athlete_1_avg_jump"],
                data["athlete_2_avg_jump"],
            ),
        ]
        slides.append({
            "type": "h2h_stat",
            "section": "JUMP SCORES",
            "metrics": jump_metrics,
            **common,
        })

    # CTA slide
    slides.append({"type": "cta", **common})

    # Add numbering
    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
