"""Filesystem watching. Turns "a file appeared" into "label this screenshot"."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler

from .namer import parse_screenshot_name
from .runner import wait_for_stable

log = logging.getLogger(__name__)


class ScreenshotHandler(FileSystemEventHandler):
    """Reacts to new screenshots only; everything else in the folder is ignored.

    Both process and stable_check are injected so the decision logic can be
    tested without a filesystem or a network.
    """

    def __init__(
        self,
        process: Callable[[Path], None],
        stable_check: Callable[[Path], bool] = wait_for_stable,
    ):
        self._process = process
        self._stable_check = stable_check
        self._handled: set[str] = set()

    def on_created(self, event) -> None:
        self._consider(event)

    def on_moved(self, event) -> None:
        # Some capture tools write a temp file and move it into place.
        self._consider(event, attribute="dest_path")

    def _consider(self, event, attribute: str = "src_path") -> None:
        if getattr(event, "is_directory", False):
            return

        path = Path(getattr(event, attribute, event.src_path))
        if parse_screenshot_name(path.name) is None:
            return

        # Watchdog can emit both a create and a move for one arrival.
        key = str(path)
        if key in self._handled:
            return
        self._handled.add(key)

        if not self._stable_check(path):
            log.warning("%s never settled; leaving it alone", path.name)
            return

        try:
            self._process(path)
        except Exception:
            # A watcher that dies on one bad file is worse than one that skips it.
            log.exception("failed while processing %s", path.name)
