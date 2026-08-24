import json
from datetime import datetime

from screenshot_labeler.renamer import (
    find_candidates,
    rename_with_log,
    undo_last_run,
)


def make_screenshot(directory, name):
    path = directory / name
    path.write_bytes(b"fake png bytes")
    return path


class TestFindCandidates:
    def test_finds_unlabeled_screenshots(self, tmp_path):
        make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        make_screenshot(tmp_path, "Screenshot 2026-08-07 090000.png")

        found = {p.name for p in find_candidates(tmp_path)}

        assert found == {
            "Screenshot 2026-08-06 113045.png",
            "Screenshot 2026-08-07 090000.png",
        }

    def test_ignores_hand_named_files(self, tmp_path):
        make_screenshot(tmp_path, "Helmet Livery.png")
        make_screenshot(tmp_path, "this is next.png")

        assert find_candidates(tmp_path) == []

    def test_ignores_already_labeled_files(self, tmp_path):
        make_screenshot(tmp_path, "Helmet Livery Editor 2026-08-06.png")

        assert find_candidates(tmp_path) == []

    def test_ignores_desktop_ini(self, tmp_path):
        (tmp_path / "desktop.ini").write_text("[.ShellClassInfo]")

        assert find_candidates(tmp_path) == []

    def test_returns_candidates_in_chronological_order(self, tmp_path):
        make_screenshot(tmp_path, "Screenshot 2026-08-07 090000.png")
        make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")

        assert [p.name for p in find_candidates(tmp_path)] == [
            "Screenshot 2026-08-06 113045.png",
            "Screenshot 2026-08-07 090000.png",
        ]


class TestRenameWithLog:
    def test_renames_the_file_on_disk(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"

        rename_with_log(source, "Helmet Livery Editor", log, run_id="run1")

        assert (tmp_path / "Helmet Livery Editor 2026-08-06.png").exists()
        assert not source.exists()

    def test_returns_the_new_path(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"

        result = rename_with_log(source, "Helmet Livery Editor", log, run_id="run1")

        assert result.name == "Helmet Livery Editor 2026-08-06.png"

    def test_preserves_file_contents(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"

        result = rename_with_log(source, "Helmet Livery Editor", log, run_id="run1")

        assert result.read_bytes() == b"fake png bytes"

    def test_writes_an_undo_log_entry(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"

        rename_with_log(source, "Helmet Livery Editor", log, run_id="run1")

        entry = json.loads(log.read_text().strip())
        assert entry["old"] == "Screenshot 2026-08-06 113045.png"
        assert entry["new"] == "Helmet Livery Editor 2026-08-06.png"
        assert entry["label"] == "Helmet Livery Editor"
        assert entry["run_id"] == "run1"

    def test_appends_rather_than_overwriting_the_log(self, tmp_path):
        log = tmp_path / "log.jsonl"
        first = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        second = make_screenshot(tmp_path, "Screenshot 2026-08-07 090000.png")

        rename_with_log(first, "First Shot", log, run_id="run1")
        rename_with_log(second, "Second Shot", log, run_id="run1")

        assert len(log.read_text().strip().splitlines()) == 2

    def test_resolves_collisions_instead_of_overwriting(self, tmp_path):
        existing = make_screenshot(tmp_path, "Helmet Livery Editor 2026-08-06.png")
        existing.write_bytes(b"original file")
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"

        result = rename_with_log(source, "Helmet Livery Editor", log, run_id="run1")

        assert result.name == "Helmet Livery Editor 2026-08-06 (2).png"
        assert existing.read_bytes() == b"original file"

    def test_dry_run_leaves_disk_untouched(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"

        result = rename_with_log(
            source, "Helmet Livery Editor", log, run_id="run1", dry_run=True
        )

        assert source.exists()
        assert result.name == "Helmet Livery Editor 2026-08-06.png"
        assert not result.exists()
        assert not log.exists()


class TestUndoLastRun:
    def test_restores_original_filenames(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"
        rename_with_log(source, "Helmet Livery Editor", log, run_id="run1")

        undo_last_run(tmp_path, log)

        assert (tmp_path / "Screenshot 2026-08-06 113045.png").exists()
        assert not (tmp_path / "Helmet Livery Editor 2026-08-06.png").exists()

    def test_undoes_only_the_most_recent_run(self, tmp_path):
        log = tmp_path / "log.jsonl"
        old = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        rename_with_log(old, "Old Run Shot", log, run_id="run1")
        recent = make_screenshot(tmp_path, "Screenshot 2026-08-07 090000.png")
        rename_with_log(recent, "New Run Shot", log, run_id="run2")

        undo_last_run(tmp_path, log)

        assert (tmp_path / "Screenshot 2026-08-07 090000.png").exists()
        assert (tmp_path / "Old Run Shot 2026-08-06.png").exists()

    def test_returns_the_restored_names(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"
        rename_with_log(source, "Helmet Livery Editor", log, run_id="run1")

        restored = undo_last_run(tmp_path, log)

        assert restored == ["Screenshot 2026-08-06 113045.png"]

    def test_skips_entries_whose_file_is_gone(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"
        renamed = rename_with_log(source, "Helmet Livery Editor", log, run_id="run1")
        renamed.unlink()

        assert undo_last_run(tmp_path, log) == []

    def test_does_not_clobber_a_file_sitting_at_the_original_name(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"
        rename_with_log(source, "Helmet Livery Editor", log, run_id="run1")
        blocker = tmp_path / "Screenshot 2026-08-06 113045.png"
        blocker.write_bytes(b"something else arrived here")

        undo_last_run(tmp_path, log)

        assert blocker.read_bytes() == b"something else arrived here"
        assert (tmp_path / "Helmet Livery Editor 2026-08-06.png").exists()

    def test_handles_a_missing_log(self, tmp_path):
        assert undo_last_run(tmp_path, tmp_path / "nonexistent.jsonl") == []
