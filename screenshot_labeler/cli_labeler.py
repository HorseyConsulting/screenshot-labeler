"""Labeling via the local `claude` CLI instead of a metered API key.

Costs nothing beyond the Claude Code subscription already on this machine, at
the price of ~12s per screenshot and a slice of the session usage limits.
Interchangeable with labeler.Labeler -- same .label(path) -> str contract.
"""

from __future__ import annotations

import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from .labeler import (
    DEFAULT_MAX_WIDTH,
    SYSTEM_PROMPT,
    build_prompt,
    clean_label,
    prepare_image,
    read_ocr_safely,
)
from .ocr import extract_text

DEFAULT_CLI_MODEL = "haiku"
DEFAULT_TIMEOUT_SECONDS = 120


class CliLabeler:
    def __init__(
        self,
        claude_path: str = "claude",
        model: str = DEFAULT_CLI_MODEL,
        max_width: int = DEFAULT_MAX_WIDTH,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
        ocr_reader=extract_text,
    ):
        self._claude_path = claude_path
        self._model = model
        self._max_width = max_width
        self._timeout = timeout
        self._run = run
        self._ocr_reader = ocr_reader

    def label(self, path: Path, use_ocr: bool = True) -> str:
        """Return a label for the screenshot, or "" if none could be determined.

        Raises RuntimeError if the CLI fails or hangs -- the caller decides
        whether that means skip or retry.
        """
        # The CLI reads the image off disk, so hand it a downscaled copy rather
        # than the full-size original: fewer tokens against the usage limit.
        encoded, _ = prepare_image(path, self._max_width)
        ocr_text = read_ocr_safely(self._ocr_reader, path) if use_ocr else ""
        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        temp_image = Path(handle.name)
        handle.close()

        try:
            temp_image.write_bytes(base64.b64decode(encoded))
            return clean_label(self._invoke(temp_image, ocr_text, use_ocr))
        finally:
            temp_image.unlink(missing_ok=True)

    def _invoke(self, image: Path, ocr_text: str = "", ocr_ran: bool = False) -> str:
        command = [
            self._claude_path,
            "-p",
            f"Read the image at {image}.\n\n{SYSTEM_PROMPT}\n\n{build_prompt(ocr_text, ocr_ran=ocr_ran)}",
            "--model",
            self._model,
            "--allowedTools",
            "Read",
            "--permission-mode",
            "dontAsk",
        ]

        # Without this, every labeled screenshot flashes a console window when
        # the watcher runs under pythonw.exe.
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            result = self._run(
                command,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                creationflags=no_window,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"claude CLI timed out after {self._timeout}s") from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"claude CLI failed (exit {result.returncode}): {detail}")

        return result.stdout
