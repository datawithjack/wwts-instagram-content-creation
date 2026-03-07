"""Main entry point for Instagram content generation pipeline."""
import argparse
import os
import sys
import webbrowser
import tempfile
from datetime import datetime

import yaml

from pipeline.templates import render_template, get_dummy_data
from pipeline.renderer import render_to_png, render_to_video


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="WWT Instagram content generator")
    parser.add_argument(
        "--template",
        required=True,
        choices=["head_to_head", "head_to_head_jump", "top_10", "site_stats", "site_stats_reel", "stat_of_the_day"],
    )
    parser.add_argument("--athlete1", help="Athlete 1 name slug")
    parser.add_argument("--athlete2", help="Athlete 2 name slug")
    parser.add_argument("--event", help="Event name slug")
    parser.add_argument("--discipline", choices=["mens", "womens"])
    parser.add_argument("--year", type=int)
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
        # TODO: Wire up DB queries
        print("DB mode not yet implemented. Use --dry-run for testing.")
        sys.exit(1)

    # Render HTML
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

    if args.video:
        if args.output:
            output_path = args.output
        else:
            output_path = os.path.join(output_dir, "mp4", f"{template_name}_{timestamp}.mp4")
        result = render_to_video(
            html, output_path, width=width, height=height, dpr=dpr,
            duration_ms=args.duration,
        )
    else:
        if args.output:
            output_path = args.output
        else:
            output_path = os.path.join(output_dir, "png", f"{template_name}_{timestamp}.png")
        result = render_to_png(html, output_path, width=width, height=height, dpr=dpr)

    print(f"Rendered: {result}")


if __name__ == "__main__":
    main()
