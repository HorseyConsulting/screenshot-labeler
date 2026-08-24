"""File operations and the undo log.

Every rename is journaled before it is considered done, so any run can be
walked back. The log lives with the tool, not in the watched folder.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .namer import build_filename, parse_screenshot_name, resolve_collision


def find_candidates(directory: Path) -> list[Path]:
    """Unlabeled screenshots in directory, oldest first.

    Anything that doesn't match the default screenshot pattern -- hand-named
    files, already-labeled files, desktop.ini -- is simply not returned.
    """
    candidates = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        taken = parse_screenshot_name(path.name)
        if taken is not None:
            candidates.append((taken, path))
    return [path for _, path in sorted(candidates, key=lambda pair: pair[0])]


def rename_with_log(
    source: Path,
    label: str,
    log_path: Path,
    run_id: str,
    model: str = "",
    dry_run: bool = False,
) -> Path:
    """Rename source to "<label> <date>.<ext>" and journal it.

    Returns the new path. In dry_run the path is computed and returned but
    nothing on disk changes and nothing is logged. Raises ValueError if the
    label is unusable or the source isn't a recognizable screenshot.
    """
    taken = parse_screenshot_name(source.name)
    if taken is None:
        raise ValueError(f"{source.name} is not an unlabeled screenshot")

    directory = source.parent
    filename = resolve_collision(directory, build_filename(label, taken, source.suffix))
    destination = directory / filename

    if dry_run:
        return destination

    source.rename(destination)
    _append_log(
        log_path,
        {
            "run_id": run_id,
            "at": datetime.now(timezone.utc).isoformat(),
            "old": source.name,
            "new": destination.name,
            "label": label,
            "model": model,
        },
    )
    return destination


def undo_last_run(directory: Path, log_path: Path) -> list[str]:
    """Restore the filenames changed by the most recent run.

    Returns the original names actually restored. Entries whose file has since
    moved or vanished, and any whose original name is now occupied, are skipped
    rather than forced -- undo must never destroy something.
    """
    entries = _read_log(log_path)
    if not entries:
        return []

    last_run = entries[-1]["run_id"]
    restored = []
    for entry in reversed([e for e in entries if e["run_id"] == last_run]):
        current = directory / entry["new"]
        original = directory / entry["old"]
        if not current.exists() or original.exists():
            continue
        current.rename(original)
        restored.append(entry["old"])
    return restored


def _append_log(log_path: Path, entry: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def _read_log(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries
