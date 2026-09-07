"""Adjust the crop of installed hero photos, by eye.

Shows every rider's photo as the 1080x1350 slide it becomes, with the text
gradient on top, and lets you drag and zoom until it looks right. Save re-crops
from the original high-resolution file and installs it.

    python adjust_photos.py --event syltfreestyle --source "C:/Users/me/Downloads/sylt"
    python adjust_photos.py --event 124 --athletes 49,68

Why this exists: ``focus.json`` can only slide a photo left and right. The
slides are 4:5 and the photos are mostly 3:2, so ``object-fit: cover`` fits the
height and crops the width -- there is no vertical slack to pan into, and the
full image height is already shown, so "zoom out", "move him up" and "too much
sky" are all unreachable through an anchor. They need a new crop, which is what
Save writes.

The originals are never modified, so any rider can be re-adjusted later.
"""

import argparse
import glob
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

from pipeline.photo_adjust import crop_box

PHOTOS_DIR = Path(__file__).parent / "assets" / "photos"
# The zoom every photo opens at.
#
# Not 1.0, and this is the whole reason: at 1.0 a 3:2 photo fills the slide's
# height exactly, so there is no vertical slack and the photo can only ever
# slide sideways. Positioning and zooming are meant to be two separate moves,
# and at 1.0 the first one is half unavailable. Opening a touch inside the
# frame buys about 130px of travel up and down, at the cost of 6% of the
# height, so a view can be picked by dragging alone and the slider is only
# reached for when a shot genuinely wants to be tighter. The slider still goes
# down to 1.0 for the widest framing a photo has.
DEFAULT_ZOOM = 1.12
# The two shapes a photo is cropped to. A hero fills the slide; a headshot is
# the square thumbnail the summary table sets in a circle, and it needs the
# same treatment for the same reason: a face that lands off-centre cannot be
# fixed with an anchor, because a square crop of a square file has no slack.
FRAMES = {"hero": (1080, 1350), "face": (600, 600)}
JPEG_QUALITY = 90


def _event_dir(event) -> Path:
    return PHOTOS_DIR / "events" / str(event)


def _faces_dir() -> Path:
    return PHOTOS_DIR / "faces"


def _credits_at(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _credits(event) -> dict:
    path = _event_dir(event) / "credits.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _original_for(entry, source_dir: Path):
    """The high-res file a hero was installed from, if it can still be found.

    ``credits.json`` records the source filename, which is the only link back
    to the original: the installed copy is capped at 1920px, so re-cropping
    from it would compound a downscale every time. Falls back to the installed
    copy, which still pans fine and only limits how far in you can zoom.
    """
    if not source_dir or not isinstance(entry, dict):
        return None
    name = entry.get("source_file")
    if not name:
        return None
    candidate = source_dir / name
    return candidate if candidate.exists() else None


def _collect(folder: Path, credits: dict, kind: str, source_dir,
             only=None) -> list:
    """Every installed photo in one folder, as adjuster items."""
    fw, fh = FRAMES[kind]
    items = []
    for path in sorted(glob.glob(str(folder / "*.jpg"))):
        athlete_id = Path(path).stem
        if not athlete_id.isdigit():
            continue
        if only is not None and int(athlete_id) not in only:
            continue
        entry = credits.get(athlete_id) or {}
        original = _original_for(entry, source_dir)
        display = original or Path(path)
        with Image.open(display) as im:
            nw, nh = im.size
        items.append({
            # Heroes and headshots share athlete ids, so the page keys on
            # kind + id. Keying on the id alone made one rider's two photos
            # the same element and only the first was ever drawn.
            "key": ("a" if kind == "hero" else "f") + athlete_id,
            "kind": kind,
            "id": int(athlete_id),
            "installed": path,
            "display": str(display),
            "from_original": original is not None,
            "source_file": entry.get("source_file") or Path(path).name,
            "handle": (entry.get("handle") if isinstance(entry, dict) else "") or "",
            "nw": nw,
            "nh": nh,
            "fw": fw,
            "fh": fh,
        })
    return items


def collect_riders(event, source_dir, only=None) -> list:
    """Every installed hero in the event folder, newest info first."""
    return _collect(_event_dir(event), _credits(event), "hero", source_dir,
                    only)


def collect_faces(source_dir, only=None) -> list:
    """Every installed headshot, for the riders this post actually uses.

    ``faces/`` is athlete-level and holds every headshot in the repo, so it is
    filtered to the cast rather than shown whole: a slalom post has no use for
    a wave rider's face and thirty extra cards make the ones that matter hard
    to find.
    """
    return _collect(_faces_dir(), _credits_at(_faces_dir() / "credits.json"),
                    "face", source_dir, only)


def save_crop(rider: dict, zoom: float, dx: float, dy: float) -> str:
    """Crop the rider's photo to the slide and install it."""
    src = Path(rider["display"])
    frame = FRAMES[rider["kind"]]
    box = crop_box((rider["nw"], rider["nh"]), frame, zoom=zoom, offset=(dx, dy))
    with Image.open(src) as im:
        im = im.convert("RGB")
        exif = im.info.get("exif")
        out = im.crop(box.as_tuple()).resize(frame, Image.LANCZOS)
        extra = {"exif": exif} if exif else {}
        out.save(rider["installed"], "JPEG", quality=JPEG_QUALITY,
                 optimize=True, **extra)
    return f"{rider['id']} {rider['kind']}: {box.as_tuple()} from {src.name}"


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Adjust hero crops</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; background: #0d1117; color: #e6edf3;
         font: 14px/1.5 -apple-system, Segoe UI, sans-serif; padding: 24px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .hint { color: #8b949e; margin-bottom: 20px; }
  .grid { display: flex; flex-wrap: wrap; gap: 24px; }
  .card { width: 288px; }
  .viewport { position: relative; width: 288px; overflow: hidden;
              border-radius: 6px; background: #161b22; cursor: grab; }
  .viewport.drag { cursor: grabbing; }
  .viewport img { position: absolute; transform-origin: 0 0;
                  user-select: none; -webkit-user-drag: none; }
  .grad { position: absolute; inset: 0; pointer-events: none;
          background: linear-gradient(to bottom,
            rgba(8,20,40,0.20) 0%, rgba(10,14,26,0.42) 40%,
            rgba(10,14,26,0.80) 62%, rgba(10,14,26,0.97) 78%,
            rgba(10,14,26,1.00) 100%); }
  .meta { margin-top: 8px; font-size: 12px; color: #8b949e;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .warn { color: #d29922; }
  .lowres { color: #f85149; }
  row { display: block; }
  input[type=range] { width: 208px; vertical-align: middle; }
  button { background: #238636; color: #fff; border: 0; border-radius: 6px;
           padding: 10px 18px; font-size: 14px; cursor: pointer; }
  button.ghost { background: #21262d; color: #c9d1d9; padding: 4px 10px;
                 font-size: 12px; }
  #bar { position: sticky; top: 0; background: #0d1117; padding: 12px 0 16px;
         z-index: 5; display: flex; gap: 12px; align-items: center; }
  #status { color: #8b949e; }
</style>
<h1>Adjust crops</h1>
<div class="hint">Drag to place the shot, then zoom with the slider or the
  wheel. Dragging never changes the zoom. Photos open just inside the frame so
  there is room to move up and down from the start: at 1.00&times; a landscape
  photo fills the slide's height exactly and can only slide sideways. The
  gradient
is where the slide's text sits. Headshots are the square thumbnails on the
  summary table and carry no gradient. Save re-crops from the original file.</div>
<div id="bar">
  <button onclick="saveAll()">Save all</button>
  <span id="status"></span>
</div>
<div class="grid" id="grid"></div>
<script>
const RIDERS = __RIDERS__;
const DEFAULT_ZOOM = __DEFAULT_ZOOM__;
const state = {};

function build(r) {
  const card = document.createElement('div');
  card.className = 'card';
  const h = Math.round(288 * r.fh / r.fw);
  card.innerHTML = `
    <div class="viewport" id="vp-${r.key}" style="height:${h}px">
      <img src="/photo/${r.key}" id="img-${r.key}" draggable="false">
      ${r.kind === 'hero' ? '<div class="grad"></div>' : ''}
    </div>
    <row><input type="range" id="z-${r.key}" min="1" max="3" step="0.01"
      value="${DEFAULT_ZOOM}">
    <button class="ghost" onclick="reset('${r.key}')">Reset</button></row>
    <div class="meta">${r.id} &middot; ${r.kind === 'hero' ? 'action' : 'headshot'}
      &middot; ${r.source_file}${r.handle ? ' &middot; ' + r.handle : ''}</div>
    <div class="meta ${r.from_original ? '' : 'lowres'}">
      ${r.from_original ? 'original ' + r.nw + '&times;' + r.nh
                        : 'ORIGINAL NOT FOUND \u2014 zoom limited (' + r.nw + '&times;' + r.nh + ')'}
    </div>
    <div class="meta warn" id="w-${r.key}"></div>`;
  document.getElementById('grid').appendChild(card);
  state[r.key] = {zoom: DEFAULT_ZOOM, dx: 0, dy: 0, r};
  const img = document.getElementById('img-' + r.key);
  img.onload = () => render(r.key);
  document.getElementById('z-' + r.key).oninput = e => {
    state[r.key].zoom = parseFloat(e.target.value); render(r.key);
  };
  const vp = document.getElementById('vp-' + r.key);
  vp.onwheel = e => {
    e.preventDefault();
    const s = state[r.key];
    s.zoom = Math.min(3, Math.max(1, s.zoom * (e.deltaY < 0 ? 1.06 : 0.94)));
    document.getElementById('z-' + r.key).value = s.zoom;
    render(r.key);
  };
  let dragging = false, px = 0, py = 0;
  vp.onmousedown = e => { dragging = true; px = e.clientX; py = e.clientY;
                          vp.classList.add('drag'); e.preventDefault(); };
  window.addEventListener('mouseup', () => { dragging = false; vp.classList.remove('drag'); });
  window.addEventListener('mousemove', e => {
    if (!dragging) return;
    const s = state[r.key];
    s.dx += (e.clientX - px) / vp.clientWidth;
    s.dy += (e.clientY - py) / vp.clientHeight;
    px = e.clientX; py = e.clientY;
    render(r.key);
  });
}

// Mirrors pipeline/photo_adjust.crop_box so what you see is what is saved.
function render(key) {
  const s = state[key], r = s.r;
  const vp = document.getElementById('vp-' + key);
  const vw = vp.clientWidth, vh = vp.clientHeight;
  const base = Math.max(vw / r.nw, vh / r.nh) * Math.max(s.zoom, 1);
  const dw = r.nw * base, dh = r.nh * base;
  const mx = (dw - vw) / 2, my = (dh - vh) / 2;
  s.dx = Math.max(-mx / vw, Math.min(mx / vw, s.dx));
  s.dy = Math.max(-my / vh, Math.min(my / vh, s.dy));
  const img = document.getElementById('img-' + key);
  img.style.width = dw + 'px';
  img.style.height = dh + 'px';
  img.style.left = (-mx + s.dx * vw) + 'px';
  img.style.top = (-my + s.dy * vh) + 'px';
  const visible = (vw / base) / r.nw;
  const room = Math.round(my / base);
  document.getElementById('w-' + key).textContent =
    'showing ' + Math.round(visible * 100) + '% of width'
    + '  \u00b7  zoom ' + s.zoom.toFixed(2) + '\u00d7'
    + (room > 0 ? '  \u00b7  \u00b1' + room + 'px up/down'
                : '  \u00b7  no vertical room at this zoom');
}

function reset(key) {
  state[key].zoom = DEFAULT_ZOOM; state[key].dx = 0; state[key].dy = 0;
  document.getElementById('z-' + key).value = DEFAULT_ZOOM;
  render(key);
}

async function saveAll() {
  const items = Object.values(state).map(s =>
    ({key: s.r.key, zoom: s.zoom, dx: s.dx, dy: s.dy}));
  document.getElementById('status').textContent = 'Saving...';
  const res = await fetch('/save', {method: 'POST', body: JSON.stringify({items})});
  const out = await res.json();
  document.getElementById('status').textContent = out.message;
}

RIDERS.forEach(build);
window.addEventListener('resize', () => Object.keys(state).forEach(render));
</script>
"""


class Handler(BaseHTTPRequestHandler):
    riders = []

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            page = (PAGE.replace("__RIDERS__", json.dumps(self.riders))
                        .replace("__DEFAULT_ZOOM__", str(DEFAULT_ZOOM)))
            return self._send(200, page.encode("utf-8"))
        if path.startswith("/photo/"):
            wanted = path.rsplit("/", 1)[-1]
            for r in self.riders:
                if r["key"] == wanted:
                    data = Path(r["display"]).read_bytes()
                    return self._send(200, data, "image/jpeg")
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if urlparse(self.path).path != "/save":
            return self._send(404, b"not found", "text/plain")
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or "{}")
        by_key = {r["key"]: r for r in self.riders}
        saved = []
        for item in payload.get("items", []):
            rider = by_key.get(item["key"])
            if rider:
                saved.append(save_crop(rider, float(item["zoom"]),
                                       float(item["dx"]), float(item["dy"])))
        for line in saved:
            print("  saved", line)
        msg = f"Saved {len(saved)} photo(s). Re-run generate.py to see them."
        self._send(200, json.dumps({"message": msg}).encode("utf-8"),
                   "application/json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True,
                        help="Event folder under assets/photos/events/")
    parser.add_argument("--source", help="Folder holding the original high-res files")
    parser.add_argument("--athletes", help="Comma-separated athlete IDs (default: all)")
    parser.add_argument("--no-faces", action="store_true",
                        help="Action shots only; leave the headshots alone")
    parser.add_argument("--port", type=int, default=8712)
    args = parser.parse_args()

    only = None
    if args.athletes:
        only = {int(a) for a in args.athletes.split(",") if a.strip()}
    source_dir = Path(args.source) if args.source else None
    if source_dir and not source_dir.exists():
        print(f"Source folder not found: {source_dir}", file=sys.stderr)
        return 1

    riders = collect_riders(args.event, source_dir, only)
    if not args.no_faces:
        # The headshots belong to whoever is on this post, which is the cast
        # the event folder already names, plus anything asked for by hand.
        cast = {r["id"] for r in riders} | (only or set())
        riders += collect_faces(source_dir, cast or None)
    if not riders:
        print(f"No installed photos in {_event_dir(args.event)}", file=sys.stderr)
        return 1

    missing = [r["id"] for r in riders if not r["from_original"]]
    if missing:
        print(f"Originals not found for {missing}; those pan from the "
              f"installed copy, so zoom is limited.")

    Handler.riders = riders
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"{len(riders)} photo(s) at {url}   (ctrl-c when done)")
    threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
