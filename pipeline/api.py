"""API client for windsurfworldtourstats.com backend."""
import os
from datetime import date

import requests
from dotenv import load_dotenv

from pipeline.helpers import clean_event_name, country_code_to_iso2, full_round_name, heat_label_from_id, nationality_to_iso

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


def fetch_finalist_stats(event_id: int, athlete_ids: list, division: str, detailed: bool = False) -> list:
    """Fetch event-so-far aggregates for a list of finalists, in the given order.

    Uses the head-to-head endpoint rather than the per-athlete stats endpoint:
    H2H is the only one that returns counting averages, and it keeps working
    mid-competition. It compares two riders per call, so the finalists are
    fetched in pairs. An odd finalist is paired with the first rider again and
    only their own side of the response is read.
    """
    ids = list(athlete_ids)
    results = {}

    for i in range(0, len(ids), 2):
        first = ids[i]
        second = ids[i + 1] if i + 1 < len(ids) else ids[0]

        resp = requests.get(
            f"{API_BASE_URL}/events/{event_id}/head-to-head",
            params={
                "athlete1_id": first,
                "athlete2_id": second,
                "division": division,
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()

        for side, athlete_id in (("athlete1", first), ("athlete2", second)):
            if athlete_id in results:
                continue
            results[athlete_id] = _finalist_entry(raw[side], athlete_id, detailed)

    return [results[aid] for aid in ids if aid in results]


def fetch_heat_routes(event_id: int, division: str, before_round: int = None) -> dict:
    """Map each athlete to their most recent sailed heat at this event.

    Returns ``{athlete_id: {"round": ..., "place": ..., "advanced": ...}}``.

    This is how a rider reached the heat they are about to sail. Rounds that
    have not run yet come back from the API with empty athlete lists (the
    draw is not published through this endpoint), so they contribute nothing
    and the latest round a rider appears in is their last outing.

    ``before_round`` ignores that round and everything after it. A recap runs
    once the final has sailed, so without it every finalist's route would read
    "FINAL" -- the heat the viewer just watched, not how they got there.
    """
    resp = requests.get(
        f"{API_BASE_URL}/events/{event_id}/heats",
        params={"sex": division},
        timeout=30,
    )
    resp.raise_for_status()
    raw = resp.json()

    routes = {}
    latest = {}
    for round_ in raw.get("rounds", []):
        order = round_.get("round_order") or 0
        if before_round is not None and order >= before_round:
            continue
        for heat in round_.get("heats", []):
            for athlete in heat.get("athletes", []):
                aid = athlete.get("athlete_id")
                if aid is None or order < latest.get(aid, -1):
                    continue
                latest[aid] = order
                routes[aid] = {
                    "round": round_.get("round_name", ""),
                    "round_order": order,
                    "place": athlete.get("place"),
                    "advanced": athlete.get("advanced"),
                }

    return routes


def _finalist_entry(side: dict, athlete_id: int, detailed: bool = False) -> dict:
    """Flatten one side of an H2H response into a finalist entry.

    The lean form is what the carousel shows. ``detailed`` adds the fields a
    commentator wants but which mislead in a 2x2 grid: heat wins and average
    heat score both scale with how many heats a rider has sailed, so on a
    graphic they read as a ranking. Read aloud with context, they are useful.
    """
    entry = {
        "athlete_id": athlete_id,
        "name": side.get("name", ""),
        "nationality": side.get("nationality", ""),
        "photo_url": side.get("profile_image", "") or "",
        "best_heat": side.get("heat_scores_best"),
        "avg_wave": side.get("waves_avg_counting"),
        "avg_jump": side.get("jumps_avg_counting"),
    }
    if detailed:
        entry.update({
            "heat_wins": side.get("heat_wins"),
            "avg_heat": side.get("heat_scores_avg"),
            "best_wave": side.get("waves_best"),
            "best_jump": side.get("jumps_best"),
        })
    return entry


def fetch_heat_history(event_id: int, division: str, discipline: str = None) -> dict:
    """Every sailed heat per athlete, oldest round first.

    Returns ``{athlete_id: [{"round", "heat", "place", "total", "advanced"}]}``.
    A commentator reads this as the rider's event so far, heat by heat.

    ``discipline`` narrows a Grand Slam to one of the disciplines it ran. This
    endpoint is the one place the filter is honoured -- see
    ``fetch_freestyle_recap`` for the two that quietly are not.
    """
    return _history_from_rounds(_fetch_rounds(event_id, division, discipline))


def _fetch_rounds(event_id: int, division: str, discipline: str = None) -> dict:
    """The raw heats response for one division, optionally one discipline."""
    params = {"sex": division}
    if discipline:
        params["discipline"] = discipline
    resp = requests.get(
        f"{API_BASE_URL}/events/{event_id}/heats",
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _history_from_rounds(raw: dict) -> dict:
    """Flatten a heats response into per-athlete history, oldest round first."""
    history = {}
    for round_ in sorted(raw.get("rounds", []), key=lambda r: r.get("round_order") or 0):
        for heat in sorted(round_.get("heats", []), key=lambda h: h.get("heat_order") or 0):
            for athlete in heat.get("athletes", []):
                aid = athlete.get("athlete_id")
                if aid is None:
                    continue
                history.setdefault(aid, []).append({
                    "round": round_.get("round_name", ""),
                    "heat": heat.get("heat_number", ""),
                    "place": athlete.get("place"),
                    "total": athlete.get("result_total"),
                    "advanced": athlete.get("advanced"),
                    # Individual rides, which carry the jump move names.
                    "scores": athlete.get("scores") or [],
                })

    return history


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

    # Compute avg from counting waves only (waves that contributed to a heat score)
    wave_scores = raw.get("wave_scores", [])
    counting_waves = [w["score"] for w in wave_scores if w.get("counting")]
    avg_wave = round(sum(counting_waves) / len(counting_waves), 2) if counting_waves else 0.0

    # Top 5 waves sorted desc
    sorted_waves = sorted(wave_scores, key=lambda w: w["score"], reverse=True)[:5]
    top_waves = [
        {"rank": i + 1, "score": w["score"], "round": full_round_name(w.get("round") or w.get("round_name", ""))}
        for i, w in enumerate(sorted_waves)
    ]

    # Top 5 jumps sorted desc (if available)
    jump_scores = raw.get("jump_scores", [])
    sorted_jumps = sorted(jump_scores, key=lambda j: j["score"], reverse=True)[:5]
    top_jumps = [
        {
            "rank": i + 1,
            "score": j["score"],
            "round": full_round_name(j.get("round") or j.get("round_name", "")),
            "move": j.get("move", ""),
        }
        for i, j in enumerate(sorted_jumps)
    ]

    # Extract best heat — handle both "best_heat" and "best_heat_score" keys
    best_heat_obj = summary.get("best_heat") or summary.get("best_heat_score", {})
    best_heat = best_heat_obj.get("score", 0)
    best_heat_round = full_round_name(best_heat_obj.get("round") or best_heat_obj.get("round_name", ""))

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
        "event_id": event_id,
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
            # The API returns it on the score row and it used to be dropped
            # here. Photo mode resolves a rider's hero shot from it, and
            # pick_photos finds their candidate frames; table slides ignore it.
            "athlete_id": r.get("athlete_id"),
            "country": nationality_to_iso(country_map.get(r.get("athlete_id"), "")),
            "score": float(r.get("score", 0)),
            "event": event_name,
            "round": r.get("round_name", ""),
            "heat": heat_label_from_id(heat_id) if heat_id else "",
            # Non-counting rows render dimmed with a footnote. carousel.py reads
            # a missing key as counting, so an absent flag has to become 1 here
            # rather than being left out.
            "counting": int(bool(r.get("counting", True))),
        }
        if is_jump:
            entry["trick_type"] = r.get("move_type", "")
            # Tweaked / 1-Foot / 1-Hand. `or ""` because the API sends null for
            # an unmodified jump, and the template tests the value directly.
            entry["modifier"] = r.get("move_variation") or ""
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
        # Normalize metric name: API has used both "total_events" and
        # "total events" (spaces) over time. Collapse to underscore form.
        metric = str(item["metric"]).strip().lower().replace(" ", "_")
        template_key = metric_map.get(metric)
        if template_key:
            result[template_key] = int(item["value"])

    # Guard: never return all-zero/empty stats — that publishes a broken
    # "0 athletes. 0 scores. 0 events." post. Fail loudly instead.
    missing = [k for k in metric_map.values() if not result.get(k)]
    if missing:
        raise ValueError(
            f"Site stats API returned no usable values for {missing}. "
            f"Raw metrics: {[i['metric'] for i in raw['stats']]}"
        )

    return result


def _wave_heats(raw: dict) -> list:
    """Every heat carrying a wave score, ordered as they were sailed.

    The score type is what separates the disciplines; the round name is not.
    A Grand Slam runs wave, freestyle and slalom under one event and names a
    round "Final" in each: Sylt 2017 has four of them, and Sylt 2018 calls the
    men's wave final "Round 6". What does hold is the shape of the scores --
    a wave heat carries ``Wave`` alongside jump move codes (``B ``, ``2xF``),
    a freestyle heat carries ``Freestyle``, and a slalom heat carries none.

    Returns ``[(round_order, heat_order, round, heat), ...]``.
    """
    found = []
    for round_ in raw.get("rounds", []):
        for heat in round_.get("heats") or []:
            athletes = heat.get("athletes") or []
            if any((score.get("type") or "").strip().lower() == "wave"
                   for athlete in athletes
                   for score in (athlete.get("scores") or [])):
                found.append((round_.get("round_order") or 0,
                              heat.get("heat_order") or 0, round_, heat))
    found.sort(key=lambda item: item[:2])
    return found


def _wave_depth(candidates: list) -> dict:
    """How far each rider got in the wave ladder.

    ``{athlete_id: (last_round_order, place_in_that_heat)}``, counting only
    riders who scored a wave themselves rather than everyone who appears in a
    heat that carried one.

    It is a cross-check on ``overall_position``, which cannot be trusted on
    its own: a rider entering two disciplines gets one row from the athletes
    endpoint and the position on it is not necessarily the wave one. Gollito
    Estredo sailed both at Sylt 2018, went out in round 2 of the wave, and
    still comes back as ``overall_position`` 1 -- his freestyle win.
    """
    depth = {}
    for round_order, _heat_order, _round, heat in candidates:
        for athlete in heat.get("athletes") or []:
            athlete_id = athlete.get("athlete_id")
            if athlete_id is None:
                continue
            if not any((score.get("type") or "").strip().lower() == "wave"
                       for score in (athlete.get("scores") or [])):
                continue
            previous = depth.get(athlete_id)
            if previous is None or round_order >= previous[0]:
                depth[athlete_id] = (round_order, athlete.get("place") or 99)
    return depth


def _wave_finishers(event_id: int, division: str, candidates: list) -> list:
    """The event's wave riders in finishing order.

    Ordered on ``overall_position``, restricted to riders who actually scored
    a wave. That restriction is what separates the disciplines: the athletes
    endpoint returns every entrant, so at a Grand Slam several riders share
    position 1, one per discipline.

    Ladder depth only breaks ties here. It deliberately does not lead: at an
    event whose double elimination was abandoned part-run, the last wave heat
    sailed is not the final, and ordering on depth would rank whoever sailed
    it above the winner.
    """
    resp = requests.get(
        f"{API_BASE_URL}/events/{event_id}/athletes",
        params={"sex": division},
        timeout=30,
    )
    resp.raise_for_status()

    depth = _wave_depth(candidates)
    riders = [a for a in resp.json().get("athletes", [])
              if a.get("athlete_id") in depth]
    riders.sort(key=lambda a: (a.get("overall_position") or 99,
                               -depth[a["athlete_id"]][0]))
    return riders


def _warn_shallow(riders: list, depth: dict) -> None:
    """Say so when a rider's placing and their ladder run disagree.

    A rider placed in the top few who went out well before the others did is
    the shape of a position borrowed from another discipline. It cannot be
    corrected from this data -- the endpoint gives one position per rider --
    but it can be made visible instead of silently wrong.
    """
    reached = [depth[r["athlete_id"]][0] for r in riders if r["athlete_id"] in depth]
    if not reached:
        return
    deepest = max(reached)
    for rider in riders:
        if depth.get(rider["athlete_id"], (deepest,))[0] < deepest:
            print(f"  WARNING: {rider.get('name', '?')} is placed "
                  f"{rider.get('overall_position')} but went out earlier than "
                  "the others in the wave ladder. Check the placing: it may "
                  "belong to another discipline.")


def _wave_event(event_id: int, division: str):
    """The event's wave heats and its wave finishing order, or raise.

    Both placings and the final are read off the same two calls, so they are
    fetched together.
    """
    resp = requests.get(
        f"{API_BASE_URL}/events/{event_id}/heats",
        params={"sex": division},
        timeout=30,
    )
    resp.raise_for_status()

    candidates = _wave_heats(resp.json())
    if not candidates:
        raise ValueError(
            f"No wave heat found for event {event_id} ({division}): not one "
            "heat came back carrying a wave score. Either the event ran no "
            "wave discipline, or its scores are missing from the API (Sylt "
            "2024 is one such event)."
        )

    return candidates, _wave_finishers(event_id, division, candidates)


def fetch_final_heat(event_id: int, division: str) -> dict:
    """Fetch the final heat itself: who placed where, and every score in it.

    Returns ``{"round_order": int, "riders": [...]}`` with riders in finishing
    order. Each rider carries ``place``, ``final_total`` and the heat's own
    scores split into ``final_waves`` / ``final_jumps``.

    This is the one heat those riders sailed together, which is what makes it
    the only like-for-like comparison after an event. Event-wide aggregates
    come from the head-to-head endpoint instead (``fetch_finalist_stats``);
    this endpoint is the only one carrying per-heat scores.

    The heat is found by shape, not by round name -- see ``_wave_heats``. Of
    the wave heats, the final is the last one the event's top two finishers
    sailed together. Simply taking the last wave heat is wrong: an unfinished
    double elimination leaves later heats behind the final, which is how the
    Sylt 2018 women's recap would otherwise be built from Huvermann against
    Sniady rather than Offringa against Iballa Ruano Moreno.

    Note that a man-on-man event puts two riders in this heat, not four:
    third and fourth sailed a separate heat and are not in the result.

    Non-counting scores are kept. A rider's highest wave in the final is the
    highest they scored, whether or not it made their counting total -- the
    same default the top 10 posts use.
    """
    candidates, finishers = _wave_event(event_id, division)
    podium = [rider["athlete_id"] for rider in finishers[:2]]

    # The top two, then the winner alone, then whatever sailed last: enough to
    # stay right on an event whose placings are missing or tied.
    chosen = candidates[-1]
    for wanted in ({*podium}, {*podium[:1]}):
        if not wanted:
            continue
        matches = [c for c in candidates
                   if wanted <= {a.get("athlete_id")
                                 for a in (c[3].get("athletes") or [])}]
        if matches:
            chosen = matches[-1]
            break

    round_, heat = chosen[2], chosen[3]
    # A wrong pick used to be invisible -- it renders as a normal carousel with
    # the wrong riders -- so say which heat this was built from.
    print(f"  final heat: round {round_.get('round_name', '?')!r} "
          f"heat {heat.get('heat_number', '?')}, "
          f"{len(heat.get('athletes') or [])} riders")

    riders = []
    for athlete in heat.get("athletes") or []:
        waves, jumps = [], []
        best_jump, best_jump_move = 0.0, ""
        for score in athlete.get("scores") or []:
            value = score.get("score")
            if value is None:
                continue
            if (score.get("type") or "").strip().lower() == "wave":
                waves.append(float(value))
                continue
            jumps.append(float(value))
            # The move name is half the story of a jump score, so the
            # best one's move is carried alongside the number.
            if float(value) > best_jump:
                best_jump = float(value)
                best_jump_move = score.get("move_type") or score.get("type") or ""

        riders.append({
            "athlete_id": athlete.get("athlete_id"),
            "name": athlete.get("athlete_name", ""),
            "photo_url": athlete.get("profile_picture_url", "") or "",
            "place": athlete.get("place"),
            "final_total": athlete.get("result_total"),
            "final_waves": sorted(waves, reverse=True),
            "final_jumps": sorted(jumps, reverse=True),
            "final_best_jump_move": best_jump_move,
        })

    riders.sort(key=lambda r: r.get("place") or 99)
    return {"round_order": round_.get("round_order") or 0, "riders": riders}


def fetch_top_finishers(event_id: int, division: str, top: int = 4) -> list:
    """The event's top ``top`` wave riders, by finishing position.

    A placings post is not a recap: it does not care which heat anyone sailed.
    That matters wherever the final is man-on-man -- at Sylt third and fourth
    never shared water with the winner, so ``fetch_final_heat`` can only ever
    return two of them.

    Each entry carries ``place``, ``name``, ``nationality``, ``sail_number``
    and ``photo_url``. Per-rider stats come from ``fetch_finalist_stats``.
    """
    candidates, finishers = _wave_event(event_id, division)
    top_riders = finishers[:top]
    _warn_shallow(top_riders, _wave_depth(candidates))

    return [{
        "athlete_id": rider.get("athlete_id"),
        "name": rider.get("name", ""),
        "nationality": rider.get("country", ""),
        "sail_number": rider.get("sail_number", ""),
        "photo_url": rider.get("profile_image", "") or "",
        "place": rider.get("overall_position"),
    } for rider in top_riders]


FREESTYLE = "Freestyle"


def fetch_freestyle_recap(event_id: int, division: str, top: int = 4) -> dict:
    """A freestyle event's top riders, with everything the recap needs.

    Returns ``{"round_order": int, "riders": [...]}``, the contract
    ``fetch_final_heat`` has, except that each rider already carries their
    event aggregates instead of them being fetched separately.

    That difference is forced rather than chosen. The wave recap reads its
    aggregates from the head-to-head endpoint, which accepts a ``discipline``
    parameter and ignores it: ask it for Lennart Neubauer's freestyle stats at
    Sylt 2025 and it answers with his wave stats, 25th off a best heat of
    6.63, with a 200 and no warning, where his freestyle event was a win off a
    best heat of 48.20. The athletes endpoint has the same split personality:
    its ``overall_position`` does respect the discipline, the score fields
    beside it do not. Neither failure is visible in the response, which is why
    this path takes nothing from either.

    The heats endpoint does filter properly, and it carries every move with
    its score, name and counting flag, which is enough to derive the lot.
    """
    raw = _fetch_rounds(event_id, division, FREESTYLE)
    history = _history_from_rounds(raw)
    if not history:
        raise ValueError(
            f"No freestyle heats for event {event_id} ({division}): not one "
            "heat came back. Either the event ran no freestyle discipline, or "
            "its scores are missing from the API."
        )

    finishers = _freestyle_finishers(event_id, division, history)[:top]
    podium = [f["athlete_id"] for f in finishers[:2]]
    final_round, final_heat = _freestyle_final(raw, podium)
    sailed_final = {a.get("athlete_id"): a for a in (final_heat.get("athletes") or [])}

    # The wave path prints the heat it built from, because picking the wrong
    # one renders as a normal carousel with the wrong riders in it.
    print(f"  final heat: round {final_round.get('round_name', '?')!r} "
          f"heat {final_heat.get('heat_number', '?')}, "
          f"{len(sailed_final)} riders")

    riders = []
    for finisher in finishers:
        entries = history.get(finisher["athlete_id"]) or []
        riders.append({
            **finisher,
            **_freestyle_aggregates(entries),
            **_freestyle_final_scores(sailed_final.get(finisher["athlete_id"])),
            "history": entries,
        })

    return {"round_order": final_round.get("round_order") or 0, "riders": riders}


def _freestyle_finishers(event_id: int, division: str, history: dict) -> list:
    """The freestyle fleet in finishing order.

    ``overall_position`` is the one field on this endpoint that is genuinely
    per discipline, so it is the placing to trust. It is still restricted to
    riders who sailed a freestyle heat: at a Grand Slam an entrant carries a
    position whether or not they entered this discipline.
    """
    resp = requests.get(
        f"{API_BASE_URL}/events/{event_id}/athletes",
        params={"sex": division, "discipline": FREESTYLE},
        timeout=30,
    )
    resp.raise_for_status()

    riders = [a for a in resp.json().get("athletes", [])
              if a.get("athlete_id") in history]
    riders.sort(key=lambda a: a.get("overall_position") or 99)

    return [{
        "athlete_id": rider.get("athlete_id"),
        "name": rider.get("name", ""),
        "nationality": rider.get("country", ""),
        "sail_number": rider.get("sail_number", ""),
        "photo_url": rider.get("profile_image", "") or "",
        "place": rider.get("overall_position"),
    } for rider in riders]


def _freestyle_final(raw: dict, podium: list) -> tuple:
    """The heat the winner and runner-up sailed, and the round holding it.

    A freestyle ladder settles third against fourth in a heat of its own,
    which runs in the same round as the final: at Sylt 2025 both 16a and 17a
    are in round "Final". Taking the round's last heat would therefore be a
    coin toss between them, so the final is identified as the heat holding the
    top two finishers.
    """
    rounds = sorted(raw.get("rounds", []), key=lambda r: r.get("round_order") or 0)
    wanted = {aid for aid in podium if aid}

    for round_ in reversed(rounds):
        heats = sorted(round_.get("heats", []), key=lambda h: h.get("heat_order") or 0)
        for heat in reversed(heats):
            ids = {a.get("athlete_id") for a in (heat.get("athletes") or [])}
            if wanted and wanted <= ids:
                return round_, heat

    # No heat held both, which means the placings and the ladder disagree.
    # The last heat sailed is the best guess left, and the caller prints it.
    last = rounds[-1] if rounds else {}
    heats = sorted(last.get("heats", []), key=lambda h: h.get("heat_order") or 0)
    return last, (heats[-1] if heats else {})


def _freestyle_aggregates(entries: list) -> dict:
    """One rider's freestyle event, reduced to the five numbers on their card.

    Bests are the highest scored, counting or not, which is the default the
    top 10 posts use. The average is over counting moves only, which is what
    the wave recap's averages mean, so the two carousels say the same thing by
    the same rule.
    """
    totals = [float(e["total"]) for e in entries if e.get("total") is not None]
    moves = [s for e in entries for s in (e.get("scores") or [])
             if s.get("score") is not None]
    counting = [float(s["score"]) for s in moves if s.get("counting")]

    return {
        "best_heat": max(totals, default=None),
        "avg_heat": round(sum(totals) / len(totals), 2) if totals else None,
        "heat_wins": sum(1 for e in entries if e.get("place") == 1),
        "best_move": max((float(s["score"]) for s in moves), default=None),
        "avg_move": round(sum(counting) / len(counting), 2) if counting else None,
    }


def _freestyle_final_scores(athlete: dict) -> dict:
    """A rider's scores in the final, or the empty shape where they missed it.

    Third and fourth sailed each other, so they have no final score. That
    absence is exactly what tells the carousel the final was man on man, and
    it is the shape ``fetch_final_heat`` already leaves behind for them.
    """
    if not athlete:
        return {"final_total": None, "final_moves": [], "final_best_move": ""}

    moves, best, best_move = [], 0.0, ""
    for score in athlete.get("scores") or []:
        value = score.get("score")
        if value is None:
            continue
        moves.append(float(value))
        if float(value) > best:
            best, best_move = float(value), score.get("move_type") or ""

    return {
        "final_total": athlete.get("result_total"),
        "final_moves": sorted(moves, reverse=True),
        "final_best_move": best_move,
    }
