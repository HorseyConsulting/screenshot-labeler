"""The one piece that talks to the network: image in, short label out."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

from .ocr import extract_text, summarize_for_prompt

DEFAULT_MODEL = "claude-haiku-4-5"

# A screenshot stays readable well below its native size, and image tokens
# scale with pixel count -- 1024px wide costs roughly a third of 1920px.
DEFAULT_MAX_WIDTH = 1024

# The model emits this when it genuinely can't tell what it's looking at.
# Better an ugly timestamp name than a confidently wrong one.
UNKNOWN = "UNKNOWN"

SYSTEM_PROMPT = """\
You name screenshots. Given one screenshot, reply with a short descriptive \
filename label and nothing else.

Rules:
- 2 to 5 words, Title Case, no punctuation, no file extension, no date.
- Name the application, website, or game first when it is identifiable, then \
the specific subject. Examples: "Helmet Livery Editor", "VS Code Python \
Traceback", "Amazon Order Confirmation", "F1 Standings Table".
- ALWAYS include the most specific identifying detail you can see -- the team, \
company, product, person, or page title. Never name only the category. Write \
"Anaheim Ducks Season Stats", NOT "NHL Team Statistics". Write "Acme Themes \
Copyright Footer", NOT "Website Settings Page". A label that could describe \
fifty different screenshots is a failed label.
- Prefer the specific over the generic. "Gmail Inbox" beats "Email". If a \
document, article, or video has a visible title, use it.
- Reply with exactly the label. No quotes, no explanation, no preamble.
- If you genuinely cannot tell what the screenshot shows, reply with exactly \
UNKNOWN."""


# Below this many characters, OCR has effectively found nothing legible.
OCR_FRAGMENT_CHARS = 12


def build_prompt(ocr_text: str = "", ocr_ran: bool = False) -> str:
    """The user-turn instruction, optionally carrying verified on-screen text.

    Vision models read small type poorly and will invent plausible-looking
    brand names. Handing them OCR output removes their weakest capability from
    the problem: they supply the understanding, OCR supplies the spelling.

    An empty OCR result is itself information: it means there is no legible
    text, so any words the model "reads" are invented. Local models do exactly
    this on low-resolution logos, and differently on each run.
    """
    instruction = "Name this screenshot."
    if not ocr_ran:
        return instruction

    if len(ocr_text) < OCR_FRAGMENT_CHARS:
        return (
            f"{instruction}\n\n"
            "OCR found little or no machine-readable text here. Do not quote "
            "words, brands or letters you cannot clearly make out -- name what "
            "the image IS rather than guessing at what it says.\n"
            "OCR failing is NOT a reason to give up: it often fails on charts, "
            "canvas-rendered pages and screenshots of images that you can read "
            "perfectly well. Still give a specific name based on what you can "
            "see. Only answer UNKNOWN if the image itself is genuinely "
            "unidentifiable to you."
        )

    return (
        f"{instruction}\n\n"
        "For reference only, here is raw text OCR found somewhere on this "
        "image. Use it ONLY to spell names correctly and to read type too "
        "small to make out. Most of it is irrelevant clutter -- do not name "
        "the screenshot after a phrase picked out of this list, and do not let "
        "it override what you can see for yourself:\n"
        f'"""{ocr_text}"""'
    )


def read_ocr_safely(reader, path: Path) -> str:
    """OCR is an enhancement; never let it break labeling."""
    try:
        return summarize_for_prompt(reader(path))
    except Exception:
        return ""


def clean_label(text: str) -> str:
    """Normalize a model's reply into a bare label, or "" if unusable.

    Shared by both engines so an API label and a CLI label are cleaned by
    identical rules.
    """
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return ""

    # A chatty CLI may narrate before answering; the label is the last line.
    cleaned = lines[-1].strip("\"'" + ". \n")
    if not cleaned or cleaned.upper() == UNKNOWN:
        return ""
    return cleaned


def prepare_image(path: Path, max_width: int = DEFAULT_MAX_WIDTH) -> tuple[str, str]:
    """Return (base64 PNG, media type), downscaled to max_width if wider.

    Kept as PNG rather than JPEG: screenshots are mostly text, and JPEG
    artifacts around small glyphs are exactly what would hurt legibility.
    """
    with Image.open(path) as image:
        image = image.convert("RGB")
        if image.width > max_width:
            height = round(image.height * max_width / image.width)
            image = image.resize((max_width, height), Image.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, "PNG", optimize=True)

    return base64.b64encode(buffer.getvalue()).decode("ascii"), "image/png"


class Labeler:
    """Wraps an Anthropic client. Injectable so the file logic tests stay offline."""

    def __init__(
        self,
        client,
        model: str = DEFAULT_MODEL,
        max_width: int = DEFAULT_MAX_WIDTH,
        ocr_reader=extract_text,
    ):
        self._client = client
        self._model = model
        self._max_width = max_width
        self._ocr_reader = ocr_reader

    def label(self, path: Path, use_ocr: bool = True) -> str:
        """Return a label for the screenshot, or "" if none could be determined.

        API errors propagate -- the caller decides whether to retry or skip.
        """
        encoded, media_type = prepare_image(path, self._max_width)
        ocr_text = read_ocr_safely(self._ocr_reader, path) if use_ocr else ""

        response = self._client.messages.create(
            model=self._model,
            max_tokens=64,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": encoded,
                            },
                        },
                        {"type": "text", "text": build_prompt(ocr_text, ocr_ran=use_ocr)},
                    ],
                }
            ],
        )

        if getattr(response, "stop_reason", None) == "refusal":
            return ""

        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        return clean_label(text)
