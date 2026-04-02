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
            "h2h_carousel": _caption_head_to_head,
            "top_10": _caption_top_10,
            "top_10_carousel": _caption_top_10,
            "about_carousel": _caption_about,
            "coming_soon_carousel": _caption_coming_soon,
            "site_stats": _caption_site_stats,
            "site_stats_reel": _caption_site_stats,
            "rider_profile": _caption_rider_profile,
            "canary_kings": _caption_canary_kings,
            "athlete_rise": _caption_athlete_rise,
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
        f"\U0001f30a Who dominated in {event}?\n\n"
        f"{a1} vs {a2} \u2014 swipe to see the wave-by-wave breakdown.\n\n"
        f"Who\u2019s your pick? Drop it below \U0001f447\n\n"
        f"Full stats \u2192 {site_url}"
    )


def _caption_top_10(data: dict, site_url: str) -> str:
    gender = data.get("title_gender", "")
    metric = data.get("title_metric", "")
    year = data.get("title_year", "")
    day = data.get("day")

    if day:
        event_name = data.get("event_name", "")
        day_label = "Finals Day" if data.get("finals_day") else f"Day {day}"
        return (
            f"\U0001f3c6 {day_label} \u2014 the 10 best {gender.lower()} {metric.lower()} at {event_name}.\n\n"
            f"Swipe to see who made the list.\n\n"
            f"Who impressed you today? \U0001f447\n\n"
            f"Full leaderboard \u2192 {site_url}"
        )

    return (
        f"\U0001f3c6 The 10 best {gender.lower()} {metric.lower()} \u2014 {year}.\n\n"
        f"Swipe to see who made the list \u2014 and who\u2019s missing.\n\n"
        f"Who deserves a spot? Tell us \U0001f447\n\n"
        f"Full leaderboard \u2192 {site_url}"
    )


def _caption_site_stats(data: dict, site_url: str) -> str:
    athletes = f"{data.get('athletes_count', 0):,}"
    scores = f"{data.get('scores_count', 0):,}"
    events = f"{data.get('events_count', 0):,}"
    return (
        f"\U0001f4ca {athletes} athletes. {scores} scores. {events} events.\n\n"
        f"The PWA World Tour \u2014 all the numbers, one place.\n\n"
        f"Explore the data \u2192 {site_url}"
    )


def _caption_rider_profile(data: dict, site_url: str) -> str:
    name = data.get("athlete_name", "")
    event = data.get("event_name", "")
    placement = ordinal(data.get("placement", 0))
    best_wave = data.get("best_wave")
    wave_line = f" with a {best_wave} best wave" if best_wave else ""
    return (
        f"\U0001f525 {name} \u2014 {placement} at {event}{wave_line}.\n\n"
        f"Swipe for the full breakdown of the event.\n\n"
        f"What do you think of their season so far? \U0001f447\n\n"
        f"Full stats \u2192 {site_url}"
    )


def _caption_about(data: dict, site_url: str) -> str:
    return (
        "\U0001f30a Windsurf World Tour Stats \u2014 the data behind professional windsurfing.\n\n"
        "Wave scores, jump scores, head to heads, and leaderboards.\n\n"
        f"Explore \u2192 {site_url}"
    )


def _caption_coming_soon(data: dict, site_url: str) -> str:
    return (
        "\U0001f525 New features coming soon to windsurfworldtourstats.com!\n\n"
        "More disciplines, athlete profiles, career head to heads, and all-time score lists.\n\n"
        f"Follow for updates \u2192 {site_url}"
    )


def _caption_canary_kings(data: dict, site_url: str) -> str:
    men = data.get("men", [])
    women = data.get("women", [])
    king = men[0]["athlete"] if men else "?"
    queen = women[0]["athlete"] if women else "?"
    return (
        f"\U0001f3c6 Who are the Kings and Queens of the Canary Islands?\n\n"
        f"Since 2016, {king} and {queen} have dominated Gran Canaria and Tenerife.\n\n"
        f"Swipe to see the full rankings. Who\u2019s next? \U0001f447\n\n"
        f"Full stats \u2192 {site_url}"
    )


def _caption_athlete_rise(data: dict, site_url: str) -> str:
    name = data.get("athlete_name", "")
    location = data.get("location", "")
    yearly = data.get("yearly_data", [])
    first_year = yearly[0]["year"] if yearly else ""
    last_year = yearly[-1]["year"] if yearly else ""
    first_name = name.split()[0] if name else ""
    return (
        f"\U0001f4ca The rise of {name} in {location}.\n\n"
        f"From {first_year} to {last_year} \u2014 {first_name}\u2019s journey to the top.\n\n"
        f"Can anyone catch them? \U0001f447\n\n"
        f"Full stats \u2192 {site_url}"
    )


def _caption_default(data: dict, site_url: str) -> str:
    return f"\U0001f30a Check out the latest windsurf stats \u2192 {site_url}"


def _get_hashtags(template_name: str, config: dict) -> str:
    hashtags_config = config.get("hashtags", {})
    # For h2h_jump, use h2h hashtags
    lookup = template_name
    if template_name == "head_to_head_jump":
        lookup = "head_to_head"
    tags = hashtags_config.get(lookup, hashtags_config.get("default", []))
    return " ".join(tags)
