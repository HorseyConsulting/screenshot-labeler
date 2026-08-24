# Backup

Code kept for reference, deliberately **not** part of the product.

Nothing here is imported by `screenshot_labeler`, exercised by the test suite,
or copied by `bootstrap.ps1` when someone installs from GitHub.

## cli_labeler.py / test_cli_labeler.py

A third labeling engine that shelled out to the local `claude` CLI. Removed in
commit `e4aa30b` (August 2026).

**Why it was removed:** it ran on the end user's own Claude Code subscription.
Selling a product whose core function depends on the customer's personal
subscription to another service is legally murky, and not worth the ambiguity
in something intended for the Microsoft Store.

**Why it's worth keeping:** it produced the best labels of any engine. On
screenshots the local model finds hard it was clearly better -- it named a
low-resolution badge `400 Milestone Badge` and declined to guess at unreadable
text, where the local 7B invents letters (`LMT 400 Logo`, and a different
answer on each run).

**To use it again personally**, copy `cli_labeler.py` back into
`screenshot_labeler/`, copy the test back into `tests/`, then re-add to
`cli.py`:

- `from .cli_labeler import DEFAULT_CLI_MODEL, CliLabeler`
- `"cli"` in the `--engine` choices and in `ENGINE_DEFAULT_MODELS`
- a branch in `make_labeler()` returning `CliLabeler(model=model, ocr_reader=ocr)`

It requires Claude Code installed and signed in. Do not ship it in a
commercial build.
