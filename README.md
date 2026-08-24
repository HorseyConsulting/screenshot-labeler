# Screenshot Bot

Renames screenshots from `Screenshot 2026-08-14 135316.png` to
`Stable Trades Helmet Livery 2026-08-14.png`, by actually looking at the image.

Runs as a background watcher: take a screenshot, and a few seconds later it has
a real name.

## Engines

Three interchangeable backends. The watcher currently runs on `ollama`.

| `--engine` | What it uses | Speed | Cost |
|---|---|---|---|
| `ollama` (current) | Qwen2.5-VL on your own GPU | ~2.5s | Free, fully offline |
| `cli` | The local `claude` CLI | ~11s | Free, uses Claude Code limits |
| `api` | `ANTHROPIC_API_KEY` | ~1s | ~$0.0008 per screenshot |

All three get the same OCR assist (below) and produce labels in the same format.

### Setup per engine

**ollama** — install [Ollama](https://ollama.com), then:

```
ollama pull qwen2.5vl:7b
```

Needs ~6 GB disk and ~5.5 GB VRAM while running. Ollama unloads the model after
about 5 minutes idle, so it costs nothing when you are not screenshotting.

**cli** — nothing to do if Claude Code is installed and signed in.

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
powershell -ExecutionPolicy Bypass -File ".\install-watcher-task.ps1" -Engine ollama
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
| `--dir PATH` | Folder to work on. Defaults to `%USERPROFILE%\OneDrive\Pictures\Screenshots`. |
| `--engine cli\|api\|ollama` | Which backend to label with. |
| `--model ID` | Per-engine default: `haiku`, `claude-haiku-4-5`, `qwen2.5vl:7b`. |
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
| `cli_labeler.py` | `claude` CLI engine. |
| `ollama_labeler.py` | Local-GPU engine over Ollama's HTTP API. |
| `runner.py` | Orchestration, retries, "leave it alone on failure". |
| `watcher.py` | Filesystem events to labeling work. |
| `cli.py` | Argument parsing and the three modes. |

## Tests

```
.venv\Scripts\python.exe -m pytest
```

122 tests. Nothing hits the network, spawns a subprocess, or loads a model —
every engine is injected as a stub for the file-operation tests.
