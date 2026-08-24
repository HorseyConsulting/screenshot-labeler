# Screenshot Bot

Renames screenshots from `Screenshot 2026-08-14 135316.png` to
`Stable Trades Helmet Livery 2026-08-14.png`, by actually looking at the image.

Runs as a background watcher: take a screenshot, and a few seconds later it has
a real name.

## Engines

| `--engine` | What it uses | Speed | Cost |
|---|---|---|---|
| `ollama` (default) | Qwen2.5-VL 7B on your own GPU | ~2.5s | Free, fully offline |
| `api` | `ANTHROPIC_API_KEY` | ~1s | ~$0.0008 per screenshot |

Both get the same OCR assist (below) and produce labels in the same format.
The local engine is the default and the only one the installer sets up.

### Setup

**ollama** — `install.ps1` handles this. Manually: install
[Ollama](https://ollama.com), then `ollama pull qwen2.5vl:7b`.

Needs ~6 GB disk and ~5.5 GB VRAM while running. Ollama unloads the model after
about 5 minutes idle, so it costs nothing when you are not screenshotting.

**api** — `setx ANTHROPIC_API_KEY "sk-ant-..."`, then open a new terminal.

## The OCR assist

Every screenshot is first read by the OCR engine built into Windows (the same
one behind Snipping Tool's text actions). That text is passed to the model
alongside the image.

This exists because vision models read small type poorly and will invent
plausible-looking brand names. Giving them verified text removes their weakest
capability from the problem: the model supplies understanding, OCR supplies
spelling.

When OCR comes back empty, that is itself useful — it means there is no legible
text, so the model is told not to claim it can read any. This measurably stopped
the local model hallucinating letters on low-resolution logos.

`--no-ocr` disables it.

## Usage

Dry-run first — prints every proposed rename, changes nothing:

```
.venv\Scripts\python.exe -m screenshot_labeler --backfill --dry-run --limit 20
```

Then for real:

```
.venv\Scripts\python.exe -m screenshot_labeler --backfill
```

Undo the most recent run:

```
.venv\Scripts\python.exe -m screenshot_labeler --undo
```

Watch in the foreground (Ctrl-C to stop):

```
.venv\Scripts\python.exe -m screenshot_labeler --watch
```

### The background watcher

```
powershell -ExecutionPolicy Bypass -File ".\install.ps1"
```

Registers a scheduled task that starts at logon and runs under `pythonw.exe`
(no console window). Re-running the installer stops any previous watcher first,
so it replaces rather than duplicates.

```powershell
Get-ScheduledTask -TaskName "Screenshot Labeler"          # is it alive?
Stop-ScheduledTask -TaskName "Screenshot Labeler"          # pause
Unregister-ScheduledTask -TaskName "Screenshot Labeler"    # remove
```

### Options

| Flag | Meaning |
|---|---|
| `--dir PATH` | Folder to work on. Defaults to your Screenshots folder, detected automatically (OneDrive-redirected or `%USERPROFILE%\Pictures\Screenshots`). |
| `--engine ollama\|api` | Which backend to label with. |
| `--model ID` | Per-engine default: `qwen2.5vl:7b` (ollama), `claude-haiku-4-5` (api). |
| `--no-ocr` | Skip the OCR assist. |
| `--dry-run` | Print proposed renames, change nothing. |
| `--limit N` | Process at most N files. |
| `--verbose` | Debug logging. |

## What it will and won't touch

It renames **only** files matching the default screenshot pattern
(`Screenshot YYYY-MM-DD HHMMSS.png/jpg`). Files you named yourself are invisible
to it by construction, as is `desktop.ini`. A file it has already renamed no
longer matches the pattern, so it is never processed twice.

Every failure path leaves the file untouched. If the engine fails, the image is
unreadable, or the model can't tell what it's looking at, the screenshot keeps
its timestamp name and the reason is logged. A wrong name is a real problem; an
ugly name is not.

## Undo

Every rename is journaled to `rename-log.jsonl` — old name, new name, label,
model, timestamp. `--undo` reverses the most recent run, skipping anything that
has since moved or whose original name is now occupied. Undo never overwrites,
and never recreates a file you deleted.

## Layout

| File | Responsibility |
|---|---|
| `namer.py` | Pure filename rules: sanitizing, reserved names, collisions. No I/O. |
| `renamer.py` | File operations and the undo log. |
| `ocr.py` | Windows OCR text extraction. |
| `labeler.py` | API engine, plus the prompts and label-cleaning shared by all engines. |
| `ollama_labeler.py` | Local-GPU engine over Ollama's HTTP API. |
| `runner.py` | Orchestration, retries, "leave it alone on failure". |
| `watcher.py` | Filesystem events to labeling work. |
| `cli.py` | Argument parsing and the three modes. |

## Tests

```
.venv\Scripts\python.exe -m pytest
```

108 tests. Nothing hits the network or loads a model — every engine is
injected as a stub for the file-operation tests.

## Privacy

On default settings **no screenshot ever leaves your computer** -- labeling runs
on your own GPU and the OCR pass uses the engine built into Windows. The
optional `api` engine does send images to Anthropic. Full detail in
[PRIVACY.md](PRIVACY.md).

## Using this

The source is public so you can see exactly what this does with your
screenshots -- which seems like the least you should expect from something that
reads them. On default settings, nothing is uploaded anywhere.

It is **not** licensed for use, redistribution, or modification (see
[LICENSE](LICENSE)). A packaged, signed build is planned. If you want to run it
in the meantime, or you are interested in that build, open an issue and say so
-- interest is genuinely useful to know about.

## Licence

Proprietary -- all rights reserved. See [LICENSE](LICENSE).
Third-party components and model licences: [NOTICE.md](NOTICE.md).
Security posture and reporting: [SECURITY.md](SECURITY.md).
