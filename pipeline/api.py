"""API client for windsurfworldtourstats.com backend."""
import os
from datetime import date

import requests
from dotenv import load_dotenv

from pipeline.helpers import clean_event_name, country_code_to_iso2, heat_label_from_id, nationality_to_iso

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
        "event_name": raw["event_name"],
        "event_id": raw["event_id"],
        "event_country": event.get("country_code", ""),
        "event_tier": event.get("stars", 0),
    }

    # Parse dates from event API
    for date_key, template_key in [("start_date", "event_date_start"), ("end_date", "event_date_end")]:
        raw_date = event.get(date_key)
        if raw_date:
            data[template_key] = date.fromisoformat(str(raw_date))

    data["athlete_1_id"] = athlete1_id
    data["athlete_2_id"] = athlete2_id

    for side, key in [("athlete1", "athlete_1"), ("athlete2", "athlete_2")]:
        a = raw[side]
        data[f"{key}_name"] = a["name"]
        data[f"{key}_photo_url"] = a.get("profile_image", "")
        data[f"{key}_placement"] = a["place"]
        data[f"{key}_heat_wins"] = a["heat_wins"]
        data[f"{key}_best_heat"] = a["heat_scores_best"]
        data[f"{key}_avg_heat"] = a["heat_scores_avg"]
        data[f"{key}_best_wave"] = a["waves_best"]
        data[f"{key}_avg_wave"] = a["waves_avg_counting"]

        if a.get("jumps_best") is not None:
            data[f"{key}_best_jump"] = a["jumps_best"]
            data[f"{key}_avg_jump"] = a["jumps_avg_counting"]

    return data


def fetch_athlete_event_stats(event_id: int, athlete_id: int, division: str) -> dict:
    """Fetch single athlete's stats at an event and flatten into template data."""
    url = f"{API_BASE_URL}/events/{event_id}/athletes/{athlete_id}/stats"
    resp = requests.get(url, params={"sex": division}, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    event = fetch_event(event_id)

    # Support both old ("athlete"/"summary") and new ("profile"/"summary_stats") API shapes
    athlete = raw.get("athlete") or raw.get("profile", {})
    summary = raw.get("summary") or raw.get("summary_stats", {})

    # Compute avg wave from all wave scores
    wave_scores = raw.get("wave_scores", [])
    avg_wave = round(sum(w["score"] for w in wave_scores) / len(wave_scores), 2) if wave_scores else 0.0

    # Top 5 waves sorted desc
    sorted_waves = sorted(wave_scores, key=lambda w: w["score"], reverse=True)[:5]
    top_waves = [
        {"rank": i + 1, "score": w["score"], "round": w.get("round") or w.get("round_name", "")}
        for i, w in enumerate(sorted_waves)
    ]

    # Top 5 jumps sorted desc (if available)
    jump_scores = raw.get("jump_scores", [])
    sorted_jumps = sorted(jump_scores, key=lambda j: j["score"], reverse=True)[:5]
    top_jumps = [
        {
            "rank": i + 1,
            "score": j["score"],
            "round": j.get("round") or j.get("round_name", ""),
            "move": j.get("move", ""),
        }
        for i, j in enumerate(sorted_jumps)
    ]

    # Extract best heat — handle both "best_heat" and "best_heat_score" keys
    best_heat_obj = summary.get("best_heat") or summary.get("best_heat_score", {})
    best_heat = best_heat_obj.get("score", 0)
    best_heat_round = best_heat_obj.get("round") or best_heat_obj.get("round_name", "")

    # Extract best wave — either a bare number or nested object
    best_wave_raw = summary.get("best_wave") or summary.get("best_wave_score", {})
    best_wave = best_wave_raw["score"] if isinstance(best_wave_raw, dict) else best_wave_raw

    # Extract best jump — either a bare number or nested object
    best_jump_raw = summary.get("best_jump") or summary.get("best_jump_score")
    if isinstance(best_jump_raw, dict):
        best_jump = best_jump_raw.get("score")
    else:
        best_jump = best_jump_raw

    data = {
        "athlete_id": athlete_id,
        "athlete_name": athlete.get("name", ""),
        "athlete_country": nationality_to_iso(athlete.get("country", "")) or athlete.get("country_code", ""),
        "athlete_photo_url": athlete.get("profile_image", ""),
        "athlete_sail_number": athlete.get("sail_number", ""),
        "event_name": clean_event_name(raw["event_name"]),
        "event_country": event.get("country_code", ""),
        "event_tier": event.get("stars", 0),
        "placement": athlete.get("overall_position") or summary.get("overall_position", 0),
        "best_heat": best_heat,
        "best_heat_round": best_heat_round,
        "best_wave": best_wave,
        "best_jump": best_jump,
        "avg_wave": avg_wave,
        "top_waves": top_waves,
        "top_jumps": top_jumps if top_jumps else None,
    }

    for date_key, template_key in [("start_date", "event_date_start"), ("end_date", "event_date_end")]:
        raw_date = event.get(date_key)
        if raw_date:
            data[template_key] = date.fromisoformat(str(raw_date))

    return data


def fetch_event_top_scores(event_id: int, score_type: str, sex: str = None, limit: int = 10) -> dict:
    """Fetch top scores for a specific event from the /events/{id}/stats API.

    Uses top_wave_scores or top_jump_scores from the event stats endpoint,
    enriched with country codes from the athletes endpoint.
    """
    # Fetch event stats
    stats_params = {}
    if sex:
        stats_params["sex"] = sex
    stats_resp = requests.get(
        f"{API_BASE_URL}/events/{event_id}/stats",
        params=stats_params,
        timeout=30,
    )
    stats_resp.raise_for_status()
    stats = stats_resp.json()

    # Pick the right score list
    score_key = "top_jump_scores" if score_type == "Jump" else "top_wave_scores"
    all_scores = stats.get(score_key, [])

    # Build athlete_id -> country map from athletes endpoint
    # Note: country_code field returns event country (bug), so use "country" (full name)
    athletes_resp = requests.get(
        f"{API_BASE_URL}/events/{event_id}/athletes",
        params=stats_params,
        timeout=30,
    )
    country_map = {}
    if athletes_resp.ok:
        for a in athletes_resp.json().get("athletes", []):
            country_map[a["athlete_id"]] = a.get("country", "")

    event = fetch_event(event_id)
    event_name = clean_event_name(stats.get("event_name", ""))
    gender_map = {"Men": "Men's", "Women": "Women's"}
    is_jump = score_type == "Jump"

    entries = []
    for i, r in enumerate(all_scores[:limit]):
        heat_id = r.get("heat_id", "")
        entry = {
            "rank": i + 1,
            "athlete": r.get("athlete_name", ""),
            "country": nationality_to_iso(country_map.get(r.get("athlete_id"), "")),
            "score": float(r.get("score", 0)),
            "event": event_name,
            "round": r.get("round_name", ""),
            "heat": heat_label_from_id(heat_id) if heat_id else "",
        }
        if is_jump:
            entry["trick_type"] = r.get("move_type", "")
        entries.append(entry)

    # Event metadata for cover slide
    event_data = {
        "event_country": event.get("country_code", ""),
        "event_stars": event.get("stars", 0),
    }
    start = event.get("start_date")
    end = event.get("end_date")
    if start:
        event_data["event_date_start"] = date.fromisoformat(str(start)).strftime("%b %d")
    if end:
        event_data["event_date_end"] = date.fromisoformat(str(end)).strftime("%b %d")

    return {
        "title_gender": gender_map.get(sex, ""),
        "title_metric": f"{score_type}s",
        "title_year": event.get("year", ""),
        "show_trick_type": is_jump,
        "is_per_event": True,
        "event_name": event_name,
        **event_data,
        "entries": entries,
    }


def fetch_site_stats() -> dict:
    """Fetch site-wide statistics from API."""
    url = f"{API_BASE_URL}/stats"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    metric_map = {
        "total_events": "events_count",
        "total_athletes": "athletes_count",
        "total_scores": "scores_count",
    }

    result = {}
    for item in raw["stats"]:
        template_key = metric_map.get(item["metric"])
        if template_key:
            result[template_key] = int(item["value"])

    return result
