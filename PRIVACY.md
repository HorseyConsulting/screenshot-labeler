# Privacy

Screenshot Bot reads your screenshots in order to name them. Screenshots are
among the most sensitive files on a computer -- they can contain banking pages,
private messages, medical portals, and work under NDA. This document states
exactly what happens to them.

## What the app does with your screenshots

| Engine | Where the image goes | Leaves your PC? |
|---|---|---|
| `ollama` (default) | A vision model running on your own GPU, via `http://127.0.0.1:11434` | **No** |
| `api` | Anthropic's API over HTTPS | **Yes** |

The OCR pass always runs locally, using the engine built into Windows. It never
uses the network.

**On the default settings, no screenshot ever leaves your computer.**

## What is stored

- **`rename-log.jsonl`**, in the application folder: one line per rename,
  recording the old filename, the new filename, the label, the model used, and
  a timestamp. It contains the *labels*, which describe your screenshots'
  contents. It never contains the images themselves. It exists so `--undo` can
  reverse a run. Delete it at any time; you only lose the ability to undo.
- **A temporary downscaled copy** of each screenshot, written to the system
  temporary folder while a label is generated and deleted immediately
  afterwards, including when labeling fails.

Nothing else is stored. There is no telemetry, no analytics, no crash
reporting, and no network call of any kind on the default settings.

## If you switch to a cloud engine

`--engine api` sends a downscaled copy of each screenshot to Anthropic for
labeling. That is a deliberate, opt-in change, and it means your screenshots
are transmitted to and processed by a third party under their terms and privacy
policy:

- <https://www.anthropic.com/legal/privacy>
- <https://www.anthropic.com/legal/consumer-terms>

Do not use the cloud engine on a machine where screenshots may contain
confidential, regulated, or personal data belonging to other people, unless you
have the authority to disclose it.

## Which files are read

Only files in the watched folder that match the default screenshot pattern
(`Screenshot YYYY-MM-DD HHMMSS.png` / `.jpg`). Files you have named yourself
are never opened, never read, and never renamed.

## Removing everything

```powershell
Unregister-ScheduledTask -TaskName "Screenshot Labeler" -Confirm:$false
```

Then delete the application folder. To remove the local model as well:

```powershell
ollama rm qwen2.5vl:7b
```

Your screenshots are never modified -- only renamed -- so removing the app
leaves your files intact.

## Contact

Questions about this policy: open an issue on the repository.
