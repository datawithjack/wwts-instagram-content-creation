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
FRAME = (1080, 1350)
JPEG_QUALITY = 90


def _event_dir(event) -> Path:
    return PHOTOS_DIR / "events" / str(event)


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


def collect_riders(event, source_dir, only=None) -> list:
    """Every installed hero in the event folder, newest info first."""
    credits = _credits(event)
    riders = []
    for path in sorted(glob.glob(str(_event_dir(event) / "*.jpg"))):
        athlete_id = Path(path).stem
        if not athlete_id.isdigit():
            continue
        if only and int(athlete_id) not in only:
            continue
        entry = credits.get(athlete_id) or {}
        original = _original_for(entry, source_dir)
        display = original or Path(path)
        with Image.open(display) as im:
            nw, nh = im.size
        riders.append({
            "id": int(athlete_id),
            "installed": path,
            "display": str(display),
            "from_original": original is not None,
            "source_file": entry.get("source_file") or Path(path).name,
            "handle": (entry.get("handle") if isinstance(entry, dict) else "") or "",
            "nw": nw,
            "nh": nh,
        })
    return riders


def save_crop(rider: dict, zoom: float, dx: float, dy: float) -> str:
    """Crop the rider's photo to the slide and install it."""
    src = Path(rider["display"])
    box = crop_box((rider["nw"], rider["nh"]), FRAME, zoom=zoom, offset=(dx, dy))
    with Image.open(src) as im:
        im = im.convert("RGB")
        exif = im.info.get("exif")
        out = im.crop(box.as_tuple()).resize(FRAME, Image.LANCZOS)
        extra = {"exif": exif} if exif else {}
        out.save(rider["installed"], "JPEG", quality=JPEG_QUALITY,
                 optimize=True, **extra)
    return f"{rider['id']}: {box.as_tuple()} from {src.name}"


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
  .viewport { position: relative; width: 288px; height: 360px; overflow: hidden;
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
<h1>Adjust hero crops</h1>
<div class="hint">Drag to move, scroll or use the slider to zoom. The gradient
is where the slide's text sits. Save re-crops from the original file.</div>
<div id="bar">
  <button onclick="saveAll()">Save all</button>
  <span id="status"></span>
</div>
<div class="grid" id="grid"></div>
<script>
const RIDERS = __RIDERS__;
const FRAME_W = 1080, FRAME_H = 1350;
const state = {};

function build(r) {
  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = `
    <div class="viewport" id="vp-${r.id}">
      <img src="/photo/${r.id}" id="img-${r.id}" draggable="false">
      <div class="grad"></div>
    </div>
    <row><input type="range" id="z-${r.id}" min="1" max="3" step="0.01" value="1">
    <button class="ghost" onclick="reset(${r.id})">Reset</button></row>
    <div class="meta">${r.id} &middot; ${r.source_file}${r.handle ? ' &middot; ' + r.handle : ''}</div>
    <div class="meta ${r.from_original ? '' : 'lowres'}">
      ${r.from_original ? 'original ' + r.nw + '&times;' + r.nh
                        : 'ORIGINAL NOT FOUND \u2014 zoom limited (' + r.nw + '&times;' + r.nh + ')'}
    </div>
    <div class="meta warn" id="w-${r.id}"></div>`;
  document.getElementById('grid').appendChild(card);
  state[r.id] = {zoom: 1, dx: 0, dy: 0, r};
  const img = document.getElementById('img-' + r.id);
  img.onload = () => render(r.id);
  document.getElementById('z-' + r.id).oninput = e => {
    state[r.id].zoom = parseFloat(e.target.value); render(r.id);
  };
  const vp = document.getElementById('vp-' + r.id);
  vp.onwheel = e => {
    e.preventDefault();
    const s = state[r.id];
    s.zoom = Math.min(3, Math.max(1, s.zoom * (e.deltaY < 0 ? 1.06 : 0.94)));
    document.getElementById('z-' + r.id).value = s.zoom;
    render(r.id);
  };
  let dragging = false, px = 0, py = 0;
  vp.onmousedown = e => { dragging = true; px = e.clientX; py = e.clientY;
                          vp.classList.add('drag'); e.preventDefault(); };
  window.addEventListener('mouseup', () => { dragging = false; vp.classList.remove('drag'); });
  window.addEventListener('mousemove', e => {
    if (!dragging) return;
    const s = state[r.id];
    s.dx += (e.clientX - px) / vp.clientWidth;
    s.dy += (e.clientY - py) / vp.clientHeight;
    px = e.clientX; py = e.clientY;
    render(r.id);
  });
}

// Mirrors pipeline/photo_adjust.crop_box so what you see is what is saved.
function render(id) {
  const s = state[id], r = s.r;
  const vp = document.getElementById('vp-' + id);
  const vw = vp.clientWidth, vh = vp.clientHeight;
  const base = Math.max(vw / r.nw, vh / r.nh) * Math.max(s.zoom, 1);
  const dw = r.nw * base, dh = r.nh * base;
  const mx = (dw - vw) / 2, my = (dh - vh) / 2;
  s.dx = Math.max(-mx / vw, Math.min(mx / vw, s.dx));
  s.dy = Math.max(-my / vh, Math.min(my / vh, s.dy));
  const img = document.getElementById('img-' + id);
  img.style.width = dw + 'px';
  img.style.height = dh + 'px';
  img.style.left = (-mx + s.dx * vw) + 'px';
  img.style.top = (-my + s.dy * vh) + 'px';
  const visible = (vw / base) / r.nw;
  document.getElementById('w-' + id).textContent =
    'showing ' + Math.round(visible * 100) + '% of width' +
    (s.zoom > 1 ? '  \u00b7  zoom ' + s.zoom.toFixed(2) + '\u00d7' : '  \u00b7  fully zoomed out');
}

function reset(id) {
  state[id].zoom = 1; state[id].dx = 0; state[id].dy = 0;
  document.getElementById('z-' + id).value = 1;
  render(id);
}

async function saveAll() {
  const items = Object.values(state).map(s =>
    ({id: s.r.id, zoom: s.zoom, dx: s.dx, dy: s.dy}));
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
            page = PAGE.replace("__RIDERS__", json.dumps(self.riders))
            return self._send(200, page.encode("utf-8"))
        if path.startswith("/photo/"):
            wanted = path.rsplit("/", 1)[-1]
            for r in self.riders:
                if str(r["id"]) == wanted:
                    data = Path(r["display"]).read_bytes()
                    return self._send(200, data, "image/jpeg")
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if urlparse(self.path).path != "/save":
            return self._send(404, b"not found", "text/plain")
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or "{}")
        by_id = {r["id"]: r for r in self.riders}
        saved = []
        for item in payload.get("items", []):
            rider = by_id.get(item["id"])
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
