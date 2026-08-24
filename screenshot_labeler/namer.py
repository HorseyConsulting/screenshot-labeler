"""Pure filename logic. No I/O except a directory existence check for collisions.

Kept separate from the file operations so the rules that decide what a file is
called can be tested exhaustively -- this is the part that can corrupt a name.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

# Windows forbids these outright in a filename component.
FORBIDDEN = '<>:"/\\|?*'

# Reserved DOS device names -- a file called "CON.png" is not creatable.
RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {
    f"LPT{i}" for i in range(1, 10)
}

MAX_LABEL_CHARS = 60

# "Screenshot 2026-08-06 113045.png" -- the Windows Snipping Tool default.
SCREENSHOT_RE = re.compile(
    r"^Screenshot (?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{6})\.(?:png|jpe?g)$",
    re.IGNORECASE,
)


def parse_screenshot_name(filename: str) -> datetime | None:
    """Return the capture time if this is an unlabeled screenshot, else None.

    Returning None is what protects hand-named files: anything not matching the
    default pattern is never eligible for renaming. It also makes renaming
    idempotent, since a labeled file no longer matches.
    """
    match = SCREENSHOT_RE.match(filename)
    if not match:
        return None
    try:
        return datetime.strptime(
            f"{match['date']} {match['time']}", "%Y-%m-%d %H%M%S"
        )
    except ValueError:
        return None


def sanitize_label(label: str) -> str:
    """Reduce a model-supplied label to something safe to put in a filename.

    Returns "" when nothing usable survives -- callers must treat that as
    "leave the file alone".
    """
    cleaned = "".join(c for c in label if c not in FORBIDDEN and ord(c) >= 32)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.strip(". ")

    if len(cleaned) > MAX_LABEL_CHARS:
        cleaned = cleaned[:MAX_LABEL_CHARS].rsplit(" ", 1)[0].strip(". ")

    if cleaned.upper() in RESERVED:
        return ""
    return cleaned


def build_filename(label: str, taken: datetime, extension: str) -> str:
    """Compose "Label YYYY-MM-DD.ext". Raises ValueError on an unusable label."""
    safe = sanitize_label(label)
    if not safe:
        raise ValueError(f"label {label!r} left nothing usable after sanitizing")
    return f"{safe} {taken:%Y-%m-%d}{extension}"


def resolve_collision(directory: Path, filename: str) -> str:
    """Append " (2)", " (3)"... until the name is free in directory."""
    candidate = Path(filename)
    stem, suffix = candidate.stem, candidate.suffix

    if not (directory / filename).exists():
        return filename

    counter = 2
    while (directory / f"{stem} ({counter}){suffix}").exists():
        counter += 1
    return f"{stem} ({counter}){suffix}"
