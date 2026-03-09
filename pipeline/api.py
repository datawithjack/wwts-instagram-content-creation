"""API client for windsurfworldtourstats.com backend."""
import os
from datetime import date

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "https://api.windsurfworldtourstats.com/api/v1")


def fetch_event(event_id: int) -> dict:
    """Fetch event details from API."""
    url = f"{API_BASE_URL}/events/{event_id}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_head_to_head(
    event_id: int,
    athlete1_id: int,
    athlete2_id: int,
    division: str,
) -> dict:
    """Fetch head-to-head comparison from API and flatten into template data."""
    from pipeline.helpers import nationality_to_iso, clean_event_name

    url = f"{API_BASE_URL}/events/{event_id}/head-to-head"
    resp = requests.get(
        url,
        params={
            "athlete1_id": athlete1_id,
            "athlete2_id": athlete2_id,
            "division": division,
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw = resp.json()

    # Also fetch event details for dates, tier, country
    event = fetch_event(event_id)

    data = {
        "event_name": clean_event_name(raw["event_name"]),
        "event_id": raw["event_id"],
        "division": raw.get("division", division),
        "event_country": event.get("country_code", ""),
        "event_tier": event.get("stars", 0),
    }

    # Parse dates from event API
    for date_key, template_key in [("start_date", "event_date_start"), ("end_date", "event_date_end")]:
        raw_date = event.get(date_key)
        if raw_date:
            data[template_key] = date.fromisoformat(str(raw_date))

    for side, key in [("athlete1", "athlete_1"), ("athlete2", "athlete_2")]:
        a = raw[side]
        data[f"{key}_name"] = a["name"]
        data[f"{key}_photo_url"] = a.get("profile_image", "")
        data[f"{key}_country"] = nationality_to_iso(a.get("nationality", ""))
        data[f"{key}_placement"] = a["place"]
        data[f"{key}_heat_wins"] = a["heat_wins"]
        data[f"{key}_best_heat"] = a["heat_scores_best"]
        data[f"{key}_avg_heat"] = a["heat_scores_avg"]
        data[f"{key}_best_wave"] = a["waves_best"]
        data[f"{key}_avg_wave"] = a["waves_avg_counting"]

        if a.get("jumps_best") is not None:
            data[f"{key}_best_jump"] = a["jumps_best"]
            data[f"{key}_avg_jump"] = a["jumps_avg_counting"]

    # Use pre-computed comparison from API for deltas
    comparison = raw.get("comparison", {})
    for metric, delta_key in [
        ("heat_scores_best", "delta_best_heat"),
        ("heat_scores_avg", "delta_avg_heat"),
        ("waves_best", "delta_best_wave"),
        ("waves_avg_counting", "delta_avg_wave"),
        ("jumps_best", "delta_best_jump"),
        ("jumps_avg_counting", "delta_avg_jump"),
    ]:
        comp = comparison.get(metric)
        if comp:
            # difference is always positive; sign depends on winner
            diff = comp["difference"]
            if comp["winner"] == "athlete1":
                data[delta_key] = -diff  # athlete2 - athlete1 is negative
            elif comp["winner"] == "athlete2":
                data[delta_key] = diff
            else:
                data[delta_key] = 0.0

    return data


def fetch_athlete_event_stats(event_id: int, athlete_id: int, division: str) -> dict:
    """Fetch single athlete's stats at an event and flatten into template data."""
    url = f"{API_BASE_URL}/events/{event_id}/athletes/{athlete_id}/stats"
    resp = requests.get(url, params={"sex": division}, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    event = fetch_event(event_id)

    athlete = raw["athlete"]
    summary = raw["summary"]

    # Compute avg wave from all wave scores
    wave_scores = raw.get("wave_scores", [])
    avg_wave = round(sum(w["score"] for w in wave_scores) / len(wave_scores), 2) if wave_scores else 0.0

    # Top 5 waves (already sorted desc from API)
    top_waves = [
        {"rank": i + 1, "score": w["score"], "round": w["round"]}
        for i, w in enumerate(wave_scores[:5])
    ]

    data = {
        "athlete_name": athlete["name"],
        "athlete_country": athlete["country_code"],
        "athlete_photo_url": athlete.get("profile_image", ""),
        "athlete_sail_number": athlete.get("sail_number", ""),
        "event_name": raw["event_name"],
        "event_country": event.get("country_code", ""),
        "event_tier": event.get("stars", 0),
        "placement": athlete["overall_position"],
        "best_heat": summary["best_heat"]["score"],
        "best_heat_round": summary["best_heat"]["round"],
        "best_wave": summary["best_wave"],
        "best_jump": summary.get("best_jump"),
        "avg_wave": avg_wave,
        "top_waves": top_waves,
    }

    for date_key, template_key in [("start_date", "event_date_start"), ("end_date", "event_date_end")]:
        raw_date = event.get(date_key)
        if raw_date:
            data[template_key] = date.fromisoformat(str(raw_date))

    return data


def fetch_event_top_scores(event_id: int, score_type: str, sex: str = None) -> dict:
    """Fetch top 10 scores for an event from the event stats API.

    Args:
        event_id: API event ID (not DB event_id)
        score_type: "Wave" or "Jump"
        sex: "Men" or "Women" (optional, defaults to API default)

    Returns:
        Template-ready dict with title fields and entries list.
    """
    from pipeline.helpers import nationality_to_iso, clean_event_name

    params = {}
    if sex:
        params["sex"] = sex

    # Fetch event stats (includes top_jump_scores and top_wave_scores)
    url = f"{API_BASE_URL}/events/{event_id}/stats"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    stats = resp.json()

    # Fetch athletes for country info
    athletes_url = f"{API_BASE_URL}/events/{event_id}/athletes"
    athletes_resp = requests.get(athletes_url, params=params, timeout=30)
    athletes_resp.raise_for_status()
    athletes_by_id = {
        a["athlete_id"]: a
        for a in athletes_resp.json().get("athletes", [])
    }

    # Select the right scores list
    scores_key = "top_jump_scores" if score_type == "Jump" else "top_wave_scores"
    raw_scores = stats.get(scores_key, [])[:10]

    is_jump = score_type == "Jump"
    gender_map = {"Men": "Men's", "Women": "Women's"}

    entries = []
    for i, s in enumerate(raw_scores):
        athlete = athletes_by_id.get(s["athlete_id"], {})
        country = nationality_to_iso(athlete.get("country", ""))
        entry = {
            "rank": i + 1,
            "athlete": s["athlete_name"],
            "country": country,
            "score": float(s["score"]),
            "event": clean_event_name(stats.get("event_name", "")),
            "round": s.get("round_name", ""),
            "heat": s.get("heat_number", ""),
        }
        if is_jump:
            entry["trick_type"] = s.get("move_type", "")
        entries.append(entry)

    # Fetch event details for header
    event = fetch_event(event_id)
    event_name_clean = clean_event_name(stats.get("event_name", ""))

    data = {
        "title_gender": gender_map.get(sex, ""),
        "title_metric": f"{score_type}s",
        "title_year": event_name_clean,
        "show_trick_type": is_jump,
        "entries": entries,
        "is_per_event": True,
        "event_name": event_name_clean,
        "event_country": event.get("country_code", ""),
        "event_tier": event.get("stars", 0),
    }

    for date_key, template_key in [("start_date", "event_date_start"), ("end_date", "event_date_end")]:
        raw_date = event.get(date_key)
        if raw_date:
            data[template_key] = date.fromisoformat(str(raw_date))

    return data


def fetch_site_stats() -> dict:
    """Fetch site-wide statistics from API."""
    url = f"{API_BASE_URL}/stats"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    metric_map = {
        "total events": "events_count",
        "total athletes": "athletes_count",
        "total scores": "scores_count",
    }

    result = {}
    for item in raw["stats"]:
        template_key = metric_map.get(item["metric"])
        if template_key:
            result[template_key] = int(item["value"])

    return result
