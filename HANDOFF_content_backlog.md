# HANDOFF — Loading the 2026 plan into `content_backlog.yaml`

> Created 2026-06-02. For a fresh terminal continuing the WWT Instagram content work.
> Project: `C:\Users\jackf\OneDrive\Documents\Projects\wwts-instagram-content-creation`

## Where we are
- Reviewed `content-plan-2026.xlsx` → **Sheet1** (the yearly grid) and rebuilt it into a reviewable, checkbox-based plan: **`2026_season_content_plan.md`**.
- Every grid cell is now a post entry with: type tag, mapped template, a `--dry-run --preview` command, and a suggested backlog `id`.
- **Decisions already baked in** (don't re-ask):
  - "Top 3" and "1st place" result posts = **`rider_profile` posts**, one per place (1st/2nd/3rd) per division — NOT a podium graphic.
  - "Rp" in the sheet = Rider Profile.
  - Chile week (w/c 8 Nov) "Sylt…" cells were a typo → **Chile**.
  - Tiree 4* week keeps its "Aloha" content on purpose (Tiree data uncertain; we want the Aloha preview).
  - `M28`/`N28` loose dates ignored. Column J ignored.

## The task now
Work through `2026_season_content_plan.md` and transfer approved posts into **`content_backlog.yaml`**, one event/section at a time. The .md is the source of truth for *what*; the .yaml is the *schedulable* artifact.

## `content_backlog.yaml` format (mirror existing entries)
```yaml
  - id: gc2026-rp-browne-1st          # unique, kebab-case
    template: rider_profile           # top_10_carousel | h2h_carousel | rider_profile | canary_kings | athlete_rise | fantasy_league_announce
    params:
      event: 120                      # real event ID (DB/API)
      athlete1: 68                    # real athlete unified ID
      division: Men                   # rider_profile + h2h use `division`; top_10_carousel uses `sex` + `score_type` (+ optional `year`/`event`)
    caption: "..."                    # optional — auto-generated if omitted
    category: seasonal                # evergreen | seasonal | recurring
    scheduled_date: "2026-07-13T06:00:00"   # ISO 8601, REQUIRED for scheduling
    notes: 1st place — Marcilio Browne       # planning note, not used by scheduler
```
**Param gotchas** (the .md preview commands use CLI flags; the YAML differs):
- `rider_profile` YAML param is **`division`** (Men/Women) — even though the CLI uses `--sex`. Plus `event`, `athlete1`.
- `top_10_carousel` YAML params: `score_type` (Wave/Jump), `sex` (Men/Women), optional `year`, optional `event`.
- `h2h_carousel`: `event`, `athlete1`, `athlete2`, `division`.

## ⛔ Blocker before live entries
Most posts need **real `event` IDs and `athlete` unified IDs** — the .md uses placeholders (`<FIJI_ID>`, `<PODIUM_ATH>`, etc.). To resolve them, query the DB/API (see `pipeline/queries.py`, `pipeline/api.py`; `python generate.py --template top_10_carousel ... ` live needs DB). We need, per event: the event ID and the 1st/2nd/3rd athlete IDs per division.
- **Recommended:** start with the **Fiji block** (first chronologically). Get the Fiji 2026 event ID + podium athlete IDs, then fill `fiji2026-rp-m1`, `fiji2026-rp-w1`, the Fiji Top-10 Waves, and the 1v2 H2H.
- Posts that need **no IDs** and can go in immediately: `canary_kings` (Mon 15 Jun), season-wide top 10s (`--year 2026`, no event), and any `fantasy_league_announce`.

## Suggested working loop (per event section)
1. Open the section in `2026_season_content_plan.md`.
2. Resolve event ID + athlete IDs (DB/API query).
3. Preview each post: `python generate.py --template <t> ... --dry-run --preview` (dummy) or live with real IDs.
4. On approval, append a YAML entry (format above) with a real `scheduled_date`.
5. Tick the `[ ]` → `[x]` in the .md.
6. Validate: `python -m pytest tests/ --ignore=tests/test_renderer.py --ignore=tests/test_site_stats.py -v`.

## Scheduling cadence (from the grid)
Sun-start weeks; working days are mostly **Mon / Wed / Fri / Sat**. Pick a consistent publish time (existing entries use early morning, e.g. `T06:00:00`). The .md has the exact calendar date for every post.

## Still-open questions (don't block ID-driven work)
- `GC 5*` event dates/ID still TBC.
- Year placeholders for throwbacks + historic rider profiles (left with the user).
- Weekly **Fantasy League** (Sat): same announce graphic vs. weekly leaderboard update — needs a decision / maybe a new template.

## Key files
| File | Purpose |
|---|---|
| `2026_season_content_plan.md` | The reviewable plan (source of *what*) |
| `content_backlog.yaml` | Schedulable posts (the *content log*) |
| `content-plan-2026.xlsx` | Original spreadsheet (Sheet1 = grid; Sheet2 = H2H design outline) |
| `generate.py` | CLI: `--template ... --dry-run --preview` |
| `CLAUDE.md` | Pipeline overview, templates, review workflow (always `--preview` over PNG) |
