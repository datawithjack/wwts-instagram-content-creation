"""H2H carousel slide builder — splits head-to-head data into 5 or 6 slide dicts.

Wave-only: cover → overview → heats → waves → cta (5 slides)
Wave+jump: cover → overview → heats → waves → jumps → cta (6 slides)
"""

from pipeline.helpers import ordinal, clean_event_name

ACCENT_WAVES = "#5AB4CC"
ACCENT_JUMPS = "#4DA89E"

MIN_BAR_WIDTH = 40


def _is_wave_jump(data: dict) -> bool:
    """Detect wave+jump event by presence of non-zero jump scores.

    Some events return jump keys with 0.00 values when no jumps were scored —
    treat those as wave-only and drop the jumps slide.
    """
    if "athlete_1_best_jump" not in data:
        return False
    return (data.get("athlete_1_best_jump") or 0) > 0 or (data.get("athlete_2_best_jump") or 0) > 0


def _fmt_score(val: float) -> str:
    return f"{val:.2f}"


def _add_global_bar_widths(metrics: list[dict]) -> list[dict]:
    """Add bar_width_1/bar_width_2 scaled to the global max across all metrics.

    All four values (2 metrics × 2 athletes) scale to one maximum so the
    "best" metric's winner = 100% and the "average" metric's bars are
    proportionally shorter.
    """
    all_raw = []
    for m in metrics:
        all_raw.extend([m["raw1"], m["raw2"]])

    global_max = max(all_raw) if all_raw else 0

    for m in metrics:
        if global_max == 0:
            m["bar_width_1"] = 100
            m["bar_width_2"] = 100
        else:
            m["bar_width_1"] = max(MIN_BAR_WIDTH, round(m["raw1"] / global_max * 100))
            m["bar_width_2"] = max(MIN_BAR_WIDTH, round(m["raw2"] / global_max * 100))

    return metrics


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
        "raw1": raw1,
        "raw2": raw2,
        "winner": winner,
        "delta": delta,
        "show_delta": True,
        "format": fmt,
        "lower_is_better": lower_is_better,
    }


def _build_common(data: dict) -> dict:
    """Extract shared context fields passed to every slide."""
    is_jump = _is_wave_jump(data)
    a1_name = data.get("athlete_1_name", "")
    a2_name = data.get("athlete_2_name", "")
    # Split on first space: first word = first name, rest = surname
    a1_parts = a1_name.split(None, 1) if a1_name else ["", ""]
    a2_parts = a2_name.split(None, 1) if a2_name else ["", ""]
    # Strip year prefix and star ratings from event name (shown separately)
    event_name = clean_event_name(data.get("event_name", ""))
    return {
        "accent_color": ACCENT_JUMPS if is_jump else ACCENT_WAVES,
        "event_name": event_name,
        "event_country": data.get("event_country", ""),
        "event_date_start": data.get("event_date_start", ""),
        "event_date_end": data.get("event_date_end", ""),
        "event_tier": data.get("event_tier", 0),
        "athlete_1_name": a1_name,
        "athlete_2_name": a2_name,
        "athlete_1_firstname": a1_parts[0].upper(),
        "athlete_2_firstname": a2_parts[0].upper(),
        "athlete_1_surname": a1_parts[1].upper() if len(a1_parts) > 1 else "",
        "athlete_2_surname": a2_parts[1].upper() if len(a2_parts) > 1 else "",
        "athlete_1_id": data.get("athlete_1_id"),
        "athlete_2_id": data.get("athlete_2_id"),
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

    # Overview: placement + heat wins — table layout (no bars)
    overview_metrics = [
        {**_build_metric(
            "FINAL PLACEMENT",
            data["athlete_1_placement"],
            data["athlete_2_placement"],
            fmt="ordinal",
            lower_is_better=True,
        ), "show_delta": False},
        {**_build_metric(
            "HEAT WINS",
            data["athlete_1_heat_wins"],
            data["athlete_2_heat_wins"],
            fmt="integer",
        ), "show_delta": False},
    ]
    slides.append({
        "type": "h2h_stat",
        "section_title": "OVERVIEW",
        "layout": "table",
        "metrics": overview_metrics,
        **common,
    })

    # Heat scores: best + average — bar layout
    heat_metrics = _add_global_bar_widths([
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
    ])
    slides.append({
        "type": "h2h_stat",
        "section_title": "HEAT SCORES",
        "layout": "bars",
        "metrics": heat_metrics,
        **common,
    })

    # Wave scores: best + avg counting — bar layout
    wave_metrics = _add_global_bar_widths([
        _build_metric(
            "BEST WAVE",
            data["athlete_1_best_wave"],
            data["athlete_2_best_wave"],
        ),
        _build_metric(
            "AVERAGE COUNTING WAVE",
            data["athlete_1_avg_wave"],
            data["athlete_2_avg_wave"],
        ),
    ])
    slides.append({
        "type": "h2h_stat",
        "section_title": "WAVE SCORES",
        "layout": "bars",
        "metrics": wave_metrics,
        **common,
    })

    # Jump scores (only for wave+jump events) — bar layout
    if is_jump:
        jump_metrics = _add_global_bar_widths([
            _build_metric(
                "BEST JUMP",
                data["athlete_1_best_jump"],
                data["athlete_2_best_jump"],
            ),
            _build_metric(
                "AVERAGE COUNTING JUMP",
                data["athlete_1_avg_jump"],
                data["athlete_2_avg_jump"],
            ),
        ])
        slides.append({
            "type": "h2h_stat",
            "section_title": "JUMP SCORES",
            "layout": "bars",
            "metrics": jump_metrics,
            **common,
        })

    # CTA slide (hide footer — CTA has its own branding)
    slides.append({"type": "cta", "hide_footer": True, **common})

    return slides
