---
name: design-audit
description: Audit and enforce design consistency across WWTS Instagram HTML templates
user-invocable: true
allowed-tools: Read, Glob, Grep, Bash
---

# Design Audit Skill

Audit HTML templates for design consistency: CSS variable usage, typography, spacing, and footer presence.

## Trigger Phrases

- "audit templates" / "check design consistency"
- "create a new template" (applies new template checklist)
- `/design-audit` (explicit invocation)

## Modes of Operation

### Audit Mode (default, read-only)

Scan all templates under `templates/` and produce a structured report. **Do NOT modify any files.**

### Fix Mode (explicit request only)

Only when the user says "fix", "apply fixes", or similar. Replace hard-coded hex values with `var()` references, add missing tokens to `base.html`, remove duplicates. Respect CLAUDE.md rule: **never restructure HTML or alter layout** — only change CSS property values.

### New Template Mode

When creating a new template, enforce the New Template Checklist (below) so it's correct from the start.

## Design Tokens

Source of truth: `templates/base.html :root` block.

| CSS Variable | Hex Value | Usage |
|---|---|---|
| `--color-bg-gradient-start` | `rgba(10, 14, 26, 0.85)` | Overlay gradient start |
| `--color-bg-gradient-end` | `rgba(10, 14, 26, 0.95)` | Overlay gradient end |
| `--color-bg-card` | `rgba(30, 41, 59, 0.4)` | Card backgrounds |
| `--color-border-card` | `rgba(51, 65, 85, 0.5)` | Card borders |
| `--color-athlete-left` | `#38bdf8` | Primary accent / left athlete |
| `--color-athlete-left-bright` | `#0ea5e9` | Brighter variant of accent |
| `--color-athlete-right` | `#2dd4bf` | Secondary accent / right athlete |
| `--color-text-primary` | `#FFFFFF` | Primary text |
| `--color-text-muted` | `#9ca3af` | Muted/secondary text |
| `--color-text-label` | `#9ca3af` | Label text (uppercase) |
| `--color-rank-1st` | `#facc15` | Gold / 1st place |
| `--color-rank-2nd` | `#d1d5db` | Silver / 2nd place |
| `--color-rank-3rd` | `#d97706` | Bronze / 3rd place |
| `--font-display` | `'Bebas Neue', sans-serif` | Headlines, big numbers |
| `--font-body` | `'Inter', sans-serif` | Body text, labels |

### Carousel-Specific Tokens

Defined in `templates/carousel/base_carousel.html`:

| CSS Variable | Default | Usage |
|---|---|---|
| `--color-discipline` | `#00D4FF` | Dynamic accent color, passed via Jinja `{{ accent_color }}`. Changes per content type (e.g. wave vs jump). Used for eyebrows, position pills, CTA URLs, trick type labels. |

### Missing Tokens (proposed additions to base.html)

| CSS Variable | Hex Value | Usage |
|---|---|---|
| `--color-star` | `#F0C040` | Star rating color (slide_cover), gold badge/score (slide_hero) |
| `--color-bg-body` | `#0a0e1a` | Body background (currently hard-coded in base.html) |
| `--color-text-on-accent` | `#0E1927` | Dark text on accent backgrounds (position pills, rank badges) |

## Audit Checklist

Run these 6 checks in order. For each issue found, record the file path, line number, severity, and suggested fix.

### 1. Hard-coded Colors

**Grep** all `.html` files under `templates/` for hex color literals (`#[0-9a-fA-F]{3,8}`).

**Exclude** from findings:
- Lines inside `:root { }` block (these are the token definitions themselves)
- Jinja expressions using context variables (e.g., `{{ accent_color }}`, `{{ tie_accent }}`) — flag as **Info** note only
- `var(--color-discipline)` usage in carousel slides — this is the correct pattern (dynamic accent)

**Map** hard-coded hex values to expected CSS variables:

| Hard-coded Value | Expected Replacement | Severity |
|---|---|---|
| `#38bdf8` | `var(--color-athlete-left)` | Critical |
| `#0ea5e9` | `var(--color-athlete-left-bright)` | Critical |
| `#2dd4bf` | `var(--color-athlete-right)` | Critical |
| `#FFFFFF` / `#ffffff` | `var(--color-text-primary)` | Warning |
| `#9ca3af` | `var(--color-text-muted)` | Warning |
| `#facc15` | `var(--color-rank-1st)` | Warning |
| `#d1d5db` | `var(--color-rank-2nd)` | Warning |
| `#d97706` | `var(--color-rank-3rd)` | Warning |
| `#F0C040` | `var(--color-star)` (needs adding to base.html) | Medium |
| `#0a0e1a` | `var(--color-bg-body)` (needs adding to base.html) | Low |
| `#0E1927` | `var(--color-text-on-accent)` (needs adding to base.html) | Low |

### 2. Footer Presence

- **Standalone templates** (1080x1350 single-image posts): Must have a footer with `windsurfworldtourstats.com`
- **Carousel slides**: Cover slide and CTA slide should have footer/URL. Mid-carousel slides (table, hero, podium) may omit it.
- **Duplicate footers**: Flag any template with the URL appearing more than once (severity: Low)

### 3. Duplicate Content

Check for repeated HTML blocks within a single template. Known issue: `slide_cta.html` has both a `.cta-url` div and a `.footer` div both containing `windsurfworldtourstats.com`.

### 4. Container Padding

Accepted padding patterns by template type:

**Standalone templates (1080x1350):**
- `80px 60px` — centered/cover layouts
- `60px 40px 40px` — data-heavy layouts

**Carousel slides (1080x1350):**
- `60px 64px` — cover slide (centered)
- `80px 60px` — hero slide (centered)
- `48px 64px 64px` — table slide (data-heavy)
- `60px 40px 40px` — table+CTA slide (data-heavy with CTA below)
- `120px 64px` — standalone CTA slide (centered, generous vertical breathing room)

Flag any other padding values on the outermost `.container` or equivalent wrapper as **Info**.

### 5. Card Border Radius

Standard border-radius for `.card` elements: `8px` (defined in base.html). Flag deviations as **Info**.

### 6. Typography

- Display font (Bebas Neue): Should always be uppercase with `letter-spacing: 0.04–0.05em`
- Body font (Inter): Weight rules — 400 for body, 500-600 for emphasis, 700 for strong labels
- Flag any `font-family` declarations that don't use `var(--font-display)` or `var(--font-body)`

#### Carousel Typography Scale

Established sizes from the top 10 carousel (reference for new carousels):

| Element | Font | Size | Weight | Spacing | Notes |
|---|---|---|---|---|---|
| Cover title | Display | 260px | 700 | 0.04em | Main hook text, multi-line |
| Big score (hero) | Display | 216px | — | 0.02em | Single large number |
| Slide title | Display | 100px | — | 0.04em | Section headers on data slides |
| CTA text | Display | 80px | — | 0.04em | "Full leaderboard & more stats" |
| CTA URL | Display | 72px | — | 0.03em | `windsurfworldtourstats.com` |
| Athlete name (hero, single) | Display | 72px | — | 0.04em | On hero slide, no tie |
| Athlete name (hero, 2-way tie) | Display | 52px | — | 0.04em | Scales down with ties |
| Athlete name (hero, 3+ tie) | Display | 40px | — | 0.04em | Scales down further |
| Score (table) | Body | 44px | 900 | — | Bold score values in table |
| Position pill | Display | 44px | 700 | 0.04em | "1ST – 5TH" range labels |
| Athlete (table) | Body | 36px | 500 | — | Names in table rows |
| Event meta | Body | 30px | 500 | 0.06em | Date ranges, star ratings |
| CTA URL (table+CTA) | Body | 30px | 600 | 0.05em | Smaller URL on combo slides |
| Eyebrow | Body | 28px | 700 | 0.1em | Uppercase, accent-colored |
| Rank (table) | Body | 28px | 600 | — | Position numbers |
| Rank badge (hero) | Display | 28px | — | 0.15em | Gold pill "BEST WAVE SCORE" |
| Cover subtitle | Body | 28px | 400 | 0.08em | "2025 Season" |
| Table event col | Body | 24px | — | — | Event names in table |
| CTA headline | Body | 24px | 600 | 0.12em | "See the full Top 10 at..." |
| CTA follow | Body | 24px | 600 | 0.12em | "@windsurfworldtourstats · Follow" |
| Table header | Body | 20px | 600 | 0.1em | Column headers |
| Swipe hint | Body | 18px | — | 0.12em | "Swipe to reveal →", 25% opacity |
| Trick type | Body | 18px | 600 | 0.04em | Uppercase, discipline-colored |
| Hero detail | Body | 18px | — | 0.05em | Event name + round info |
| Trick badge (hero) | Body | 15px | 700 | 0.04em | Pill on hero athlete row |

## Audit Report Format

```
## Design Audit Report

**Templates scanned**: N
**Issues found**: X critical, Y warnings, Z notes

### Critical
- `templates/carousel/slide_cover.html:50` — Hard-coded `#38bdf8`, use `var(--color-athlete-left)`
  ...

### Warning
- ...

### Note
- `templates/carousel/slide_tied_highlight.html` — Uses `{{ tie_accent }}` Jinja context variable for accent color (not an error, but not a CSS variable)
  ...
```

## Carousel Architecture

Carousel slides use a layered template inheritance:

```
base.html                          ← global tokens, fonts, body sizing, bg overlay
  └─ carousel/base_carousel.html   ← --color-discipline, shared carousel classes (.eyebrow, .slide-title, .position-pill, .container)
       └─ carousel/slide_*.html    ← individual slide templates
```

### Shared files
- `carousel/base_carousel.html` — defines `--color-discipline`, shared CSS classes, block structure (`carousel_head`, `carousel_content`)
- `carousel/_macros.html` — reusable Jinja macros:
  - `table_component(rows, show_trick_type, is_per_event, row_height)` — data table with rank/flag/athlete/score columns
  - `cta_block(discipline)` — "Full leaderboard & more stats" + URL + follow text
  - `slide_header(title, event_name, is_per_event, pill_text)` — eyebrow + title + position pill

### Shared CSS classes (from base_carousel.html)
| Class | Purpose |
|---|---|
| `.eyebrow` | Small uppercase accent-colored label (Inter 28px/700) |
| `.slide-title` | Large section header (Bebas Neue 100px) |
| `.position-pill` | Accent-bg pill showing rank range (Bebas Neue 44px) |
| `.container` | Full-width/height flex column — each slide overrides padding/alignment |

### Carousel slide types (top 10 carousel, established)
| Slide | File | Purpose |
|---|---|---|
| Cover | `slide_cover.html` | Big title hook, event info, "Swipe to reveal" |
| Hero | `slide_hero.html` | #1 score spotlight with gold badge, big score, athlete(s) |
| Table | `slide_table.html` | 5-row data table (ranks 2-6 or 6-10) |
| Table+CTA | `slide_table_cta.html` | 3-row data table + CTA block below |
| CTA | `slide_cta.html` | Standalone CTA: URL + follow prompt |

## New Template Checklist

When creating a new template, verify all items:

### Standalone templates (single-image posts)
1. Extends `base.html` via `{% extends "base.html" %}`
2. All colors use CSS variables from `:root` (no hard-coded hex)
3. Fonts use `var(--font-display)` or `var(--font-body)` (no direct `font-family` names)
4. Display text uses `text-transform: uppercase` and `letter-spacing: 0.04–0.05em`
5. Card elements use `.card` class or equivalent styles from base
6. Footer with `windsurfworldtourstats.com`
7. Dimensions: 1080x1350 (feed) or 1080x1080 (square), 2x DPR
8. Container padding follows accepted patterns
9. Background overlay via `bg_image_path` conditional (inherited from base.html)
10. No duplicate content blocks

### Carousel slides
1. Extends `carousel/base_carousel.html` (NOT `base.html` directly)
2. Uses `{% block carousel_head %}` for styles and `{% block carousel_content %}` for HTML
3. Imports macros from `carousel/_macros.html` as needed
4. Uses `var(--color-discipline)` for accent color (not hard-coded accent hex)
5. All other colors use CSS variables from base `:root`
6. Fonts use `var(--font-display)` or `var(--font-body)`
7. Typography sizes follow the carousel scale (see Typography section)
8. Container padding follows carousel patterns (see Container Padding section)
9. Cover and CTA slides include `windsurfworldtourstats.com` URL
10. No duplicate content blocks

## Fix Mode Rules

When applying fixes:

1. **Only change CSS property values** — never restructure HTML, reorder elements, or alter layout
2. **Add missing tokens** to `base.html :root` block if needed (e.g., `--color-star`)
3. **Replace hex literals** with `var()` references using the mapping table above
4. **Remove duplicates** — keep the semantically correct instance (e.g., keep `.footer`, remove duplicate `.cta-url` if they're redundant)
5. **Never touch** Jinja template variables like `{{ tie_accent }}` — these are intentionally dynamic
6. **Test after fixing** — run `python -m pytest tests/ --ignore=tests/test_renderer.py --ignore=tests/test_site_stats.py -v`

## Canonical Reference

For the full brand design system (colors, typography, spacing, components), see:
`C:\Users\jackf\OneDrive\Documents\Projects\windsurf-world-tour-stats-app\docs\instagram-style-guide.md`
