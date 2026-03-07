# WWT Instagram Automation Pipeline
## windsurfworldtourstats.com | Jack Frank Andrew

---

## Overview

Automated Instagram content generation pipeline that pulls live data from MySQL HeatWave (Oracle Cloud), populates Figma-matched HTML templates, renders pixel-perfect PNG/MP4 outputs via Playwright, and queues posts for publishing -- zero manual data entry.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Data source | MySQL HeatWave (Oracle Cloud) |
| Backend / CLI | Python 3.11+ |
| Template engine | HTML/CSS (Jinja2) |
| Renderer | Playwright for Python (headless Chromium) |
| Fonts | Google Fonts -- Bebas Neue, Inter |
| Video (Reels) | Remotion (React-based, later phase) |
| Scheduling | Python cron / GitHub Actions |
| Post publishing | Buffer API or Meta Graph API (later phase) |
| Config | `.env` + `config.yaml` |

---

## Brand Tokens

```css
/* Aligned with main app design system (windsurf-world-tour-stats-app) */
--color-bg-gradient-start: rgba(10, 14, 26, 0.85);
--color-bg-gradient-end: rgba(10, 14, 26, 0.95);
--color-bg-card: rgba(30, 41, 59, 0.4);       /* slate-800/40 */
--color-border-card: rgba(51, 65, 85, 0.5);    /* slate-700/50 */
--color-athlete-left: #38bdf8;                  /* cyan-400 -- athlete 1 */
--color-athlete-left-bright: #0ea5e9;           /* cyan-500 */
--color-athlete-right: #2dd4bf;                 /* teal-400 -- athlete 2 */
--color-text-primary: #FFFFFF;
--color-text-muted: #9ca3af;                    /* gray-400 */
--color-text-label: #9ca3af;                    /* gray-400, uppercase */
--color-rank-1st: #facc15;                      /* yellow-400 */
--color-rank-2nd: #d1d5db;                      /* gray-300 */
--color-rank-3rd: #d97706;                      /* amber-600 */
--font-display: 'Bebas Neue', sans-serif;
--font-body: 'Inter', sans-serif;
```

---

## Directory Structure

```
wwt-instagram-pipeline/
├── README.md
├── .env                          # DB credentials, API keys
├── config.yaml                   # Template dimensions, default params, hashtag sets
├── requirements.txt              # Python dependencies
├── pyproject.toml                # Project metadata
│
├── data/
│   └── queries/
│       ├── head_to_head.sql
│       ├── top_10_waves.sql
│       ├── rider_profile.sql
│       ├── stat_of_the_day.sql
│       └── site_stats.sql
│
├── templates/
│   ├── base.html                 # Shared layout, fonts, CSS variables
│   ├── head_to_head.html
│   ├── top_10.html
│   ├── rider_profile.html
│   ├── stat_of_the_day.html
│   └── site_stats.html
│
├── assets/
│   ├── backgrounds/
│   │   └── ocean_bg.jpg          # Background texture from Figma
│   ├── logos/
│   │   └── wwt_logo.png
│   └── fonts/                    # Local font fallbacks if needed
│
├── pipeline/
│   ├── __init__.py
│   ├── db.py                     # MySQL HeatWave connection + query runner
│   ├── renderer.py               # Playwright render orchestration (Python-native)
│   ├── templates.py              # Jinja2 template population + helpers
│   ├── images.py                 # Athlete photo fetching/caching
│   └── publisher.py              # Buffer/Meta API posting (Phase 2)
│
├── tests/
│   ├── __init__.py
│   ├── test_db.py
│   ├── test_templates.py
│   ├── test_renderer.py
│   └── test_helpers.py
│
├── generate.py                   # Main entry point
│
└── output/
    ├── png/                      # Rendered static images
    └── mp4/                      # Rendered Reels (Phase 2)
```

---

## Phase 1 -- Static Image Pipeline

### Step 1: Helpers + Tests (`pipeline/templates.py`)

Pure formatting functions, tested first:
- `ordinal(n)` -- 1 -> "1st", 2 -> "2nd", etc.
- `format_date_range(start, end)` -- "Jan 31 - Feb 08"
- `star_rating(tier)` -- event tier -> star string
- `format_delta(value)` -- "+2.70" with sign

### Step 2: Database Connection (`pipeline/db.py`)

- Connect to MySQL HeatWave via `mysql-connector-python`
- Load credentials from `.env`
- Generic `run_query(sql, params)` function returning list of dicts
- Simple single connection (no pooling needed for CLI tool)
- `lookup_athlete_id(name_slug)` -- resolves slugs like "sarah_kenyon" to athlete IDs

### Step 3: SQL Queries (`data/queries/`)

Each template has a dedicated SQL file. Parameterised by:
- `event_id` -- for event-specific posts
- `athlete_id` / `athlete_id_2` -- for head to head / rider profile
- `year` / `discipline` -- for top 10, stat of the day

**head_to_head.sql** should return:
```
athlete_1_name, athlete_1_photo_url, athlete_1_placement,
athlete_1_heat_wins, athlete_1_best_heat, athlete_1_avg_heat,
athlete_1_best_wave, athlete_1_avg_wave,
athlete_2_name, athlete_2_photo_url, athlete_2_placement,
athlete_2_heat_wins, athlete_2_best_heat, athlete_2_avg_heat,
athlete_2_best_wave, athlete_2_avg_wave,
event_name, event_country, event_date_start, event_date_end, event_tier
```

Deltas computed in Python helpers for flexibility, not in SQL.

### Step 4: Template Population (`pipeline/templates.py`)

- Jinja2 renders HTML templates with injected data
- Registers custom filters: ordinal, format_date_range, star_rating, format_delta
- Handles:
  - Delta sign logic (positive shown on winning athlete's side)
  - Photo URL injection with CSS fallback placeholder (initials on coloured bg)

### Step 5: Athlete Photos (`pipeline/images.py`)

- Fetch athlete profile photo from DB stored URL
- Cache locally in `assets/photos/` by athlete_id
- Photo placeholders handled via CSS in templates (initials on coloured bg) -- no Pillow needed
- Rounded corners via CSS `border-radius` in template

### Step 6: Playwright Render (`pipeline/renderer.py`)

All Python, no Node.js subprocess:
```python
# Uses playwright for Python directly
# Launches headless Chromium
# Loads populated HTML via file:// URL
# Waits for fonts + images to load
# Screenshots at 2x device pixel ratio for retina quality
# Saves to output/png/
# Background image referenced via file:// absolute path (no base64 bloat)
```

### Step 7: Main Entry Point (`generate.py`)

```python
# CLI usage examples:
python generate.py --template head_to_head --athlete1 sarah_kenyon --athlete2 jane_seman --event margaret_river_2026
python generate.py --template top_10 --discipline mens --year 2025
python generate.py --template rider_profile --athlete jaegar_stone
python generate.py --template stat_of_the_day --auto   # picks best stat automatically
python generate.py --template site_stats               # pulls live counts from DB

# Utility flags:
python generate.py --template head_to_head --dry-run   # uses dummy data, no DB needed
python generate.py --template head_to_head --preview    # opens HTML in browser, skips render
```

---

## Templates to Build

### 1. Head to Head (design complete)
- Parameters: athlete_1, athlete_2, event
- Output: 1080x1350px portrait

### 2. Top 10 Waves / Scores
- Parameters: discipline (mens/womens), year, metric (wave_score/heat_score)
- Output: 1080x1350px portrait
- Design: already drafted

### 3. Site Stats / Milestone
- Parameters: none (live DB counts)
- Output: 1080x1350px portrait
- Animation version: Reels (Phase 2)

### 4. Rider Profile (to design)
- Parameters: athlete_id
- Suggested content: name, nationality, career wins, best event result, highest single wave, current world ranking, events competed
- Output: 1080x1350px portrait

### 5. Stat of the Day (to design)
- Parameters: date or auto-select
- Suggested content: single headline stat with context -- "Highest wave score ever recorded at Margaret River"
- Output: 1080x1080px square

### 6. New Feature Announcement (to design)
- Parameters: feature name, description, URL
- Output: 1080x1080px square

---

## Output Specifications

| Format | Dimensions | DPR | Use |
|---|---|---|---|
| Portrait | 1080 x 1350px | 2x | Feed posts |
| Square | 1080 x 1080px | 2x | Stat of day, announcements |
| Story/Reel | 1080 x 1920px | 2x | Phase 2 |

---

## Config (`config.yaml`)

```yaml
templates:
  head_to_head:
    width: 1080
    height: 1350
    dpr: 2
  top_10:
    width: 1080
    height: 1350
    dpr: 2
  site_stats:
    width: 1080
    height: 1350
    dpr: 2
  stat_of_the_day:
    width: 1080
    height: 1080
    dpr: 2

hashtags:
  head_to_head:
    - "#windsurf"
    - "#PWA"
    - "#wavewindsurfing"
    - "#windsurfstats"
  top_10:
    - "#windsurf"
    - "#PWA"
    - "#topwaves"
    - "#windsurfstats"
  default:
    - "#windsurf"
    - "#PWA"
    - "#windsurfstats"

output_dir: ./output
assets_dir: ./assets
```

---

## Phase 2 -- Animated Reels (Remotion)

Build after Phase 1 is stable.

### Site Stats Counter Reel
- Sequence: background fade -> numbers count up (0 to target, eased) -> labels fade in -> logo slides up -> URL appears -> hold 2s -> loop
- Duration: ~5 seconds
- Built in Remotion (React), exported via `npx remotion render`

### Head to Head Reveal Reel
- Sequence: event title -> athlete names slide in from sides -> stats reveal row by row -> deltas pop in -> hold
- Duration: ~8 seconds

### Remotion stack:
```
remotion/
├── src/
│   ├── compositions/
│   │   ├── SiteStats.tsx
│   │   └── HeadToHead.tsx
│   └── Root.tsx
└── package.json
```

---

## Phase 3 -- Auto Publishing

- **Buffer API** -- simplest, supports Instagram scheduling, good free tier
- **Meta Graph API** -- direct, requires Facebook Business setup, more control
- Recommend Buffer first for speed, migrate to Meta Graph API if needed

**publisher.py** responsibilities:
- Upload PNG to Buffer/Meta
- Set caption (auto-generated from template data)
- Schedule post time (configurable -- e.g. 7am Qatar time)
- Log post history to avoid duplicates

---

## Caption Generation

Auto-generate captions from template data:

```python
# Head to Head example output:
"HEAD TO HEAD | 2026 Margaret River Wave Classic

Sarah Kenyon 1st vs Jane Seman 2nd

Despite finishing 2nd, Jane posted better heat and wave scores across the event.

Full stats at windsurfworldtourstats.com

#windsurf #PWA #wavewindsurfing #MargaretRiver #windsurfstats"
```

Hashtag sets stored in `config.yaml` by post type.

---

## Environment Variables (`.env`)

```
# Database
MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DATABASE=

# Oracle Cloud (if using OCI SDK)
OCI_CONFIG_PATH=~/.oci/config

# Publishing (Phase 3)
BUFFER_ACCESS_TOKEN=
META_ACCESS_TOKEN=
META_INSTAGRAM_ACCOUNT_ID=

# Paths
OUTPUT_DIR=./output
ASSETS_DIR=./assets
```

---

## Python Dependencies (`requirements.txt`)

```
mysql-connector-python
jinja2
Pillow
python-dotenv
pyyaml
requests
playwright
pytest
```

---

## Development Order (TDD)

1. **Tests first**: `tests/test_helpers.py` -- ordinal, date formatting, star rating, delta formatting
2. **Helpers**: `pipeline/templates.py` -- implement helpers to pass tests
3. **Tests**: `tests/test_db.py` -- mock DB connection and query runner
4. **DB module**: `pipeline/db.py` -- connection + query runner + slug lookup
5. **SQL**: `data/queries/head_to_head.sql` -- first query
6. **Template**: `templates/base.html` + `templates/head_to_head.html` -- pixel-perfect Figma recreation
7. **Tests**: `tests/test_templates.py` -- assert rendered HTML contains expected values
8. **Template engine**: `pipeline/templates.py` -- Jinja2 population with filters
9. **Tests**: `tests/test_renderer.py` -- Playwright render produces PNG
10. **Renderer**: `pipeline/renderer.py` -- Playwright Python screenshot
11. **Images**: `pipeline/images.py` -- photo fetch and cache
12. **CLI**: `generate.py` -- entry point with --dry-run and --preview flags
13. Remaining templates (top_10, site_stats, rider_profile, stat_of_the_day)
14. Phase 2: Remotion animations
15. Phase 3: Auto publishing

---

## Notes for Build Sessions

- Match Figma exactly -- use `--font-display: 'Bebas Neue'` and `--font-body: 'Inter'` loaded from Google Fonts in base.html
- Playwright must wait for `document.fonts.ready` before screenshotting
- Render at `device_scale_factor=2` for retina output
- Background ocean image referenced via `file://` absolute path (no base64 bloat)
- Athlete photos fetched and cached locally before render -- never fetch at render time
- Deltas computed in Python helpers for flexibility and testability
- Keep templates as pure HTML/CSS -- no JS in templates
- Test each template with hardcoded dummy data before wiring to DB
- Photo placeholders via CSS (initials on coloured bg), not Pillow
- Rounded corners via CSS `border-radius`, not image processing
