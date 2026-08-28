"""Find, rank and credit candidate photos for a rider from the PWA Drive.

The pure logic behind ``pick_photos.py``. Kept apart from the contact sheet and
the install step so the parts that are easy to get quietly wrong -- which files
belong to which rider, which copy to read, who took the shot -- can be tested
without a Drive mounted.

Three things the Drive does that a naive lookup gets wrong:

1. **Two sail formats.** The same rider appears as ``J7`` and ``JPN7``. Takuma
   Sugi is ``J-7`` in the API: searching only ``J7`` finds 6 files, ``JPN7``
   finds 44.
2. **Two copies of every frame, sometimes.** Tenerife keeps a ~1.5MB copy in the
   day folder and a ~26MB copy in ``HIGH RES`` under the same filename. Gran
   Canaria keeps only the large one.
3. **Credit varies by event and by file.** Tenerife 2025 is Rafa Soulart with
   the photographer in the filename; Tenerife 2026 is John Carter with it only
   in the XMP; and about a third of files carry no credit at all.
"""

import json
import os
import re
from pathlib import Path

from PIL import Image

from pipeline.helpers import ISO3_TO_ISO2, nationality_to_iso

# Athlete photos in this repo are 1920px on the long edge at 1-2.5MB. The slide
# is 1080x1350, so this is already generous; the Drive's 8192px originals are
# 20-40MB and have no business in git.
REPO_MAX_PX = 1920
JPEG_QUALITY = 88

# Sail as registered: letters, an optional separator, then digits.
_SAIL = re.compile(r"^([A-Za-z]+)[\s\-_]*(\d+)$")

# XMP is a plain-text packet near the head of the file, so the credit can be
# read without decoding the image -- which matters when the file is 40MB and
# streaming down from Drive.
_XMP_HEAD_BYTES = 300_000
_CREATOR = re.compile(rb"<dc:creator>\s*<rdf:Seq>\s*<rdf:li>([^<]+)</rdf:li>")
_RIGHTS = re.compile(rb"<dc:rights>\s*<rdf:Alt>\s*<rdf:li[^>]*>([^<]+)</rdf:li>")

# Photographers who sign their filenames. 2025 does this; 2026 does not.
FILENAME_MARKERS = {
    "RAFASOULART": ("Rafa Soulart", "@rafasoulart"),
    "PHOTOMEDANO": ("Photo Medano", ""),
    "JOHNCARTER": ("John Carter", "@jcwindsurf"),
    "TOMBRENDT": ("Tom Brendt", ""),
}

# Whatever the files call them, mapped to the handle a caption should credit.
HANDLES = {
    "john carter": "@jcwindsurf",
    "rafasoulart": "@rafasoulart",
    "rafael e.": "@rafasoulart",
    "tombrendtfoto": "",
}


def sail_tokens(sail_number, country: str = "") -> list[str]:
    """Candidate filename tokens for a rider, literal form first.

    ``("J-7", "Japan")`` -> ``["J7", "JAP7", "JPN7"]``. The alternates come from
    the athlete's country rather than a hardcoded letter map, so a rider from a
    country nobody has hit yet still works.

    Only expands towards the three-letter form, never back to a single letter:
    ``BRA105`` -> ``B105`` would collide with an unrelated rider.
    """
    if not sail_number:
        return []
    match = _SAIL.match(str(sail_number).strip())
    if not match:
        return []
    prefix, digits = match.group(1).upper(), match.group(2)

    tokens = [f"{prefix}{digits}"]

    iso2 = nationality_to_iso(country) if country else ""
    if iso2:
        aliases = sorted(code for code, two in ISO3_TO_ISO2.items() if two == iso2)
        tokens.extend(f"{code}{digits}" for code in aliases)

    seen = set()
    return [t for t in tokens if not (t in seen or seen.add(t))]


def token_of(filename: str) -> str:
    """The sail field of a PWA filename, e.g. ``TF26_wv_G21_1317.jpg`` -> G21.

    Returns "" for anything not in that shape rather than guessing, so an
    unexpected name is skipped instead of matched against the wrong rider.
    """
    parts = os.path.basename(str(filename)).split("_")
    return parts[2] if len(parts) >= 4 else ""


def matches_token(filename: str, token: str) -> bool:
    """Whether a file belongs to this sail. Whole field only, never a prefix.

    ``E95`` and ``E959`` are different riders, as are ``E11`` and ``E1111``.
    """
    return token_of(filename).upper() == str(token).upper()


def cheapest_copies(paths) -> list[Path]:
    """One path per distinct filename: the smallest copy that exists.

    Tenerife holds the same frame at 1.5MB and 26MB; reading the small one turns
    a several-minute contact sheet into a few seconds. Where only the large copy
    exists, as at Gran Canaria, this is a no-op.
    """
    best: dict[str, Path] = {}
    for raw in paths:
        path = Path(raw)
        key = path.name.lower()
        current = best.get(key)
        if current is None or path.stat().st_size < current.stat().st_size:
            best[key] = path
    return [best[k] for k in sorted(best)]


def _xmp_credit(path) -> tuple[str, str]:
    """(creator, rights) from the file's XMP packet, or ("", "")."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(_XMP_HEAD_BYTES)
    except OSError:
        return "", ""
    creator = _CREATOR.search(head)
    rights = _RIGHTS.search(head)
    return (creator.group(1).decode("utf-8", "replace").strip() if creator else "",
            rights.group(1).decode("utf-8", "replace").strip() if rights else "")


def credit_for(path) -> dict:
    """Who took this photo: filename marker, then XMP, then unknown.

    Never infers from a sibling file or from the event. Untagged frames turn up
    inside a folder named ``JOHN CARTER``, so a missing tag is not evidence that
    someone else shot it -- it is just missing.
    """
    path = Path(path)
    name = path.name
    flat = re.sub(r"[^A-Z0-9]", "", name.upper())

    for marker, (photographer, handle) in FILENAME_MARKERS.items():
        if marker in flat:
            return {"photographer": photographer, "handle": handle,
                    "source_file": name, "confirmed": True, "via": "filename"}

    creator, rights = _xmp_credit(path)
    if creator or rights:
        photographer = creator or rights
        handle = HANDLES.get(photographer.lower(), "")
        if not handle and rights:
            handle = HANDLES.get(rights.lower(), "")
        return {"photographer": photographer, "handle": handle,
                "source_file": name, "confirmed": True, "via": "xmp"}

    return {"photographer": "", "handle": "", "source_file": name,
            "confirmed": False, "via": "",
            "note": "UNTAGGED - credit unconfirmed"}


def find_year_root(year, drive_root: str = "") -> Path | None:
    """The shared PWA folder for a season, e.g. ``.../2026``.

    Google Drive exposes a folder shared with you at
    ``G:/.shortcut-targets-by-id/<target-id>/<name>`` once you add a shortcut to
    it. The id belongs to the folder, not the shortcut, so it survives the
    shortcut being moved or renamed -- but it changes if the share is recreated.
    Globbing for the year rather than hardcoding the id means neither breaks us.

    ``PWA_DRIVE_ROOT`` overrides, for a machine that syncs it somewhere else.
    """
    override = drive_root or os.environ.get("PWA_DRIVE_ROOT", "")
    if override:
        candidate = Path(override) / str(year)
        return candidate if candidate.is_dir() else None

    import glob as _glob
    for base in ("G:/.shortcut-targets-by-id/*", "G:/My Drive", "G:/Shared drives/*"):
        for hit in _glob.glob(f"{base}/{year}"):
            if os.path.isdir(hit):
                return Path(hit)
    return None


def thumbnail_for(src, cache_dir, max_px: int = 1000) -> Path:
    """A small cached copy of a frame, built once.

    Gran Canaria keeps only 20-40MB originals, and a baseline JPEG cannot be
    read in part, so the first sheet for such an event pays a real download.
    Keying the cache on size and mtime as well as the path means that cost is
    paid once and never again, including across runs.
    """
    src = Path(src)
    stat = src.stat()
    import hashlib
    key = hashlib.sha1(
        f"{src.resolve()}|{stat.st_size}|{int(stat.st_mtime)}|{max_px}".encode()
    ).hexdigest()[:16]

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{key}.jpg"
    if dest.exists():
        return dest

    with Image.open(src) as im:
        # draft() lets the JPEG decoder skip most of the work by decoding at a
        # fraction of full size -- worth a lot on an 8192px frame.
        im.draft("RGB", (max_px, max_px))
        im = im.convert("RGB")
        im.thumbnail((max_px, max_px), Image.LANCZOS)
        im.save(dest, "JPEG", quality=82, optimize=True)
    return dest


_FOLDER_PREFIX = re.compile(r"^\s*\d+\s*-\s*")


def match_event_folder(event_name: str, folder_names) -> str:
    """The Drive folder for an event, matched on its name.

    The Drive numbers its folders (``06 - TENERIFE``) and the API does not
    (``Tenerife Grand Slam``), so this strips the number and asks whether what
    is left appears in the event name. Longest match wins, so a folder called
    ``CANARIA`` cannot beat ``GRAN CANARIA``.

    Returns "" when nothing matches, rather than guessing at the closest
    folder -- picking photos from the wrong event is worse than picking none.
    """
    if not event_name or not folder_names:
        return ""
    haystack = re.sub(r"[^A-Z ]", "", event_name.upper())

    best, best_len = "", 0
    for folder in folder_names:
        stripped = _FOLDER_PREFIX.sub("", folder).strip().upper()
        if not stripped:
            continue
        if stripped in haystack and len(stripped) > best_len:
            best, best_len = folder, len(stripped)
    return best


def install_photo(src, dest_dir, athlete_id, max_px: int = REPO_MAX_PX,
                  square: int = 0) -> Path:
    """Copy a chosen frame into the repo as ``{athlete_id}.jpg``, downscaled.

    ``square`` crops a centred square first, for the headshot that feeds the
    slide's portrait mode when a rider has no landscape action shot.

    Never upscales: a source already smaller than ``max_px`` is written at its
    own size rather than interpolated up to look like something it is not.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{athlete_id}.jpg"

    with Image.open(src) as im:
        im = im.convert("RGB")
        if square:
            side = min(im.size)
            left = (im.width - side) // 2
            top = (im.height - side) // 2
            im = im.crop((left, top, left + side, top + side)).resize(
                (square, square), Image.LANCZOS)
        elif max(im.size) > max_px:
            im.thumbnail((max_px, max_px), Image.LANCZOS)
        im.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)

    return dest


def merge_json_entry(path, key: str, value, comment: str = "") -> dict:
    """Set one rider's entry in focus.json / credits.json, keeping the rest.

    Both files are hand-editable and hold every rider for an event, so a write
    has to merge rather than replace. A file that has been corrupted by hand is
    started again rather than allowed to swallow the new entry -- losing a
    broken file is better than silently not saving the pick.
    """
    path = Path(path)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except ValueError:
            data = {}

    if comment and "_comment" not in data:
        data["_comment"] = comment
    data[str(key)] = value

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + os.linesep,
                    encoding="utf-8")
    return data
