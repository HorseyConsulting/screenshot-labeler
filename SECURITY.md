# Security

## Reporting a vulnerability

Open a private security advisory on this repository, or email the maintainer.
Please do not open a public issue for anything exploitable.

## What this application can reach

Screenshot Bot runs with your user account's permissions and:

- **Reads** image files in the watched folder that match the screenshot naming
  pattern. It does not read any other file.
- **Renames** those files in place. It never deletes, never overwrites, and
  never modifies file contents.
- **Writes** a temporary downscaled copy to the system temp folder, removed
  immediately after labeling.
- **Appends** to `rename-log.jsonl` in the application folder.
- **Connects** to `http://127.0.0.1:11434` (local Ollama) on default settings.
  Only the optional `cli` and `api` engines make outbound internet connections.

## Deliberate design choices

- **Renames are journaled before being considered complete**, so any run can be
  reversed with `--undo`.
- **Collisions never overwrite.** A name already in use gets a numeric suffix.
- **Undo never overwrites either**, and never recreates a file you deleted.
- **Every failure path leaves the file untouched.** A screenshot that keeps its
  timestamp name is a non-event; one renamed incorrectly is not.
- **Labels are sanitised before touching the filesystem** -- characters Windows
  forbids are stripped, reserved device names (`CON`, `NUL`, `COM1`...) are
  rejected, and length is capped. A model cannot produce a filename that
  escapes the target directory.

## Credentials

No secret is ever stored in the application folder, which may be inside a
synced directory such as OneDrive or Dropbox. The optional `api` engine reads
`ANTHROPIC_API_KEY` from the user's environment only.

## Installing from the internet

`bootstrap.ps1` is designed to be run as `irm <url> | iex`. That pattern
executes a remote script without review. Read the script before running it, or
clone the repository and run `install.ps1` directly.
