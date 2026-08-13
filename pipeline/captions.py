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
            "wave_count": _caption_wave_count,
            "finals_preview": _caption_finals_preview,
            "athlete_rise": _caption_athlete_rise,
            "event_picks": _caption_event_picks,
            "freestyle_scores_live": _caption_freestyle_scores_live,
            "slalom_scores_live": _caption_slalom_scores_live,
            "wave_scores_live": _caption_wave_scores_live,
            "fuerte_fantasy_mvps": _caption_fantasy_mvps,
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

    if data.get("perfect_10s_mode"):
        return (
            "There\u2019s been a lot of talk about perfect 10s over the last few events. "
            "Here\u2019s every one scored since 2016.\n\n"
            "Would love to dig out the clips and compare them \U0001f440\n\n"
            "Anyone interested in me building out a full list of the top jumps and waves ever, "
            "by season and rider? Comment below \U0001f447\n\n"
            f"Full stats \u2192 {site_url}"
        )

    if data.get("so_far"):
        event_name = data.get("event_name", "")
        return (
            f"\U0001f3c4 The {event_name} is well underway.\n\n"
            f"Here are the highest {gender.lower()} {metric.lower().rstrip('s')} scores so far.\n\n"
            f"Who has been your standout rider? \U0001f447\n\n"
            f"Full leaderboard → {site_url}"
        )

    if day or data.get("finals_day"):
        event_name = data.get("event_name", "")
        day_label = "Finals Day" if data.get("finals_day") else f"Day {day}"
        return (
            f"\U0001f3c6 {day_label} \u2014 the best {gender.lower()} {metric.lower()} at {event_name}.\n\n"
            f"Swipe to see who made the list.\n\n"
            f"Who impressed you this round? \U0001f447\n\n"
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
    year = data.get("event_date_start")
    year_str = f" {year.year}" if hasattr(year, "year") else ""
    placement = ordinal(data.get("placement", 0))
    return (
        f"\U0001f525 {name} \u2014 {placement} at the {event}{year_str}.\n\n"
        f"Swipe for the full stat breakdown \u2014 best waves, heat scores, and more.\n\n"
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
        f"Since 2006, {king} and {queen} have dominated Gran Canaria and Tenerife.\n\n"
        f"Swipe to see the full rankings. Who\u2019s next? \U0001f447\n\n"
        f"Full stats \u2192 {site_url}"
    )


def _caption_fantasy_mvps(data: dict, site_url: str) -> str:
    men = data.get("men", [])
    women = data.get("women", [])
    event = data.get("event", {})
    location = event.get("location", "Fuerteventura")
    top_man = men[0]["athlete"] if men else "?"
    top_woman = women[0]["athlete"] if women else "?"
    return (
        f"\U0001f3c6 The Fantasy MVPs of {location}.\n\n"
        f"These are the riders who won you the most fantasy points at the "
        f"freestyle event, scored across the single and double eliminations.\n\n"
        f"{top_man} and {top_woman} topped the men's and women's charts. "
        f"Swipe for the full top 10, plus how many players had them on their team.\n\n"
        f"Don't forget to get a team in for the Tenerife wave event, starting at "
        f"the end of July. Link in bio.\n\n"
        f"Full stats → {site_url}"
    )


def _caption_wave_count(data: dict, site_url: str) -> str:
    def _leaders(rows):
        if not rows:
            return "?"
        top = max(int(r["wave_count"]) for r in rows)
        names = [r["athlete"] for r in rows if int(r["wave_count"]) == top]
        if len(names) == 1:
            return names[0]
        return " & ".join([", ".join(names[:-1]), names[-1]]) if len(names) > 2 else " & ".join(names)

    king = _leaders(data.get("men", []))
    queen = _leaders(data.get("women", []))
    return (
        f"\U0001f30a Who made the most of Cloudbreak?\n\n"
        f"Pure wave count — not who won, but who put in the work. "
        f"{queen} and {king} caught the most waves in Fiji.\n\n"
        f"(More heats means more waves — swipe for the per-heat numbers too.)\n\n"
        f"Full stats → {site_url}"
    )


def _caption_finals_preview(data: dict, site_url: str) -> str:
    meta = data.get("event_meta") or {}
    event = meta.get("event_name", "the final")
    year = meta.get("year", "")
    where = f"{event} {year}".strip()

    if data.get("heats") is not None:
        return _caption_finals_heats(data, where, site_url)

    def _top(rows):
        scored = [r for r in rows or [] if (r.get("best_heat") or 0) > 0]
        if not scored:
            return None
        best = max(scored, key=lambda r: r["best_heat"])
        return f"{best['name']} ({best['best_heat']:.2f})"

    top_man = _top(data.get("men"))
    top_woman = _top(data.get("women"))

    lead_ins = []
    if top_man:
        lead_ins.append(f"Best heat score of the men's finalists: {top_man}.")
    if top_woman:
        lead_ins.append(f"Best of the women's: {top_woman}.")
    leaders = " ".join(lead_ins)

    return (
        f"\U0001f3c1 Finals day at {where}.\n\n"
        f"Four men and four women left. Here is the road to the final: "
        f"best heat score, average counting wave and average counting jump "
        f"from the event so far.\n\n"
        f"{leaders}\n\n"
        f"Who are you backing? Drop your pick below.\n\n"
        f"Full stats → {site_url}"
    )


def _caption_finals_heats(data: dict, where: str, site_url: str) -> str:
    heats = data.get("heats") or []
    riders = sum(len(h.get("athletes") or []) for h in heats)
    division = (data.get("division_label") or "").replace("'S", "").lower()
    who = f"{riders} {division}" if division else str(riders)
    round_name = (heats[0].get("label", "").rsplit(" ", 1)[0].lower() if heats else "heats") or "heats"

    return (
        f"\U0001f3c1 {round_name.title()}s at {where}.\n\n"
        f"{who} riders left, {len(heats)} heats. Swipe for every draw and how "
        f"each rider got here: best heat score, average counting wave and "
        f"average counting jump from the event so far.\n\n"
        f"Who is making the final?\n\n"
        f"Full stats → {site_url}"
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


def _caption_event_picks(data: dict, site_url: str) -> str:
    event = data.get("event", {})
    photo_credit = event.get("photo_credit", "")
    category = event.get("category", "")
    cat_str = f"{category.lower()} " if category else ""
    picks = sorted(data.get("picks", []), key=lambda p: p.get("rank", 0))
    winner = picks[0]["name"] if picks else "?"
    credit_line = f"{photo_credit}\n\n" if photo_credit else ""
    return (
        f"Only hours to go until the event kicks off..\n\n"
        f"This is how we see the {cat_str}fleet playing out.\n\n"
        f"Part data, part gut - swipe to see who we’ve got, from 4 down to our pick to win: "
        f"{winner}.\n\n"
        f"Who are you backing? Drop your top 4 below\n\n"
        f"{credit_line}"
        f"Full stats → {site_url}"
    )


def _caption_freestyle_scores_live(data: dict, site_url: str) -> str:
    return (
        "\U0001f6a8 Windsurf Fantasy League scores are LIVE! \U0001f6a8\n\n"
        "The freestyle results are in from Fuerteventura. See how your picks "
        "stacked up and where you land on the leaderboard.\n\n"
        "How did you do?! \U0001f447\n\n"
        f"\U0001f449 Check your score: link in bio ({site_url})\n\n"
        "⏳ And there's just 1 day left to get your Slalom X team in for "
        "Fuerteventura. Lock is 06:00 local, Wednesday 22 July."
    )


def _caption_slalom_scores_live(data: dict, site_url: str) -> str:
    return (
        "\U0001f6a8 Windsurf Fantasy League scores are LIVE! \U0001f6a8\n\n"
        "The Slalom X results are in from Fuerteventura. See how your picks "
        "stacked up and where you land on the leaderboard.\n\n"
        "How did you do?! \U0001f447\n\n"
        f"\U0001f449 Check your score: link in bio ({site_url})\n\n"
        "\U0001f30a Next up: Tenerife picks are open now, so get your team in "
        "before the wave action starts."
    )


def _caption_wave_scores_live(data: dict, site_url: str) -> str:
    return (
        "\U0001f6a8 Windsurf Fantasy League scores are LIVE! \U0001f6a8\n\n"
        "The wave results are in from Tenerife. See how your picks "
        "stacked up and where you land on the leaderboard.\n\n"
        "How did you do?! \U0001f447\n\n"
        f"\U0001f449 Check your score: link in bio ({site_url})\n\n"
        "\U0001f3c6 Check where you sit in the 2026 season standings."
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
