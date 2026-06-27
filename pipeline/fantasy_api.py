"""Fantasy API client — reads the live fantasy endpoints behind the picks UI.

The fantasy API lives under {API_BASE}/fantasy, uses its own OAuth2 form login
(username = email, password), and sits behind Cloudflare (so a browser-like
User-Agent is required or requests 403). Endpoints used here:

    POST /auth/login                       -> { access_token, ... }   (form-encoded)
    GET  /seasons/{year}                   -> { events: [...], tiers, ... }
    GET  /events/{id}/startlist            -> [StartListAthlete, ...]
    GET  /events/{id}/pick-stats           -> { athletes: [{athlete_id, pick_pct}] }

Credentials come from FANTASY_EMAIL / FANTASY_PASSWORD in .env (same as the picks
screen recorder). The fantasy event id is a different id space from the public
site events — resolve it from /seasons/{year} events[].id.
"""
import json
import os
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("API_BASE_URL", "https://api.windsurfworldtourstats.com/api/v1")
FANTASY_BASE = f"{API_BASE}/fantasy"
ORIGIN = "https://www.windsurfworldtourstats.com"
# Cloudflare rejects the default python-urllib UA; mimic a desktop browser.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _request(method: str, path: str, token: str | None = None,
             form: dict | None = None) -> dict | list:
    url = FANTASY_BASE + path
    data = urllib.parse.urlencode(form).encode() if form is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Origin", ORIGIN)
    req.add_header("Referer", ORIGIN + "/")
    req.add_header("Accept", "application/json")
    if form is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def login(email: str | None = None, password: str | None = None) -> str:
    """Log in and return a bearer token. Defaults to FANTASY_EMAIL/PASSWORD."""
    email = email or os.getenv("FANTASY_EMAIL")
    password = password or os.getenv("FANTASY_PASSWORD")
    if not email or not password:
        raise RuntimeError("FANTASY_EMAIL / FANTASY_PASSWORD must be set in .env")
    resp = _request("POST", "/auth/login", form={"username": email, "password": password})
    return resp["access_token"]


def get_season(year: int, token: str) -> dict:
    return _request("GET", f"/seasons/{year}", token=token)


def get_startlist(event_id: int, token: str) -> list:
    return _request("GET", f"/events/{event_id}/startlist", token=token)


def get_pick_stats(event_id: int, token: str) -> dict:
    return _request("GET", f"/events/{event_id}/pick-stats", token=token)


def find_event(season: dict, name_substr: str) -> dict | None:
    """Return the first event in a season whose name contains name_substr."""
    needle = name_substr.lower()
    for event in season.get("events", []):
        if needle in (event.get("event_name") or "").lower():
            return event
    return None
