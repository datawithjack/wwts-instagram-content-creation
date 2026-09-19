"""Publish the headshots approved in #32 to the stats site (#33).

    python upload_headshots.py --event 126                  # dry run: prints the plan
    python upload_headshots.py --event 126 --apply          # uploads + updates
    python upload_headshots.py --rollback data/headshots/rollback-event-126-<ts>.json [--apply]

Dry run by default. ``--apply`` for each approved rider:

1. uploads ``assets/photos/faces/{id}.jpg`` unchanged (credit already in its
   EXIF) to R2 as ``athlete-photos/{id}_{ts}.jpg``;
2. fetches it back from ``img.windsurfworldtourstats.com`` and stops if it is
   not a 200 JPEG -- a row is never pointed at a URL that does not load;
3. sets ``ATHLETES.liveheats_image_url`` by primary key, compare-and-set on the
   value seen at planning time, so a row changed meanwhile is left alone.

Every old value is written to a rollback file BEFORE the first write. The
database is production -- there is no other copy.
"""

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

from pipeline.db import get_connection, run_query
from pipeline.headshot_publish import plan_changes, plan_rollback
from pipeline.photo_picker import merge_json_entry
from pipeline.publisher import _get_r2_client

REPO_ROOT = Path(__file__).resolve().parent
MANIFEST_DIR = REPO_ROOT / "data" / "headshots"
# Cloudflare answers a default python-requests User-Agent with a 403.
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) wwts-headshots"}


def _current(athlete_ids):
    if not athlete_ids:
        return {}
    marks = ",".join(["%s"] * len(athlete_ids))
    rows = run_query(f"SELECT id, liveheats_image_url FROM ATHLETES WHERE id IN ({marks})",
                     tuple(athlete_ids))
    return {r["id"]: r["liveheats_image_url"] for r in rows}


def _show(plan):
    for p in plan:
        who = f"{p['athlete_id']:>5} {p.get('name', '')[:24]:<24}"
        if p["op"] in ("publish", "update"):
            print(f"  {p['op']:<8} {who} {p['old']!r} -> {p['new']!r}")
        else:
            print(f"  {p['op']:<8} {who} {p.get('reason', '')}")
    counts = {}
    for p in plan:
        counts[p["op"]] = counts.get(p["op"], 0) + 1
    print("  " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))


def _probe(url):
    resp = requests.get(url, headers=BROWSER_UA, timeout=30)
    ctype = resp.headers.get("Content-Type", "")
    if resp.status_code != 200 or not ctype.startswith("image/jpeg"):
        raise RuntimeError(f"{url} answered {resp.status_code} {ctype!r}")
    return len(resp.content)


def _update(cursor, step):
    cursor.execute(
        "UPDATE ATHLETES SET liveheats_image_url = %s "
        "WHERE id = %s AND liveheats_image_url <=> %s",
        (step["new"], step["athlete_id"], step["old"]))
    if cursor.rowcount != 1:
        raise RuntimeError(f"athlete {step['athlete_id']}: row changed since planning, "
                           f"not written")


def publish(event_id, apply, force):
    manifest_path = MANIFEST_DIR / f"event-{event_id}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids = [int(k) for k in manifest if not k.startswith("_")]
    now = int(time.time())
    plan = plan_changes(manifest, _current(ids), now, force=force)
    print(f"Plan for {manifest_path.relative_to(REPO_ROOT)}:")
    _show(plan)

    writes = [p for p in plan if p["op"] in ("publish", "update")]
    if not apply or not writes:
        print("\nDry run - nothing written." if not apply else "\nNothing to write.")
        return 0

    missing = [p["file"] for p in writes if p["op"] == "publish"
               and not (REPO_ROOT / p["file"]).is_file()]
    if missing:
        print(f"Missing files, nothing written: {missing}")
        return 1

    rollback = MANIFEST_DIR / f"rollback-event-{event_id}-{now}.json"
    rollback.write_text(json.dumps(
        [{"athlete_id": p["athlete_id"], "name": p.get("name", ""),
          "old": p["old"], "new": p["new"]} for p in writes], indent=2) + "\n",
        encoding="utf-8")
    print(f"\nRollback file: {rollback.relative_to(REPO_ROOT)}")

    import os
    bucket = os.environ["R2_BUCKET_NAME"]
    client = _get_r2_client()
    conn = get_connection()
    cursor = conn.cursor()
    done = 0
    try:
        for p in writes:
            if p["op"] == "publish":
                client.put_object(Bucket=bucket, Key=p["key"],
                                  Body=(REPO_ROOT / p["file"]).read_bytes(),
                                  ContentType="image/jpeg",
                                  CacheControl="public, max-age=31536000, immutable")
                size = _probe(p["new"])
            _update(cursor, p)
            conn.commit()
            done += 1
            if p["op"] == "publish":
                merge_json_entry(manifest_path, str(p["athlete_id"]),
                                 {**manifest[str(p["athlete_id"])],
                                  "published_url": p["new"],
                                  "published": date.today().isoformat()})
                print(f"  published {p['athlete_id']:>5} {p.get('name', '')[:24]:<24} "
                      f"{size // 1024}KB")
            else:
                print(f"  updated   {p['athlete_id']:>5} {p.get('name', '')[:24]}")
    except Exception as exc:
        conn.rollback()
        print(f"\nSTOPPED after {done} of {len(writes)}: {exc}")
        print(f"Undo what was written: python upload_headshots.py --rollback "
              f"{rollback.relative_to(REPO_ROOT).as_posix()} --apply")
        return 1
    finally:
        cursor.close()
        conn.close()
    print(f"\n{done} of {len(writes)} written.")
    return 0


def undo(path, apply):
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    plan = plan_rollback(records, _current([r["athlete_id"] for r in records]))
    print(f"Rollback plan from {path}:")
    _show(plan)
    writes = [p for p in plan if p["op"] == "update"]
    if not apply or not writes:
        print("\nDry run - nothing written." if not apply else "\nNothing to write.")
        return 0
    conn = get_connection()
    cursor = conn.cursor()
    try:
        for p in writes:
            _update(cursor, p)
            conn.commit()
            print(f"  restored {p['athlete_id']}")
    finally:
        cursor.close()
        conn.close()
    print("R2 objects are left in place; nothing points at them any more.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--event", type=int, help="stats-app event id of the manifest")
    group.add_argument("--rollback", help="a rollback file written by --apply")
    parser.add_argument("--apply", action="store_true", help="write; default is a dry run")
    parser.add_argument("--force", action="store_true",
                        help="replace real LiveHeats/Cloudinary photos too")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
    if args.rollback:
        return undo(args.rollback, args.apply)
    return publish(args.event, args.apply, args.force)


if __name__ == "__main__":
    sys.exit(main())
