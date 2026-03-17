"""Coming Soon carousel slide builder — 5 hardcoded slides for Instagram."""

ACCENT_COLOR = "#5AB4CC"

FEATURES = [
    {
        "title": "More Disciplines",
        "subtitle": "Foil Slalom, Slalom X & Freestyle results",
    },
    {
        "title": "Athlete Profiles",
        "subtitle": "Complete career stats for every athlete",
    },
    {
        "title": "Career Head to Heads",
        "subtitle": "Compare any two athletes across their careers",
    },
    {
        "title": "All-Time Score Lists",
        "subtitle": "The highest scores across every discipline, event and season",
    },
]


def build_coming_soon_slides() -> list[dict]:
    """Build 5 slide dicts: cover → 3 features → cta."""
    slides = []

    # Cover
    slides.append({
        "type": "coming_soon_cover",
        "title": "New Features",
        "subtitle": "What's next for windsurfworldtourstats.com",
        "accent_color": ACCENT_COLOR,
    })

    # Feature slides
    for feature in FEATURES:
        slides.append({
            "type": "coming_soon_feature",
            "title": feature["title"],
            "subtitle": feature["subtitle"],
            "accent_color": ACCENT_COLOR,
        })

    # CTA
    slides.append({
        "type": "coming_soon_cta",
        "handle": "@windsurfworldtourstats",
        "accent_color": ACCENT_COLOR,
    })

    total = len(slides)
    for i, slide in enumerate(slides, 1):
        slide["slide_number"] = i
        slide["total_slides"] = total

    return slides
