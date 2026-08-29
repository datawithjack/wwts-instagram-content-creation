"""From a set of picked photos to an entry in the backlog.

``pick_photos.py`` used to stop once the photos were installed and the slides
were open in eight browser tabs. The rest of making a post -- reading the
slides, writing the caption, choosing a time, recording it -- happened by hand
in YAML afterwards. This module is those steps: the browser page is the shell,
and the decisions live here where they can be tested.

Two things it deliberately does not do. It does not publish: the backlog plus
the poll-backlog Action already do that, and keeping publishing out preserves
the property that nothing goes live without a deliberate commit. And it does
not pretend that writing the file schedules anything -- the poller runs from
GitHub Actions against ``main``, so an entry exists only once it is pushed.
"""

import os
import re
from datetime import datetime, timezone
from urllib.parse import quote

from pipeline.api import fetch_event_top_scores
from pipeline.backlog import find_entry, propose_id, upsert_entry
from pipeline.captions import (
    build_caption_body,
    hashtags_for,
    missing_photo_credits,
    with_photo_credits,
)
from pipeline.carousel import build_slides
from pipeline.post_options import apply_post_options
from pipeline.preview import slide_html
from pipeline.scheduler import load_config

TEMPLATE = "top_10_carousel"
BACKLOG_PATH = "content_backlog.yaml"

# The Action polls every 30 minutes and publishes whatever is due, so a post
# goes out at the next poll after its time rather than on the minute.
POLL_MINUTES = 30

NOT_SCHEDULED_YET = (
    "Written to content_backlog.yaml. Nothing is scheduled yet: the poller runs "
    "from GitHub Actions against main, so commit and push before this can "
    "publish."
)

# Stops at quotes and brackets rather than at whitespace: these paths run
# through OneDrive\Documents, and a folder with a space in it is one rename away.
_FILE_URL = re.compile(r"file:///([^\"'()<>]+)")


def build_post(plan: dict) -> tuple[dict, list[str]]:
    """Fetch the data for a picked post and render its slides.

    ``plan`` is what ``pick_photos.generation_plan`` produced: the event, the
    score type and the division. Photo mode is not optional here -- the whole
    reason this flow exists is that photos were just picked for it.
    """
    data = fetch_event_top_scores(
        event_id=plan["event_id"], score_type=plan["score_type"],
        sex=plan.get("sex"),
    )
    apply_post_options(data, {"photos": True, "event": plan["event_id"]})
    return data, slide_html(build_slides(data))


def local_asset_urls(html: str) -> str:
    """Point slide images at a route this server can serve.

    The slides address photos as ``file:///``, which is what a preview opened
    from disk needs. The review page is served over http, and a browser blocks
    a file:// subresource of an http page without saying so, which would show
    up as slides that are simply missing their photographs.
    """
    return _FILE_URL.sub(
        lambda m: "/local?p=" + quote(m.group(1).rstrip(), safe="/"), html)


def review_payload(plan: dict, event_name: str, year, config: dict = None) -> dict:
    """Everything the review step of the page needs."""
    config = config or load_config()
    data, slides = build_post(plan)
    return {
        "slides": [local_asset_urls(html) for html in slides],
        "caption": build_caption_body(TEMPLATE, data, config),
        "hashtags": hashtags_for(TEMPLATE, config),
        # The page warns live if an edit drops one of these.
        "credits": data.get("photo_credits") or [],
        "post_id": propose_id(event_name, year, plan.get("sex"),
                              plan["score_type"]),
        "template": TEMPLATE,
        "params": {"score_type": plan["score_type"], "sex": plan.get("sex"),
                   "event": plan["event_id"], "photos": True},
        "poll_minutes": POLL_MINUTES,
    }


def normalise_schedule(value: str) -> tuple[str, str | None]:
    """An ISO UTC timestamp in the shape the backlog uses, plus any warning.

    A browser datetime input gives local time; the page converts and sends UTC,
    because the file documents scheduled_date as ISO 8601 UTC and in BST a
    local reading is an hour out.
    """
    text = (value or "").strip().rstrip("Z")
    if not text:
        raise ValueError("Pick a publish time first.")
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{value!r} is not a date and time.")

    when = when.replace(tzinfo=None)
    canonical = when.strftime("%Y-%m-%dT%H:%M:%S")
    warning = None
    if when < datetime.now(timezone.utc).replace(tzinfo=None):
        warning = ("That time is in the past. The poller treats any past "
                   "unpublished post as due, so this will publish at the next "
                   "poll after it is pushed.")
    return canonical, warning


def lookup(path: str, post_id: str) -> dict:
    """What is already in the backlog under this id, if anything."""
    existing = find_entry(path, (post_id or "").strip())
    if not existing:
        return {"exists": False}
    return {
        "exists": True,
        "caption": existing.get("caption", ""),
        "scheduled_date": existing.get("scheduled_date"),
        "published": bool(existing.get("published")),
        "template": existing.get("template"),
    }


def save_to_backlog(path: str, entry: dict, credits: list) -> dict:
    """Write the entry, repairing the credit line if it was edited away.

    ``credits`` is the handle list, not a data dict. It was a data dict once,
    and the caller had a review payload keyed ``credits`` rather than
    ``photo_credits``, so nothing was ever owed and a deleted credit line
    stayed deleted. Taking the list leaves nothing to mismatch.
    """
    post_id = (entry.get("id") or "").strip()
    if not post_id:
        raise ValueError("The post needs an id.")

    # Raised before anything is written: a half-saved entry is worse than none.
    scheduled_date, time_warning = normalise_schedule(entry.get("scheduled_date"))

    owed = {"photo_credits": list(credits or [])}
    caption = (entry.get("caption") or "").strip()
    restored = missing_photo_credits(caption, owed)
    if restored:
        caption = with_photo_credits(caption, owed)

    result = upsert_entry(path, {
        "id": post_id,
        "template": entry.get("template", TEMPLATE),
        "params": entry.get("params") or {},
        "caption": caption,
        "category": entry.get("category", "seasonal"),
        "scheduled_date": scheduled_date,
        "notes": entry.get("notes"),
    })

    return {
        **result,
        "id": post_id,
        "caption": caption,
        "scheduled_date": scheduled_date,
        "credits_restored": restored,
        "time_warning": time_warning,
        "message": NOT_SCHEDULED_YET,
        "path": os.path.abspath(path),
    }
