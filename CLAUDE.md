# WWT Instagram Content Creation Pipeline

## Overview
Automated Instagram image generation pipeline for windsurfworldtourstats.com. Pulls live data from the production API and MySQL HeatWave, renders HTML templates to PNG via Playwright.

## Architecture

### Data Sources
- **API** (`pipeline/api.py`): H2H stats, event details, site stats from `https://api.windsurfworldtourstats.com/api/v1`
- **MySQL HeatWave** (`pipeline/db.py` + `pipeline/queries.py`): Top 10 queries (supports per-event, per-year, all-time)

### Pipeline Flow
1. `generate.py` — CLI entry point, fetches data (API or DB), renders HTML, screenshots to PNG
2. `pipeline/templates.py` — Jinja2 template population with custom filters
3. `pipeline/renderer.py` — Playwright headless Chromium screenshot at 2x DPR
4. `.github/workflows/generate-content.yml` — GitHub Actions (manual dispatch + scheduled)

### Key Modules
| Module | Purpose |
|---|---|
| `pipeline/api.py` | API client (fetch_head_to_head, fetch_site_stats, fetch_event, fetch_athlete_event_stats) |
| `pipeline/queries.py` | SQL query builders (build_top10_query, build_canary_kings_query, build_athlete_rise_query) |
| `pipeline/db.py` | MySQL connection + query runner |
| `pipeline/templates.py` | Jinja2 env, filters, render_template, get_dummy_data |
| `pipeline/helpers.py` | Formatting helpers (ordinal, format_delta, country_flag, etc.) |
| `pipeline/renderer.py` | Playwright render_to_png, render_to_video |
| `pipeline/publisher.py` | Upload to R2, create/publish Instagram container via Meta Graph API |
| `pipeline/captions.py` | Caption + hashtag generation per template |
| `pipeline/analysis_carousel.py` | Canary Kings analysis carousel slide builder |
| `pipeline/athlete_rise_carousel.py` | Athlete rise progression carousel slide builder |

## Review Workflow
**ALWAYS generate `--preview` over PNG when the user is reviewing a design.** Use `--preview` for every iteration. Only render PNG when the user explicitly asks for one, or at the very end to attach a final asset to a ticket/publish. PNG renders take ~30s, use Playwright, and clutter `output/png/`; previews open instantly in the browser.

## CLI Usage
```bash
# Dry run (dummy data, no API/DB needed)
python generate.py --template head_to_head --dry-run --preview
python generate.py --template top_10 --dry-run --preview

# Live — H2H from API
python generate.py --template head_to_head --event 42 --athlete1 1 --athlete2 2 --division Women

# Live — Top 10 from DB
python generate.py --template top_10 --score-type Wave --sex Men --year 2025

# Live — Site stats from API
python generate.py --template site_stats

# Analysis carousel — Canary Kings (dry-run or live from DB)
python generate.py --template canary_kings --dry-run --preview
python generate.py --template canary_kings --preview

# Athlete rise carousel (dry-run or live from DB)
python generate.py --template athlete_rise --dry-run --preview
python generate.py --template athlete_rise --athlete1 48 --location "Gran Canaria" --sex Men --preview

# Preview in browser (no PNG render)
python generate.py --template head_to_head --dry-run --preview

# Publish to Instagram after rendering
python generate.py --template site_stats --dry-run --publish now
python generate.py --template site_stats --dry-run --publish now --caption "Custom caption"
```

## Templates
- `head_to_head.html` — Two-athlete comparison, single image (wave events) — **legacy, use h2h_carousel**
- `head_to_head_jump.html` — Two-athlete comparison, single image (wave + jump) — **legacy, use h2h_carousel**
- `h2h_carousel` — H2H carousel: cover → overview → heat scores → wave scores → [jump scores] → CTA (5-6 slides)
- `top_10.html` — Top 10 scores leaderboard
- `site_stats.html` — Site-wide stat counters (with count-up animation for video)
- `rider_profile.html` — Single athlete performance at an event (carousel: cover → hero → stats → waves → CTA)
- `canary_kings` — Analysis carousel: Kings & Queens of the Canaries (cover → men bars → women bars → CTA, 4 slides)
- `athlete_rise` — Athlete rise carousel: year-over-year progression at a location (cover → dual chart → explanation, 3+ slides)

## Template Layout Rules
- HTML template layouts are manually tuned by the user. Do NOT modify template HTML/CSS layout unless explicitly asked.
- When adding new templates, generate a working skeleton and let the user refine the visual layout.

## Design Review: Colors
- The cyan accent (`#00D4FF`) used across templates is too bright/garish. Needs a review pass across all slides to use more muted, toned-down accent colors.
- Analysis carousel uses `#5ab4cc` (muted cyan accent), `#2a8ab0` (Gran Canaria bars), `#1e9485` (Tenerife bars).
- Run `/design-audit` to check color consistency across all templates.

## Testing
```bash
# Fast tests (no Playwright)
python -m pytest tests/ --ignore=tests/test_renderer.py --ignore=tests/test_site_stats.py -v

# All tests (includes Playwright render)
python -m pytest tests/ -v
```

## Publishing
- **Flow**: Render PNG → Upload to Cloudflare R2 → Create Instagram media container → Poll until ready → Publish → Delete from R2
- **CLI**: `--publish now` flag on any generate command
- **Meta Graph API**: v22.0, requires permanent Page Access Token
- **New Pages Experience**: `/me/accounts` returns empty; query page directly by ID (`1055784894276445?fields=access_token,instagram_business_account`)
- **IMPORTANT — No duplicate publishes**: If `--publish now` fails with a 400 error after rate limiting, the post may have already published successfully. Always check Instagram before retrying. Do NOT re-run `--publish now` without confirming the post didn't go live — duplicate posts require manual deletion.
- **Known issue**: The publish step can fail with a 400 after the container was actually created and published. The error comes from a second publish attempt after a rate-limit retry. This needs fixing in `pipeline/publisher.py` — the publish flow should check container status before retrying publish.

## Environment Variables
See `.env`. Key vars:
- `API_BASE_URL` — Production API (defaults to `https://api.windsurfworldtourstats.com/api/v1`)
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` — For top 10 queries. **DB cut over to the JFA Analytics tenant on 2026-05-18** (new password + tunnel target — see Session Progress below). DB-backed templates (`top_10_carousel`, `canary_kings`, `athlete_rise`) only work while the SSH tunnel is up: `ssh -L 3306:10.0.1.240:3306 -i ~/.ssh/ssh-key-2025-08-30.key ubuntu@129.151.141.211`. `rider_profile` + `h2h_carousel` use the API, so they work without the tunnel.
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL` — Cloudflare R2
- `META_ACCESS_TOKEN`, `META_INSTAGRAM_ACCOUNT_ID` — Meta Graph API publishing

## Brand
- Fonts: Bebas Neue (display), Inter (body) — loaded from Google Fonts
- Colors: see `wwt_instagram_pipeline_plan.md` brand tokens section
- Output: 1080x1350 portrait (feed), 1080x1080 square (stat of day), 2x DPR

## Session Progress (2026-06-02) — 2026 backlog loading
Loading `2026_season_content_plan.md` → `content_backlog.yaml`. See `HANDOFF_content_backlog.md` for the full task brief.

**Done this session:**
- Branch `content-backlog-2026` created off `main` for this work.
- **DB cutover applied to `.env`** — JFA Analytics tenant (live 2026-05-18). `MYSQL_PASSWORD` → `Windsurf2026!`; `SSH_TUNNEL` target → VM `129.151.141.211`, internal DB `10.0.1.240`. Source of truth: `windsurf-world-tour-stats-app/backend/.env`.
- **Resolved 2026 event IDs from the API** (the handoff's main blocker): Fiji **205** (Jun 6–14), GC **122** (Jul 4–12), Tenerife **124** (Jul 31–Aug 9), Sylt **126** (Sep 25–Oct 4), Tiree **207** (Oct 10–16), Aloha **128** (Oct 19–30), Chile **132** (Nov 14–29).

**Decisions:**
- **Focus = rider profiles only.** Skip fantasy announcements. Skip `canary_kings` until its data is extended back to 2005.
- Workflow: preview → user checks → tick `[x]` in `2026_season_content_plan.md` → add entry to `content_backlog.yaml`. Nothing committed yet.

**Blockers / next session:**
- `rider_profile` uses the API (no tunnel needed), but the plan's earliest rider profiles are Fiji *recap* posts — Fiji 2026 (event 205) runs Jun 6–14, so podium athlete IDs don't exist yet.
- Historic-throwback rider profiles still have **year placeholders** (open questions in the plan) to resolve before they're buildable.
- Pick up by choosing which rider profiles to preview first (historic throwbacks once years are confirmed, or Fiji recap after the event finishes).

## Next Steps
1. **Rider profile cover redesign** — Add athlete photo to rider profile cover slide (similar to H2H split-photo cover approach)
2. **Full design review** — Run `/design-audit` across all templates to ensure consistent colors, fonts, spacing, and footers

## Skills
- `/design-audit` — Audit templates for design consistency (colors, fonts, spacing, footers)

## 12-Post Grid Plan

First 12 posts for @windsurfworldtourstats Instagram. Grid ordering matters — posts 1-3 are the most recent (top row).

| # | Post | Template | Data Source | Status |
|---|------|----------|-------------|--------|
| 1 | Rolling number reel + sound | `site_stats_reel` | API `/stats` | **Gap: sound** |
| 2 | About carousel | **New template** | Hardcoded text | **Gap: template** |
| 3 | Follow along / CTA | **New template** | Hardcoded text | **Gap: template** |
| 4 | Top 10 women waves — Margaret River | `top_10_carousel` | DB query (event filter) | **Ready** |
| 5 | Men H2H — Margaret River | `head_to_head` / `head_to_head_jump` | API | **Ready** |
| 6 | Rider profile — Margaret River | `rider_profile` | API | **Ready** |
| 7 | Pro Am waves 2025 — rider profile | `rider_profile` | API | **Ready if data exists** |
| 8 | Pro Am waves 2025 — top wave scores | `top_10_carousel` | DB query (event filter) | **Ready if data exists** |
| 9 | Pro Am 2025 — H2H | `head_to_head` | API | **Ready if data exists** |
| 10 | Top 10 wave scores of 2025 | `top_10_carousel` | DB query (year filter) | **Ready** |
| 11 | Most 10s in Pozo — count leaderboard | **New template** | **New query** | **Gap: query + template** |
| 12 | All-time best wave scores | `top_10_carousel` | DB query (no filters) | **Ready** |

### Phases

**Phase A: Generate ready posts (4, 5, 6, 10, 12)**
- Use existing templates + live data. Need Margaret River event ID, athlete IDs.
- `--dry-run --preview` first, then live data, then `--publish now`

**Phase B: Verify Pro Am data (7, 8, 9)**
- Query API/DB for Pro Am 2025 event(s) to confirm data exists.
- If data exists, generate using existing templates.

**Phase C: Sound support for reel (post 1)**
- Add ffmpeg audio overlay to `render_to_video` or as post-processing.
- Need royalty-free audio track. File: `pipeline/renderer.py`

**Phase D: Brand templates (posts 2, 3)**
- Post 2 — About carousel: Multi-slide introducing the page/brand. Reusable HTML template.
- Post 3 — CTA post: Single-image "follow for more stats" template.
- New templates in `templates/`, dummy data in `pipeline/templates.py`, captions in `pipeline/captions.py`.

**Phase E: Count leaderboard (post 11)**
- New `build_count_query()` in `pipeline/queries.py` — count of scores meeting a threshold, grouped by athlete, filtered by event/year/score_type.
- New or adapted template (reuse `top_10` layout with count instead of score).
- TDD: `tests/test_count_query.py`
- Caveat text: "Data since 2016"

### Suggested Execution Order
1. Phase A — quick wins, 5 posts ready
2. Phase B — verify Pro Am data, may unlock 3 more
3. Phase E — new count query (most interesting new capability)
4. Phase D — brand templates (design-heavy, less code)
5. Phase C — sound support (nice-to-have, can add sound manually)

### Key Files to Modify
- `pipeline/queries.py` — new `build_count_query()`
- `pipeline/templates.py` — dummy data for new templates
- `pipeline/captions.py` — captions for new templates
- `pipeline/renderer.py` — sound support (Phase C)
- `templates/about_carousel.html` — new (Phase D)
- `templates/cta.html` — new (Phase D)
- `templates/count_leaderboard.html` — new or adapt top_10 (Phase E)
- `content_backlog.yaml` — add all 12 posts
- `tests/test_count_query.py` — new tests for count query
