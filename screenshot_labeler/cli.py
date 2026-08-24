"""Command-line entry point: backfill, watch, or undo."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from .labeler import DEFAULT_MODEL, Labeler
from .ocr import extract_text
from .paths import find_screenshots_dir
from .ollama_labeler import DEFAULT_OLLAMA_MODEL, OllamaLabeler
from .renamer import find_candidates, undo_last_run
from .runner import ProcessResult, process_directory, process_one

DEFAULT_WATCH_DIR = find_screenshots_dir()
TOOL_DIR = Path(__file__).resolve().parent.parent
LOG_PATH = TOOL_DIR / "rename-log.jsonl"

log = logging.getLogger("screenshot_labeler")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="screenshot-labeler",
        description="Rename screenshots from timestamps to descriptive labels.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--watch", action="store_true", help="watch for new screenshots")
    mode.add_argument("--backfill", action="store_true", help="label existing screenshots")
    mode.add_argument("--undo", action="store_true", help="reverse the most recent run")

    parser.add_argument("--dir", type=Path, default=DEFAULT_WATCH_DIR)
    parser.add_argument(
        "--engine",
        choices=("ollama", "api"),
        # Local by default: it is the only engine the installer can guarantee
        # exists on a machine that just downloaded this.
        default=os.environ.get("SCREENSHOT_LABELER_ENGINE", "ollama"),
        help=(
            "ollama: a vision model running locally on your GPU (fully offline). "
            "api: Anthropic API, requires ANTHROPIC_API_KEY."
        ),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("SCREENSHOT_LABELER_MODEL"),
        help="defaults per engine: 'qwen2.5vl:7b' (ollama), 'claude-haiku-4-5' (api)",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="skip the Windows OCR pass that feeds verified on-screen text to the model",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show what would happen, change nothing"
    )
    parser.add_argument("--limit", type=int, help="process at most N files (backfill)")
    parser.add_argument("--verbose", action="store_true")
    return parser


ENGINE_DEFAULT_MODELS = {
    "ollama": DEFAULT_OLLAMA_MODEL,
    "api": DEFAULT_MODEL,
}


def resolve_model(engine: str, model: str | None) -> str:
    return model or ENGINE_DEFAULT_MODELS[engine]


def make_labeler(engine: str, model: str, use_ocr: bool = True):
    """Build the configured labeler. Fails loudly rather than half-working."""
    # Disabling OCR is expressed as a reader that finds nothing, so no engine
    # needs to know the flag exists.
    ocr = extract_text if use_ocr else (lambda path: "")

    if engine == "ollama":
        return OllamaLabeler(model=model, ocr_reader=ocr)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set.\n"
            'Set it once with:  setx ANTHROPIC_API_KEY "sk-ant-..."\n'
            "then open a new terminal -- or use --engine ollama instead."
        )
    from anthropic import Anthropic

    return Labeler(Anthropic(), model=model, ocr_reader=ocr)


def describe(result: ProcessResult) -> str:
    if result.status == "renamed":
        return f"  {result.path.name}\n    -> {result.new_name}"
    return f"  {result.path.name}\n    -- {result.status}: {result.error}"


def run_backfill(args) -> int:
    pending = find_candidates(args.dir)
    if not pending:
        print(f"Nothing to do: no unlabeled screenshots in {args.dir}")
        return 0

    limit = args.limit if args.limit is not None else len(pending)
    print(f"{len(pending)} unlabeled screenshot(s) found; processing {min(limit, len(pending))}.")
    if args.dry_run:
        print("DRY RUN - nothing on disk will change.\n")

    model = resolve_model(args.engine, args.model)
    labeler = make_labeler(args.engine, model, use_ocr=not args.no_ocr)
    run_id = datetime.now().strftime("backfill-%Y%m%d-%H%M%S")
    print(f"Engine: {args.engine} (model: {model})\n")

    results = process_directory(
        args.dir,
        labeler,
        LOG_PATH,
        run_id,
        model=model,
        limit=args.limit,
        dry_run=args.dry_run,
        on_result=lambda r: print(describe(r), flush=True),
    )

    renamed = sum(1 for r in results if r.status == "renamed")
    print(f"\n{renamed} renamed, {len(results) - renamed} left alone.")
    if not args.dry_run and renamed:
        print(f"Undo this run with:  python -m screenshot_labeler --undo --dir \"{args.dir}\"")
    return 0


def run_watch(args) -> int:
    from watchdog.observers import Observer

    from .watcher import ScreenshotHandler

    model = resolve_model(args.engine, args.model)
    labeler = make_labeler(args.engine, model, use_ocr=not args.no_ocr)
    run_id = datetime.now().strftime("watch-%Y%m%d-%H%M%S")

    def handle(path: Path) -> None:
        result = process_one(path, labeler, LOG_PATH, run_id, model=model)
        log.info(describe(result).strip())

    observer = Observer()
    observer.schedule(ScreenshotHandler(process=handle), str(args.dir), recursive=False)
    observer.start()
    log.info("Watching %s (engine: %s, model: %s). Ctrl-C to stop.", args.dir, args.engine, model)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping.")
    finally:
        observer.stop()
        observer.join()
    return 0


def run_undo(args) -> int:
    restored = undo_last_run(args.dir, LOG_PATH)
    if not restored:
        print("Nothing to undo.")
        return 0
    print(f"Restored {len(restored)} filename(s):")
    for name in restored:
        print(f"  {name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.dir.exists():
        # Windows creates this on the first screenshot; making it early lets
        # the watcher start on a machine that has never taken one.
        try:
            args.dir.mkdir(parents=True, exist_ok=True)
            log.info("Created %s", args.dir)
        except OSError as exc:
            raise SystemExit(f"Could not create {args.dir}: {exc}")
    elif not args.dir.is_dir():
        raise SystemExit(f"Not a directory: {args.dir}")

    if args.undo:
        return run_undo(args)
    if args.backfill:
        return run_backfill(args)
    return run_watch(args)


if __name__ == "__main__":
    sys.exit(main())
