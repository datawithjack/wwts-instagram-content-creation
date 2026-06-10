"""One-off: build a 'Rider of the Day' preview for Finn Mellon at Fiji 2026
from DB data (the API has no live mid-comp data). Throwaway test harness for
the --rider-of-day mode; not part of the pipeline. DB-backed rider_profile
will be wired properly as a follow-up.
"""
import os
import statistics
import tempfile
import webbrowser
from collections import defaultdict

from pipeline.db import run_query
from pipeline.helpers import short_round_name, clean_event_name, nationality_to_iso
from pipeline.rp_carousel import build_slides
from pipeline.templates import render_template

ATHLETE_ID = 35       # Finn Mellon (unified)
EVENT_ID = 490099     # Fiji 2026 DB pwa_event_id

# All Finn Mellon wave scores at Fiji
rows = run_query(
    """
    SELECT s.score, s.counting, s.heat_id, hp.round_name
    FROM PWA_IWT_HEAT_SCORES s
    JOIN ATHLETE_SOURCE_IDS asi ON asi.source=s.source AND asi.source_id=s.athlete_id
    JOIN PWA_IWT_HEAT_PROGRESSION hp ON hp.heat_id=s.heat_id AND hp.source=s.source
    WHERE asi.athlete_id=%s AND s.pwa_event_id=%s AND s.type='Wave'
    ORDER BY s.score DESC
    """,
    (ATHLETE_ID, EVENT_ID),
)
counting = [r for r in rows if r["counting"] == 1]

# best_heat = max combined counting-wave score within a single heat
heat_totals = defaultdict(float)
heat_round = {}
for r in counting:
    heat_totals[r["heat_id"]] += float(r["score"])
    heat_round[r["heat_id"]] = r["round_name"]
best_heat_id = max(heat_totals, key=heat_totals.get)
best_heat = heat_totals[best_heat_id]
best_heat_round = short_round_name(heat_round[best_heat_id])

best_wave = float(counting[0]["score"])
avg_wave = statistics.mean(float(r["score"]) for r in counting)
top_waves = [
    {"rank": i + 1, "score": float(r["score"]), "round": short_round_name(r["round_name"])}
    for i, r in enumerate(counting[:5])
]

# Athlete + event metadata
ath = run_query("SELECT primary_name, nationality FROM ATHLETES WHERE id=%s", (ATHLETE_ID,))[0]
ev = run_query(
    "SELECT event_name, country_code, stars, start_date, end_date FROM PWA_IWT_EVENTS WHERE event_id=%s",
    (EVENT_ID,),
)[0]

data = {
    "event_id": EVENT_ID,
    "athlete_id": ATHLETE_ID,
    "athlete_name": ath["primary_name"],
    "athlete_country": nationality_to_iso(ath["nationality"] or ""),
    "athlete_photo_url": "",
    "athlete_sail_number": "",
    "event_name": clean_event_name(ev["event_name"]),
    "event_country": ev.get("country_code", ""),
    "event_tier": ev.get("stars", 0) or 0,
    "event_date_start": ev.get("start_date"),
    "event_date_end": ev.get("end_date"),
    "placement": 0,
    "best_heat": best_heat,
    "best_heat_round": best_heat_round,
    "best_wave": best_wave,
    "best_jump": None,
    "avg_wave": avg_wave,
    "top_waves": top_waves,
    "top_jumps": None,
    "rider_of_day": True,
    "day": 2,
}

slides = build_slides(data)
for slide in slides:
    html = render_template(f"carousel/slide_{slide['type']}", slide)
    html = html.replace("<body>", '<body style="zoom: 0.5;">')
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        print(f"Preview: {f.name}")
        webbrowser.open(f"file:///{f.name.replace(os.sep, '/')}")

print(f"Built {len(slides)} slides for {data['athlete_name']} @ {data['event_name']}")
print(f"best_heat={best_heat:.2f} ({best_heat_round}) best_wave={best_wave:.2f} avg_wave={avg_wave:.2f}")
