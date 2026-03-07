"""Formatting helpers for Instagram templates."""
from datetime import date


def ordinal(n: int) -> str:
    """Convert integer to ordinal string: 1 -> '1st', 2 -> '2nd', etc."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_date_range(start: date, end: date) -> str:
    """Format date range: 'Jan 31 - Feb 08' or 'Jun 10' if same day."""
    if start == end:
        return start.strftime("%b %d")
    return f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"


def star_rating(tier: int, max_stars: int = 5) -> str:
    """Convert tier number to star string using filled/empty star chars."""
    return "\u2605" * tier + "\u2606" * (max_stars - tier)


def format_delta(value: float) -> str:
    """Format delta with sign: +2.70 or -1.50."""
    return f"{value:+.2f}"


def compute_deltas(row: dict, fields: list[str]) -> dict:
    """Compute athlete_2 - athlete_1 deltas for given stat fields."""
    deltas = {}
    for field in fields:
        a1 = row[f"athlete_1_{field}"]
        a2 = row[f"athlete_2_{field}"]
        deltas[f"delta_{field}"] = round(a2 - a1, 2)
    return deltas


def format_number(n: int) -> str:
    """Format integer with comma thousands separator."""
    return f"{n:,}"


def country_flag(code: str) -> str:
    """Convert 2-letter country code to flag emoji. e.g. 'ES' -> '🇪🇸'."""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())
