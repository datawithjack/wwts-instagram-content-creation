# Plan: Manual Athlete Photo Overrides

## Context
The API returns PWA profile page URLs (not actual images) for some athletes, so photo covers don't work for them. Athletes from Live Heats have proper image URLs. We already have local photos in `assets/photos/` (by ID or name), and the photo cover template (`slide_rp_cover_photo.html`) exists but isn't wired up. We need to centralize photo resolution: detect bad URLs, fall back to local files, and activate the photo cover automatically.

## Approach: Centralized `pipeline/photos.py`

One new module with a single `resolve_photo_url()` function that all templates call. Replaces scattered photo logic in 3 places.

### `resolve_photo_url(url_or_path, athlete_id=None, athlete_name=None) -> str`

Priority order:
1. Local file path exists → convert to `file:///` URL
2. Valid image URL (liveheats.com, or ends in `.jpg`/`.webp`/`.png`) → pass through
3. PWA page URL (contains `pwaworldtour.com`, no image extension) → discard
4. Local fallback by `athlete_id` → check `assets/photos/{id}.{webp,jpg,png}`
5. Local fallback by `athlete_name` → check `assets/photos/{name}.{webp,jpg,png}`
6. No match → return `""`

## Files to Modify

| File | Change |
|------|--------|
| `pipeline/photos.py` | **New** — `resolve_photo_url()` |
| `tests/test_photos.py` | **New** — 8 unit tests |
| `pipeline/api.py` | Wire `resolve_photo_url` into `fetch_head_to_head` + `fetch_athlete_event_stats` |
| `pipeline/rp_carousel.py` | Use `rp_cover_photo` type when photo exists |
| `tests/test_rp_carousel.py` | Add 2 tests for photo cover activation |
| `pipeline/analysis_carousel.py` | Replace inline fallback (lines 82-88) with `resolve_photo_url` |
| `pipeline/templates.py` | Remove lines 54-57 (file:/// conversion block), update `_resolve_photo` in dummy data |
| `generate.py` | Wire `resolve_photo_url` for athlete_rise path |

## Execution Order (TDD)

1. Write `tests/test_photos.py` (red)
2. Implement `pipeline/photos.py` (green)
3. Add photo cover tests to `tests/test_rp_carousel.py` (red)
4. Update `pipeline/rp_carousel.py` — activate photo cover (green)
5. Refactor: wire into `api.py`, `analysis_carousel.py`, `templates.py`, `generate.py`
6. Run full test suite

## Verification
- `python -m pytest tests/test_photos.py tests/test_rp_carousel.py -v`
- `python generate.py --template rider_profile --event 134 --athlete1 52 --division Men --preview` (Aloha Classic — has Live Heats photo, should get photo cover)
- `python generate.py --template rider_profile --event 119 --athlete1 187 --division Men --preview` (Margaret River — has `assets/photos/187.jpg`, should fall back to local and get photo cover)
- `python generate.py --template rider_profile --dry-run --preview` (dummy data, should use local photo)
