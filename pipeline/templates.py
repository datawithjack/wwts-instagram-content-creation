"""Jinja2 template population and rendering."""
import os
from datetime import date

from jinja2 import Environment, FileSystemLoader

from pipeline.helpers import (
    ordinal,
    format_date_range,
    star_rating,
    format_delta,
    compute_deltas,
    format_number,
    country_flag,
    trick_type_label,
)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "photos")


def get_jinja_env() -> Environment:
    """Create Jinja2 environment with custom filters."""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    env.filters["ordinal"] = ordinal
    env.filters["format_delta"] = format_delta
    env.filters["star_rating"] = star_rating
    env.filters["format_number"] = format_number
    env.globals["format_date_range"] = format_date_range
    env.filters["country_flag"] = country_flag
    env.filters["trick_type_label"] = trick_type_label
    return env


def resolve_photo_override(athlete_id, current_url: str) -> str:
    """Check for a local photo override in assets/photos/ by athlete ID.

    Returns the file:// URL if a local file exists, otherwise returns current_url unchanged.
    Checks extensions in order: webp, jpg, png.
    """
    if not athlete_id:
        return current_url
    for ext in ("webp", "jpg", "png"):
        local = os.path.join(PHOTOS_DIR, f"{athlete_id}.{ext}")
        if os.path.exists(local):
            return "file:///" + os.path.abspath(local).replace(os.sep, "/")
    return current_url


def _apply_photo_overrides(data: dict) -> None:
    """Apply local photo overrides to template data dict (mutates in place).

    Checks these athlete ID → photo URL mappings:
    - athlete_1_id → athlete_1_photo_url (H2H)
    - athlete_2_id → athlete_2_photo_url (H2H)
    - athlete_id → athlete_photo_url (rider profile, athlete rise)
    """
    mappings = [
        ("athlete_1_id", "athlete_1_photo_url"),
        ("athlete_2_id", "athlete_2_photo_url"),
        ("athlete_id", "athlete_photo_url"),
    ]
    for id_key, photo_key in mappings:
        aid = data.get(id_key)
        if aid:
            data[photo_key] = resolve_photo_override(aid, data.get(photo_key, ""))


def render_template(template_name: str, data: dict) -> str:
    """Render a named template with data, returning HTML string."""
    env = get_jinja_env()

    # Compute deltas for head_to_head variants
    if template_name in ("head_to_head", "head_to_head_jump"):
        delta_fields = ["best_heat", "avg_heat", "best_wave", "avg_wave"]
        if template_name == "head_to_head_jump":
            delta_fields.extend(["best_jump", "avg_jump"])
        deltas = compute_deltas(data, delta_fields)
        data = {**data, **deltas}

    # Resolve background image path
    assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
    bg_path = os.path.join(assets_dir, "backgrounds", "background-1.jpg")
    if os.path.exists(bg_path):
        bg_url = "file:///" + os.path.abspath(bg_path).replace(os.sep, "/")
        data = {**data, "bg_image_path": bg_url}

    # Apply local photo overrides (by athlete ID)
    _apply_photo_overrides(data)

    # Resolve athlete photo paths to file:// URLs
    for key in ("athlete_1_photo_url", "athlete_2_photo_url", "athlete_photo_url"):
        path = data.get(key, "")
        if path and os.path.exists(path):
            data[key] = "file:///" + os.path.abspath(path).replace(os.sep, "/")

    # Map variant names to their base template file
    template_file_map = {
        "site_stats_reel": "site_stats.html",
    }
    # Carousel slide templates live under carousel/ subdirectory
    if template_name.startswith("carousel/"):
        template_file = f"{template_name}.html"
    else:
        template_file = template_file_map.get(template_name, f"{template_name}.html")

    template = env.get_template(template_file)
    return template.render(**data)


def _resolve_photo(filename: str) -> str:
    """Check if a photo exists in assets/photos/ and return path or empty."""
    assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "photos")
    path = os.path.join(assets_dir, filename)
    if os.path.exists(path):
        return os.path.abspath(path)
    return ""


def get_dummy_data(template_name: str) -> dict:
    """Return dummy data for testing templates without a DB connection."""
    if template_name == "head_to_head":
        return {
            "event_name": "2026 Margaret River Wave Classic",
            "event_country": "Australia",
            "event_date_start": date(2026, 1, 31),
            "event_date_end": date(2026, 2, 8),
            "event_tier": 4,
            "athlete_1_name": "Sarah Kenyon",
            "athlete_1_photo_url": _resolve_photo("sarak kenyon.webp"),
            "athlete_1_placement": 1,
            "athlete_1_heat_wins": 2,
            "athlete_1_best_heat": 9.33,
            "athlete_1_avg_heat": 8.85,
            "athlete_1_best_wave": 5.00,
            "athlete_1_avg_wave": 4.43,
            "athlete_2_name": "Jane Seman",
            "athlete_2_photo_url": _resolve_photo("jane seman.webp"),
            "athlete_2_placement": 2,
            "athlete_2_heat_wins": 1,
            "athlete_2_best_heat": 12.03,
            "athlete_2_avg_heat": 10.65,
            "athlete_2_best_wave": 6.30,
            "athlete_2_avg_wave": 5.33,
        }
    if template_name == "head_to_head_jump":
        base = get_dummy_data("head_to_head")
        base.update({
            "athlete_1_best_jump": 7.20,
            "athlete_1_avg_jump": 5.85,
            "athlete_2_best_jump": 8.10,
            "athlete_2_avg_jump": 6.40,
        })
        return base
    if template_name == "top_10":
        return {
            "title_gender": "Men's",  # includes possessive
            "title_metric": "Waves",
            "title_year": 2025,
            "is_per_event": False,
            "entries": [
                {"rank": 1, "athlete": "Marc Pare Rico", "country": "ES", "score": 8.83, "event": "Chile World Cup", "round": "Final", "heat": "H52a"},
                {"rank": 2, "athlete": "Takara Ishii", "country": "JP", "score": 8.80, "event": "Puerto Rico World Cup", "round": "Semi", "heat": "H48b"},
                {"rank": 3, "athlete": "Bernd Roediger", "country": "US", "score": 8.50, "event": "Puerto Rico", "round": "Quarter", "heat": "H44a"},
                {"rank": 4, "athlete": "Jaegar Stone", "country": "AU", "score": 8.33, "event": "Margaret River Wave Classic", "round": "Final", "heat": "H52b"},
                {"rank": 5, "athlete": "Jaegar Stone", "country": "AU", "score": 8.33, "event": "Margaret River Wave Classic", "round": "Final", "heat": "H52a"},
                {"rank": 6, "athlete": "Jaegar Stone", "country": "AU", "score": 8.33, "event": "Margaret River Wave Classic", "round": "Semi", "heat": "H49a"},
                {"rank": 7, "athlete": "Jaegar Stone", "country": "AU", "score": 8.33, "event": "Margaret River Wave Classic", "round": "Semi", "heat": "H49b"},
                {"rank": 8, "athlete": "Jaegar Stone", "country": "AU", "score": 8.33, "event": "Margaret River Wave Classic", "round": "QF", "heat": "H45a"},
                {"rank": 9, "athlete": "Jaegar Stone", "country": "AU", "score": 8.33, "event": "Margaret River Wave Classic", "round": "QF", "heat": "H45b"},
                {"rank": 10, "athlete": "Jaegar Stone", "country": "AU", "score": 8.33, "event": "Margaret River Wave Classic", "round": "R3", "heat": "H38a"},
            ],
        }
    if template_name == "top_10_carousel":
        return {
            "title_gender": "Men's",
            "title_metric": "Jumps",
            "title_year": 2025,
            "is_per_event": True,
            "event_name": "Gran Canaria World Cup",
            "event_country": "ESP",
            "event_date_start": "Jul 05",
            "event_date_end": "Jul 13",
            "event_stars": 5,
            "show_trick_type": True,
            "entries": [
                {"rank": 1, "athlete": "Antoine Albert", "country": "gp", "score": 10.00, "event": "Gran Canaria World Cup", "round": "Final", "heat": "H52a", "trick_type": "2xF"},
                {"rank": 1, "athlete": "Julien Mas", "country": "fr", "score": 10.00, "event": "Gran Canaria World Cup", "round": "Semi", "heat": "H48b", "trick_type": "P"},
                {"rank": 1, "athlete": "Marc Pare Rico", "country": "es", "score": 10.00, "event": "Gran Canaria World Cup", "round": "Final", "heat": "H52b", "trick_type": "F"},
                {"rank": 1, "athlete": "Takara Ishii", "country": "jp", "score": 10.00, "event": "Gran Canaria World Cup", "round": "QF", "heat": "H44a", "trick_type": "B"},
                {"rank": 5, "athlete": "Jaegar Stone", "country": "au", "score": 9.50, "event": "Gran Canaria World Cup", "round": "Final", "heat": "H52a", "trick_type": "F"},
                {"rank": 6, "athlete": "Bernd Roediger", "country": "us", "score": 9.30, "event": "Gran Canaria World Cup", "round": "Semi", "heat": "H49a", "trick_type": "P"},
                {"rank": 7, "athlete": "Philip Koster", "country": "de", "score": 9.10, "event": "Gran Canaria World Cup", "round": "QF", "heat": "H45a", "trick_type": "2xF"},
                {"rank": 8, "athlete": "Leon Jamaer", "country": "de", "score": 8.90, "event": "Gran Canaria World Cup", "round": "R3", "heat": "H38a", "trick_type": "B"},
                {"rank": 9, "athlete": "Ricardo Campello", "country": "ve", "score": 8.70, "event": "Gran Canaria World Cup", "round": "Semi", "heat": "H48a", "trick_type": "P"},
                {"rank": 10, "athlete": "Alex Mussolini", "country": "es", "score": 8.50, "event": "Gran Canaria World Cup", "round": "R3", "heat": "H38b", "trick_type": "F"},
            ],
        }
    if template_name == "top_10_carousel_waves":
        return {
            "title_gender": "Women's",
            "title_metric": "Waves",
            "title_year": 2025,
            "is_per_event": True,
            "event_name": "Margaret River Wave Classic",
            "event_country": "AUS",
            "event_date_start": "Jan 31",
            "event_date_end": "Feb 08",
            "event_stars": 4,
            "show_trick_type": False,
            "entries": [
                {"rank": 1, "athlete": "Sarah Kenyon", "country": "za", "score": 8.50, "event": "Margaret River Wave Classic", "round": "Final", "heat": "H28a"},
                {"rank": 2, "athlete": "Iballa Moreno", "country": "es", "score": 8.30, "event": "Margaret River Wave Classic", "round": "Final", "heat": "H28a"},
                {"rank": 3, "athlete": "Steffi Wahl", "country": "de", "score": 8.10, "event": "Margaret River Wave Classic", "round": "Semi", "heat": "H26b"},
                {"rank": 4, "athlete": "Maria Andres", "country": "es", "score": 7.90, "event": "Margaret River Wave Classic", "round": "Semi", "heat": "H26a"},
                {"rank": 5, "athlete": "Lina Erzen", "country": "si", "score": 7.70, "event": "Margaret River Wave Classic", "round": "QF", "heat": "H24a"},
                {"rank": 6, "athlete": "Motoko Sato", "country": "jp", "score": 7.50, "event": "Margaret River Wave Classic", "round": "QF", "heat": "H24b"},
                {"rank": 7, "athlete": "Jane Seman", "country": "au", "score": 7.30, "event": "Margaret River Wave Classic", "round": "R3", "heat": "H20a"},
                {"rank": 8, "athlete": "Vicky Gomez", "country": "ve", "score": 7.10, "event": "Margaret River Wave Classic", "round": "R3", "heat": "H20b"},
                {"rank": 9, "athlete": "Nayra Alonso", "country": "es", "score": 6.90, "event": "Margaret River Wave Classic", "round": "Semi", "heat": "H26a"},
                {"rank": 10, "athlete": "Justyna Sniady", "country": "pl", "score": 6.70, "event": "Margaret River Wave Classic", "round": "QF", "heat": "H24a"},
            ],
        }
    if template_name == "top_10_carousel_jumps_no_tie":
        return {
            "title_gender": "Men's",
            "title_metric": "Jumps",
            "title_year": 2025,
            "is_per_event": True,
            "event_name": "Gran Canaria World Cup",
            "event_country": "ESP",
            "event_date_start": "Jul 05",
            "event_date_end": "Jul 13",
            "event_stars": 5,
            "show_trick_type": True,
            "entries": [
                {"rank": 1, "athlete": "Antoine Albert", "country": "gp", "score": 10.00, "event": "Gran Canaria World Cup", "round": "Final", "heat": "H52a", "trick_type": "2xF"},
                {"rank": 2, "athlete": "Julien Mas", "country": "fr", "score": 9.80, "event": "Gran Canaria World Cup", "round": "Semi", "heat": "H48b", "trick_type": "P"},
                {"rank": 3, "athlete": "Marc Pare Rico", "country": "es", "score": 9.60, "event": "Gran Canaria World Cup", "round": "Final", "heat": "H52b", "trick_type": "F"},
                {"rank": 4, "athlete": "Takara Ishii", "country": "jp", "score": 9.40, "event": "Gran Canaria World Cup", "round": "QF", "heat": "H44a", "trick_type": "B"},
                {"rank": 5, "athlete": "Jaegar Stone", "country": "au", "score": 9.20, "event": "Gran Canaria World Cup", "round": "Final", "heat": "H52a", "trick_type": "F"},
                {"rank": 6, "athlete": "Bernd Roediger", "country": "us", "score": 9.00, "event": "Gran Canaria World Cup", "round": "Semi", "heat": "H49a", "trick_type": "P"},
                {"rank": 7, "athlete": "Philip Koster", "country": "de", "score": 8.80, "event": "Gran Canaria World Cup", "round": "QF", "heat": "H45a", "trick_type": "2xF"},
                {"rank": 8, "athlete": "Leon Jamaer", "country": "de", "score": 8.60, "event": "Gran Canaria World Cup", "round": "R3", "heat": "H38a", "trick_type": "B"},
                {"rank": 9, "athlete": "Ricardo Campello", "country": "ve", "score": 8.40, "event": "Gran Canaria World Cup", "round": "Semi", "heat": "H48a", "trick_type": "P"},
                {"rank": 10, "athlete": "Alex Mussolini", "country": "es", "score": 8.20, "event": "Gran Canaria World Cup", "round": "R3", "heat": "H38b", "trick_type": "F"},
            ],
        }
    if template_name == "perfect_10s":
        # 12 perfect 10.00 wave scores from the live DB (2016-2019),
        # ordered chronologically descending (latest first).
        rows = [
            {"athlete": "Bernd Roediger", "country": "us", "year": 2019, "event": "Mercedes-Benz Aloha Classic", "round": "R3", "heat": "H20a", "sex": "M"},
            {"athlete": "Antoine Martin", "country": "gp", "year": 2019, "event": "Mercedes-Benz Aloha Classic", "round": "R5", "heat": "H23a", "sex": "M"},
            {"athlete": "Víctor Fernández", "country": "es", "year": 2019, "event": "Gran Canaria PWA World Cup", "round": "R3", "heat": "H18b", "sex": "M"},
            {"athlete": "Moritz Mauch", "country": "es", "year": 2018, "event": "Gran Canaria", "round": "R1", "heat": "H26b", "sex": "M"},
            {"athlete": "Daida Ruano Moreno", "country": "es", "year": 2018, "event": "Gran Canaria", "round": "R2", "heat": "H10b", "sex": "W"},
            {"athlete": "Adam Lewis", "country": "gb", "year": 2018, "event": "Tenerife", "round": "R5", "heat": "H23b", "sex": "M"},
            {"athlete": "Víctor Fernández", "country": "es", "year": 2017, "event": "Gran Canaria", "round": "R6", "heat": "H25a", "sex": "M"},
            {"athlete": "Moritz Mauch", "country": "es", "year": 2017, "event": "Mercedes-Benz World Cup Sylt", "round": "R1", "heat": "H8a", "sex": "M"},
            {"athlete": "Philip Köster", "country": "de", "year": 2017, "event": "Mercedes-Benz World Cup Sylt", "round": "R6", "heat": "H33a", "sex": "M"},
            {"athlete": "Antoine Martin", "country": "gp", "year": 2017, "event": "Gran Canaria", "round": "R2", "heat": "H9a", "sex": "M"},
            {"athlete": "Kai Lenny", "country": "us", "year": 2016, "event": "Aloha Classic", "round": "R5", "heat": "H42a", "sex": "M"},
            {"athlete": "Robby Swift", "country": "gb", "year": 2016, "event": "Aloha Classic", "round": "R5", "heat": "H43a", "sex": "M"},
        ]
        entries = [
            {"rank": i + 1, "score": 10.00, **row}
            for i, row in enumerate(rows)
        ]
        return {
            "title_gender": "",
            "title_metric": "Waves",
            "title_year": "All Time",
            "show_trick_type": False,
            "is_per_event": False,
            "perfect_10s_mode": True,
            "custom_title": "EVERY PERFECT 10 WAVE",
            "custom_subtitle": "",
            "entries": entries,
        }
    if template_name == "about_carousel":
        from pipeline.about import build_about_slides
        return {"slides": build_about_slides()}
    if template_name == "coming_soon_carousel":
        from pipeline.coming_soon import build_coming_soon_slides
        return {"slides": build_coming_soon_slides()}
    if template_name == "h2h_carousel":
        return get_dummy_data("head_to_head")
    if template_name == "h2h_carousel_jump":
        return get_dummy_data("head_to_head_jump")
    if template_name in ("site_stats", "site_stats_reel"):
        return {
            "athletes_count": 359,
            "scores_count": 43515,
            "events_count": 58,
        }
    if template_name == "fantasy_league_announce":
        return {
            "eyebrow": "BETA ACCESS",
            "headline_lines": ["WINDSURF", "FANTASY", "LEAGUE"],
            "sub_lines": [
                "Build your fantasy team and score points across the 2026 tour.",
            ],
            "cta": "TESTERS WANTED. COMMENT BETA TO JOIN.",
            "url": "windsurfworldtourstats.com",
        }
    if template_name == "canary_kings":
        return {
            "men": [
                {"athlete": "Philip Köster", "nationality": "Germany", "athlete_id": 49, "wins": 5, "gc_wins": 4, "tf_wins": 1, "photo_url": "https://www.liveheats.com/images/b2e3b752-d739-4f4c-9b04-bb14b29d4aef.webp"},
                {"athlete": "Víctor Fernández", "nationality": "Spain", "athlete_id": 56, "wins": 3, "gc_wins": 1, "tf_wins": 2, "photo_url": "https://www.liveheats.com/images/6537867d-aaae-443a-9116-ece23adf9c74.webp"},
                {"athlete": "Marc Paré Rico", "nationality": "Spain", "athlete_id": 97, "wins": 2, "gc_wins": 0, "tf_wins": 2, "photo_url": "https://www.liveheats.com/images/91f017d3-3e01-4e79-ae67-425a233897a1.webp"},
                {"athlete": "Ricardo Campello", "nationality": "Venezuela (Bolivarian Republic of)", "athlete_id": 91, "wins": 1, "gc_wins": 1, "tf_wins": 0, "photo_url": "https://www.liveheats.com/images/050503b5-9b6f-47d0-809e-373e0b56ae3b.webp"},
                {"athlete": "Jaeger Stone", "nationality": "Australian", "athlete_id": 187, "wins": 1, "gc_wins": 0, "tf_wins": 1, "photo_url": None},
                {"athlete": "Marcilio Browne", "nationality": "Brazil", "athlete_id": 68, "wins": 1, "gc_wins": 1, "tf_wins": 0, "photo_url": "https://www.liveheats.com/images/877ad891-76ec-49fc-8eb6-d9f899293e9f.webp"},
                {"athlete": "Marino Gil Gherardi", "nationality": "Spain", "athlete_id": 48, "wins": 1, "gc_wins": 1, "tf_wins": 0, "photo_url": "https://www.liveheats.com/images/1ff8b666-5d0e-48ae-b72e-0a311feefef0.webp"},
            ],
            "women": [
                {"athlete": "Daida Ruano Moreno", "nationality": "Spanish", "athlete_id": 147, "wins": 7, "gc_wins": 7, "tf_wins": 0, "photo_url": None},
                {"athlete": "Iballa Ruano Moreno", "nationality": "Spanish", "athlete_id": 178, "wins": 4, "gc_wins": 0, "tf_wins": 4, "photo_url": None},
                {"athlete": "Sarah-Quita Offringa", "nationality": "Aruba", "athlete_id": 5, "wins": 2, "gc_wins": 1, "tf_wins": 1, "photo_url": "https://www.liveheats.com/images/7c3df566-6afe-4912-83bf-2b21b73ae490.webp"},
                {"athlete": "Lina Erpenstein", "nationality": "Germany", "athlete_id": 16, "wins": 1, "gc_wins": 0, "tf_wins": 1, "photo_url": "https://www.liveheats.com/images/4d2e15d9-b0ab-461e-9b3f-e2f65e4dc541.webp"},
            ],
        }
    if template_name == "athlete_rise":
        return {
            "title": "THE RISE OF MARINO GIL GHERARDI AT THE GRAN CANARIA WORLD CUP",
            "subtitle": "Check out the meteoric rise of Marino's world cup performances at his home spot in Gran Canaria",
            "athlete_name": "Marino Gil Gherardi",
            "athlete_photo_url": "https://www.liveheats.com/images/1ff8b666-5d0e-48ae-b72e-0a311feefef0.webp",
            "location": "Gran Canaria",
            "accent_color": "#9478B5",
            "yearly_data": [
                {"year": 2017, "placement": 33, "best_heat": 16.50, "best_wave": 5.50, "best_jump": 7.38, "best_jump_type": "B"},
                {"year": 2018, "placement": 17, "best_heat": 25.38, "best_wave": 7.38, "best_jump": 7.25, "best_jump_type": "F"},
                {"year": 2019, "placement": 17, "best_heat": 26.65, "best_wave": 7.95, "best_jump": 7.00, "best_jump_type": "B"},
                {"year": 2022, "placement": 6, "best_heat": 20.43, "best_wave": 7.38, "best_jump": 7.50, "best_jump_type": "F"},
                {"year": 2023, "placement": 2, "best_heat": 31.25, "best_wave": 8.12, "best_jump": 10.00, "best_jump_type": "PF"},
                {"year": 2024, "placement": 1, "best_heat": 28.43, "best_wave": 6.62, "best_jump": 9.57, "best_jump_type": "PF"},
                {"year": 2025, "placement": 3, "best_heat": 27.47, "best_wave": 5.62, "best_jump": 10.00, "best_jump_type": "PF"},
            ],
        }
    if template_name == "rider_profile":
        return {
            "athlete_name": "Marc Pare Rico",
            "athlete_country": "ES",
            "athlete_photo_url": _resolve_photo("marc pare rico.webp"),
            "athlete_sail_number": "E-73",
            "event_name": "2026 Chile World Cup",
            "event_country": "CL",
            "event_date_start": date(2026, 3, 1),
            "event_date_end": date(2026, 3, 8),
            "event_tier": 5,
            "placement": 1,
            "best_heat": 16.33,
            "best_heat_round": "Final",
            "best_wave": 8.83,
            "best_jump": 7.50,
            "avg_wave": 6.12,
            "top_waves": [
                {"rank": 1, "score": 8.83, "round": "Final"},
                {"rank": 2, "score": 7.60, "round": "Semi"},
                {"rank": 3, "score": 7.20, "round": "Quarter"},
                {"rank": 4, "score": 6.90, "round": "Semi"},
                {"rank": 5, "score": 6.50, "round": "Round 3"},
            ],
        }
    raise ValueError(f"No dummy data for template: {template_name}")
