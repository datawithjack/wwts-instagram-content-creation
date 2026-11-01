"""Which lifestyle frame belongs to which athlete, and where the headshot sits.

The pure half of ``build_headshots.py`` (#32), kept apart so the part that is
easy to get quietly wrong -- matching a frame to a person -- is tested without
a Drive or a database.

**A frame is matched on the sail its rider held AT the event it was shot at.**
The stats site's fallback photo keys off a rider's *current* sail, and PWA
reassigns sails, which is how Alice Arutkin came to render as a man (stats-app
#230). A frame's filename carries its event and year (``SY25_ls_GRE734_...``),
so the lookup uses that event's own results and nothing else.
"""

import re
from pathlib import Path

from PIL import Image

from pipeline.photo_picker import sail_tokens

# EVENTYY_kind_SAIL_... : SY25_ls_ARU91_00156 copy.jpg,
# SY25_fl_ITA140_RAFASOULART_00240 copy.jpg
_FRAME = re.compile(r"^([A-Za-z]+)(\d{2})_([A-Za-z]+)_([A-Za-z0-9]+)_")

# Posed portraits beat candid lifestyle, which beats whatever the day folders
# hold. Matched on the folder path, case-insensitively.
_FOLDER_RANK = (("rider portraits", 0), ("lifestyle", 1))

# How many face-heights the square spans, and where the face sits in it: a
# little above centre leaves room for shoulders, which is what a round avatar
# crops down to.
DEFAULT_SCALE = 2.6
FACE_CENTRE_FROM_TOP = 0.42

# Matches assets/photos/faces/: one file serves the Instagram slides and the
# stats site's avatars (#33 uploads these bytes unchanged).
HEADSHOT_PX = 640
HEADSHOT_QUALITY = 85

_EXIF_ARTIST = 0x013B
_EXIF_COPYRIGHT = 0x8298


def parse_frame(name: str) -> dict | None:
    """``SY25_ls_ARU91_00156 copy.jpg`` -> event code, year, kind and sail.

    None for anything not in the convention -- a frame with no sail in its
    name has no rider we can name, and guessing is how #230 happened.
    """
    m = _FRAME.match(name)
    if not m:
        return None
    return {"event_code": m.group(1).upper(), "year": 2000 + int(m.group(2)),
            "kind": m.group(3).lower(), "token": m.group(4).upper()}


def holders_by_token(results) -> dict[str, int]:
    """Filename sail token -> the one athlete who held it at this event.

    ``results`` is ``(athlete_id, sail_number, nationality)`` for every result
    row of ONE event. A token two different athletes held there is dropped: the
    filename cannot say which of them is in the picture.
    """
    seen: dict[str, set] = {}
    for athlete_id, sail, nationality in results:
        for token in sail_tokens(sail, nationality or ""):
            seen.setdefault(token.upper(), set()).add(athlete_id)
    return {tok: next(iter(ids)) for tok, ids in seen.items() if len(ids) == 1}


def frames_for(athlete_id, files, holders, event_code: str, year: int,
               kinds=("ls",)) -> list[tuple[str, str]]:
    """This athlete's frames from one event: ``(folder, filename)`` pairs.

    Lifestyle only by default -- an action shot is a helmet, a harness line and
    a rider forty metres away.
    """
    out = []
    for folder, name in files:
        frame = parse_frame(name)
        if (frame and frame["event_code"] == event_code.upper()
                and frame["year"] == year and frame["kind"] in kinds
                and holders.get(frame["token"]) == athlete_id):
            out.append((folder, name))
    return out


def _folder_rank(folder: str) -> int:
    lowered = folder.lower()
    for needle, rank in _FOLDER_RANK:
        if needle in lowered:
            return rank
    return len(_FOLDER_RANK)


def _frame_key(name: str) -> str:
    """``SY25_ls_GRE734_00036 copy.jpg`` and ``SY25_ls_GRE734_00036.jpg`` are one frame."""
    stem = name.rsplit(".", 1)[0].lower()
    return stem[:-5] if stem.endswith(" copy") else stem


def rank_frames(frames, limit: int = 6) -> list[tuple[str, str]]:
    """Best folders first, then by filename, one copy per frame; at most ``limit``.

    Where a frame sits in two folders, the better folder's copy is kept.
    """
    seen, out = set(), []
    for folder, name in sorted(frames, key=lambda f: (_folder_rank(f[0]), f[1])):
        key = _frame_key(name)
        if key not in seen:
            seen.add(key)
            out.append((folder, name))
    return out[:limit]


def square_box(width: int, height: int, face, scale: float = DEFAULT_SCALE):
    """``(left, top, side)`` of a square around ``face`` = ``(x, y, w, h)``.

    Sized from the face, placed with the face a little above centre, then
    pushed back inside the frame. Never larger than the frame's short edge.
    """
    x, y, w, h = face
    side = min(int(max(w, h) * scale), width, height)
    left = int(x + w / 2 - side / 2)
    top = int(y + h / 2 - side * FACE_CENTRE_FROM_TOP)
    left = max(0, min(left, width - side))
    top = max(0, min(top, height - side))
    return left, top, side


def render_headshot(src, box, dest, credit=None, size: int = HEADSHOT_PX) -> Path:
    """Crop ``box`` out of ``src`` and write a square JPEG headshot to ``dest``.

    ``box`` is ``(left, top, side)`` as fractions -- of the width, the height
    and the SHORT edge -- so a box drawn on the sheet's thumbnail lands in the
    same place on the larger copy rendered here.

    Never upscales: a crop smaller than ``size`` is written at its own size.
    The photographer goes into EXIF Artist/Copyright so the credit travels with
    the file; an unknown credit is left out rather than guessed.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    left_f, top_f, side_f = box

    with Image.open(src) as im:
        im = im.convert("RGB")
        width, height = im.size
        side = max(1, min(round(side_f * min(width, height)), width, height))
        left = max(0, min(round(left_f * width), width - side))
        top = max(0, min(round(top_f * height), height - side))
        out = im.crop((left, top, left + side, top + side))
    if side > size:
        out = out.resize((size, size), Image.LANCZOS)

    exif = Image.Exif()
    photographer = ((credit or {}).get("photographer") or "").strip()
    if photographer:
        exif[_EXIF_ARTIST] = photographer
        exif[_EXIF_COPYRIGHT] = f"PWA World Tour / {photographer}"
    out.save(dest, "JPEG", quality=HEADSHOT_QUALITY, optimize=True,
             progressive=True, exif=exif.tobytes())
    return dest
