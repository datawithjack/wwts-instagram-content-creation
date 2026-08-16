"""Main entry point for Instagram content generation pipeline."""
import argparse
import os
import sys
import webbrowser
import tempfile
from datetime import datetime

import yaml
from dotenv import load_dotenv

load_dotenv()

from pipeline.api import fetch_head_to_head, fetch_site_stats, fetch_athlete_event_stats, fetch_event_top_scores, fetch_finalist_stats, fetch_heat_routes, fetch_heat_history, fetch_event, fetch_final_heat
from pipeline.captions import build_caption
from pipeline.db import run_query
from pipeline.helpers import nationality_to_iso, clean_event_name, heat_label_from_id, short_round_name, full_round_name
from pipeline.queries import build_top10_query, build_canary_kings_query, build_athlete_rise_query, build_wave_count_query, build_fantasy_mvp_points_query, build_fantasy_session_pick_pct_query
from pipeline.templates import render_template, get_dummy_data, resolve_action_url, resolve_hero_url, resolve_hero_focus, resolve_photo_credit
from pipeline.renderer import render_to_png, render_to_video, render_carousel, render_h2h_carousel, render_rp_carousel, render_analysis_carousel, render_athlete_rise_carousel, render_picks_carousel, render_wave_count_carousel, render_fuerte_fantasy_mvps_carousel, render_slalom_mvps_carousel, render_finals_preview_carousel, render_finals_recap_carousel


def fetch_live_data(template_name: str, args) -> dict:
    """Fetch live data from API or DB based on template type."""
    if template_name == "tour_availability_reel":
        from pipeline.tour_availability import build_tour_availability_live
        return build_tour_availability_live()

    if template_name in ("head_to_head", "head_to_head_jump", "h2h_carousel"):
        if not all([args.event, args.athlete1, args.athlete2, args.division]):
            print("H2H requires: --event, --athlete1, --athlete2, --division")
            sys.exit(1)
        return fetch_head_to_head(
            event_id=args.event,
            athlete1_id=args.athlete1,
            athlete2_id=args.athlete2,
            division=args.division,
        )

    if template_name in ("top_10", "top_10_carousel"):
        # Perfect-10s mode: bespoke query, mixed gender, 12 entries
        if getattr(args, "mode", None) == "perfect-10s":
            from pipeline.queries import build_perfect_10s_wave_query
            sql, params = build_perfect_10s_wave_query()
            rows = run_query(sql, params)
            entries = []
            for i, r in enumerate(rows):
                elim = (r.get("elimination_name") or "").lower()
                if elim.startswith("mens"):
                    sex = "M"
                elif elim.startswith("womens"):
                    sex = "W"
                else:
                    sex = ""
                entries.append({
                    "rank": i + 1,
                    "athlete": r["athlete"],
                    "country": nationality_to_iso(r.get("country", "")),
                    "score": float(r["score"]),
                    "year": int(r["year"]),
                    "event": clean_event_name(r["event"]),
                    "round": short_round_name(r.get("round", "")),
                    "heat": heat_label_from_id(r.get("heat_id", "")),
                    "sex": sex,
                })
            return {
                "title_gender": "",
                "title_metric": "Waves",
                "title_year": "All Time",
                "show_trick_type": False,
                "is_per_event": False,
                "perfect_10s_mode": True,
                "custom_title": "EVERY PERFECT 10 WAVE",
                "custom_subtitle": "",
                "entries": entries,
            }

        if not args.score_type:
            print("Top 10 requires: --score-type (Wave or Jump)")
            sys.exit(1)

        # Use API for per-event top 10; fall back to DB if API 404s.
        # Jumps skip the API and go straight to the DB — only the DB carries
        # the trick modifier (1-Foot, 1-Hand, Tweaked). For per-event jumps
        # --event is therefore the DB pwa_event_id, not the API event id.
        if args.event and args.score_type != "Jump":
            try:
                return fetch_event_top_scores(
                    event_id=args.event,
                    score_type=args.score_type,
                    sex=args.sex,
                )
            except Exception:
                print("API per-event endpoint unavailable, falling back to DB...")

        # Use DB for queries (per-event, by year, or all-time)
        rounds_list = [r.strip() for r in args.rounds.split(",")] if getattr(args, "rounds", None) else None
        sql, params = build_top10_query(
            score_type=args.score_type,
            sex=args.sex,
            year=args.year,
            event_id=args.event,
            rounds=rounds_list,
            include_non_counting=not getattr(args, "counting_only", False),
        )
        rows = run_query(sql, params)
        gender_map = {"Men": "Men's", "Women": "Women's"}
        is_jump = args.score_type == "Jump"
        is_per_event = bool(args.event)

        entries = []
        for i, r in enumerate(rows):
            # Show the full round name (e.g. "Semifinal", not "SF"), tidying
            # machine formats like "RUN_3" -> "Run 3" and "FINAL" -> "Final".
            round_str = full_round_name(r.get("round", ""))
            heat = heat_label_from_id(r.get("heat_id", ""))
            entry = {
                "rank": i + 1,
                "athlete": r["athlete"],
                "country": nationality_to_iso(r.get("country", "")),
                "score": float(r["score"]),
                "event": clean_event_name(r["event"]),
                "round": round_str,
                "heat": heat,
                "counting": int(r.get("counting", 1)),
            }
            if is_jump:
                entry["trick_type"] = r.get("trick_type", "")
                entry["modifier"] = r.get("modifier", "") or ""
            entries.append(entry)

        data = {
            "title_gender": gender_map.get(args.sex, ""),
            "title_metric": f"{args.score_type}s",
            "title_year": args.year or "All Time",
            "show_trick_type": is_jump,
            "is_per_event": is_per_event,
            "entries": entries,
        }

        # Enrich with event metadata for per-event queries
        if is_per_event:
            event_row = run_query(
                "SELECT event_name, start_date, end_date, stars, country_code "
                "FROM PWA_IWT_EVENTS WHERE event_id = %s LIMIT 1",
                (args.event,),
            )
            if event_row:
                ev = event_row[0]
                data["event_name"] = clean_event_name(ev["event_name"])
                data["event_country"] = ev.get("country_code", "")
                data["event_stars"] = ev.get("stars", 0)
                start = ev.get("start_date")
                end = ev.get("end_date")
                if start:
                    from datetime import date as dt_date
                    if isinstance(start, str):
                        start = dt_date.fromisoformat(start)
                    data["event_date_start"] = start.strftime("%b %d")
                if end:
                    if isinstance(end, str):
                        end = dt_date.fromisoformat(end)
                    data["event_date_end"] = end.strftime("%b %d")
                # Set year from event if not provided
                if not args.year and start:
                    data["title_year"] = start.year

        return data

    if template_name in ("site_stats", "site_stats_reel"):
        return fetch_site_stats()

    if template_name == "rider_profile":
        if not all([args.event, args.athlete1, args.division]):
            print("Rider profile requires: --event, --athlete1, --division")
            sys.exit(1)
        return fetch_athlete_event_stats(
            event_id=args.event,
            athlete_id=args.athlete1,
            division=args.division,
        )

    if template_name == "finals_preview":
        men_ids = _parse_ids(getattr(args, "men", None))
        women_ids = _parse_ids(getattr(args, "women", None))
        heat_groups = [
            _parse_ids(group)
            for group in (getattr(args, "heats", None) or "").split("|")
            if group.strip()
        ]
        if not args.event or not (men_ids or women_ids or heat_groups):
            print("Finals preview requires: --event (API id) and --men/--women, or --heats "
                  "('46,69,68,205|135,64,49,61|...' one group per heat, with --division)")
            sys.exit(1)
        if heat_groups and not args.division:
            print("--heats also requires --division (Men or Women)")
            sys.exit(1)

        event = fetch_event(args.event)
        from datetime import date as dt_date
        event_meta = {
            "event_name": clean_event_name(event.get("event_name", "")),
            "year": event.get("year", ""),
            "country": event.get("country_code", ""),
            "stars": event.get("stars", 0),
            "event_id": args.event,
        }
        for api_key, meta_key in (("start_date", "start_date"), ("end_date", "end_date")):
            raw_date = event.get(api_key)
            if raw_date:
                event_meta[meta_key] = dt_date.fromisoformat(str(raw_date))

        if heat_groups:
            # One API round-trip for the whole round, then split back into the
            # drawn heats (the draw itself is not in the API — it comes in on
            # --heats because only the live bracket has it).
            flat = [aid for group in heat_groups for aid in group]
            stats = {a["athlete_id"]: a for a in fetch_finalist_stats(args.event, flat, args.division)}

            # One more call gives each rider's last sailed heat, which is the
            # route line on their card ("ELIMINATION R3 · 1ST" / "SEEDED").
            for aid, route in fetch_heat_routes(args.event, args.division).items():
                if aid in stats:
                    stats[aid]["route_round"] = route.get("round")
                    stats[aid]["route_place"] = route.get("place")
                    stats[aid]["route_order"] = route.get("round_order")

            round_label = (getattr(args, "round_label", None) or "Quarter Final").upper()
            return {
                "division_label": f"{args.division.upper()}'S",
                "heats": [
                    {
                        "label": f"{round_label} {i}",
                        "athletes": [stats[aid] for aid in group if aid in stats],
                    }
                    for i, group in enumerate(heat_groups, 1)
                ],
                "event_meta": event_meta,
            }

        return {
            "men": fetch_finalist_stats(args.event, men_ids, "Men") if men_ids else [],
            "women": fetch_finalist_stats(args.event, women_ids, "Women") if women_ids else [],
            "event_meta": event_meta,
        }

    if template_name == "finals_recap":
        if not args.event or not args.division:
            print("Finals recap requires: --event (API id) and --division (Men or Women)")
            sys.exit(1)

        final = fetch_final_heat(args.event, args.division)
        riders = final["riders"]
        if not riders:
            print(f"No final found for event {args.event} ({args.division}). "
                  "The recap only works once the final has sailed.")
            sys.exit(1)

        # Event-wide aggregates for the individual rider slides. The final's
        # own scores already came back with the heat.
        ids = [r["athlete_id"] for r in riders]
        aggregates = {
            a["athlete_id"]: a
            for a in fetch_finalist_stats(args.event, ids, args.division, detailed=True)
        }

        # Route excludes the final itself -- otherwise every rider's route
        # would read "FINAL", the heat the reader has just been shown.
        routes = fetch_heat_routes(args.event, args.division, before_round=final["round_order"])

        for rider in riders:
            agg = aggregates.get(rider["athlete_id"], {})
            for key in ("nationality", "best_heat", "best_wave", "best_jump",
                        "avg_wave", "avg_jump", "heat_wins", "avg_heat"):
                if agg.get(key) is not None:
                    rider[key] = agg[key]
            route = routes.get(rider["athlete_id"]) or {}
            rider["route_round"] = route.get("round")
            rider["route_place"] = route.get("place")
            rider["action_url"] = resolve_hero_url(rider["athlete_id"], args.event)
            rider["hero_focus"] = resolve_hero_focus(rider["athlete_id"], args.event)
            rider["photo_credit"] = (
                resolve_photo_credit(rider["athlete_id"], args.event)
                if rider["action_url"] else ""
            )

        # Heat-by-heat history drives heats-sailed (the denominator on HEATS
        # WON) and names the move behind each rider's best jump.
        history = fetch_heat_history(args.event, args.division)
        by_id = {r["athlete_id"]: r for r in riders}
        for aid, entries in history.items():
            if aid in by_id:
                by_id[aid]["history"] = entries

        # Sail numbers come off the event athlete list (used on the water).
        try:
            import requests as _requests
            from pipeline.api import API_BASE_URL
            resp = _requests.get(
                f"{API_BASE_URL}/events/{args.event}/athletes",
                params={"sex": args.division}, timeout=30,
            )
            if resp.ok:
                for a in resp.json().get("athletes", []):
                    if a["athlete_id"] in by_id:
                        by_id[a["athlete_id"]]["sail_number"] = a.get("sail_number", "")
        except Exception as exc:
            print(f"Sail numbers unavailable ({exc}); continuing without them.")

        # World rankings live in the DB, so they need the SSH tunnel. Without
        # it the carousel still builds, just with no rank badge.
        try:
            placeholders = ",".join(["%s"] * len(ids))
            for row in run_query(
                f"SELECT athlete_id, `rank` FROM WWT_WORLD_RANKINGS "
                f"WHERE athlete_id IN ({placeholders})",
                tuple(ids),
            ):
                if row["athlete_id"] in by_id:
                    by_id[row["athlete_id"]]["world_rank"] = row["rank"]
        except Exception as exc:
            print(f"World rankings unavailable ({exc}); continuing without them.")

        event = fetch_event(args.event)
        from datetime import date as dt_date
        event_meta = {
            "event_name": clean_event_name(event.get("event_name", "")),
            "year": event.get("year", ""),
            "country": event.get("country_code", ""),
            "stars": event.get("stars", 0),
            "event_id": args.event,
        }
        for api_key in ("start_date", "end_date"):
            raw_date = event.get(api_key)
            if raw_date:
                event_meta[api_key] = dt_date.fromisoformat(str(raw_date))

        # Credits follow the countdown order (4th shown first), so the
        # lead image's photographer is named first in the caption.
        credits = [r.get("photo_credit") for r in sorted(
            riders, key=lambda r: -(r.get("place") or 0)) if r.get("photo_credit")]

        return {"riders": riders, "division": args.division,
                "event_meta": event_meta, "photo_credits": credits}

    if template_name == "commentator_brief":
        heat_groups = [
            _parse_ids(group)
            for group in (getattr(args, "heats", None) or "").split("|")
            if group.strip()
        ]
        if not args.event or not heat_groups or not args.division:
            print("Commentator brief requires: --event (API id), --division and --heats "
                  "('46,69,68,205|135,64,49,61|...' one group per heat)")
            sys.exit(1)

        flat = [aid for group in heat_groups for aid in group]
        riders = {
            a["athlete_id"]: a
            for a in fetch_finalist_stats(args.event, flat, args.division, detailed=True)
        }

        for aid, route in fetch_heat_routes(args.event, args.division).items():
            if aid in riders:
                riders[aid]["route_round"] = route.get("round")
                riders[aid]["route_place"] = route.get("place")
                riders[aid]["route_order"] = route.get("round_order")

        for aid, history in fetch_heat_history(args.event, args.division).items():
            if aid in riders:
                riders[aid]["history"] = history

        # Sail numbers come off the event athlete list (used on the water).
        try:
            import requests as _requests
            from pipeline.api import API_BASE_URL
            resp = _requests.get(
                f"{API_BASE_URL}/events/{args.event}/athletes",
                params={"sex": args.division}, timeout=30,
            )
            if resp.ok:
                for a in resp.json().get("athletes", []):
                    if a["athlete_id"] in riders:
                        riders[a["athlete_id"]]["sail_number"] = a.get("sail_number", "")
        except Exception as exc:
            print(f"Sail numbers unavailable ({exc}); continuing without them.")

        # World rankings live in the DB, so they need the SSH tunnel. Without
        # it the sheet still builds, just with no rank badge.
        try:
            placeholders = ",".join(["%s"] * len(flat))
            rank_rows = run_query(
                f"SELECT athlete_id, `rank` FROM WWT_WORLD_RANKINGS "
                f"WHERE athlete_id IN ({placeholders}) AND sex = %s AND discipline = 'wave' "
                f"AND year = (SELECT MAX(year) FROM WWT_WORLD_RANKINGS)",
                tuple(flat) + (args.division,),
            )
            for row in rank_rows or []:
                if row["athlete_id"] in riders:
                    riders[row["athlete_id"]]["world_rank"] = row["rank"]
        except Exception as exc:
            print(f"World rankings unavailable ({exc}); continuing without them. Is the SSH tunnel up?")

        event = fetch_event(args.event)
        round_label = (getattr(args, "round_label", None) or "Quarter Final").upper()
        return {
            "division_label": f"{args.division.upper()}'S",
            "heats": [
                {
                    "label": f"{round_label} {i}",
                    "athletes": [riders[aid] for aid in group if aid in riders],
                }
                for i, group in enumerate(heat_groups, 1)
            ],
            "event_meta": {
                "event_name": clean_event_name(event.get("event_name", "")),
                "year": event.get("year", ""),
                "stars": event.get("stars", 0),
            },
            "generated_at": datetime.now().strftime("%-d %b %Y, %H:%M") if os.name != "nt"
                            else datetime.now().strftime("%d %b %Y, %H:%M").lstrip("0"),
        }

    if template_name == "canary_kings":
        men_sql, men_params = build_canary_kings_query("Men")
        women_sql, women_params = build_canary_kings_query("Women")
        men_data = run_query(men_sql, men_params)
        women_data = run_query(women_sql, women_params)
        return {"men": men_data, "women": women_data}

    if template_name == "wave_count":
        if not args.event:
            print("Wave count requires: --event (DB pwa_event_id)")
            sys.exit(1)
        include_non_counting = not getattr(args, "counting_only", False)
        men_sql, men_params = build_wave_count_query("Men", args.event, include_non_counting)
        women_sql, women_params = build_wave_count_query("Women", args.event, include_non_counting)
        men_data = run_query(men_sql, men_params)
        women_data = run_query(women_sql, women_params)
        # Event metadata for the cover (name, country, dates, stars) + hero photo
        event_meta = {"event_id": args.event}
        event_row = run_query(
            "SELECT event_name, start_date, end_date, stars, country_code "
            "FROM PWA_IWT_EVENTS WHERE event_id = %s LIMIT 1",
            (args.event,),
        )
        if event_row:
            ev = event_row[0]
            from datetime import date as dt_date
            event_meta["event_name"] = clean_event_name(ev["event_name"])
            event_meta["country"] = ev.get("country_code", "")
            event_meta["stars"] = ev.get("stars", 0)
            start = ev.get("start_date")
            end = ev.get("end_date")
            if isinstance(start, str):
                start = dt_date.fromisoformat(start)
            if isinstance(end, str):
                end = dt_date.fromisoformat(end)
            event_meta["start_date"] = start
            event_meta["end_date"] = end
            if start:
                event_meta["year"] = start.year
        return {"men": men_data, "women": women_data, "event_meta": event_meta}

    if template_name == "athlete_rise":
        if not all([args.athlete1, args.location, args.sex]):
            print("Athlete rise requires: --athlete1, --location, --sex")
            sys.exit(1)
        event_pattern = f"%%{args.location}%%"
        sql, params = build_athlete_rise_query(args.athlete1, event_pattern, args.sex)
        rows = run_query(sql, params)
        yearly_data = []
        for r in rows:
            yearly_data.append({
                "year": int(r["year"]),
                "placement": int(r["placement"]) if r.get("placement") else None,
                "best_heat": float(r["best_heat"]) if r.get("best_heat") else None,
                "best_wave": float(r["best_wave"]) if r.get("best_wave") else None,
                "best_jump": float(r["best_jump"]) if r.get("best_jump") else None,
                "best_jump_type": r.get("best_jump_type", "").strip() if r.get("best_jump_type") else None,
            })
        # Build title from athlete name (lookup from DB)
        name_rows = run_query(
            "SELECT primary_name, liveheats_image_url FROM ATHLETES WHERE id = %s LIMIT 1",
            (args.athlete1,),
        )
        athlete_name = name_rows[0]["primary_name"] if name_rows else f"Athlete {args.athlete1}"
        athlete_photo_url = name_rows[0].get("liveheats_image_url", "") if name_rows else ""
        # Custom rise-cover hero override: assets/photos/rise/{athlete_id}.{ext}
        # (scoped to athlete_rise so it doesn't affect rider_profile photos)
        rise_dir = os.path.join(os.path.dirname(__file__), "assets", "photos", "rise")
        for ext in ("webp", "jpg", "png"):
            local_hero = os.path.join(rise_dir, f"{args.athlete1}.{ext}")
            if os.path.exists(local_hero):
                athlete_photo_url = "file:///" + os.path.abspath(local_hero).replace(os.sep, "/")
                break
        return {
            "title": f"THE RISE OF {athlete_name.upper()} IN {args.location.upper()}",
            "subtitle": f"Check out the meteoric rise of {athlete_name.split()[0]}'s world cup performances at {args.location}",
            "athlete_id": args.athlete1,
            "athlete_name": athlete_name,
            "athlete_photo_url": athlete_photo_url or "",
            "location": args.location,
            "accent_color": "#9478B5",
            "yearly_data": yearly_data,
        }

    if template_name == "event_picks":
        if not args.picks_data:
            print("Event picks requires: --picks-data <path to JSON> (or use --dry-run)")
            sys.exit(1)
        from pipeline.picks_carousel import load_picks_data
        return load_picks_data(args.picks_data)

    if template_name == "fuerte_fantasy_mvps":
        from pipeline.fuerte_fantasy_mvps import assemble_mvp_data
        # Fuerteventura 2026 freestyle Session is app/DB event 123 (multi-discipline).
        event_id = args.event or 123
        points_sql, points_params = build_fantasy_mvp_points_query(event_id)
        pct_sql, pct_params = build_fantasy_session_pick_pct_query(event_id, "freestyle")
        points_rows = run_query(points_sql, points_params)
        pct_rows = run_query(pct_sql, pct_params)
        # Event metadata for the cover/eyebrows.
        event_meta = {"location": "Fuerteventura", "year": 2026}
        event_row = run_query(
            "SELECT event_name, start_date FROM PWA_IWT_EVENTS WHERE id = %s LIMIT 1",
            (event_id,),
        )
        if event_row:
            ev = event_row[0]
            event_meta["name"] = clean_event_name(ev.get("event_name", ""))
            start = ev.get("start_date")
            if isinstance(start, str):
                from datetime import date as dt_date
                start = dt_date.fromisoformat(start)
            if start:
                event_meta["year"] = start.year
        return assemble_mvp_data(points_rows, pct_rows, event_meta)

    if template_name == "slalom_mvps":
        from pipeline.slalom_mvps import assemble_slalom_mvp_data, verify_against_app_scores
        from pipeline.queries import (
            build_slalom_mvp_heats_query,
            build_slalom_mvp_classify_query,
            build_slalom_elimination_view_query,
        )
        # Fuerteventura 2026 is app/DB event 123 (multi-discipline: freestyle +
        # Slalom X). Picks are stored under discipline 'slalom_x'.
        event_id = args.event or 123
        heats_sql, heats_params = build_slalom_mvp_heats_query(event_id)
        classify_sql, classify_params = build_slalom_mvp_classify_query(event_id)
        elim_sql, elim_params = build_slalom_elimination_view_query(event_id)
        pct_sql, pct_params = build_fantasy_session_pick_pct_query(event_id, "slalom_x")

        heat_rows = run_query(heats_sql, heats_params)
        classify_rows = run_query(classify_sql, classify_params)
        elim_rows = run_query(elim_sql, elim_params)
        pct_rows = run_query(pct_sql, pct_params)

        event_meta = {"location": "Fuerteventura", "year": 2026}
        event_row = run_query(
            "SELECT event_name, start_date FROM PWA_IWT_EVENTS WHERE id = %s LIMIT 1",
            (event_id,),
        )
        if event_row:
            ev = event_row[0]
            event_meta["name"] = clean_event_name(ev.get("event_name", ""))
            start = ev.get("start_date")
            if isinstance(start, str):
                from datetime import date as dt_date
                start = dt_date.fromisoformat(start)
            if start:
                event_meta["year"] = start.year

        data = assemble_slalom_mvp_data(
            heat_rows, classify_rows, elim_rows, pct_rows, event_meta
        )

        # The scoring rules here are a port of the app's engine (see
        # pipeline/slalom_mvps.py). Cross-check every athlete the app itself
        # scored: a post that disagreed with the leaderboard players can see
        # would be worse than no post, so fail loudly rather than render.
        breakdown_rows = run_query(
            "SELECT breakdown_json FROM FANTASY_SESSION_SCORES "
            "WHERE event_id = %s AND discipline = %s",
            (event_id, "slalom_x"),
        )
        problems = verify_against_app_scores(data, breakdown_rows)
        if problems:
            print("Computed points disagree with the app's own fantasy scores:")
            for p in problems:
                print(f"  - {p}")
            sys.exit(1)
        ranked = [r for f in ("men", "women") for r in data.get(f, [])]
        # Only athletes somebody picked appear in the app's stored breakdowns, so
        # report what was actually verified rather than implying full coverage.
        import json as _json
        scored_ids = set()
        for _row in breakdown_rows or []:
            try:
                for _slot in _json.loads(_row["breakdown_json"]).get("slots", []):
                    scored_ids.add(int(_slot["athlete_id"]))
            except (ValueError, TypeError, KeyError):
                continue
        verified = sum(1 for r in ranked if r["athlete_id"] in scored_ids)
        print(
            f"Scoring cross-checked against the app: {verified}/{len(ranked)} "
            f"ranked athletes matched exactly "
            f"({len(ranked) - verified} unpicked, so the app never scored them)."
        )
        return data

    print(f"Live data not implemented for template: {template_name}")
    sys.exit(1)


def _slug(text: str) -> str:
    """Lowercase filename-safe slug, e.g. 'MEN QUARTER FINAL 4' -> 'men_quarter_final_4'."""
    import re
    # Apostrophes close up ("Men's" -> "mens") rather than becoming separators.
    text = (text or "").lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _parse_ids(raw: str) -> list:
    """Parse a comma-separated athlete ID list (e.g. '48,21,97,49')."""
    if not raw:
        return []
    return [int(part) for part in raw.split(",") if part.strip()]


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="WWT Instagram content generator")
    parser.add_argument(
        "--template",
        required=True,
        choices=["head_to_head", "head_to_head_jump", "h2h_carousel", "top_10", "top_10_carousel", "about_carousel", "coming_soon_carousel", "site_stats", "site_stats_reel", "stat_of_the_day", "rider_profile", "canary_kings", "athlete_rise", "wave_count", "fantasy_league_announce", "fantasy_rules", "tour_rules_reel", "tour_availability_reel", "session_vs_tour_reel", "how_to_pick_reel", "freestyle_scores_live", "slalom_scores_live", "wave_scores_live", "event_picks", "fuerte_fantasy_mvps", "slalom_mvps", "finals_preview", "finals_recap", "commentator_brief"],
    )
    parser.add_argument("--athlete1", type=int, help="Athlete 1 unified ID")
    parser.add_argument("--athlete2", type=int, help="Athlete 2 unified ID")
    parser.add_argument("--event", type=int, help="Event ID")
    parser.add_argument("--division", choices=["Men", "Women"], help="Division for H2H")
    parser.add_argument("--sex", choices=["Men", "Women"], help="Sex filter for top 10 / athlete rise")
    parser.add_argument("--location", help="Location pattern for athlete rise (e.g. 'Gran Canaria')")
    parser.add_argument("--picks-data", help="Path to event picks JSON file (event_picks template)")
    parser.add_argument("--men", help="Finals preview: comma-separated men's finalist athlete IDs, in draw order")
    parser.add_argument("--women", help="Finals preview: comma-separated women's finalist athlete IDs, in draw order")
    parser.add_argument("--heats", help="Finals preview: one slide per drawn heat, e.g. '46,69,68,205|135,64,49,61' (needs --division)")
    parser.add_argument("--round-label", help="Finals preview: heat slide label prefix (default 'Quarter Final')")
    parser.add_argument("--score-type", choices=["Wave", "Jump"], help="Score type for top 10")
    parser.add_argument("--year", type=int, help="Year filter for top 10")
    parser.add_argument("--day", type=int, help="Day number for daily top 10 label (e.g. 1, 2, 3)")
    parser.add_argument("--finals-day", action="store_true", help="Label as Finals Day instead of Day N")
    parser.add_argument("--so-far", action="store_true", help="Label as 'So Far' for a mid-event top 10 (instead of Day N)")
    parser.add_argument("--rounds", help="Comma-separated round names to filter (e.g. 'Final,R5 B-Final')")
    parser.add_argument("--counting-only", action="store_true", help="Top 10: only scores that counted toward the heat total (default now includes non-counting)")
    parser.add_argument("--mode", help="Variant mode for a template (e.g. 'perfect-10s' for the all-time perfect-10 wave carousel)")
    parser.add_argument("--rider-of-day", action="store_true", help="Rider profile mid-comp variant: no finish position (cover shows 'RIDER OF THE DAY', placing shows TBC)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use dummy data instead of DB",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Open HTML in browser instead of rendering PNG",
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="Render as animated MP4 video instead of static PNG",
    )
    parser.add_argument("--duration", type=int, default=6000, help="Video duration in ms")
    parser.add_argument("--output", help="Custom output path")
    parser.add_argument(
        "--publish",
        choices=["now"],
        help="Publish to Instagram after rendering",
    )
    parser.add_argument("--caption", help="Custom caption override")

    args = parser.parse_args()
    config = load_config()

    template_name = args.template
    template_config = config["templates"].get(template_name, {})
    width = template_config.get("width", 1080)
    height = template_config.get("height", 1350)
    dpr = template_config.get("dpr", 2)

    # Get data
    if args.dry_run or template_name in ("coming_soon_carousel", "about_carousel", "freestyle_scores_live", "slalom_scores_live", "wave_scores_live", "fantasy_rules", "tour_rules_reel", "session_vs_tour_reel", "how_to_pick_reel"):
        # --mode perfect-10s overrides the dummy lookup for top_10_carousel
        if template_name in ("top_10", "top_10_carousel") and getattr(args, "mode", None) == "perfect-10s":
            data = get_dummy_data("perfect_10s")
        else:
            data = get_dummy_data(template_name)
    else:
        data = fetch_live_data(template_name, args)

    # Thread --day into data for daily top 10
    if getattr(args, "day", None):
        data["day"] = args.day
    if getattr(args, "finals_day", False):
        data["finals_day"] = True
    if getattr(args, "so_far", False):
        data["so_far"] = True

    # Thread --rider-of-day into rider profile data (mid-comp, no placement)
    if getattr(args, "rider_of_day", False):
        data["rider_of_day"] = True

    is_carousel = template_name in ("top_10_carousel", "coming_soon_carousel", "about_carousel", "fantasy_rules", "h2h_carousel", "rider_profile", "canary_kings", "athlete_rise", "wave_count", "event_picks", "fuerte_fantasy_mvps", "slalom_mvps", "finals_preview", "finals_recap", "commentator_brief")

    # Carousel preview: open all slides in browser tabs
    if is_carousel and args.preview:
        if template_name in ("coming_soon_carousel", "about_carousel", "fantasy_rules"):
            slides = data["slides"]
        elif template_name == "h2h_carousel":
            from pipeline.h2h_carousel import build_slides as build_h2h_slides
            slides = build_h2h_slides(data)
        elif template_name == "rider_profile":
            from pipeline.rp_carousel import build_slides as build_rp_slides
            slides = build_rp_slides(data)
        elif template_name == "canary_kings":
            from pipeline.analysis_carousel import build_canary_kings_slides
            slides = build_canary_kings_slides(data["men"], data["women"])
        elif template_name == "athlete_rise":
            from pipeline.athlete_rise_carousel import build_athlete_rise_slides
            slides = build_athlete_rise_slides(data)
        elif template_name == "wave_count":
            from pipeline.wave_count_carousel import build_wave_count_slides
            slides = build_wave_count_slides(data["men"], data["women"], data.get("event_meta"))
        elif template_name == "event_picks":
            from pipeline.picks_carousel import build_slides as build_picks_slides
            slides = build_picks_slides(data)
        elif template_name == "fuerte_fantasy_mvps":
            from pipeline.fuerte_fantasy_mvps import build_slides as build_mvp_slides
            slides = build_mvp_slides(data)
        elif template_name == "slalom_mvps":
            from pipeline.slalom_mvps import build_slides as build_slalom_mvp_slides
            slides = build_slalom_mvp_slides(data)
        elif template_name == "finals_recap":
            from pipeline.finals_recap import build_slides as build_recap_slides
            slides = build_recap_slides(data)
        elif template_name == "finals_preview":
            from pipeline.finals_preview import build_slides as build_finals_slides
            slides = build_finals_slides(data)
        elif template_name == "commentator_brief":
            from pipeline.commentator_brief import build_pages
            slides = build_pages(data)
            # The brief sheet is taller than base.html's 1350 default and
            # brings its own footer.
            for slide in slides:
                slide.update({"width": width, "height": height, "hide_footer": True})
        else:
            from pipeline.carousel import build_slides
            slides = build_slides(data)
        for slide in slides:
            html = render_template(f"carousel/slide_{slide['type']}", slide)
            html = html.replace("<body>", '<body style="zoom: 0.5;">')
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", delete=False, encoding="utf-8"
            ) as f:
                f.write(html)
                print(f"Preview: {f.name}")
                webbrowser.open(f"file:///{f.name.replace(os.sep, '/')}")
        return

    # Single-template preview
    if not is_carousel:
        html = render_template(template_name, data)

    if args.preview:
        html = html.replace("<body>", '<body style="zoom: 0.5;">')
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html)
            print(f"Preview: {f.name}")
            webbrowser.open(f"file:///{f.name.replace(os.sep, '/')}")
        return

    # Render output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = config.get("output_dir", "./output")

    if is_carousel:
        carousel_dir = os.path.join(output_dir, "png")
        if template_name in ("coming_soon_carousel", "about_carousel", "fantasy_rules"):
            slides = data["slides"]
            result_paths = []
            os.makedirs(carousel_dir, exist_ok=True)
            prefix = template_name.replace("_carousel", "")
            for i, slide in enumerate(slides, 1):
                html = render_template(f"carousel/slide_{slide['type']}", slide)
                output_path = os.path.join(carousel_dir, f"{prefix}_{timestamp}_{i}.png")
                render_to_png(html, output_path, width=width, height=height, dpr=dpr)
                result_paths.append(output_path)
        elif template_name == "h2h_carousel":
            result_paths = render_h2h_carousel(
                data, carousel_dir,
                base_name=f"h2h_carousel_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        elif template_name == "rider_profile":
            result_paths = render_rp_carousel(
                data, carousel_dir,
                base_name=f"rider_profile_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        elif template_name == "canary_kings":
            result_paths = render_analysis_carousel(
                data["men"], data["women"], carousel_dir,
                base_name=f"canary_kings_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        elif template_name == "athlete_rise":
            result_paths = render_athlete_rise_carousel(
                data, carousel_dir,
                base_name=f"athlete_rise_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        elif template_name == "wave_count":
            result_paths = render_wave_count_carousel(
                data["men"], data["women"], carousel_dir,
                base_name=f"wave_count_{timestamp}",
                event_meta=data.get("event_meta"),
                width=width, height=height, dpr=dpr,
            )
        elif template_name == "event_picks":
            result_paths = render_picks_carousel(
                data, carousel_dir,
                base_name=f"event_picks_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        elif template_name == "slalom_mvps":
            result_paths = render_slalom_mvps_carousel(
                data, carousel_dir,
                base_name=f"slalom_mvps_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        elif template_name == "commentator_brief":
            from pipeline.commentator_brief import build_pages
            # Sheets land in their own per-event folder with readable names, so
            # the whole round can be sent on as-is. Re-running overwrites: the
            # generated-at stamp inside each sheet is the version marker.
            meta = data.get("event_meta") or {}
            event_slug = _slug(f"{meta.get('event_name', 'event')} {meta.get('year', '')}")
            brief_dir = os.path.join(output_dir, "commentary_notes", event_slug)
            os.makedirs(brief_dir, exist_ok=True)
            result_paths = []
            for page in build_pages(data):
                # base.html sizes the body from these, and the sheet is taller
                # than the 1350 default; the base footer is replaced by ours.
                page.update({"width": width, "height": height, "hide_footer": True})
                page_html = render_template(f"carousel/slide_{page['type']}", page)
                out_path = os.path.join(brief_dir, f"{_slug(page['title'])}.png")
                render_to_png(page_html, out_path, width=width, height=height, dpr=dpr)
                result_paths.append(out_path)
        elif template_name == "finals_recap":
            result_paths = render_finals_recap_carousel(
                data, carousel_dir,
                base_name=f"finals_recap_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        elif template_name == "finals_preview":
            result_paths = render_finals_preview_carousel(
                data, carousel_dir,
                base_name=f"finals_preview_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        elif template_name == "fuerte_fantasy_mvps":
            result_paths = render_fuerte_fantasy_mvps_carousel(
                data, carousel_dir,
                base_name=f"fuerte_fantasy_mvps_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        else:
            result_paths = render_carousel(
                data, carousel_dir,
                base_name=f"top_10_carousel_{timestamp}",
                width=width, height=height, dpr=dpr,
            )
        for p in result_paths:
            print(f"Rendered: {p}")

        if args.publish == "now":
            from pipeline.publisher import publish_carousel as publish_carousel_to_ig

            caption = args.caption or build_caption(template_name, data, config)
            print("Publishing carousel to Instagram...")
            pub_result = publish_carousel_to_ig(result_paths, caption)
            print(f"Published! Media ID: {pub_result['media_id']}")
        return

    # Auto-enable video for reel templates
    use_video = args.video or template_name.endswith("_reel")

    if use_video:
        if args.output:
            output_path = args.output
        else:
            output_path = os.path.join(output_dir, "mp4", f"{template_name}_{timestamp}.mp4")
        result = render_to_video(
            html, output_path, width=width, height=height, dpr=1,
            duration_ms=args.duration,
        )
    else:
        if args.output:
            output_path = args.output
        else:
            output_path = os.path.join(output_dir, "png", f"{template_name}_{timestamp}.png")
        result = render_to_png(html, output_path, width=width, height=height, dpr=dpr)

    print(f"Rendered: {result}")

    # Publish to Instagram if requested
    if args.publish == "now":
        from pipeline.publisher import publish as publish_to_instagram

        caption = args.caption or build_caption(template_name, data, config)
        print("Publishing to Instagram...")
        pub_result = publish_to_instagram(result, caption)
        print(f"Published! Media ID: {pub_result['media_id']}")


if __name__ == "__main__":
    main()
