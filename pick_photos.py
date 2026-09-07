"""Pick athlete photos for a post from the PWA Drive, by eye.

Builds a contact sheet of *every* candidate frame for each rider, shown as the
1080x1350 slide it would become, and serves it on localhost so that clicking
Save writes the photos and the json straight into the repo.

    python pick_photos.py --event 124 --score-type Wave --sex Women
    python pick_photos.py --event 122 --athletes 49,68,97,19

Why a browser and not a model choosing: scanning fifty thumbnails is a
three-second job for a person and an expensive, error-prone one for a model,
which is how the first Tenerife and Gran Canaria posts ended up with photos
picked out of an arbitrary sample of six.
"""

import argparse
import glob
import json
import mimetypes
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pipeline import post_flow
from pipeline.api import fetch_event, fetch_event_top_scores
from pipeline.helpers import ordinal
from pipeline.photo_picker import (
    cheapest_copies,
    credit_for,
    find_year_root,
    install_photo,
    match_event_folder,
    matches_token,
    merge_json_entry,
    sail_tokens,
    thumbnail_for,
)
from pipeline.photo_sheet import render_sheet

PHOTOS_DIR = Path("assets/photos")
CACHE_DIR = Path(".cache/photo_picker")
REPO_ROOT = Path(__file__).resolve().parent
BACKLOG = str(REPO_ROOT / "content_backlog.yaml")

FOCUS_COMMENT = ("object-position per athlete, set from the picker's crop slider. "
                 "A landscape frame keeps its full height at 1080x1350 and loses "
                 "about half its width, so the X value is what matters.")
CREDITS_COMMENT = ("Photographer per photo, resolved from the filename then the "
                   "file's own XMP. Entries marked unconfirmed carry no credit "
                   "tag anywhere: confirm before crediting them.")


def _athlete_index(event_id, sex):
    """athlete_id -> API record, for sail numbers and countries."""
    import requests

    from pipeline.api import API_BASE_URL
    params = {"sex": sex} if sex else {}
    resp = requests.get(f"{API_BASE_URL}/events/{event_id}/athletes",
                        params=params, timeout=30)
    resp.raise_for_status()
    return {a["athlete_id"]: a for a in resp.json().get("athletes", [])}


def _db_sails(athlete_ids) -> dict:
    """athlete_id -> {sail_number, country} read from the results table.

    The API only rosters the disciplines it covers, which at Sylt is the wave
    event: none of the historic slalom fleet is in it, so every one of them
    came back without a sail and matched no frame. The results table has
    them, keyed through ATHLETE_SOURCE_IDS.

    Most-used sail per rider, not the latest. A sail changes hands and a
    rider's own number changes over a career; the one they raced under most
    is the one most of the archive is filed under.
    """
    if not athlete_ids:
        return {}
    from pipeline.db import run_query

    holes = ", ".join(["%s"] * len(athlete_ids))
    rows = run_query(f"""
        SELECT asi.athlete_id AS aid,
               r.sail_number  AS sail,
               a.nationality  AS country,
               COUNT(*)       AS n
        FROM PWA_IWT_RESULTS r
        JOIN ATHLETE_SOURCE_IDS asi
          ON asi.source = 'PWA' AND asi.source_id = r.athlete_id
        LEFT JOIN ATHLETES a ON a.id = asi.athlete_id
        WHERE asi.athlete_id IN ({holes})
          AND r.sail_number IS NOT NULL AND r.sail_number <> ''
        GROUP BY asi.athlete_id, r.sail_number, a.nationality
        ORDER BY aid, n DESC
    """, tuple(athlete_ids))

    # The country is only here to expand the sail token: "F-465" has to reach
    # FRA465, which is how every one of Nicolas Goyard's frames is filed. The
    # same riders missing a nationality in ATHLETES are the ones the slide
    # overrides, so read it from there rather than leaving the token short.
    from pipeline.sylt_kings import NATIONALITY_OVERRIDES

    best = {}
    for row in rows:
        best.setdefault(row["aid"], {
            "sail_number": row["sail"],
            "country": (row["country"]
                        or NATIONALITY_OVERRIDES.get(row["aid"], "")),
        })
    return best


def _event_dir(event_id):
    """The Drive folder holding this event's photos, plus its name and year."""
    event = fetch_event(event_id)
    name = event.get("event_name") or event.get("name") or ""
    year = (event.get("date_start") or "")[:4] or event.get("year")
    if not year:
        return None, name, year

    root = find_year_root(year)
    if not root:
        return None, name, year

    folders = [p.name for p in root.iterdir() if p.is_dir()]
    match = match_event_folder(name, folders)
    return (root / match if match else None), name, year


def _riders_from_scores(event_id, score_type, sex, top):
    """The riders behind the top N scores, in slide order, deduped."""
    data = fetch_event_top_scores(event_id=event_id, score_type=score_type, sex=sex)
    metric = data["title_metric"][:-1].upper()
    seen, riders = set(), []
    for entry in data["entries"][:top]:
        aid = entry.get("athlete_id")
        if aid is None or aid in seen:
            continue
        seen.add(aid)
        riders.append({
            "athlete_id": aid,
            "name": entry["athlete"],
            "score": entry["score"],
            "rank_label": ordinal(entry["rank"]).upper(),
            "metric": metric,
        })
    return riders


def _collect(riders, event_dir, index):
    """Attach every candidate frame, cheapest copy of each, to each rider."""
    all_files = glob.glob(os.path.join(str(event_dir), "**", "*.jpg"), recursive=True)
    print(f"  scanning {len(all_files)} files in {event_dir.name}")

    for rider in riders:
        record = index.get(rider["athlete_id"], {})
        sail = record.get("sail_number") or ""
        tokens = sail_tokens(sail, record.get("country", ""))
        rider["sail"] = sail or "unknown"
        rider["tokens"] = tokens or ["-"]

        hits = [f for f in all_files
                if any(matches_token(f, t) for t in tokens)] if tokens else []
        rider["candidates"] = []
        for path in cheapest_copies(hits):
            parts = path.name.split("_")
            rider["candidates"].append({
                "path": str(path),
                "name": path.name,
                "kind": parts[1] if len(parts) > 1 else "",
                "credit": credit_for(path),
                "score_label": f"{rider['score']:.2f}",
            })
        # Action shots first: a leaderboard slide wants the rider on the water.
        rider["candidates"].sort(key=lambda c: (c["kind"] != "wv", c["name"]))
    return riders


def _build_thumbs(riders):
    total = sum(len(r["candidates"]) for r in riders)
    done = 0
    for rider in riders:
        for cand in rider["candidates"]:
            thumb = thumbnail_for(cand["path"], CACHE_DIR)
            cand["thumb"] = thumb.name
            done += 1
            if done % 10 == 0 or done == total:
                print(f"  thumbnails {done}/{total}", end="\r", flush=True)
    print()


# The square headshot the summary table sets in a circle. 640px matches what
# the existing faces are stored at.
FACE_PX = 640


def _install(selection, event_id, faces: bool = False):
    """Write the chosen frames and their json into the repo.

    ``faces`` installs athlete-level square headshots into ``faces/`` instead
    of an event folder. A headshot is timeless, so it is not event-keyed, and
    the table slide reads it from there for every post.
    """
    event_dir = (PHOTOS_DIR / "faces" if faces
                 else PHOTOS_DIR / "events" / str(event_id))
    installed = []
    for athlete_id, choice in selection.items():
        src = Path(choice["file"])
        dest = install_photo(src, event_dir, athlete_id,
                             square=FACE_PX if faces else 0)
        if not faces:
            # object-position only means something on a full-bleed hero. A
            # square crop of a square file has no slack to shift.
            merge_json_entry(event_dir / "focus.json", athlete_id,
                             choice.get("focus", "50% 50%"),
                             comment=FOCUS_COMMENT)

        credit = credit_for(src)
        entry = {"photographer": credit["photographer"], "handle": credit["handle"],
                 "source_file": credit["source_file"]}
        if not credit["confirmed"]:
            entry["note"] = "UNTAGGED - credit unconfirmed"
        merge_json_entry(event_dir / "credits.json", athlete_id, entry,
                         comment=CREDITS_COMMENT)
        installed.append(f"{athlete_id} <- {src.name}")
        print(f"  installed {dest} ({dest.stat().st_size // 1024}KB) "
              f"from {src.name}")
    return installed


def generation_plan(event_id, score_type, sex, athletes_mode: bool):
    """What post to build once the photos are in, or None if there isn't one.

    ``--athletes`` names riders directly rather than coming from a leaderboard,
    so there is no top-10 post to generate from it. That mode is for topping up
    the photo library, and it should say so rather than fail.
    """
    if athletes_mode:
        return None
    return {"event_id": event_id, "score_type": score_type, "sex": sex}


def generate_post(event_id, score_type, sex, event_name="", year=None):
    """Build the photo-variant carousel for this event, for review in the page.

    The slides used to open as a browser tab each, which is eight tabs and no
    way to write a caption while looking at them. They come back as HTML now and
    the page shows them inline.
    """
    return post_flow.review_payload(
        {"event_id": event_id, "score_type": score_type, "sex": sex},
        event_name, year,
    )


def generate_after_save(plan, installed, event_name="", year=None):
    """Build the post, reporting rather than raising.

    The photos are already written by the time this runs, so a failure here must
    never read as though the picking was lost. Whatever happens, the caller gets
    the list of what was installed back.
    """
    if not plan:
        return {"ok": True, "skipped": True, "installed": installed,
                "message": "Photos installed. No post to build for --athletes."}
    try:
        post = generate_post(event_name=event_name, year=year, **plan)
    except Exception as exc:
        return {"ok": False, "installed": installed,
                "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "skipped": False, "installed": installed,
            "slides": len(post["slides"]), "post": post}


def _serve(html, riders, event_id, plan=None, meta=None, faces=False):
    """Serve the flow: pick, install, review, caption, schedule, save, stop.

    The server stays up past the photo install now, because the page still
    needs it: it serves the slide photographs, answers backlog id lookups, and
    takes the finished entry. It stops when the entry is written, or when there
    was no post to write one for.
    """
    done = threading.Event()
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # the CLI prints what matters; access logs only add noise

        def _send(self, body, content_type):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload):
            self._send(json.dumps(payload).encode("utf-8"), "application/json")

        def do_GET(self):
            route = urlparse(self.path)
            if route.path.startswith("/thumbs/"):
                path = CACHE_DIR / os.path.basename(route.path)
                if not path.exists():
                    self.send_error(404)
                    return
                self._send(path.read_bytes(), "image/jpeg")
                return

            # Slide photos. The page is served over http, so the slides' own
            # file:/// urls are blocked by the browser; post_flow rewrites them
            # to here. Confined to the repo, which is where every one of them
            # lives -- this is a localhost tool, not a file server.
            if route.path == "/local":
                wanted = parse_qs(route.query).get("p", [""])[0]
                try:
                    path = Path(wanted).resolve()
                    path.relative_to(REPO_ROOT)
                except (ValueError, OSError):
                    self.send_error(403)
                    return
                if not path.is_file():
                    self.send_error(404)
                    return
                self._send(path.read_bytes(),
                           mimetypes.guess_type(path.name)[0]
                           or "application/octet-stream")
                return

            if route.path == "/lookup":
                post_id = parse_qs(route.query).get("id", [""])[0]
                self._send_json(post_flow.lookup(BACKLOG, post_id))
                return

            self._send(html.encode("utf-8"), "text/html; charset=utf-8")

        def _payload(self):
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length) or b"{}")

        def do_POST(self):
            route = urlparse(self.path).path
            if route == "/backlog":
                self._send_json(self._save_backlog())
                return

            try:
                print()
                installed = _install(self._payload(), event_id, faces=faces)
                result["installed"] = installed
                # Building the post runs after the photos are safely written,
                # and reports rather than raising: a failure here must not read
                # as though the picking was lost.
                print("\nBuilding the post...")
                outcome = generate_after_save(plan, installed, **(meta or {}))
                body = {**outcome, "installed": installed}
                if not outcome["ok"]:
                    print(f"  build failed: {outcome['error']}")
                    print("  the photos are installed and safe")
                else:
                    result["credits"] = outcome.get("post", {}).get("credits", [])
                    print("  post built. Caption and time are in the browser.")
            except Exception as exc:                      # surfaced in the page
                body = {"ok": False, "error": str(exc)}
                result["error"] = str(exc)
            self._send_json(body)
            # There is nothing to caption or schedule without a post, so a run
            # that cannot build one ends here, as it always did.
            if not body.get("ok") or body.get("skipped"):
                done.set()

        def _save_backlog(self):
            try:
                entry = self._payload()
                saved = post_flow.save_to_backlog(
                    BACKLOG, entry, result.get("credits") or [])
            except Exception as exc:
                print(f"  backlog write failed: {exc}")
                return {"ok": False, "error": str(exc)}

            result["backlog"] = saved
            print(f"\n  {saved['action']} {saved['id']} "
                  f"@ {saved['scheduled_date']}Z in {BACKLOG}")
            if saved["credits_restored"]:
                print("  credit line restored: "
                      + ", ".join(saved["credits_restored"]))
            if saved["was_published"]:
                print("  WARNING: that id has already published; the poller "
                      "skips published posts, so re-dating it publishes nothing")
            if saved["time_warning"]:
                print(f"  {saved['time_warning']}")
            done.set()
            return {"ok": True, **saved}

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"\nSheet: {url}")
    webbrowser.open(url)
    print("Pick a frame per rider and hit Save, then read the post, write the "
          "caption and set a time.")
    print("Ctrl-C at any point leaves everything as it is.")
    try:
        done.wait()
    except KeyboardInterrupt:
        print("\nStopped.")
    server.shutdown()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", type=int, required=True, help="API event id")
    parser.add_argument("--faces", action="store_true",
                        help="Install square headshots into assets/photos/faces/ "
                             "instead of an event folder")
    parser.add_argument("--folder",
                        help="Photo folder to read instead of the Drive lookup, "
                             "e.g. a PWA archive directory like '2018 Sylt'")
    parser.add_argument("--athletes", help="Comma-separated athlete ids")
    parser.add_argument("--score-type", choices=["Wave", "Jump"], default="Wave")
    parser.add_argument("--sex", choices=["Men", "Women"])
    parser.add_argument("--top", type=int, default=5,
                        help="How many top scores to source riders for (default 5)")
    parser.add_argument("--drive-root", help="Override the PWA Drive location")
    args = parser.parse_args()

    if args.drive_root:
        os.environ["PWA_DRIVE_ROOT"] = args.drive_root

    if args.folder:
        # The archive is flat -- "2018 Sylt", "Sylt Archive Individual Riders"
        # -- so find_year_root, which wants {root}/{year}/{event}, resolves
        # none of it. Naming the folder skips the lookup entirely.
        event_dir = Path(args.folder)
        if not event_dir.is_dir():
            print(f"No such folder: {event_dir}")
            sys.exit(1)
        event_name, year = event_dir.name, None
    else:
        event_dir, event_name, year = _event_dir(args.event)
        if not event_dir:
            print(f"No Drive folder found for event {args.event} ({event_name!r}).")
            print("Check the season shortcut is in My Drive, or pass --drive-root.")
            sys.exit(1)
    print(f"Event: {event_name}\nPhotos: {event_dir}")

    try:
        index = _athlete_index(args.event, args.sex)
    except Exception as exc:
        # A folder named directly does not need the event to roster anyone.
        print(f"  no API roster ({type(exc).__name__}); falling back to the DB")
        index = {}
    if args.athletes:
        wanted = [int(x) for x in args.athletes.split(",")]
        gaps = [a for a in wanted if not index.get(a, {}).get("sail_number")]
        if gaps:
            found = _db_sails(gaps)
            print(f"  {len(found)}/{len(gaps)} sails from the DB "
                  f"(not in the API roster)")
            for aid, rec in found.items():
                index[aid] = {**index.get(aid, {}), **rec}
        riders = [{"athlete_id": a, "name": index.get(a, {}).get("name", str(a)),
                   "score": 0.0, "rank_label": "", "metric": args.score_type.upper()}
                  for a in wanted]
    else:
        riders = _riders_from_scores(args.event, args.score_type, args.sex, args.top)

    _collect(riders, event_dir, index)
    for rider in riders:
        print(f"  {rider['name']:26} sail {rider['sail']:8} "
              f"{len(rider['candidates']):3} frames")

    if not any(r["candidates"] for r in riders):
        print("\nNo candidates for anyone. Check the sail numbers above.")
        sys.exit(1)

    print("\nBuilding thumbnails (first run on an event is the slow one)...")
    _build_thumbs(riders)

    label = f"{event_name} {args.sex or ''} {args.score_type}s".strip()
    plan = generation_plan(args.event, args.score_type, args.sex,
                           athletes_mode=bool(args.athletes))
    _serve(render_sheet(riders, label), riders, args.event, plan,
           meta={"event_name": event_name, "year": year}, faces=args.faces)


if __name__ == "__main__":
    main()
