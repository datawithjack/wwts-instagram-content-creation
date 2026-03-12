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

### Missing Tokens (proposed additions to base.html)

| CSS Variable | Hex Value | Usage |
|---|---|---|
| `--color-star` | `#F0C040` | Star rating color (used in slide_cover) |
| `--color-bg-body` | `#0a0e1a` | Body background (currently hard-coded in base.html) |
| `--color-text-on-accent` | `#0E1927` | Dark text on accent backgrounds (used in slide_tied_grid) |

## Audit Checklist

Run these 6 checks in order. For each issue found, record the file path, line number, severity, and suggested fix.

### 1. Hard-coded Colors

**Grep** all `.html` files under `templates/` for hex color literals (`#[0-9a-fA-F]{3,8}`).

**Exclude** from findings:
- Lines inside `:root { }` block (these are the token definitions themselves)
- Jinja expressions using context variables (e.g., `{{ tie_accent }}`) — flag as **Info** note only

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

Two accepted padding patterns:
- `80px 60px` — centered/cover slides
- `60px 40px 40px` — data-heavy slides (tables, grids)

Flag any other padding values on the outermost `.container` or equivalent wrapper as **Info**.

### 5. Card Border Radius

Standard border-radius for `.card` elements: `8px` (defined in base.html). Flag deviations as **Info**.

### 6. Typography

- Display font (Bebas Neue): Should always be uppercase with `letter-spacing: 0.05em`
- Body font (Inter): Weight rules — 400 for body, 500-600 for emphasis, 700 for strong labels
- Flag any `font-family` declarations that don't use `var(--font-display)` or `var(--font-body)`

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

## New Template Checklist

When creating a new template, verify all 10 items:

1. Extends `base.html` via `{% extends "base.html" %}`
2. All colors use CSS variables from `:root` (no hard-coded hex)
3. Fonts use `var(--font-display)` or `var(--font-body)` (no direct `font-family` names)
4. Display text uses `text-transform: uppercase` and `letter-spacing: 0.05em`
5. Card elements use `.card` class or equivalent styles from base
6. Footer with `windsurfworldtourstats.com` (standalone templates) or URL on cover/CTA slides (carousels)
7. Dimensions match target: 1080x1350 (feed), 1080x1080 (square), or carousel slide size
8. Container padding follows accepted patterns (`80px 60px` or `60px 40px 40px`)
9. Background overlay via `bg_image_path` conditional (inherited from base.html)
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
