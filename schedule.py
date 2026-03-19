"""CLI for batch-rendering and scheduling content from the calendar."""
import argparse
import os
import sys
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

load_dotenv()

from pipeline.scheduler import (
    load_calendar,
    filter_posts,
    filter_posts_due,
    run_calendar,
    run_poll,
    sort_by_scheduled_date,
    validate_scheduled_dates,
)


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
        choices=["now", "schedule", "poll"],
        help="Publish mode: 'now', 'schedule', or 'poll' (cron-based backlog polling)",
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

    # Poll mode — find due posts in backlog and publish them
    if args.publish == "poll":
        if args.dry_run:
            now = datetime.now(timezone.utc)
            calendar = load_calendar(args.calendar)
            due = filter_posts_due(calendar.get("posts", []))
            print(f"\nCurrent UTC: {now.isoformat()}")
            print(f"{len(due)} post(s) due:")
            for p in due:
                print(f"  - {p.get('id')} @ {p.get('scheduled_date')}")
            print("\nDry run — nothing rendered or published.")
            return
        results = run_poll(args.calendar)
        ok = [r for r in results if "error" not in r]
        failed = [r for r in results if "error" in r]
        print(f"\nDone: {len(ok)} published, {len(failed)} failed")
        for f in failed:
            print(f"  FAILED: {f['id']} — {f['error']}")
        return

    if args.dry_run:
        print("\nDry run — nothing rendered or published.")
        return

    # Handle scheduling
    schedule_time = None
    if args.publish == "schedule":
        if args.schedule_start:
            # Legacy mode: CLI --schedule-start with interval spacing
            base_time = datetime.fromisoformat(args.schedule_start).replace(
                tzinfo=timezone.utc
            )
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
            # Per-post scheduled_date mode
            has_dates = [p for p in posts if p.get("scheduled_date")]
            no_dates = [p for p in posts if not p.get("scheduled_date")]
            if not has_dates:
                print("No posts have scheduled_date and --schedule-start not provided.")
                print("Add scheduled_date to posts or use --schedule-start.")
                sys.exit(1)
            if no_dates:
                print(f"\nSkipping {len(no_dates)} post(s) without scheduled_date:")
                for p in no_dates:
                    print(f"  - {p.get('id', p['template'])}")

            validate_scheduled_dates(has_dates)
            posts = sort_by_scheduled_date(has_dates)

            print(f"\nScheduling {len(posts)} post(s) using per-post dates:")
            for p in posts:
                print(f"  - {p.get('id')} @ {p['scheduled_date']}")

            results = run_calendar(posts, publish_mode="schedule", output_dir=args.output)
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
