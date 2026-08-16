"""Snapshot the HeatScoringPRO move dictionary.

PWA rates every judged move on a 0-10 difficulty scale and serves it from a
public tRPC procedure. The app repo's importer already reads this to attach a
difficulty to each scored move, but has nowhere to persist it
(datawithjack/windsurf-world-tour-stats-app#77), so the rating is computed and
discarded on every run. This module keeps a dated snapshot on disk so content
work can use difficulty before the DB column exists.

The dictionary is slow-moving but NOT static, which is why every snapshot is
stamped and kept rather than overwritten:

  * ``deletedAt`` is part of the upstream model, so moves can be retired.
  * Four entries are placeholders ("New Move", "New Move high 1/2/3") sitting
    at difficulty 10, which judges pick for an unnamed new trick. They get
    named later, so a row's identity changes over time.
  * Difficulty is a judging parameter and can be recalibrated between seasons.

Treat a snapshot as "the dictionary as at <date>", not as the truth.
"""

import json
import os
from datetime import date, datetime, timezone
from urllib.parse import quote

import requests

BASE = "https://pwa.heatscoringpro.com/api/trpc/"

SNAPSHOT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "moves"
)

# SLALOM is a race with no judged moves; move.getAll 400s for it.
CATEGORIES = ("FREESTYLE", "WAVE")

# Placeholder rows a judge selects for an unnamed new trick. They score 10, so
# a naive "hardest move landed" ranks them above every real trick.
PLACEHOLDER_SLUGS = {"NEW", "NEW2", "NEW-H2", "NEW-H3"}


def fetch_moves(category: str, timeout: int = 30) -> list:
    """Fetch the move dictionary for one category. Public, no auth."""
    payload = quote(json.dumps({"0": {"json": {"category": category}}}))
    resp = requests.get(
        f"{BASE}move.getAll?batch=1&input={payload}",
        headers={"User-Agent": "wwts-instagram/1.0", "Accept": "application/json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()[0]["result"]["data"]["json"]


def is_placeholder(move: dict) -> bool:
    """Whether a row is an unnamed-new-trick placeholder rather than a real move."""
    return (move.get("slug") or "").upper() in PLACEHOLDER_SLUGS


def snapshot(categories=CATEGORIES, out_dir: str = None) -> str:
    """Write a dated snapshot of every category. Returns the file path.

    The file carries its own provenance (endpoint, fetch time) so a reader a
    year from now can tell what it is and how stale it has become.
    """
    out_dir = out_dir or SNAPSHOT_DIR
    os.makedirs(out_dir, exist_ok=True)

    fetched_at = datetime.now(timezone.utc)
    payload = {
        "source": "heatscoringpro",
        "endpoint": f"{BASE}move.getAll",
        "fetched_at": fetched_at.isoformat(),
        "as_at": fetched_at.date().isoformat(),
        "note": (
            "Dictionary is slow-moving but not static: deletedAt exists upstream, "
            "placeholder rows get renamed, and difficulty can be recalibrated. "
            "Treat as the dictionary as at this date."
        ),
        "categories": {},
    }
    for cat in categories:
        moves = fetch_moves(cat)
        payload["categories"][cat] = {
            "count": len(moves),
            "placeholders": sorted(m["slug"] for m in moves if is_placeholder(m)),
            "moves": moves,
        }

    path = os.path.join(out_dir, f"hsp_moves_{fetched_at.date().isoformat()}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


def load_snapshot(path: str = None, out_dir: str = None) -> dict:
    """Load a snapshot, defaulting to the most recent one on disk."""
    if path is None:
        out_dir = out_dir or SNAPSHOT_DIR
        files = sorted(f for f in os.listdir(out_dir) if f.startswith("hsp_moves_"))
        if not files:
            raise FileNotFoundError(f"no snapshot in {out_dir}")
        path = os.path.join(out_dir, files[-1])
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def difficulty_by_slug(snap: dict, category: str = "FREESTYLE",
                       include_placeholders: bool = False) -> dict:
    """``slug -> difficulty`` for one category.

    Placeholders are excluded by default: they sit at 10 and would top any
    "hardest move" ranking without describing a real trick.
    """
    out = {}
    for mv in snap["categories"][category]["moves"]:
        if not include_placeholders and is_placeholder(mv):
            continue
        if mv.get("difficulty") is not None:
            out[mv["slug"]] = mv["difficulty"]
    return out
