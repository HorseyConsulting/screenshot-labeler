"""Post-install check: does this machine actually produce a sensible label?

Generates a screenshot with known content, labels it with the configured
engine, and reports whether the result is usable. Exits non-zero on failure so
the installer can surface the problem instead of claiming success.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Words that indicate the model genuinely read the test image.
EXPECTED_ANY = ("gmail", "inbox", "mail", "email", "message")


def load_font(size: int):
    for candidate in ("segoeui.ttf", "arial.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_test_screenshot(path: Path) -> Path:
    """A synthetic but realistic screenshot with unambiguous content."""
    image = Image.new("RGB", (1100, 620), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    draw.rectangle([0, 0, 1100, 76], fill=(210, 60, 45))
    draw.text((28, 24), "Gmail", fill=(255, 255, 255), font=load_font(34))
    draw.text((190, 32), "Inbox  (3 unread)", fill=(255, 235, 230), font=load_font(24))

    rows = [
        ("Anna Whitfield", "Re: Thursday's budget review", "10:42"),
        ("GitHub", "[screenshot-bot] 2 new pull requests", "09:15"),
        ("Vancouver Whitecaps", "Your season ticket renewal", "Yesterday"),
    ]
    y = 120
    for sender, subject, when in rows:
        draw.text((32, y), sender, fill=(20, 20, 20), font=load_font(22))
        draw.text((300, y), subject, fill=(70, 70, 70), font=load_font(22))
        draw.text((940, y), when, fill=(120, 120, 120), font=load_font(20))
        draw.line([(28, y + 44), (1070, y + 44)], fill=(228, 228, 228))
        y += 78

    image.save(path, "PNG")
    return path


def build_labeler(engine: str, model: str | None):
    if engine == "ollama":
        from screenshot_labeler.ollama_labeler import DEFAULT_OLLAMA_MODEL, OllamaLabeler

        return OllamaLabeler(model=model or DEFAULT_OLLAMA_MODEL)
    import os

    from anthropic import Anthropic

    from screenshot_labeler.labeler import DEFAULT_MODEL, Labeler

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return Labeler(Anthropic(), model=model or DEFAULT_MODEL)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default="ollama", choices=("ollama", "api"))
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent))

    from screenshot_labeler.ocr import is_available

    print(f"    Windows OCR:  {'available' if is_available() else 'NOT available (labels will be weaker)'}")

    with tempfile.TemporaryDirectory() as workspace:
        source = make_test_screenshot(Path(workspace) / "Screenshot 2026-01-01 120000.png")

        try:
            labeler = build_labeler(args.engine, args.model)
        except Exception as exc:
            print(f"    FAILED to start the '{args.engine}' engine: {exc}")
            return 1

        print(f"    Labeling a test screenshot with '{args.engine}'...")
        started = time.time()
        try:
            label = labeler.label(source)
        except Exception as exc:
            print(f"    FAILED: {type(exc).__name__}: {exc}")
            return 1
        elapsed = time.time() - started

    if not label:
        print(f"    FAILED: the model returned no label ({elapsed:.1f}s).")
        return 1

    print(f"    Result: \"{label}\"  ({elapsed:.1f}s)")

    if any(word in label.lower() for word in EXPECTED_ANY):
        print("    PASSED: the label matches the test image.")
        return 0

    # A label was produced but missed the subject -- working, just weak.
    print("    WARNING: a label was produced, but it does not mention the")
    print("             test image's subject (an email inbox). Labeling works,")
    print("             but quality on this machine may be poor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
