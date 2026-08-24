# Third-party components

Screenshot Bot itself is proprietary (see LICENSE). It depends on the
components below, each under its own licence. This list is provided for
attribution and compliance and should be verified before any commercial
release.

## Python packages

| Package | Licence | Used for |
|---|---|---|
| Pillow | MIT-CMU (HPND) | Reading and downscaling screenshots |
| watchdog | Apache 2.0 | Watching the folder for new files |
| winsdk | MIT | Reaching the Windows OCR API from Python |
| anthropic | MIT | The optional `api` engine |
| pytest | MIT | Tests only; not shipped |

## Runtime dependencies

| Component | Licence | Notes |
|---|---|---|
| Python | PSF Licence | Installed by `install.ps1` if absent |
| Ollama | MIT | Installed by `install.ps1` if absent |
| Windows OCR (`Windows.Media.Ocr`) | Part of Windows | No separate distribution |

## Models

Model licences differ from software licences, and several restrict commercial
use. Verified against upstream on 2026-08-24:

| Model | Upstream licence | Commercial use | Auto-selected |
|---|---|---|---|
| `qwen2.5vl:7b` | Apache 2.0 | Yes | **Yes** -- the only model the installer picks |
| `qwen2.5vl:3b` | Qwen Research Licence | **No** | No -- deliberately excluded |
| `moondream` | Apache 2.0 | Yes | No -- quality too low to be useful |

### Warning: Ollama reports the wrong licence for qwen2.5vl:3b

`ollama show qwen2.5vl:3b --license` prints the **Apache 2.0** licence text.
Upstream, `Qwen/Qwen2.5-VL-3B-Instruct` is published under the Qwen Research
Licence, whose section 2(a) grants rights "FOR NON-COMMERCIAL PURPOSES ONLY",
with "Non-Commercial" defined in section 1(i) as "for research or evaluation
purposes only", and section 2(b) requiring a separate licence for commercial
use.

Do not rely on `ollama show --license` to clear a model for commercial use.
Check the upstream model card.

Because of this, `install.ps1` selects `qwen2.5vl:7b` on every machine,
including ones with too little VRAM to run it comfortably, rather than falling
back to the 3 B. Passing `-Model qwen2.5vl:3b` explicitly still works and is
appropriate for personal or evaluation use, but must not ship in a paid
release.

If a smaller commercially usable model is needed for low-end hardware, it has
to be sourced elsewhere -- candidates worth evaluating include SmolVLM
(Apache 2.0) and Florence-2 (MIT), both of which are weaker and would need
testing against real screenshots before being trusted.

No model weights are redistributed by this project. They are downloaded by the
user from Ollama's registry at install time, which affects but does not remove
the licensing question.

## Claude / Anthropic

The `cli` and `api` engines send screenshots to Anthropic and are governed by
Anthropic's terms:

- <https://www.anthropic.com/legal/consumer-terms>
- <https://www.anthropic.com/legal/commercial-terms>

The `cli` engine consumes the user's own Claude Code subscription. Reselling
access to it, or building a paid product whose value depends on the end user's
personal subscription, may not be permitted -- check the terms before shipping
that engine in a commercial release.
