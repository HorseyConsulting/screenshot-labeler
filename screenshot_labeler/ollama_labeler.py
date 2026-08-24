"""Labeling with a vision model running locally via Ollama.

No account, no network, no per-image cost -- the model runs on this machine's
own GPU. Slower and blander than Haiku, but private and free, which is what
makes it the right default for a machine that has no Claude subscription.

Talks to Ollama's HTTP API rather than its CLI: one JSON object back beats
parsing terminal output, and it keeps the model resident between calls.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from .labeler import (
    DEFAULT_MAX_WIDTH,
    SYSTEM_PROMPT,
    build_prompt,
    clean_label,
    prepare_image,
    read_ocr_safely,
)
from .ocr import extract_text

DEFAULT_OLLAMA_MODEL = "qwen2.5vl:7b"
DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT_SECONDS = 180


def post_json(url: str, payload: dict, timeout: int) -> dict:
    """Minimal JSON POST. Kept tiny so the package needs no HTTP dependency."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class OllamaLabeler:
    def __init__(
        self,
        model: str = DEFAULT_OLLAMA_MODEL,
        host: str = DEFAULT_HOST,
        max_width: int = DEFAULT_MAX_WIDTH,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        post=post_json,
        ocr_reader=extract_text,
    ):
        self._model = model
        self._host = host.rstrip("/")
        self._max_width = max_width
        self._timeout = timeout
        self._post = post
        self._ocr_reader = ocr_reader

    def label(self, path: Path, use_ocr: bool = True) -> str:
        """Return a label for the screenshot, or "" if none could be determined."""
        encoded, _ = prepare_image(path, self._max_width)
        ocr_text = read_ocr_safely(self._ocr_reader, path) if use_ocr else ""

        payload = {
            "model": self._model,
            "prompt": build_prompt(ocr_text, ocr_ran=use_ocr),
            "system": SYSTEM_PROMPT,
            "images": [encoded],
            "stream": False,
            "options": {
                # Deterministic and short: this is a naming task, not prose.
                "temperature": 0.1,
                "num_predict": 32,
            },
        }

        try:
            response = self._post(f"{self._host}/api/generate", payload, self._timeout)
        except Exception as exc:
            raise RuntimeError(
                f"Ollama request failed ({type(exc).__name__}: {exc}). "
                "Is the Ollama service running?"
            ) from exc

        return clean_label(response.get("response", ""))
