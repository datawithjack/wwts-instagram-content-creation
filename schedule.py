"""CLI for batch-rendering and scheduling content from the calendar."""
import argparse
import os
import sys
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

load_dotenv()

from pipeline.scheduler import load_calendar, filter_posts, run_calendar


def main():
    parser = argparse.ArgumentParser(
        description="Batch render/publish content from the calendar"
    )
    parser.add_argument(
        "--calendar",
        default="content_calendar.yaml",
        help="Path to content calendar YAML (default: content_calendar.yaml)",
    )
    parser.add_argument(
        "--category",
        choices=["evergreen", "seasonal", "recurring"],
        help="Filter posts by category",
    )
    parser.add_argument("--template", help="Filter posts by template name")
    parser.add_argument(
        "--ids",
        nargs="+",
        help="Run specific post IDs (space-separated)",
    )
    parser.add_argument(
        "--publish",
        choices=["now", "schedule"],
        help="Publish mode: 'now' or 'schedule'",
    )
    parser.add_argument(
        "--schedule-start",
        help="Start datetime for scheduling (ISO format, e.g. 2026-04-01T09:00)",
    )
    parser.add_argument(
        "--schedule-interval",
        type=int,
        default=24,
        help="Hours between scheduled posts (default: 24)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List posts without rendering")
    parser.add_argument("--output", help="Override output directory")

    args = parser.parse_args()

    # Load and filter calendar
    calendar = load_calendar(args.calendar)
    posts = filter_posts(
        calendar["posts"],
        category=args.category,
        template=args.template,
        ids=args.ids,
    )

    if not posts:
        print("No posts match the given filters.")
        sys.exit(1)

    print(f"Found {len(posts)} post(s):")
    for p in posts:
        print(f"  - {p.get('id', p['template'])} [{p.get('category', '?')}]")

    if args.dry_run:
        print("\nDry run — nothing rendered or published.")
        return

    # Handle scheduling
    schedule_time = None
    if args.publish == "schedule":
        if not args.schedule_start:
            print("--schedule-start is required when using --publish schedule")
            sys.exit(1)
        base_time = datetime.fromisoformat(args.schedule_start).replace(
            tzinfo=timezone.utc
        )
        # Each post gets scheduled at base_time + (index * interval)
        interval = timedelta(hours=args.schedule_interval)
        print(f"\nScheduling {len(posts)} posts starting {base_time.isoformat()}")
        print(f"  Interval: every {args.schedule_interval}h")

        results = []
        for i, post in enumerate(posts):
            post_time = base_time + (interval * i)
            print(f"\n  [{i+1}/{len(posts)}] {post.get('id')} @ {post_time.isoformat()}")
            batch = run_calendar([post], publish_mode="schedule", schedule_time=post_time, output_dir=args.output)
            results.extend(batch)
    else:
        print(f"\nPublish mode: {args.publish or 'render only'}")
        results = run_calendar(posts, publish_mode=args.publish, output_dir=args.output)

    # Summary
    ok = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]
    print(f"\nDone: {len(ok)} succeeded, {len(failed)} failed")
    for f in failed:
        print(f"  FAILED: {f['id']} — {f['error']}")


if __name__ == "__main__":
    main()
