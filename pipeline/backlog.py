"""Read and write entries in content_backlog.yaml, in place.

The backlog is a hand-maintained planning document that happens to be valid
YAML. It carries section comments, commented-out entry stubs and a reference
block at the end, and those comments hold decisions recorded nowhere else. A
round trip through a YAML dumper deletes every one of them, so writes here are
line-level text edits -- the same approach ``scheduler.mark_post_published``
already takes for the same reason.

Reads go through ``yaml.safe_load``, which is a safe direction: it only has to
understand the file, not reproduce it.
"""

import re

import yaml

# The order fields appear in when one has to be inserted. Fields the writer
# does not manage (published, published_at, publish_attempts) are left exactly
# where the poller put them.
FIELD_ORDER = ("id", "template", "params", "caption", "category",
               "scheduled_date", "notes")

_PLAIN_SCALAR = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-/]*$")


def find_entry(path: str, post_id: str) -> dict | None:
    """The entry with this id, or None. Commented-out stubs are not entries."""
    if not post_id:
        return None
    with open(path, "r", encoding="utf-8") as fh:
        posts = (yaml.safe_load(fh) or {}).get("posts") or []
    for post in posts:
        if isinstance(post, dict) and post.get("id") == post_id:
            return post
    return None


def propose_id(event_name: str, year, sex: str | None, score_type: str) -> str:
    """A default id in the shape the file already uses.

    ``tenerife2026-womens-waves-top10``. Only a starting point: the page shows
    it in an editable field, because the file's own convention is not perfectly
    consistent and the person naming the post knows better than a rule does.

    The place name is the first word that is neither the year nor the star
    rating: the API calls this event "2026 Tenerife Grand Slam *****", and
    taking word one gives ``20262026-womens-waves-top10``.
    """
    words = [re.sub(r"[^a-z0-9]", "", w.lower()) for w in (event_name or "").split()]
    slug = next((w for w in words if w and not re.fullmatch(r"(19|20)\d\d", w)), "")
    parts = [f"{slug}{year}"]
    if sex:
        parts.append("womens" if sex.lower().startswith("w") else "mens")
    parts.append(f"{score_type.lower()}s")
    parts.append("top10")
    return "-".join(parts)


def _scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if _PLAIN_SCALAR.match(text):
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _literal_block(key: str, text: str, indent: str, nl: str) -> list[str]:
    """A ``|-`` block scalar. Blank lines stay genuinely blank."""
    lines = [f"{indent}{key}: |-{nl}"]
    for line in str(text).split("\n"):
        stripped = line.rstrip()
        lines.append(f"{indent}  {stripped}{nl}" if stripped else nl)
    return lines


def _field_lines(key: str, value, indent: str = "    ",
                 nl: str = "\n") -> list[str]:
    if key == "params":
        out = [f"{indent}params:{nl}"]
        for k, v in (value or {}).items():
            out.append(f"{indent}  {k}: {_scalar(v)}{nl}")
        return out if len(out) > 1 else [f"{indent}params: {{}}{nl}"]
    if key == "caption" or (key == "notes" and "\n" in str(value)):
        return _literal_block(key, value, indent, nl)
    if key == "scheduled_date":
        # Always quoted: an unquoted ISO date is parsed by YAML into a datetime,
        # which used to take the whole poll down rather than just its own post.
        return [f'{indent}scheduled_date: "{value}"{nl}']
    if key == "notes":
        return [f"{indent}notes: >{nl}{indent}  {value}{nl}"]
    return [f"{indent}{key}: {_scalar(value)}{nl}"]


def entry_text(entry: dict, nl: str = "\n") -> str:
    """One entry as the text it takes in the file."""
    lines = [f"  - id: {_scalar(entry['id'])}{nl}"]
    for key in FIELD_ORDER:
        if key == "id" or entry.get(key) in (None, ""):
            continue
        lines.extend(_field_lines(key, entry[key], nl=nl))
    return "".join(lines)


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def _entry_bounds(lines: list[str], post_id: str) -> tuple[int, int] | None:
    """The half-open line range of the entry with this id, or None.

    A commented-out stub never matches: the comment marker is part of the
    stripped line, so ``# - id: x`` is not ``- id: x``.
    """
    start = None
    for i, line in enumerate(lines):
        if line.strip() == f"- id: {post_id}":
            start = i
            break
    if start is None:
        return None

    base = _indent_of(lines[start])
    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _indent_of(lines[j]) <= base:
            return start, j
    return start, len(lines)


def _field_span(lines: list[str], lo: int, hi: int, key: str,
                indent: int) -> tuple[int, int] | None:
    """Where ``key`` lives inside an entry, continuation lines included."""
    prefix = " " * indent + key + ":"
    for i in range(lo, hi):
        if not lines[i].startswith(prefix):
            continue
        rest = lines[i][len(prefix):]
        if rest and not rest[0].isspace():
            continue                        # `caption_draft:` is not `caption:`
        end = j = i + 1
        while j < hi:
            if not lines[j].strip():
                j += 1                      # a blank line inside a block scalar
                continue
            if _indent_of(lines[j]) > indent:
                j += 1
                end = j
                continue
            break
        return i, end
    return None


def _last_content_line(lines: list[str], hi: int) -> int:
    """The last line before ``hi`` that is neither blank nor a comment."""
    for i in range(hi - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith("#"):
            return i
    return hi - 1


def _append(lines: list[str], entry: dict, nl: str = "\n") -> None:
    """Put a new entry at the end of the posts list.

    Not at the end of the file: the file finishes with a reference comment
    block and a run of commented-out stubs, and an entry written after those
    would sit outside ``posts:`` and be silently ignored.
    """
    tail = _last_content_line(lines, len(lines))
    block = entry_text(entry, nl)
    lines[tail + 1:tail + 1] = [nl] + block.splitlines(keepends=True)


def _patch(lines: list[str], bounds: tuple[int, int], entry: dict,
           nl: str = "\n") -> None:
    """Overwrite the managed fields of an existing entry, in place."""
    start, end = bounds
    field_indent = _indent_of(lines[start]) + 2

    for key in FIELD_ORDER:
        if key == "id" or entry.get(key) in (None, ""):
            continue
        new_lines = _field_lines(key, entry[key], " " * field_indent, nl)
        span = _field_span(lines, start, end, key, field_indent)
        if span:
            lines[span[0]:span[1]] = new_lines
            end += len(new_lines) - (span[1] - span[0])
            continue

        # Missing: put it where the file's own field order says it belongs,
        # which is immediately before the first later field that does exist.
        insert_at = None
        for later in FIELD_ORDER[FIELD_ORDER.index(key) + 1:]:
            later_span = _field_span(lines, start, end, later, field_indent)
            if later_span:
                insert_at = later_span[0]
                break
        if insert_at is None:
            insert_at = _last_content_line(lines, end) + 1
        lines[insert_at:insert_at] = new_lines
        end += len(new_lines)


def upsert_entry(path: str, entry: dict) -> dict:
    """Write ``entry`` into the backlog, updating in place if the id exists.

    Returns what happened: ``action`` is "created" or "updated", ``replaced``
    is the whole previous entry so the caller can show what it is overwriting
    rather than quietly binning a hand-written caption, and ``was_published``
    flags the case where re-dating changes nothing because the poller skips
    published posts.
    """
    existing = find_entry(path, entry["id"])

    # newline="" keeps each line's own ending, so a CRLF file stays CRLF and
    # the diff is the entry that changed rather than all 753 lines of it.
    with open(path, "r", encoding="utf-8", newline="") as fh:
        lines = fh.readlines()
    nl = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"

    bounds = _entry_bounds(lines, entry["id"])
    if bounds is None:
        _append(lines, entry, nl)
        action = "created"
    else:
        _patch(lines, bounds, entry, nl)
        action = "updated"

    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.writelines(lines)

    return {
        "action": action,
        "replaced": existing,
        "was_published": bool(existing and existing.get("published")),
    }
