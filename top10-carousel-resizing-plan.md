# Carousel Resizing Plan

Goal: Increase text sizes across all carousel slides to better fill the 1080x1350 canvas.

## Top 10 Carousel

### Cover (`slide_cover.html`)
- Remove "PWA World Tour · " from eyebrow, keep just `{{ year }}`
- No change to year positioning

### Hero (`slide_hero.html`)
| Element | Before | After |
|---|---|---|
| rank-badge | 28px | 36px |
| big-score | 216px | 280px |
| athlete name (single) | 72px | 96px |
| athlete name (2-tie) | 52px | 68px |
| athlete name (3+ tie) | 40px | 52px |
| flag (multi) | 40x29 | 52x38 |
| flag (single) | 80x58 | 100x72 |
| trick pill | 15px | 20px |
| detail text | 18px | 24px |

### Table (`slide_table.html` + `slide_table_cta.html` — both share same column CSS)
| Element | Before | After |
|---|---|---|
| header labels | 20px | 24px |
| rank | 28px | 36px |
| flag | 36x26 | 44x32 |
| athlete | 36px | 44px |
| score | 44px | 56px |
| event col | 24px | 30px |
| type col | 18px | 22px |
| header override | 20px | 24px |

### Table CTA block (in `slide_table_cta.html`)
| Element | Before | After |
|---|---|---|
| cta-text | 80px | 100px |
| cta-url | 30px | 36px |
| cta-follow | 22px | 28px |

### CTA (`slide_cta.html`)
| Element | Before | After |
|---|---|---|
| headline | 24px | 32px |
| url | 72px | 96px |
| follow | 24px | 32px |

## About Carousel

### About CTA (`slide_about_cta.html`)
| Element | Before | After |
|---|---|---|
| cta-title | 88px | 110px |
| cta-url | 52px | 68px |
| cta-follow | 24px | 32px |

### About Numbers (`slide_about_numbers.html`)
| Element | Before | After |
|---|---|---|
| stat-value | 140px | 180px |
| stat-label | 28px | 36px |

### About Text (`slide_about_text.html`)
| Element | Before | After |
|---|---|---|
| text-line | 34px | 42px |

### About Features (`slide_about_features.html`)
| Element | Before | After |
|---|---|---|
| feature-text | 36px | 44px |

## Coming Soon Carousel

### Coming Soon CTA (`slide_coming_soon_cta.html`)
| Element | Before | After |
|---|---|---|
| cta-eyebrow | 28px | 36px |
| cta-title | 120px | 150px |
| cta-url | 52px | 68px |
| cta-follow | 24px | 32px |

### Coming Soon Feature (`slide_coming_soon_feature.html`)
| Element | Before | After |
|---|---|---|
| feature-subtitle | 32px | 40px |
