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
from pipeline.helpers import nationality_to_iso, clean_event_name, heat_label_from_id, short_round_name
from pipeline.queries import build_top10_query, build_canary_kings_query, build_athlete_rise_query
from pipeline.templates import render_template, get_dummy_data
from pipeline.renderer import render_to_png, render_to_video, render_carousel, render_h2h_carousel, render_rp_carousel, render_analysis_carousel, render_athlete_rise_carousel


def fetch_live_data(template_name: str, args) -> dict:
    """Fetch live data from API or DB based on template type."""
    if template_name in ("head_to_head", "head_to_head_jump", "h2h_carousel"):
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

        # Use API for per-event top 10; fall back to DB if API 404s
        if args.event:
            try:
                return fetch_event_top_scores(
                    event_id=args.event,
                    score_type=args.score_type,
                    sex=args.sex,
                )
            except Exception:
                print("API per-event endpoint unavailable, falling back to DB...")

        # Use DB for queries (per-event, by year, or all-time)
        sql, params = build_top10_query(
            score_type=args.score_type,
            sex=args.sex,
            year=args.year,
            event_id=args.event,
        )
        rows = run_query(sql, params)
        gender_map = {"Men": "Men's", "Women": "Women's"}
        is_jump = args.score_type == "Jump"
        is_per_event = bool(args.event)

        entries = []
        for i, r in enumerate(rows):
            round_str = short_round_name(r.get("round", ""))
            heat = heat_label_from_id(r.get("heat_id", ""))
            entry = {
                "rank": i + 1,
                "athlete": r["athlete"],
                "country": nationality_to_iso(r.get("country", "")),
                "score": float(r["score"]),
                "event": clean_event_name(r["event"]),
                "round": round_str,
                "heat": heat,
            }
            if is_jump:
                entry["trick_type"] = r.get("trick_type", "")
            entries.append(entry)

        data = {
            "title_gender": gender_map.get(args.sex, ""),
            "title_metric": f"{args.score_type}s",
            "title_year": args.year or "All Time",
            "show_trick_type": is_jump,
            "is_per_event": is_per_event,
            "entries": entries,
        }

        # Enrich with event metadata for per-event queries
        if is_per_event:
            event_row = run_query(
                "SELECT event_name, start_date, end_date, stars, country_code "
                "FROM PWA_IWT_EVENTS WHERE event_id = %s AND source = 'PWA' LIMIT 1",
                (args.event,),
            )
            if event_row:
                ev = event_row[0]
                data["event_name"] = clean_event_name(ev["event_name"])
                data["event_country"] = ev.get("country_code", "")
                data["event_stars"] = ev.get("stars", 0)
                start = ev.get("start_date")
                end = ev.get("end_date")
                if start:
                    from datetime import date as dt_date
                    if isinstance(start, str):
                        start = dt_date.fromisoformat(start)
                    data["event_date_start"] = start.strftime("%b %d")
                if end:
                    if isinstance(end, str):
                        end = dt_date.fromisoformat(end)
                    data["event_date_end"] = end.strftime("%b %d")
                # Set year from event if not provided
                if not args.year and start:
                    data["title_year"] = start.year

        return data

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

    if template_name == "canary_kings":
        men_sql, men_params = build_canary_kings_query("Men")
        women_sql, women_params = build_canary_kings_query("Women")
        men_data = run_query(men_sql, men_params)
        women_data = run_query(women_sql, women_params)
        return {"men": men_data, "women": women_data}

    if template_name == "athlete_rise":
        if not all([args.athlete1, args.location, args.sex]):
            print("Athlete rise requires: --athlete1, --location, --sex")
            sys.exit(1)
        event_pattern = f"%%{args.location}%%"
        sql, params = build_athlete_rise_query(args.athlete1, event_pattern, args.sex)
        rows = run_query(sql, params)
        yearly_data = []
        for r in rows:
            yearly_data.append({
                "year": int(r["year"]),
                "placement": int(r["placement"]) if r.get("placement") else None,
                "best_heat": float(r["best_heat"]) if r.get("best_heat") else None,
                "best_wave": float(r["best_wave"]) if r.get("best_wave") else None,
                "best_jump": float(r["best_jump"]) if r.get("best_jump") else None,
                "best_jump_type": r.get("best_jump_type", "").strip() if r.get("best_jump_type") else None,
            })
        # Build title from athlete name (lookup from DB)
        name_rows = run_query(
            "SELECT primary_name, liveheats_image_url FROM ATHLETES WHERE id = %s LIMIT 1",
            (args.athlete1,),
        )
        athlete_name = name_rows[0]["primary_name"] if name_rows else f"Athlete {args.athlete1}"
        athlete_photo_url = name_rows[0].get("liveheats_image_url", "") if name_rows else ""
        return {
            "title": f"THE RISE OF {athlete_name.upper()} IN {args.location.upper()}",
            "subtitle": f"Check out the meteoric rise of {athlete_name.split()[0]}'s world cup performances at {args.location}",
            "athlete_id": args.athlete1,
            "athlete_name": athlete_name,
            "athlete_photo_url": athlete_photo_url or "",
            "location": args.location,
            "accent_color": "#9478B5",
            "yearly_data": yearly_data,
        }

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
        choices=["head_to_head", "head_to_head_jump", "h2h_carousel", "top_10", "top_10_carousel", "about_carousel", "coming_soon_carousel", "site_stats", "site_stats_reel", "stat_of_the_day", "rider_profile", "canary_kings", "athlete_rise"],
    )
    parser.add_argument("--athlete1", type=int, help="Athlete 1 unified ID")
    parser.add_argument("--athlete2", type=int, help="Athlete 2 unified ID")
    parser.add_argument("--event", type=int, help="Event ID")
    parser.add_argument("--division", choices=["Men", "Women"], help="Division for H2H")
    parser.add_argument("--sex", choices=["Men", "Women"], help="Sex filter for top 10 / athlete rise")
    parser.add_argument("--location", help="Location pattern for athlete rise (e.g. 'Gran Canaria')")
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
    if args.dry_run or template_name in ("coming_soon_carousel", "about_carousel"):
        data = get_dummy_data(template_name)
    else:
        data = fetch_live_data(template_name, args)

    is_carousel = template_name in ("top_10_carousel", "coming_soon_carousel", "about_carousel", "h2h_carousel", "rider_profile", "canary_kings", "athlete_rise")

    # Carousel preview: open all slides in browser tabs
    if is_carousel and args.preview:
        if template_name in ("coming_soon_carousel", "about_carousel"):
            slides = data["slides"]
        elif template_name == "h2h_carousel":
            from pipeline.h2h_carousel import build_slides as build_h2h_slides
            slides = build_h2h_slides(data)
        elif template_name == "rider_profile":
            from pipeline.rp_carousel import build_slides as build_rp_slides
            slides = build_rp_slides(data)
        elif template_name == "canary_kings":
            from pipeline.analysis_carousel import build_canary_kings_slides
            slides = build_canary_kings_slides(data["men"], data["women"])
        elif template_name == "athlete_rise":
            from pipeline.athlete_rise_carousel import build_athlete_rise_slides
            slides = build_athlete_rise_slides(data)
        else:
            from pipeline.carousel import build_slides
            slides = build_slides(data)
        for slide in slides:
            html = render_template(f"carousel/slide_{slide['type']}", slide)
            html = html.replace("<body>", '<body style="zoom: 0.5;">')
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
        html = html.replace("<body>", '<body style="zoom: 0.5;">')
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
        if template_name in ("coming_soon_carousel", "about_carousel"):
            from pipeline.renderer import render_to_png
            slides = data["slides"]
            result_paths = []
            os.makedirs(carousel_dir, exist_ok=True)
            prefix = template_name.replace("_carousel", "")
            for i, slide in enumerate(slides, 1):
                html = render_template(f"carousel/slide_{slide['type']}", slide)
                output_path = os.path.join(carousel_dir, f"{prefix}_{timestamp}_{i}.png")
                render_to_png(html, output_path, width=width, height=height, dpr=dpr)
                result_paths.append(output_path)
        elif template_name == "h2h_carousel":
            result_paths = render_h2h_carousel(
                data, carousel_dir,
                base_name=f"h2h_carousel_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        elif template_name == "rider_profile":
            result_paths = render_rp_carousel(
                data, carousel_dir,
                base_name=f"rider_profile_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        elif template_name == "canary_kings":
            result_paths = render_analysis_carousel(
                data["men"], data["women"], carousel_dir,
                base_name=f"canary_kings_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        elif template_name == "athlete_rise":
            result_paths = render_athlete_rise_carousel(
                data, carousel_dir,
                base_name=f"athlete_rise_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        else:
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
