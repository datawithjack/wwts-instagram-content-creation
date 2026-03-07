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
| `pipeline/api.py` | API client (fetch_head_to_head, fetch_site_stats, fetch_event) |
| `pipeline/queries.py` | SQL query builders (build_top10_query) |
| `pipeline/db.py` | MySQL connection + query runner |
| `pipeline/templates.py` | Jinja2 env, filters, render_template, get_dummy_data |
| `pipeline/helpers.py` | Formatting helpers (ordinal, format_delta, country_flag, etc.) |
| `pipeline/renderer.py` | Playwright render_to_png, render_to_video |

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
```

## Templates
- `head_to_head.html` — Two-athlete comparison (wave events)
- `head_to_head_jump.html` — Two-athlete comparison (wave + jump events)
- `top_10.html` — Top 10 scores leaderboard
- `site_stats.html` — Site-wide stat counters (with count-up animation for video)

## Testing
```bash
# Fast tests (no Playwright)
python -m pytest tests/ --ignore=tests/test_renderer.py --ignore=tests/test_site_stats.py -v

# All tests (includes Playwright render)
python -m pytest tests/ -v
```

## Environment Variables
See `.env.example`. Key vars:
- `API_BASE_URL` — Production API (defaults to `https://api.windsurfworldtourstats.com/api/v1`)
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` — For top 10 queries

## Brand
- Fonts: Bebas Neue (display), Inter (body) — loaded from Google Fonts
- Colors: see `wwt_instagram_pipeline_plan.md` brand tokens section
- Output: 1080x1350 portrait (feed), 1080x1080 square (stat of day), 2x DPR
