"""Main entry point for Instagram content generation pipeline."""
import argparse
import os
import sys
import webbrowser
import tempfile
from datetime import datetime

import yaml
from dotenv import load_dotenv

load_dotenv()

from pipeline.api import fetch_head_to_head, fetch_site_stats, fetch_athlete_event_stats, fetch_event_top_scores
from pipeline.captions import build_caption
from pipeline.db import run_query
from pipeline.helpers import nationality_to_iso, clean_event_name
from pipeline.queries import build_top10_query
from pipeline.templates import render_template, get_dummy_data
from pipeline.renderer import render_to_png, render_to_video, render_carousel


def fetch_live_data(template_name: str, args) -> dict:
    """Fetch live data from API or DB based on template type."""
    if template_name in ("head_to_head", "head_to_head_jump"):
        if not all([args.event, args.athlete1, args.athlete2, args.division]):
            print("H2H requires: --event, --athlete1, --athlete2, --division")
            sys.exit(1)
        return fetch_head_to_head(
            event_id=args.event,
            athlete1_id=args.athlete1,
            athlete2_id=args.athlete2,
            division=args.division,
        )

    if template_name in ("top_10", "top_10_carousel"):
        if not args.score_type:
            print("Top 10 requires: --score-type (Wave or Jump)")
            sys.exit(1)

        # Use API for per-event top 10 (no DB needed)
        if args.event:
            return fetch_event_top_scores(
                event_id=args.event,
                score_type=args.score_type,
                sex=args.sex,
            )

        # Use DB for cross-event queries (by year or all-time)
        sql, params = build_top10_query(
            score_type=args.score_type,
            sex=args.sex,
            year=args.year,
        )
        rows = run_query(sql, params)
        gender_map = {"Men": "Men's", "Women": "Women's"}
        is_jump = args.score_type == "Jump"
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
            "title_gender": gender_map.get(args.sex, ""),
            "title_metric": f"{args.score_type}s",
            "title_year": args.year or "All Time",
            "show_trick_type": is_jump,
            "is_per_event": False,
            "entries": entries,
        }

    if template_name in ("site_stats", "site_stats_reel"):
        return fetch_site_stats()

    if template_name == "rider_profile":
        if not all([args.event, args.athlete1, args.division]):
            print("Rider profile requires: --event, --athlete1, --division")
            sys.exit(1)
        return fetch_athlete_event_stats(
            event_id=args.event,
            athlete_id=args.athlete1,
            division=args.division,
        )

    print(f"Live data not implemented for template: {template_name}")
    sys.exit(1)


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="WWT Instagram content generator")
    parser.add_argument(
        "--template",
        required=True,
        choices=["head_to_head", "head_to_head_jump", "top_10", "top_10_carousel", "site_stats", "site_stats_reel", "stat_of_the_day", "rider_profile"],
    )
    parser.add_argument("--athlete1", type=int, help="Athlete 1 unified ID")
    parser.add_argument("--athlete2", type=int, help="Athlete 2 unified ID")
    parser.add_argument("--event", type=int, help="Event ID")
    parser.add_argument("--division", choices=["Men", "Women"], help="Division for H2H")
    parser.add_argument("--sex", choices=["Men", "Women"], help="Sex filter for top 10")
    parser.add_argument("--score-type", choices=["Wave", "Jump"], help="Score type for top 10")
    parser.add_argument("--year", type=int, help="Year filter for top 10")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use dummy data instead of DB",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Open HTML in browser instead of rendering PNG",
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="Render as animated MP4 video instead of static PNG",
    )
    parser.add_argument("--duration", type=int, default=6000, help="Video duration in ms")
    parser.add_argument("--output", help="Custom output path")
    parser.add_argument(
        "--publish",
        choices=["now"],
        help="Publish to Instagram after rendering",
    )
    parser.add_argument("--caption", help="Custom caption override")

    args = parser.parse_args()
    config = load_config()

    template_name = args.template
    template_config = config["templates"].get(template_name, {})
    width = template_config.get("width", 1080)
    height = template_config.get("height", 1350)
    dpr = template_config.get("dpr", 2)

    # Get data
    if args.dry_run:
        data = get_dummy_data(template_name)
    else:
        data = fetch_live_data(template_name, args)

    is_carousel = template_name == "top_10_carousel"

    # Carousel preview: open all 5 slides in browser tabs
    if is_carousel and args.preview:
        from pipeline.carousel import build_slides
        slides = build_slides(data)
        for slide in slides:
            html = render_template(f"carousel/slide_{slide['type']}", slide)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", delete=False, encoding="utf-8"
            ) as f:
                f.write(html)
                print(f"Preview: {f.name}")
                webbrowser.open(f"file:///{f.name.replace(os.sep, '/')}")
        return

    # Single-template preview
    if not is_carousel:
        html = render_template(template_name, data)

    if args.preview:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html)
            print(f"Preview: {f.name}")
            webbrowser.open(f"file:///{f.name.replace(os.sep, '/')}")
        return

    # Render output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = config.get("output_dir", "./output")

    if is_carousel:
        carousel_dir = os.path.join(output_dir, "png")
        result_paths = render_carousel(
            data, carousel_dir,
            base_name=f"top_10_carousel_{timestamp}",
            width=width, height=height, dpr=dpr,
        )
        for p in result_paths:
            print(f"Rendered: {p}")

        if args.publish == "now":
            from pipeline.publisher import publish_carousel as publish_carousel_to_ig

            caption = args.caption or build_caption(template_name, data, config)
            print("Publishing carousel to Instagram...")
            pub_result = publish_carousel_to_ig(result_paths, caption)
            print(f"Published! Media ID: {pub_result['media_id']}")
        return

    # Auto-enable video for reel templates
    use_video = args.video or template_name.endswith("_reel")

    if use_video:
        if args.output:
            output_path = args.output
        else:
            output_path = os.path.join(output_dir, "mp4", f"{template_name}_{timestamp}.mp4")
        result = render_to_video(
            html, output_path, width=width, height=height, dpr=1,
            duration_ms=args.duration,
        )
    else:
        if args.output:
            output_path = args.output
        else:
            output_path = os.path.join(output_dir, "png", f"{template_name}_{timestamp}.png")
        result = render_to_png(html, output_path, width=width, height=height, dpr=dpr)

    print(f"Rendered: {result}")

    # Publish to Instagram if requested
    if args.publish == "now":
        from pipeline.publisher import publish as publish_to_instagram

        caption = args.caption or build_caption(template_name, data, config)
        print("Publishing to Instagram...")
        pub_result = publish_to_instagram(result, caption)
        print(f"Published! Media ID: {pub_result['media_id']}")


if __name__ == "__main__":
    main()
