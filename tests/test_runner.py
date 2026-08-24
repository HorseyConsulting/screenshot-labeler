from pathlib import Path

from screenshot_labeler.runner import (
    ProcessResult,
    process_directory,
    process_one,
    wait_for_stable,
)


def make_screenshot(directory, name, data=b"fake png bytes"):
    path = directory / name
    path.write_bytes(data)
    return path


class StubLabeler:
    """Returns canned labels, or raises, without touching the network."""

    def __init__(self, *, returns=None, raises=None):
        self._returns = returns
        self._raises = raises
        self.seen = []

    def label(self, path):
        self.seen.append(Path(path).name)
        if self._raises is not None:
            raise self._raises
        if isinstance(self._returns, list):
            return self._returns.pop(0)
        return self._returns


def no_sleep(_seconds):
    return None


class TestProcessOne:
    def test_renames_when_a_label_comes_back(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"

        result = process_one(
            source, StubLabeler(returns="Helmet Livery Editor"), log, "run1", sleep=no_sleep
        )

        assert result.status == "renamed"
        assert result.new_name == "Helmet Livery Editor 2026-08-06.png"
        assert (tmp_path / "Helmet Livery Editor 2026-08-06.png").exists()

    def test_leaves_the_file_alone_when_the_model_cannot_tell(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"

        result = process_one(source, StubLabeler(returns=""), log, "run1", sleep=no_sleep)

        assert result.status == "skipped"
        assert source.exists()

    def test_leaves_the_file_alone_when_the_api_fails(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"

        result = process_one(
            source, StubLabeler(raises=RuntimeError("api down")), log, "run1", sleep=no_sleep
        )

        assert result.status == "failed"
        assert "api down" in result.error
        assert source.exists()

    def test_leaves_the_file_alone_when_the_label_is_unusable(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"

        result = process_one(source, StubLabeler(returns="///"), log, "run1", sleep=no_sleep)

        assert result.status == "skipped"
        assert source.exists()

    def test_retries_a_locked_file_then_succeeds(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"
        attempts = []

        def flaky_rename(path, label, log_path, run_id, model="", dry_run=False):
            attempts.append(1)
            if len(attempts) < 3:
                raise OSError("file is locked by another process")
            return path.parent / "Helmet Livery Editor 2026-08-06.png"

        result = process_one(
            source,
            StubLabeler(returns="Helmet Livery Editor"),
            log,
            "run1",
            sleep=no_sleep,
            rename_fn=flaky_rename,
        )

        assert result.status == "renamed"
        assert len(attempts) == 3

    def test_gives_up_after_repeated_lock_failures(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"

        def always_locked(path, label, log_path, run_id, model="", dry_run=False):
            raise OSError("file is locked by another process")

        result = process_one(
            source,
            StubLabeler(returns="Helmet Livery Editor"),
            log,
            "run1",
            sleep=no_sleep,
            rename_fn=always_locked,
        )

        assert result.status == "failed"
        assert source.exists()

    def test_dry_run_reports_the_new_name_without_renaming(self, tmp_path):
        source = make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        log = tmp_path / "log.jsonl"

        result = process_one(
            source,
            StubLabeler(returns="Helmet Livery Editor"),
            log,
            "run1",
            sleep=no_sleep,
            dry_run=True,
        )

        assert result.status == "renamed"
        assert result.new_name == "Helmet Livery Editor 2026-08-06.png"
        assert source.exists()
        assert not log.exists()


class TestProcessDirectory:
    def test_processes_every_candidate(self, tmp_path):
        make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        make_screenshot(tmp_path, "Screenshot 2026-08-07 090000.png")
        labeler = StubLabeler(returns=["First Shot", "Second Shot"])

        results = process_directory(
            tmp_path, labeler, tmp_path / "log.jsonl", "run1", sleep=no_sleep
        )

        assert [r.status for r in results] == ["renamed", "renamed"]
        assert (tmp_path / "First Shot 2026-08-06.png").exists()
        assert (tmp_path / "Second Shot 2026-08-07.png").exists()

    def test_never_touches_hand_named_files(self, tmp_path):
        make_screenshot(tmp_path, "Helmet Livery.png", b"precious")
        make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        labeler = StubLabeler(returns="First Shot")

        process_directory(tmp_path, labeler, tmp_path / "log.jsonl", "run1", sleep=no_sleep)

        assert (tmp_path / "Helmet Livery.png").read_bytes() == b"precious"
        assert labeler.seen == ["Screenshot 2026-08-06 113045.png"]

    def test_honours_the_limit(self, tmp_path):
        for day in (6, 7, 8):
            make_screenshot(tmp_path, f"Screenshot 2026-08-0{day} 090000.png")
        labeler = StubLabeler(returns=["A Shot", "B Shot", "C Shot"])

        results = process_directory(
            tmp_path, labeler, tmp_path / "log.jsonl", "run1", limit=2, sleep=no_sleep
        )

        assert len(results) == 2
        assert len(labeler.seen) == 2

    def test_one_failure_does_not_stop_the_rest(self, tmp_path):
        make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        make_screenshot(tmp_path, "Screenshot 2026-08-07 090000.png")
        labeler = StubLabeler(returns=["", "Second Shot"])

        results = process_directory(
            tmp_path, labeler, tmp_path / "log.jsonl", "run1", sleep=no_sleep
        )

        assert [r.status for r in results] == ["skipped", "renamed"]
        assert (tmp_path / "Second Shot 2026-08-07.png").exists()

    def test_reports_progress_through_the_callback(self, tmp_path):
        make_screenshot(tmp_path, "Screenshot 2026-08-06 113045.png")
        seen = []

        process_directory(
            tmp_path,
            StubLabeler(returns="First Shot"),
            tmp_path / "log.jsonl",
            "run1",
            sleep=no_sleep,
            on_result=seen.append,
        )

        assert len(seen) == 1
        assert isinstance(seen[0], ProcessResult)


class TestWaitForStable:
    def test_returns_true_for_a_file_that_is_done_writing(self, tmp_path):
        path = make_screenshot(tmp_path, "shot.png")

        assert wait_for_stable(path, sleep=no_sleep) is True

    def test_returns_false_for_a_file_that_never_exists(self, tmp_path):
        assert wait_for_stable(tmp_path / "missing.png", sleep=no_sleep) is False

    def test_returns_false_while_the_file_keeps_growing(self, tmp_path):
        path = make_screenshot(tmp_path, "shot.png")
        growth = {"n": 0}

        def grow(_seconds):
            growth["n"] += 1
            path.write_bytes(b"x" * (growth["n"] * 100))

        assert wait_for_stable(path, sleep=grow, attempts=3) is False
