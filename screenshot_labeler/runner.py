"""Orchestration: label a screenshot, rename it, and never make things worse.

The governing rule here is that every failure path leaves the file untouched.
A screenshot that keeps its timestamp name is a non-event; one renamed to
something wrong is a real problem.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .renamer import find_candidates, rename_with_log

RENAME_ATTEMPTS = 4
STABLE_ATTEMPTS = 5
STABLE_POLL_SECONDS = 0.4


@dataclass
class ProcessResult:
    path: Path
    status: str  # "renamed" | "skipped" | "failed"
    new_name: str = ""
    label: str = ""
    error: str = ""


def wait_for_stable(
    path: Path,
    attempts: int = STABLE_ATTEMPTS,
    poll_seconds: float = STABLE_POLL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """True once the file's size stops changing between polls.

    A screenshot is not fully written the instant the file appears, and
    OneDrive/Dropbox may still be touching it. Reading it too early yields a
    truncated image and a nonsense label.
    """
    try:
        previous = path.stat().st_size
    except OSError:
        return False

    for _ in range(attempts):
        sleep(poll_seconds)
        try:
            current = path.stat().st_size
        except OSError:
            return False
        if current == previous and current > 0:
            return True
        previous = current
    return False


def process_one(
    path: Path,
    labeler,
    log_path: Path,
    run_id: str,
    model: str = "",
    dry_run: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    rename_fn: Callable[..., Path] = rename_with_log,
) -> ProcessResult:
    """Label and rename one screenshot. Any problem leaves it where it is."""
    try:
        label = labeler.label(path)
    except Exception as exc:  # network, decode, refusal -- all handled alike
        return ProcessResult(path, "failed", error=f"{type(exc).__name__}: {exc}")

    if not label:
        return ProcessResult(path, "skipped", error="no usable label")

    last_error = ""
    for attempt in range(RENAME_ATTEMPTS):
        try:
            destination = rename_fn(
                path, label, log_path, run_id=run_id, model=model, dry_run=dry_run
            )
            return ProcessResult(path, "renamed", destination.name, label)
        except ValueError as exc:
            # Label sanitized down to nothing -- retrying cannot help.
            return ProcessResult(path, "skipped", label=label, error=str(exc))
        except OSError as exc:
            # Usually a sync client or screenshot tool still holding the file.
            last_error = str(exc)
            if attempt < RENAME_ATTEMPTS - 1:
                sleep(0.5 * (2**attempt))

    return ProcessResult(path, "failed", label=label, error=last_error)


def process_directory(
    directory: Path,
    labeler,
    log_path: Path,
    run_id: str,
    model: str = "",
    limit: int | None = None,
    dry_run: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    on_result: Callable[[ProcessResult], None] | None = None,
) -> list[ProcessResult]:
    """Process every unlabeled screenshot in directory, oldest first."""
    candidates: Iterable[Path] = find_candidates(directory)
    if limit is not None:
        candidates = list(candidates)[:limit]

    results = []
    for path in candidates:
        result = process_one(
            path, labeler, log_path, run_id, model=model, dry_run=dry_run, sleep=sleep
        )
        results.append(result)
        if on_result:
            on_result(result)
    return results
