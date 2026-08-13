# Carousel Design Audit — Fix Report

Audit of all 5 carousel slide types (cover, hero, podium, table, table_cta) plus tied variants (tied_grid, tied_highlight) and standalone CTA.

---

## Priority Summary

| Priority | Issue | Impact |
|----------|-------|--------|
| **P0** | Broken flag image (hero slide) | Visible bug in published content |
| **P0** | Duplicate watermark on slide 5 | Visible bug, looks unpolished |
| **P1** | Podium slide missing event context | Slide 3 has no title in per-event mode |
| **P1** | "10TH - 10TH" range label | Looks like a bug to viewers |
| **P2** | Cover slide gender color not discipline-aware | Inconsistent color story across slides |
| **P2** | Position pill color on tied_grid | Inconsistent with tied_highlight |
| **P3** | Container padding standardization | Subtle visual inconsistency |
| **P3** | Extract shared carousel CSS to base template | Maintenance/DX improvement |
| **P3** | Cover title wrapping variance | Minor layout shift |

---

## Findings

### 1. Broken Flag Image (Hero Slide — Slide 2) — P0

- **Issue**: Belgium flag on hero slide shows as broken image icon (`be` country code renders as tiny broken img placeholder)
- **Root cause**: `flagcdn.com` uses ISO 3166-1 alpha-2 codes. Belgium is `be` which should work — likely the `row.country` value from the DB is something unexpected (e.g. "BEL" 3-letter code, or the `.lower()` filter isn't being applied correctly for this athlete)
- **Fix**: Debug what `row.country` value Sol Degrieck gets from the DB. May need a country code mapping if DB stores 3-letter IOC codes
- **File**: `templates/carousel/slide_hero.html`, `pipeline/helpers.py` or `pipeline/db.py`

### 2. Duplicate Watermark on Slide 5 (table_cta) — P0

- **Issue**: Two overlapping "windsurfworldtourstats.com" watermarks visible in bottom-right corner — one from the `.watermark` div and one from the `.footer` div
- **Fix**: Remove either the `.footer` div or the `.watermark` div from `slide_table_cta.html`. The `.watermark` is the global carousel element; the `.footer` is redundant
- **File**: `templates/carousel/slide_table_cta.html`

### 3. Podium Slide Missing Event Context in Per-Event Mode — P1

- **Issue**: When `is_per_event` is true, the podium slide skips the eyebrow and title entirely (the conditional `{% if not is_per_event %}` gates both). This leaves slide 3 with just the "2ND - 3RD" pill and the two cards — no context about what event/discipline this is for. Compare to slides 4 and 5 which always show the event name eyebrow and full title
- **Fix**: The podium template should show the event name + title when `is_per_event` is true, matching the table slides' behavior
- **File**: `templates/carousel/slide_podium.html`

### 4. "10TH - 10TH" Range Label on Last Slide — P1

- **Issue**: When only 1 row remains for the final slide (e.g., just rank 10), the position pill reads "10TH - 10TH" which looks odd
- **Fix**: Add a conditional — if `rows[0].rank == rows[-1].rank`, show just "10TH" instead of "10TH - 10TH"
- **File**: `templates/carousel/slide_table.html`, `templates/carousel/slide_table_cta.html`

### 5. Cover Slide Gender Color Not Discipline-Aware — P2

- **Issue**: The hero slide (slide 2) uses discipline-based coloring (cyan for waves, gold for jumps) for the score, rank badge, and round label. But the cover slide (slide 1) always uses cyan for the gender word regardless of discipline
- **Fix**: The cover slide `.gender` class should also be discipline-aware — use gold for jumps to maintain visual continuity into slide 2
- **File**: `templates/carousel/slide_cover.html`

### 6. Position Pill Color Inconsistency on tied_grid — P2

- **Issue**:
  - Table slides (4, 5): Position pill is always cyan (`#00D4FF`) regardless of discipline
  - Tied grid: Position pill uses `#F0C040` (gold) always, even for waves
  - Tied highlight: Uses `{{ tie_accent }}` which is dynamic
- **Fix**: The position pill on tied_grid should use `{{ tie_accent }}` like tied_highlight does, so it adapts to discipline (cyan for waves, gold for jumps)
- **File**: `templates/carousel/slide_tied_grid.html`

### 7. Inconsistent Container Padding Across Slides — P3

| Slide | Template | Current Padding |
|-------|----------|----------------|
| 1 | cover | `60px 64px` |
| 2 | hero | `80px 60px` |
| 3 | podium | `60px 40px 40px` |
| 4 | table | `48px 64px 40px` |
| 5 | table_cta | `60px 40px 40px` |

- **Fix**: Standardize horizontal padding. The table slides use 40px sides (needed for table width), but at minimum align the top padding. Suggest: `48px 40px 40px` for slides 3-5, keeping cover/hero as special cases

### 8. Global Decorations Duplicated in Every Template — P3

- **Issue**: The accent-bar-right, accent-line-bottom, slide-counter, and watermark CSS blocks (~60 lines) are copy-pasted identically across all 8 carousel templates. This is a maintenance risk — any tweak requires editing 8 files
- **Fix**: Extract shared carousel decoration styles into a `carousel_base.html` that extends `base.html`, then have each slide extend `carousel_base.html`

### 9. Cover Title Sizing Inconsistency — P3

- **Issue**: On the cover slide, "WOMEN'S TOP 10 WAVES" wraps differently between carousel sets. The 260px font size causes layout variance depending on the word length of the metric
- **Fix**: Test with all metric variants (Waves, Jumps) and ensure consistent wrapping. Could use `max-width` or slightly smaller font to guarantee 3-line layout
- **File**: `templates/carousel/slide_cover.html`

### 10. CTA Slide Watermark Clash — P2

- **Issue**: The standalone `slide_cta.html` has both a `.watermark` (absolute bottom-right) and a `.footer` (absolute bottom-center). Two branding elements compete for the bottom of the slide
- **Fix**: Pick one. The watermark is the global convention; remove the separate `.footer` from `slide_cta.html`
- **File**: `templates/carousel/slide_cta.html`

---

## Files to Modify

| File | Issues |
|------|--------|
| `templates/carousel/slide_hero.html` | #1 Flag image debugging |
| `templates/carousel/slide_table_cta.html` | #2 Remove duplicate watermark/footer, #4 single-row range label |
| `templates/carousel/slide_podium.html` | #3 Show event name + title in per-event mode |
| `templates/carousel/slide_table.html` | #4 Handle single-row "Nth - Nth" edge case |
| `templates/carousel/slide_cover.html` | #5 Discipline-aware gender color, #9 title wrapping |
| `templates/carousel/slide_tied_grid.html` | #6 Use `{{ tie_accent }}` for position pill |
| `templates/carousel/slide_cta.html` | #10 Remove duplicate footer |
| `pipeline/helpers.py` or `pipeline/db.py` | #1 Debug country code for flag resolution |

---

## Verification

After applying fixes, render all 3 carousel variants with `--dry-run --preview`:

```bash
# Women's waves
python generate.py --template top_10 --score-type Wave --sex Women --dry-run --preview

# Men's waves
python generate.py --template top_10 --score-type Wave --sex Men --dry-run --preview

# Men's jumps
python generate.py --template top_10 --score-type Jump --sex Men --dry-run --preview
```

Confirm:
- [ ] Flags render correctly on hero slide (especially Belgium)
- [ ] No duplicate watermarks on final slide
- [ ] Podium slide shows event context in per-event mode
- [ ] Position pill shows single rank (not "Nth - Nth") when only 1 row
- [ ] Position pill colors are discipline-consistent across tied variants
- [ ] Cover slide gender color matches discipline (gold for jumps)
