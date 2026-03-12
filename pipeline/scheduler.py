"""Content calendar scheduler — batch render and publish from a manifest."""
import os
from datetime import datetime

import yaml

from pipeline.api import fetch_head_to_head, fetch_site_stats, fetch_athlete_event_stats
from pipeline.captions import build_caption
from pipeline.db import run_query
from pipeline.helpers import nationality_to_iso, clean_event_name
from pipeline.publisher import publish, schedule_post
from pipeline.queries import build_top10_query
from pipeline.renderer import render_to_png
from pipeline.templates import render_template


def load_calendar(path: str) -> dict:
    """Load a content calendar YAML file."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_config():
    """Load the main config.yaml."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config.yaml"
    )
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def filter_posts(
    posts: list,
    category: str = None,
    template: str = None,
    ids: list = None,
) -> list:
    """Filter calendar posts by category, template, or specific IDs."""
    result = posts
    if category:
        result = [p for p in result if p.get("category") == category]
    if template:
        result = [p for p in result if p.get("template") == template]
    if ids:
        id_set = set(ids)
        result = [p for p in result if p.get("id") in id_set]
    return result


def resolve_post_data(post: dict) -> dict:
    """Fetch live data for a calendar post based on its template and params."""
    template = post["template"]
    params = post.get("params", {})

    if template in ("head_to_head", "head_to_head_jump"):
        return fetch_head_to_head(
            event_id=params["event"],
            athlete1_id=params["athlete1"],
            athlete2_id=params["athlete2"],
            division=params["division"],
        )

    if template == "top_10":
        score_type = params["score_type"]
        sex = params.get("sex")
        year = params.get("year")
        event_id = params.get("event")

        sql, query_params = build_top10_query(
            score_type=score_type, sex=sex, year=year, event_id=event_id
        )
        rows = run_query(sql, query_params)
        gender_map = {"Men": "Men's", "Women": "Women's"}
        is_jump = score_type == "Jump"
        entries = []
        for i, r in enumerate(rows):
            entry = {
                "rank": i + 1,
                "athlete": r["athlete"],
                "country": nationality_to_iso(r.get("country", "")),
                "score": float(r["score"]),
                "event": clean_event_name(r["event"]),
                "round": r.get("round", ""),
            }
            if is_jump:
                entry["trick_type"] = r.get("trick_type", "")
            entries.append(entry)
        return {
            "title_gender": gender_map.get(sex, ""),
            "title_metric": f"{score_type}s",
            "title_year": year or "All Time",
            "show_trick_type": is_jump,
            "is_per_event": False,
            "entries": entries,
        }

    if template in ("site_stats", "site_stats_reel"):
        return fetch_site_stats()

    if template == "rider_profile":
        return fetch_athlete_event_stats(
            event_id=params["event"],
            athlete_id=params["athlete1"],
            division=params["division"],
        )

    raise ValueError(f"Unknown template: {template}")


def run_calendar(
    posts: list,
    publish_mode: str = None,
    schedule_time: datetime = None,
    output_dir: str = None,
) -> list:
    """Render and optionally publish a list of calendar posts.

    Args:
        posts: List of post definitions from the calendar.
        publish_mode: None (render only), "now", or "schedule".
        schedule_time: Required if publish_mode is "schedule".
        output_dir: Override output directory.

    Returns:
        List of result dicts, one per post.
    """
    config = load_config()
    out_dir = output_dir or config.get("output_dir", "./output")
    results = []

    for post in posts:
        post_id = post.get("id", post["template"])
        try:
            # Fetch data
            data = resolve_post_data(post)

            # Render HTML
            template_name = post["template"]
            html = render_template(template_name, data)

            # Render PNG
            template_config = config["templates"].get(template_name, {})
            width = template_config.get("width", 1080)
            height = template_config.get("height", 1350)
            dpr = template_config.get("dpr", 2)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(
                out_dir, "png", f"{template_name}_{timestamp}.png"
            )
            rendered = render_to_png(
                html, output_path, width=width, height=height, dpr=dpr
            )

            # Build caption
            caption_override = post.get("caption")
            caption = build_caption(template_name, data, config, caption_override)

            result = {"id": post_id, "output": rendered, "caption": caption}

            # Publish
            if publish_mode == "now":
                pub = publish(rendered, caption)
                result["media_id"] = pub["media_id"]
            elif publish_mode == "schedule" and schedule_time:
                sched = schedule_post(rendered, caption, schedule_time)
                result["container_id"] = sched["container_id"]

            results.append(result)
            print(f"  OK: {post_id} -> {rendered}")

        except Exception as e:
            results.append({"id": post_id, "error": str(e)})
            print(f"  FAIL: {post_id} — {e}")

    return results
