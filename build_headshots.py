"""Build square headshots for a start list's riders from the PWA Drive (#32).

    python build_headshots.py --event 126 --first-results-event 378

For every rider on the start list without a real photo on the stats site, find
their lifestyle frames, propose a face crop, and serve a contact sheet. Nothing
is chosen for you: each rider starts on "keep as is", and Save writes only what
you picked -- ``assets/photos/faces/{id}.jpg``, ``faces/credits.json`` and the
decision manifest ``data/headshots/event-{id}.json``. Publishing to the site is
``#33``, not this.

A frame is matched on the sail its rider held AT the frame's own event, taken
from that event's results -- never on today's sail (stats-app #230). Riders are
tried at ``--first-results-event`` first, then at their other events from
``--since`` onwards, newest first, stopping at the first event with frames.
"""

import argparse
import json
import os
import threading
import webbrowser
from collections import Counter
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from pipeline.db import run_query
from pipeline.headshots import (
    frames_for,
    holders_by_token,
    parse_frame,
    rank_frames,
    render_headshot,
    square_box,
)
from pipeline.photo_picker import (
    credit_for,
    find_year_root,
    match_event_folder,
    merge_json_entry,
    thumbnail_for,
)

REPO_ROOT = Path(__file__).resolve().parent
FACES_DIR = REPO_ROOT / "assets" / "photos" / "faces"
CACHE_DIR = REPO_ROOT / ".cache" / "headshots"
MANIFEST_DIR = REPO_ROOT / "data" / "headshots"

SHEET_PX = 1000    # what the face detector and the sheet see
RENDER_PX = 2400   # what the 640 headshot is cut from
GUESS_URL = "https://www.pwaworldtour.com/profile_images/{}.jpg"
# Worst-covered fleet first: slalom foil had 0 of 34 real photos.
DISCIPLINE_ORDER = {"slalom_foil": 0, "slalom_x": 1, "freestyle": 2, "wave": 3}

CREDITS_COMMENT = ("Photographer per headshot, resolved from the filename then the "
                   "file's own XMP. Entries marked unconfirmed carry no credit tag "
                   "anywhere: confirm before crediting them.")
MANIFEST_COMMENT = ("Headshot decisions per athlete id (#32). approve = "
                    "faces/{id}.jpg is the photo to publish; suppress = the site's "
                    "sail-number guess is the wrong person and should be hidden. "
                    "Published by #33.")


# --------------------------------------------------------------------- data

def _targets(event_id, only):
    rows = run_query(
        """SELECT a.id, a.primary_name AS name, a.nationality,
                  a.pwa_sail_number AS sail, a.liveheats_image_url AS stored_url,
                  GROUP_CONCAT(DISTINCT s.discipline ORDER BY s.discipline) AS disciplines
           FROM FANTASY_START_LISTS s JOIN ATHLETES a ON a.id = s.athlete_id
           WHERE s.event_id = %s
           GROUP BY a.id, a.primary_name, a.nationality, a.pwa_sail_number,
                    a.liveheats_image_url""", (event_id,))
    riders = []
    for r in rows:
        if only and r["id"] not in only:
            continue
        if not only and r["stored_url"]:
            continue  # a real LiveHeats / Cloudinary / R2 photo: not ours to replace
        if r["stored_url"] == "":
            current = ""                      # already suppressed
        elif r["sail"] and r["sail"] not in ("", "??"):
            current = GUESS_URL.format(r["sail"])
        else:
            current = ""
        discs = (r["disciplines"] or "").split(",")
        riders.append({
            "athlete_id": r["id"], "name": r["name"], "sail": r["sail"] or "",
            "disciplines": discs, "current": current, "stored": r["stored_url"],
            "order": min(DISCIPLINE_ORDER.get(d, 9) for d in discs),
        })
    riders.sort(key=lambda r: (r["order"], r["name"]))
    return riders


def _rider_events(athlete_ids, since):
    """athlete_id -> [(event_id, event_name, year)] from PWA results.

    Both sides pinned to source 'PWA': a LiveHeats athlete id can collide
    numerically with a PWA one, and that collision would be a wrong face.
    """
    if not athlete_ids:
        return {}
    marks = ",".join(["%s"] * len(athlete_ids))
    rows = run_query(
        f"""SELECT DISTINCT x.athlete_id, r.event_id, r.event_name, r.year
            FROM PWA_IWT_RESULTS r
            JOIN ATHLETE_SOURCE_IDS x ON x.source_id = r.athlete_id AND x.source = 'PWA'
            WHERE r.source = 'PWA' AND r.year >= %s AND x.athlete_id IN ({marks})""",
        (since, *athlete_ids))
    out = {}
    for r in rows:
        out.setdefault(r["athlete_id"], []).append(
            (r["event_id"], r["event_name"], int(r["year"])))
    return out


_holders_cache = {}


def _holders(event_id):
    """Sail token -> athlete id for one event, from its own results.

    Unlinked result rows stay in as ``pwa:<id>`` so their sail still counts as
    taken: dropping them could make someone else's claim on it look unique.
    """
    if event_id not in _holders_cache:
        rows = run_query(
            """SELECT COALESCE(x.athlete_id, CONCAT('pwa:', r.athlete_id)) AS who,
                      r.sail_number, a.nationality
               FROM PWA_IWT_RESULTS r
               LEFT JOIN ATHLETE_SOURCE_IDS x
                      ON x.source_id = r.athlete_id AND x.source = 'PWA'
               LEFT JOIN ATHLETES a ON a.id = x.athlete_id
               WHERE r.event_id = %s AND r.source = 'PWA'
                 AND r.sail_number IS NOT NULL AND r.sail_number <> ''""",
            (event_id,))
        results = []
        for r in rows:
            who = r["who"]
            who = int(who) if str(who).isdigit() else who
            results.append((who, r["sail_number"], r["nationality"]))
        _holders_cache[event_id] = holders_by_token(results)
    return _holders_cache[event_id]


_listing_cache = {}


def _event_listing(event_name, year):
    """(event_dir, [(folder, filename)] of lifestyle frames, event code)."""
    key = (event_name, year)
    if key in _listing_cache:
        return _listing_cache[key]
    result = (None, [], "")
    root = find_year_root(year)
    if root:
        folders = [p.name for p in root.iterdir() if p.is_dir()]
        match = match_event_folder(event_name, folders)
        if match:
            event_dir = root / match
            print(f"  listing {event_dir.name} ...", flush=True)
            files = []
            for dirpath, _, names in os.walk(event_dir):
                rel = os.path.relpath(dirpath, event_dir)
                files.extend((rel, n) for n in names
                             if "_ls_" in n.lower() and n.lower().endswith((".jpg", ".jpeg")))
            codes = Counter(f["event_code"] for f in (parse_frame(n) for _, n in files)
                            if f and f["year"] == year)
            code = codes.most_common(1)[0][0] if codes else ""
            result = (event_dir, files, code)
    _listing_cache[key] = result
    return result


# ------------------------------------------------------------------- faces

_cascade = None


def _detect(thumb_path):
    """Largest face as (x, y, w, h), the image size, and a flag for the sheet."""
    global _cascade
    import cv2
    if _cascade is None:
        _cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    img = cv2.imread(str(thumb_path))
    height, width = img.shape[:2]
    short = min(width, height)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    found = _cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6,
                                      minSize=(int(short * 0.04),) * 2)
    faces = sorted((tuple(int(v) for v in f) for f in found),
                   key=lambda f: f[2] * f[3], reverse=True)
    if not faces:
        # Nothing found: a guess at an upper-middle head, for the owner to move.
        guess = int(short * 0.15)
        return (width // 2 - guess // 2, int(height * 0.25), guess, guess), \
            (width, height), "no face found - click the face"
    flag = ""
    big = faces[0][2] * faces[0][3]
    others = [f for f in faces[1:] if f[2] * f[3] >= big * 0.5]
    if others:
        flag = f"{len(others) + 1} faces - check it is the right one"
    return faces[0], (width, height), flag


# ------------------------------------------------------------------- build

def _candidates(rider, events, first_event, limit):
    """Frames for one rider from the first event (in preference order) with any."""
    ordered = sorted(events, key=lambda e: (e[0] != first_event, -e[2], -e[0]))
    for event_id, event_name, year in ordered:
        event_dir, files, code = _event_listing(event_name, year)
        if not event_dir or not code:
            continue
        frames = frames_for(rider["athlete_id"], files, _holders(event_id), code, year)
        if frames:
            return [(event_dir / folder / name, folder, event_id, event_name)
                    for folder, name in rank_frames(frames, limit)]
    return []


def build(riders, rider_events, first_event, limit):
    for n, rider in enumerate(riders, 1):
        print(f"[{n}/{len(riders)}] {rider['name']}", flush=True)
        rider["candidates"] = []
        existing = FACES_DIR / f"{rider['athlete_id']}.jpg"
        if existing.exists():
            rider["candidates"].append({
                "kind": "existing", "label": "already in faces/",
                "thumb": f"/faces/{existing.name}", "w": 1, "h": 1,
                "box": [0, 0, 1], "flag": "", "credit": "", "event": ""})
        for path, folder, event_id, event_name in _candidates(
                rider, rider_events.get(rider["athlete_id"], []), first_event, limit):
            thumb = thumbnail_for(path, CACHE_DIR, SHEET_PX)
            face, (w, h), flag = _detect(thumb)
            left, top, side = square_box(w, h, face)
            credit = credit_for(path)
            rider["candidates"].append({
                "kind": "frame", "path": str(path), "label": f"{folder}/{path.name}",
                "thumb": f"/thumbs/{thumb.name}", "w": w, "h": h,
                "box": [left / w, top / h, side / min(w, h)], "flag": flag,
                "credit": credit["photographer"] or "UNTAGGED",
                "credit_full": credit, "event_id": event_id, "event": event_name})
        print(f"    {len(rider['candidates'])} candidates", flush=True)
    return riders


# -------------------------------------------------------------------- save

def save(decisions, riders, event_id):
    by_id = {str(r["athlete_id"]): r for r in riders}
    manifest = MANIFEST_DIR / f"event-{event_id}.json"
    done = []
    for aid, choice in decisions.items():
        rider = by_id[str(aid)]
        entry = {"name": rider["name"], "action": choice["action"],
                 "decided": date.today().isoformat()}
        if choice["action"] == "approve":
            cand = rider["candidates"][int(choice["index"])]
            if cand["kind"] == "frame":
                work = thumbnail_for(cand["path"], CACHE_DIR, RENDER_PX)
                dest = render_headshot(work, choice["box"], FACES_DIR / f"{aid}.jpg",
                                       credit=cand["credit_full"])
                credit = cand["credit_full"]
                c_entry = {"photographer": credit["photographer"],
                           "handle": credit["handle"],
                           "source_file": credit["source_file"],
                           "confirmed": credit["confirmed"], "via": credit["via"]}
                if not credit["confirmed"]:
                    c_entry["note"] = "UNTAGGED - credit unconfirmed"
                merge_json_entry(FACES_DIR / "credits.json", str(aid), c_entry,
                                 comment=CREDITS_COMMENT)
                entry.update({"source_file": Path(cand["path"]).name,
                              "source_event_id": cand["event_id"],
                              "source_event": cand["event"],
                              "photographer": credit["photographer"]})
                done.append(f"{rider['name']}: {dest.name} "
                            f"({dest.stat().st_size // 1024}KB) from {Path(cand['path']).name}")
            else:
                entry["source_file"] = f"faces/{aid}.jpg (existing)"
                done.append(f"{rider['name']}: kept existing faces/{aid}.jpg")
        else:
            done.append(f"{rider['name']}: suppress the sail-number guess")
        merge_json_entry(manifest, str(aid), entry, comment=MANIFEST_COMMENT)
    for line in done:
        print("  " + line)
    return done


# -------------------------------------------------------------------- sheet

def _sheet(riders, event_id):
    public = [{k: v for k, v in r.items() if k != "stored"} for r in riders]
    for r in public:
        r["candidates"] = [{k: v for k, v in c.items() if k not in ("path", "credit_full")}
                           for c in r["candidates"]]
    data = json.dumps(public)
    return SHEET_HTML.replace("__DATA__", data).replace("__EVENT__", str(event_id))


def serve(riders, event_id):
    html = _sheet(riders, event_id)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, body, ctype, code=200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = urlparse(self.path).path
            for prefix, base in (("/thumbs/", CACHE_DIR), ("/faces/", FACES_DIR)):
                if route.startswith(prefix):
                    path = base / os.path.basename(route)
                    if path.is_file():
                        self._send(path.read_bytes(), "image/jpeg")
                    else:
                        self.send_error(404)
                    return
            self._send(html.encode("utf-8"), "text/html; charset=utf-8")

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            try:
                decisions = json.loads(self.rfile.read(length) or b"{}")
                body = {"ok": True, "done": save(decisions, riders, event_id)}
            except Exception as exc:                      # shown in the page
                body = {"ok": False, "error": repr(exc)}
            self._send(json.dumps(body).encode("utf-8"), "application/json")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"\nSheet: {url}\nSave as often as you like; Ctrl-C when finished.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


SHEET_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Headshots - event __EVENT__</title>
<style>
body{background:#0b1220;color:#e5e7eb;font:14px system-ui,sans-serif;margin:0;padding:16px 16px 90px}
h1{font-size:18px;margin:0 0 12px}
.rider{border-top:1px solid #1f2937;padding:14px 0}
.head{display:flex;gap:12px;align-items:center;margin-bottom:8px}
.head b{font-size:16px}.muted{color:#94a3b8;font-size:12px}
.cur{width:64px;height:64px;border-radius:50%;background:#1f2937 center/cover;flex:none;
     display:flex;align-items:center;justify-content:center;font-size:10px;color:#94a3b8;text-align:center}
.cands{display:flex;gap:12px;flex-wrap:wrap}
.cand{background:#111827;border:2px solid #1f2937;border-radius:8px;padding:8px;width:260px}
.cand.sel{border-color:#22d3ee}
.prev{width:160px;height:160px;border-radius:50%;background-repeat:no-repeat;margin:0 auto 6px}
.full{position:relative;width:260px;cursor:crosshair}
.full img{width:260px;display:block}
.box{position:absolute;border:2px solid #22d3ee;pointer-events:none}
.flag{color:#fbbf24;font-size:12px}.lbl{font-size:11px;color:#94a3b8;word-break:break-all}
.opts{display:flex;gap:14px;margin:6px 0;flex-wrap:wrap}
button{background:#1f2937;color:#e5e7eb;border:1px solid #374151;border-radius:6px;padding:2px 8px;cursor:pointer}
#bar{position:fixed;left:0;right:0;bottom:0;background:#020617;border-top:1px solid #1f2937;padding:10px 16px;display:flex;gap:12px;align-items:center}
#save{background:#0e7490;border-color:#0e7490;padding:8px 18px;font-weight:600}
#out{font-size:12px;white-space:pre-wrap;max-height:60px;overflow:auto}
</style></head><body>
<h1>Headshots for event __EVENT__ <span class="muted">- every rider starts on "keep as is"; click a face on a full frame to move the crop</span></h1>
<div id="list"></div>
<div id="bar"><button id="save">Save picked</button><span id="count" class="muted"></span><div id="out"></div></div>
<script>
const riders = __DATA__;
const state = {};           // athlete_id -> {action, index}
const list = document.getElementById('list');
const P = 160, D = 260;

function short(c){ return Math.min(c.w, c.h); }
function paint(c, prev, box){
  const s = c.box[2]*short(c), k = P/s;
  prev.style.backgroundImage = `url(${c.thumb})`;
  prev.style.backgroundSize = `${c.w*k}px ${c.h*k}px`;
  prev.style.backgroundPosition = `${-c.box[0]*c.w*k}px ${-c.box[1]*c.h*k}px`;
  if (box){ const q = D/c.w; box.style.left = c.box[0]*c.w*q+'px'; box.style.top = c.box[1]*c.h*q+'px';
    box.style.width = box.style.height = s*q+'px'; }
}
function clamp(c){
  const s = Math.min(c.box[2]*short(c), c.w, c.h);
  c.box[2] = s/short(c);
  c.box[0] = Math.max(0, Math.min(c.box[0]*c.w, c.w - s))/c.w;
  c.box[1] = Math.max(0, Math.min(c.box[1]*c.h, c.h - s))/c.h;
}
function count(){
  const n = Object.values(state).filter(v => v.action !== 'keep').length;
  document.getElementById('count').textContent = `${n} decision(s) to save`;
}
riders.forEach(r => {
  state[r.athlete_id] = {action: 'keep'};
  const el = document.createElement('div'); el.className = 'rider';
  const cur = r.current ? `<div class="cur" style="background-image:url('${r.current}')" title="current site photo (sail-number guess)"></div>`
                        : `<div class="cur">initials</div>`;
  el.innerHTML = `<div class="head">${cur}<div><b>${r.name}</b> <span class="muted">#${r.athlete_id} · ${r.disciplines.join(', ')} · sail ${r.sail||'none'}</span>
    <div class="muted">${r.candidates.length ? (r.candidates.find(c=>c.event)||{}).event||'' : 'no candidate frames'}</div></div></div>
    <div class="opts"><label><input type="radio" name="r${r.athlete_id}" value="keep" checked> keep as is</label>
    ${r.current ? `<label><input type="radio" name="r${r.athlete_id}" value="suppress"> current photo is the WRONG person - hide it</label>` : ''}</div>
    <div class="cands"></div>`;
  const cands = el.querySelector('.cands');
  r.candidates.forEach((c, i) => {
    const card = document.createElement('div'); card.className = 'cand';
    card.innerHTML = `<label><input type="radio" name="r${r.athlete_id}" value="${i}"> use this</label>
      <div class="prev"></div>
      ${c.kind === 'frame' ? `<div class="full"><img src="${c.thumb}"><div class="box"></div></div>
      <div><button data-z="0.87">zoom in</button> <button data-z="1.15">zoom out</button></div>` : ''}
      <div class="flag">${c.flag||''}</div><div class="lbl">${c.label}<br>credit: ${c.credit||'-'}</div>`;
    const prev = card.querySelector('.prev'), box = card.querySelector('.box');
    paint(c, prev, box);
    if (c.kind === 'frame'){
      card.querySelector('.full').addEventListener('click', e => {
        const rect = e.currentTarget.getBoundingClientRect(), q = D/c.w;
        const x = (e.clientX-rect.left)/q, y = (e.clientY-rect.top)/q, s = c.box[2]*short(c);
        c.box[0] = (x - s/2)/c.w; c.box[1] = (y - s*0.42)/c.h; clamp(c); paint(c, prev, box);
      });
      card.querySelectorAll('button[data-z]').forEach(b => b.addEventListener('click', () => {
        const s0 = c.box[2]*short(c), cx = c.box[0]*c.w + s0/2, cy = c.box[1]*c.h + s0/2;
        const s = s0*parseFloat(b.dataset.z);
        c.box[2] = s/short(c); c.box[0] = (cx - s/2)/c.w; c.box[1] = (cy - s/2)/c.h; clamp(c); paint(c, prev, box);
      }));
    }
    cands.appendChild(card);
  });
  el.addEventListener('change', e => {
    const v = e.target.value;
    state[r.athlete_id] = v === 'keep' || v === 'suppress' ? {action: v} : {action: 'approve', index: +v};
    el.querySelectorAll('.cand').forEach((cd, i) => cd.classList.toggle('sel', v === String(i)));
    count();
  });
  list.appendChild(el);
});
count();
document.getElementById('save').addEventListener('click', async () => {
  const out = {};
  riders.forEach(r => {
    const s = state[r.athlete_id];
    if (s.action === 'approve') out[r.athlete_id] = {action: 'approve', index: s.index, box: r.candidates[s.index].box};
    else if (s.action === 'suppress') out[r.athlete_id] = {action: 'suppress'};
  });
  const res = await fetch('/save', {method: 'POST', body: JSON.stringify(out)});
  const body = await res.json();
  document.getElementById('out').textContent = body.ok ? `Saved ${body.done.length}:\n` + body.done.join('\n') : 'FAILED: ' + body.error;
});
</script></body></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--event", type=int, required=True,
                        help="stats-app event id whose start list to cover")
    parser.add_argument("--first-results-event", type=int,
                        help="results event to try first, e.g. 378 = Sylt 2025")
    parser.add_argument("--since", type=int, default=2025,
                        help="earliest results year to fall back to (default 2025)")
    parser.add_argument("--athletes", help="comma-separated athlete ids; overrides "
                        "the no-real-photo filter")
    parser.add_argument("--limit", type=int, default=6, help="frames per rider")
    parser.add_argument("--drive-root", help="override the PWA Drive location")
    args = parser.parse_args()
    if args.drive_root:
        os.environ["PWA_DRIVE_ROOT"] = args.drive_root

    only = {int(a) for a in args.athletes.split(",")} if args.athletes else set()
    riders = _targets(args.event, only)
    print(f"{len(riders)} riders to cover")
    events = _rider_events([r["athlete_id"] for r in riders], args.since)
    build(riders, events, args.first_results_event, args.limit)

    by_disc = Counter()
    for r in riders:
        by_disc[(r["disciplines"][0], "frames" if any(
            c["kind"] == "frame" for c in r["candidates"]) else "none")] += 1
    print("\nCoverage (first discipline):")
    for (disc, kind), n in sorted(by_disc.items()):
        print(f"  {disc:<12} {kind:<7} {n}")
    serve(riders, args.event)

    manifest = MANIFEST_DIR / f"event-{args.event}.json"
    decided = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    tally = Counter()
    for r in riders:
        entry = decided.get(str(r["athlete_id"]))
        state = entry["action"] if entry else (
            "undecided" if r["candidates"] else "no candidate")
        tally[(r["disciplines"][0], state)] += 1
    print(f"\nDecisions in {manifest.relative_to(REPO_ROOT)}:")
    for (disc, state), n in sorted(tally.items()):
        print(f"  {disc:<12} {state:<13} {n}")


if __name__ == "__main__":
    main()
