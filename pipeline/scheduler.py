"""Content calendar scheduler — batch render and publish from a manifest."""
import os
from datetime import datetime, timezone, timedelta

import yaml
from ruamel.yaml import YAML

from pipeline.api import fetch_head_to_head, fetch_site_stats, fetch_athlete_event_stats, fetch_event_top_scores
from pipeline.captions import build_caption
from pipeline.db import run_query
from pipeline.helpers import nationality_to_iso, clean_event_name
from pipeline.publisher import publish, publish_carousel, schedule_post
from pipeline.queries import build_top10_query
from pipeline.renderer import render_to_png, render_carousel
from pipeline.templates import render_template

# Templates that render as multi-slide carousels
CAROUSEL_TEMPLATES = {
    "top_10_carousel", "h2h_carousel", "rider_profile",
    "canary_kings", "athlete_rise", "about_carousel", "coming_soon_carousel",
}


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


def parse_scheduled_date(date_str: str) -> datetime:
    """Parse a scheduled_date string to a timezone-aware datetime (UTC)."""
    dt = datetime.fromisoformat(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def sort_by_scheduled_date(posts: list) -> list:
    """Sort posts by scheduled_date ascending. Posts without a date go last."""
    def sort_key(post):
        sd = post.get("scheduled_date")
        if sd is None:
            return (1, datetime.max.replace(tzinfo=timezone.utc))
        return (0, parse_scheduled_date(sd))
    return sorted(posts, key=sort_key)


def validate_scheduled_dates(posts: list) -> None:
    """Raise ValueError if any post has a scheduled_date in the past."""
    now = datetime.now(timezone.utc)
    for post in posts:
        sd = post.get("scheduled_date")
        if sd and parse_scheduled_date(sd) < now:
            raise ValueError(
                f"Post '{post.get('id', '?')}' has scheduled_date {sd} in the past"
            )


def filter_posts_due(
    posts: list,
    now: datetime = None,
) -> list:
    """Return unpublished posts whose scheduled_date is at or before now + 5min.

    Any past unpublished post is considered due, regardless of how long ago
    it was scheduled. This ensures posts are picked up even if the cron job
    runs late.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    window_end = now + timedelta(minutes=5)

    due = []
    for post in posts:
        if post.get("published"):
            continue
        sd = post.get("scheduled_date")
        if not sd:
            continue
        dt = parse_scheduled_date(sd)
        if dt <= window_end:
            due.append(post)
    return due


def mark_post_published(calendar_path: str, post_id: str) -> None:
    """Mark a post as published in the YAML file, preserving comments.

    Uses line-level text insertion after the scheduled_date line to avoid
    ruamel.yaml placing fields at the end of the mapping.
    """
    with open(calendar_path, "r") as f:
        lines = f.readlines()

    # Find the post by id, then find its scheduled_date line
    found_post = False
    insert_after = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == f"id: {post_id}" or stripped == f"- id: {post_id}":
            found_post = True
        if found_post and stripped.startswith("scheduled_date:"):
            insert_after = i
            break

    if insert_after is None:
        raise ValueError(f"Post '{post_id}' not found in {calendar_path}")

    # Detect indentation from the scheduled_date line
    indent = lines[insert_after][: len(lines[insert_after]) - len(lines[insert_after].lstrip())]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    new_lines = [
        f"{indent}published: true\n",
        f"{indent}published_at: \"{timestamp}\"\n",
    ]
    lines[insert_after + 1:insert_after + 1] = new_lines

    with open(calendar_path, "w") as f:
        f.writelines(lines)


def run_poll(calendar_path: str) -> list:
    """Poll the backlog for due posts, publish them, and mark as published."""
    calendar = load_calendar(calendar_path)
    posts = calendar.get("posts", [])
    due = filter_posts_due(posts)

    if not due:
        print("0 posts due — nothing to publish.")
        return []

    print(f"{len(due)} post(s) due for publishing:")
    for p in due:
        print(f"  - {p.get('id')} @ {p.get('scheduled_date')}")

    results = run_calendar(due, publish_mode="now")

    for result in results:
        if "error" not in result:
            mark_post_published(calendar_path, result["id"])
            print(f"  MARKED: {result['id']} as published")
        else:
            print(f"  SKIP MARKING: {result['id']} — failed: {result['error']}")

    return results


def resolve_post_data(post: dict) -> dict:
    """Fetch live data for a calendar post based on its template and params."""
    template = post["template"]
    params = post.get("params", {})

    if template in ("head_to_head", "head_to_head_jump", "h2h_carousel"):
        return fetch_head_to_head(
            event_id=params["event"],
            athlete1_id=params["athlete1"],
            athlete2_id=params["athlete2"],
            division=params["division"],
        )

    if template in ("top_10", "top_10_carousel"):
        score_type = params["score_type"]
        sex = params.get("sex")
        year = params.get("year")
        event_id = params.get("event")

        # Use API for per-event top 10; fall back to DB otherwise
        if event_id:
            return fetch_event_top_scores(
                event_id=event_id, score_type=score_type, sex=sex,
            )

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


def _render_carousel_slides(
    template_name: str, data: dict, output_dir: str, timestamp: str,
    width: int, height: int, dpr: int,
) -> list[str]:
    """Render carousel slides to PNGs. Returns list of file paths."""
    if template_name == "top_10_carousel":
        return render_carousel(
            data, output_dir,
            base_name=f"top_10_carousel_{timestamp}",
            width=width, height=height, dpr=dpr,
        )
    if template_name == "h2h_carousel":
        from pipeline.renderer import render_h2h_carousel
        return render_h2h_carousel(
            data, output_dir,
            base_name=f"h2h_carousel_{timestamp}",
            width=width, height=height, dpr=dpr,
        )
    if template_name == "rider_profile":
        from pipeline.renderer import render_rp_carousel
        return render_rp_carousel(
            data, output_dir,
            base_name=f"rider_profile_{timestamp}",
            width=width, height=height, dpr=dpr,
        )
    if template_name == "canary_kings":
        from pipeline.renderer import render_analysis_carousel
        return render_analysis_carousel(
            data["men"], data["women"], output_dir,
            base_name=f"canary_kings_{timestamp}",
            width=width, height=height, dpr=dpr,
        )
    if template_name == "athlete_rise":
        from pipeline.renderer import render_athlete_rise_carousel
        return render_athlete_rise_carousel(
            data, output_dir,
            base_name=f"athlete_rise_{timestamp}",
            width=width, height=height, dpr=dpr,
        )
    # Generic carousel (about, coming_soon)
    from pipeline.carousel import build_slides
    from pipeline.renderer import render_to_png as _render_png
    slides = build_slides(data) if "slides" not in data else data["slides"]
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    prefix = template_name.replace("_carousel", "")
    for i, slide in enumerate(slides, 1):
        html = render_template(f"carousel/slide_{slide['type']}", slide)
        output_path = os.path.join(output_dir, f"{prefix}_{timestamp}_{i}.png")
        _render_png(html, output_path, width=width, height=height, dpr=dpr)
        paths.append(output_path)
    return paths


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

            template_name = post["template"]
            template_config = config["templates"].get(template_name, {})
            width = template_config.get("width", 1080)
            height = template_config.get("height", 1350)
            dpr = template_config.get("dpr", 2)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            png_dir = os.path.join(out_dir, "png")

            is_carousel = template_name in CAROUSEL_TEMPLATES

            # Build caption
            caption_override = post.get("caption")
            caption = build_caption(template_name, data, config, caption_override)

            if is_carousel:
                rendered_paths = _render_carousel_slides(
                    template_name, data, png_dir, timestamp, width, height, dpr,
                )
                result = {"id": post_id, "output": rendered_paths, "caption": caption}
            else:
                html = render_template(template_name, data)
                output_path = os.path.join(png_dir, f"{template_name}_{timestamp}.png")
                rendered = render_to_png(html, output_path, width=width, height=height, dpr=dpr)
                rendered_paths = [rendered]
                result = {"id": post_id, "output": rendered, "caption": caption}

            # Publish
            if publish_mode == "now":
                if is_carousel:
                    pub = publish_carousel(rendered_paths, caption)
                else:
                    pub = publish(rendered_paths[0], caption)
                result["media_id"] = pub["media_id"]
            elif publish_mode == "schedule":
                # CLI schedule_time overrides per-post date
                effective_time = schedule_time
                if not effective_time and post.get("scheduled_date"):
                    effective_time = parse_scheduled_date(post["scheduled_date"])
                if effective_time:
                    if is_carousel:
                        # TODO: schedule_carousel not yet implemented — publish now as fallback
                        pub = publish_carousel(rendered_paths, caption)
                        result["media_id"] = pub["media_id"]
                        result["note"] = "carousel scheduled publish not yet supported, published immediately"
                    else:
                        sched = schedule_post(rendered_paths[0], caption, effective_time)
                        result["container_id"] = sched["container_id"]
                    result["scheduled_date"] = post.get("scheduled_date")
                else:
                    result["skipped"] = "no scheduled_date and no --schedule-start"
                    print(f"  SKIP: {post_id} — no scheduled_date")

            results.append(result)
            print(f"  OK: {post_id} -> {rendered_paths if is_carousel else rendered_paths[0]}")

        except Exception as e:
            results.append({"id": post_id, "error": str(e)})
            print(f"  FAIL: {post_id} — {e}")

    return results
