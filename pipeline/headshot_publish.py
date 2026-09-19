"""What publishing the approved headshots would change on the stats site (#33).

Pure planning, so the part that decides what happens to a production row is
tested: ``upload_headshots.py`` executes exactly this plan, and ``--dry-run``
prints it.

The site reads ``ATHLETES.liveheats_image_url`` before its sail-number guess on
every surface -- athlete pages, fantasy picker, leaderboards -- so one write per
rider covers them all. The column name is wrong (stats-app #232); the value can
be LiveHeats, Cloudinary or ours.
"""

from pathlib import Path

# Never R2_PUBLIC_URL: this repo's .env still names pub-*.r2.dev, which
# Telefonica blocks wholesale -- a URL on it is a photo that silently fails for
# a whole ISP (stats-app #151).
PUBLIC_HOST = "https://img.windsurfworldtourstats.com"
KEY_PREFIX = "athlete-photos/"
FACES_DIR = Path("assets/photos/faces")


def _ours(url) -> bool:
    return bool(url) and f"/{KEY_PREFIX}" in url


def plan_changes(manifest: dict, current: dict, now: int, force: bool = False) -> list[dict]:
    """One planned step per manifest entry.

    ``current`` is athlete id -> the row's stored value (None = NULL; absent =
    no such athlete). ``op`` is ``publish`` (upload + update), ``update``,
    ``skip`` or ``refuse``. ``old`` is the value the update will compare
    against, so a row that changed since planning is not written.
    """
    plan = []
    for key, entry in manifest.items():
        if key.startswith("_"):
            continue
        aid = int(key)
        step = {"athlete_id": aid, "name": entry.get("name", ""), "action": entry["action"]}
        if aid not in current:
            plan.append({**step, "op": "refuse", "reason": "no such athlete"})
            continue
        old = current[aid]
        real = bool(old) and not _ours(old)

        if entry["action"] == "approve":
            if old and old == entry.get("published_url"):
                plan.append({**step, "op": "skip", "reason": "already published"})
            elif real and not force:
                plan.append({**step, "op": "refuse", "old": old,
                             "reason": "row holds a real photo (use --force to replace)"})
            else:
                r2_key = f"{KEY_PREFIX}{aid}_{now}.jpg"
                plan.append({**step, "op": "publish", "old": old,
                             "file": (FACES_DIR / f"{aid}.jpg").as_posix(), "key": r2_key,
                             "new": f"{PUBLIC_HOST}/{r2_key}"})
        elif entry["action"] == "suppress":
            if old == "":
                plan.append({**step, "op": "skip", "reason": "already suppressed"})
            elif real:
                plan.append({**step, "op": "refuse", "old": old,
                             "reason": "never hides a real photo"})
            else:
                plan.append({**step, "op": "update", "old": old, "new": ""})
        else:
            plan.append({**step, "op": "refuse", "reason": f"unknown action {entry['action']!r}"})
    return plan


def plan_rollback(records: list[dict], current: dict) -> list[dict]:
    """Put each row back to its old value -- only where it still holds ours."""
    plan = []
    for rec in records:
        aid = rec["athlete_id"]
        if aid in current and current[aid] == rec["new"]:
            plan.append({"athlete_id": aid, "op": "update", "old": rec["new"], "new": rec["old"]})
        else:
            plan.append({"athlete_id": aid, "op": "refuse",
                         "reason": "row changed since publish; left alone"})
    return plan
