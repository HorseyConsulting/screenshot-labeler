"""Text extraction using the OCR engine built into Windows.

Costs nothing, needs no download, no account, and no network -- it is the same
engine behind Snipping Tool's text actions. It reads text well and understands
nothing, which is exactly complementary to a vision model: give the model
verified text and it stops guessing at small type.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

DEFAULT_MAX_CHARS = 600


def _load_runtime():
    """Import the WinRT projection lazily so non-Windows imports don't explode."""
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.storage import FileAccessMode, StorageFile

    return BitmapDecoder, OcrEngine, FileAccessMode, StorageFile


def is_available() -> bool:
    """True if this machine can do OCR at all."""
    try:
        _, OcrEngine, _, _ = _load_runtime()
        return OcrEngine.try_create_from_user_profile_languages() is not None
    except Exception:
        return False


def extract_text(path: Path) -> str:
    """Return the text visible in the image, or "" if there is none or OCR fails.

    Never raises: OCR is an enhancement, and a screenshot with no readable text
    is an ordinary outcome rather than an error.
    """
    try:
        return asyncio.run(_extract(Path(path)))
    except Exception:
        return ""


async def _extract(path: Path) -> str:
    BitmapDecoder, OcrEngine, FileAccessMode, StorageFile = _load_runtime()

    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        return ""

    file = await StorageFile.get_file_from_path_async(str(path.resolve()))
    stream = await file.open_async(FileAccessMode.READ)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    result = await engine.recognize_async(bitmap)
    return "\n".join(line.text for line in result.lines).strip()


def summarize_for_prompt(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Condense OCR output into something worth putting in a prompt.

    Truncates from the front: headings, titles and app names cluster at the top
    of a screenshot, and that is what makes a good filename.
    """
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[:max_chars].rsplit(" ", 1)[0].strip()
