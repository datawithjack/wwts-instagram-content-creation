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
