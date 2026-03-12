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
| `pipeline/queries.py` | SQL query builders (build_top10_query) |
| `pipeline/db.py` | MySQL connection + query runner |
| `pipeline/templates.py` | Jinja2 env, filters, render_template, get_dummy_data |
| `pipeline/helpers.py` | Formatting helpers (ordinal, format_delta, country_flag, etc.) |
| `pipeline/renderer.py` | Playwright render_to_png, render_to_video |
| `pipeline/publisher.py` | Upload to R2, create/publish Instagram container via Meta Graph API |
| `pipeline/captions.py` | Caption + hashtag generation per template |

## CLI Usage
```bash
# Dry run (dummy data, no API/DB needed)
python generate.py --template head_to_head --dry-run
python generate.py --template top_10 --dry-run

# Live — H2H from API
python generate.py --template head_to_head --event 42 --athlete1 1 --athlete2 2 --division Women

# Live — Top 10 from DB
python generate.py --template top_10 --score-type Wave --sex Men --year 2025

# Live — Site stats from API
python generate.py --template site_stats

# Preview in browser (no PNG render)
python generate.py --template head_to_head --dry-run --preview

# Publish to Instagram after rendering
python generate.py --template site_stats --dry-run --publish now
python generate.py --template site_stats --dry-run --publish now --caption "Custom caption"
```

## Templates
- `head_to_head.html` — Two-athlete comparison (wave events)
- `head_to_head_jump.html` — Two-athlete comparison (wave + jump events)
- `top_10.html` — Top 10 scores leaderboard
- `site_stats.html` — Site-wide stat counters (with count-up animation for video)
- `rider_profile.html` — Single athlete performance at an event

## Template Layout Rules
- HTML template layouts are manually tuned by the user. Do NOT modify template HTML/CSS layout unless explicitly asked.
- When adding new templates, generate a working skeleton and let the user refine the visual layout.

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
- **Meta Graph API**: v21.0, requires permanent Page Access Token
- **New Pages Experience**: `/me/accounts` returns empty; query page directly by ID (`1055784894276445?fields=access_token,instagram_business_account`)

## Environment Variables
See `.env`. Key vars:
- `API_BASE_URL` — Production API (defaults to `https://api.windsurfworldtourstats.com/api/v1`)
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` — For top 10 queries
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL` — Cloudflare R2
- `META_ACCESS_TOKEN`, `META_INSTAGRAM_ACCOUNT_ID` — Meta Graph API publishing

## Brand
- Fonts: Bebas Neue (display), Inter (body) — loaded from Google Fonts
- Colors: see `wwt_instagram_pipeline_plan.md` brand tokens section
- Output: 1080x1350 portrait (feed), 1080x1080 square (stat of day), 2x DPR

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
- `content_calendar.yaml` — add all 12 posts
- `tests/test_count_query.py` — new tests for count query
