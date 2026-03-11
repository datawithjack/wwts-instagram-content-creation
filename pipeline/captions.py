"""Caption generation for Instagram posts."""
from pipeline.helpers import ordinal


def build_caption(
    template_name: str, data: dict, config: dict, caption_override: str = None
) -> str:
    """Build an Instagram caption from template data and config.

    If caption_override is provided, uses that as the body text
    but still appends hashtags.
    """
    site_url = config.get("captions", {}).get("site_url", "windsurfworldtourstats.com")

    if caption_override:
        body = caption_override
    else:
        builders = {
            "head_to_head": _caption_head_to_head,
            "head_to_head_jump": _caption_head_to_head,
            "top_10": _caption_top_10,
            "top_10_carousel": _caption_top_10,
            "site_stats": _caption_site_stats,
            "site_stats_reel": _caption_site_stats,
            "rider_profile": _caption_rider_profile,
        }
        builder = builders.get(template_name, _caption_default)
        body = builder(data, site_url)

    hashtags = _get_hashtags(template_name, config)
    return f"{body}\n\n{hashtags}"


def _caption_head_to_head(data: dict, site_url: str) -> str:
    event = data.get("event_name", "")
    a1 = data.get("athlete_1_name", "")
    a2 = data.get("athlete_2_name", "")
    return (
        f"{a1} vs {a2} at the {event}.\n"
        f"Full stats at {site_url}"
    )


def _caption_top_10(data: dict, site_url: str) -> str:
    gender = data.get("title_gender", "")
    metric = data.get("title_metric", "")
    year = data.get("title_year", "")
    return (
        f"Top 10 {gender} {metric} — {year}.\n"
        f"Full leaderboard at {site_url}"
    )


def _caption_site_stats(data: dict, site_url: str) -> str:
    athletes = f"{data.get('athletes_count', 0):,}"
    scores = f"{data.get('scores_count', 0):,}"
    events = f"{data.get('events_count', 0):,}"
    return (
        f"{athletes} athletes. {scores} scores. {events} events.\n"
        f"Explore the data at {site_url}"
    )


def _caption_rider_profile(data: dict, site_url: str) -> str:
    name = data.get("athlete_name", "")
    event = data.get("event_name", "")
    placement = ordinal(data.get("placement", 0))
    return (
        f"{name} at the {event} — {placement}.\n"
        f"Full stats at {site_url}"
    )


def _caption_default(data: dict, site_url: str) -> str:
    return f"Check out the latest windsurf stats at {site_url}"


def _get_hashtags(template_name: str, config: dict) -> str:
    hashtags_config = config.get("hashtags", {})
    # For h2h_jump, use h2h hashtags
    lookup = template_name
    if template_name == "head_to_head_jump":
        lookup = "head_to_head"
    tags = hashtags_config.get(lookup, hashtags_config.get("default", []))
    return " ".join(tags)
