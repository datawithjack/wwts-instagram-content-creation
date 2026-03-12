"""About carousel slide builder — 4 hardcoded slides for Instagram."""

ACCENT_COLOR = "#00D4FF"

ABOUT_LINES = [
    'Every <span class="highlight">PWA</span> wave event result and score since 2016.',
    'Full <span class="highlight">LiveHeats</span> data from 2023 to present.',
    '<span class="highlight">Unified</span> athlete database.',
    'A <span class="highlight">different perspective</span> on athlete performance — compare head to heads, explore top 10 leaderboards, and dig into the numbers behind every event.',
]


def build_about_slides() -> list[dict]:
    """Build 4 slide dicts: cover → what we do → by the numbers → cta."""
    slides = []

    # Cover
    slides.append({
        "type": "about_cover",
        "title": "Windsurf World Tour Stats",
        "subtitle": "Digging into the numbers behind the PWA tour",
        "accent_color": ACCENT_COLOR,
    })

    # What's Inside
    slides.append({
        "type": "about_text",
        "title": "What's Inside",
        "lines": ABOUT_LINES,
        "accent_color": ACCENT_COLOR,
    })

    # By The Numbers
    slides.append({
        "type": "about_numbers",
        "title": "By The Numbers",
        "stats": [
            {"value": "58+", "label": "Events"},
            {"value": "350+", "label": "Athletes"},
            {"value": "43,000+", "label": "Scores"},
        ],
        "accent_color": ACCENT_COLOR,
    })

    # CTA
    slides.append({
        "type": "about_cta",
        "handle": "@windsurfworldtourstats",
        "accent_color": ACCENT_COLOR,
    })

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
