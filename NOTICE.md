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

**These need checking before you sell anything.** Model licences differ from
software licences and several restrict commercial use.

| Model | Licence (verify before release) | Selected when |
|---|---|---|
| `qwen2.5vl:7b` | Understood to be Apache 2.0 | GPU with 8 GB+ VRAM |
| `qwen2.5vl:3b` | **Understood to be the Qwen Research Licence, which restricts commercial use** | GPU under 8 GB VRAM |
| `moondream` | Apache 2.0 | Not currently selected |

The 3 B model is what `install.ps1` picks automatically on lower-end hardware,
which is the majority of PCs. If its licence does restrict commercial use, a
paid release must either drop that tier or substitute a permissively licensed
model of similar size.

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
