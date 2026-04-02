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


TRICK_TYPE_LABELS = {
    "F": "Forward",
    "2xF": "Double Forward",
    "B": "Backloop",
    "P": "Pushloop",
    "T": "Taka",
    "PF": "Push Forward",
    "TF": "Taka Forward",
    "PT": "Push Taka",
    "2xP": "Double Pushloop",
    "T2xF": "Taka Double Fwd",
    "3xF": "Triple Forward",
    "AC": "Air Chacho",
    "CR": "Cheese Roll",
    "SHAKKA": "Shaka",
    "AIR SPOCK": "Air Spock",
    "Jump": "Jump",
    "OTHER": "Other",
}


def trick_type_label(code: str) -> str:
    """Convert a trick type code to a display label."""
    if not code:
        return ""
    return TRICK_TYPE_LABELS.get(code.strip(), code.strip())


def clean_event_name(name: str) -> str:
    """Strip leading year and trailing star ratings from event names.

    e.g. '2025 Chile World Cup *****' -> 'Chile World Cup'
    """
    import re
    # Strip leading year (4 digits + space)
    name = re.sub(r"^\d{4}\s+", "", name)
    # Strip trailing stars
    name = re.sub(r"\s*\*+\s*$", "", name)
    return name.strip()


def heat_label_from_id(heat_id: str) -> str:
    """Extract a display heat label from a heat_id like '1830_48a' -> 'H48a'."""
    if not heat_id or "_" not in heat_id:
        return ""
    suffix = heat_id.rsplit("_", 1)[-1]
    return f"H{suffix}" if suffix else ""


def short_round_name(round_name: str) -> str:
    """Shorten round names for table display. e.g. 'Round 7' -> 'R7', 'Quarterfinal' -> 'QF'."""
    if not round_name:
        return ""
    import re
    m = re.match(r"^Round\s+(\d+)$", round_name, re.IGNORECASE)
    if m:
        return f"R{m.group(1)}"
    abbrevs = {
        "final": "Final",
        "semifinal": "SF",
        "semi": "SF",
        "quarterfinal": "QF",
        "quarter": "QF",
        "r1 seeding": "R1",
    }
    return abbrevs.get(round_name.strip().lower(), round_name)


def country_flag(code: str) -> str:
    """Convert 2-letter country code to flag emoji. e.g. 'ES' -> '🇪🇸'."""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


# Maps nationality strings (as stored in DB) to 2-letter ISO country codes
NATIONALITY_TO_ISO = {
    "american": "us",
    "andorran": "ad",
    "argentina": "ar",
    "argentinian": "ar",
    "aruba": "aw",
    "australia": "au",
    "australian": "au",
    "austrian": "at",
    "barbadian": "bb",
    "belgian": "be",
    "belgium": "be",
    "brazil": "br",
    "brazilian": "br",
    "british": "gb",
    "canada": "ca",
    "canadian": "ca",
    "catalan": "es",
    "chile": "cl",
    "chilean": "cl",
    "cypriot": "cy",
    "czech republic": "cz",
    "czechia": "cz",
    "danish": "dk",
    "denmark": "dk",
    "dutch": "nl",
    "fijian": "fj",
    "france": "fr",
    "french": "fr",
    "german": "de",
    "germany": "de",
    "greece": "gr",
    "greek": "gr",
    "guadeloupe": "gp",
    "hawaii": "us",
    "ireland": "ie",
    "israel": "il",
    "israeli": "il",
    "italian": "it",
    "italy": "it",
    "japan": "jp",
    "japanese": "jp",
    "latvia": "lv",
    "morocco": "ma",
    "netherlands": "nl",
    "norway": "no",
    "norwegian": "no",
    "peru": "pe",
    "poland": "pl",
    "polish": "pl",
    "puerto rican": "pr",
    "puerto rico": "pr",
    "russian": "ru",
    "saint barthélemy": "bl",
    "spain": "es",
    "spanish": "es",
    "swedish": "se",
    "swiss": "ch",
    "switzerland": "ch",
    "turkish": "tr",
    "united kingdom of great britain and northern ireland": "gb",
    "united states of america": "us",
    "uruguay": "uy",
    "venezuela (bolivarian republic of)": "ve",
    "venezuelan": "ve",
}


def nationality_to_iso(nationality: str) -> str:
    """Convert a nationality string to a 2-letter ISO country code.

    Returns empty string if no mapping found.
    """
    if not nationality:
        return ""
    return NATIONALITY_TO_ISO.get(nationality.strip().lower(), "")


# ISO 3166-1 alpha-3 to alpha-2 mapping (countries seen in windsurf tour data)
ISO3_TO_ISO2 = {
    "ARG": "ar", "ARU": "aw", "AUS": "au", "AUT": "at", "BAR": "bb",
    "BEL": "be", "BRA": "br", "CAN": "ca", "CHI": "cl", "COL": "co",
    "CRO": "hr", "CUW": "cw", "CZE": "cz", "DEN": "dk", "DOM": "do",
    "ECU": "ec", "ESP": "es", "FIN": "fi", "FRA": "fr", "GBR": "gb",
    "GER": "de", "GRE": "gr", "GUA": "gp", "HAW": "us", "HUN": "hu",
    "IRL": "ie", "ISR": "il", "ITA": "it", "JAP": "jp", "JPN": "jp",
    "KOR": "kr", "MAR": "ma", "MEX": "mx", "NCA": "nc", "NED": "nl",
    "NOR": "no", "NZL": "nz", "PER": "pe", "POL": "pl", "POR": "pt",
    "PUR": "pr", "RUS": "ru", "SUI": "ch", "SVK": "sk", "SWE": "se",
    "TUR": "tr", "UKR": "ua", "URU": "uy", "USA": "us", "VEN": "ve",
    "ZAF": "za", "RSA": "za", "AND": "ad", "BER": "bm",
}


def country_code_to_iso2(code: str) -> str:
    """Convert a 3-letter country code (e.g. 'ESP') to 2-letter ISO (e.g. 'es').

    If already 2 letters, returns lowercase. Returns empty string if unknown.
    """
    if not code:
        return ""
    code = code.strip().upper()
    if len(code) == 2:
        return code.lower()
    return ISO3_TO_ISO2.get(code, "")
