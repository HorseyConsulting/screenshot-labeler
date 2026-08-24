from pathlib import Path

from screenshot_labeler.watcher import ScreenshotHandler


class FakeEvent:
    def __init__(self, path, is_directory=False):
        self.src_path = str(path)
        self.dest_path = str(path)
        self.is_directory = is_directory


def handler_recording_into(seen, stable=True):
    return ScreenshotHandler(
        process=lambda path: seen.append(Path(path).name),
        stable_check=lambda path: stable,
    )


class TestScreenshotHandler:
    def test_processes_a_new_screenshot(self, tmp_path):
        seen = []
        handler = handler_recording_into(seen)

        handler.on_created(FakeEvent(tmp_path / "Screenshot 2026-08-06 113045.png"))

        assert seen == ["Screenshot 2026-08-06 113045.png"]

    def test_ignores_a_hand_named_file(self, tmp_path):
        seen = []
        handler = handler_recording_into(seen)

        handler.on_created(FakeEvent(tmp_path / "Helmet Livery.png"))

        assert seen == []

    def test_ignores_an_already_labeled_file(self, tmp_path):
        seen = []
        handler = handler_recording_into(seen)

        handler.on_created(FakeEvent(tmp_path / "Helmet Livery Editor 2026-08-06.png"))

        assert seen == []

    def test_ignores_directories(self, tmp_path):
        seen = []
        handler = handler_recording_into(seen)

        handler.on_created(FakeEvent(tmp_path / "Screenshot 2026-08-06 113045.png", True))

        assert seen == []

    def test_skips_a_file_that_never_settles(self, tmp_path):
        seen = []
        handler = handler_recording_into(seen, stable=False)

        handler.on_created(FakeEvent(tmp_path / "Screenshot 2026-08-06 113045.png"))

        assert seen == []

    def test_handles_files_that_arrive_via_a_move(self, tmp_path):
        """Some capture tools write to a temp name then move it into place."""
        seen = []
        handler = handler_recording_into(seen)

        handler.on_moved(FakeEvent(tmp_path / "Screenshot 2026-08-06 113045.png"))

        assert seen == ["Screenshot 2026-08-06 113045.png"]

    def test_processes_each_file_only_once(self, tmp_path):
        seen = []
        handler = handler_recording_into(seen)
        event = FakeEvent(tmp_path / "Screenshot 2026-08-06 113045.png")

        handler.on_created(event)
        handler.on_created(event)

        assert seen == ["Screenshot 2026-08-06 113045.png"]

    def test_a_failing_process_does_not_kill_the_watcher(self, tmp_path):
        def explode(_path):
            raise RuntimeError("boom")

        handler = ScreenshotHandler(process=explode, stable_check=lambda path: True)

        handler.on_created(FakeEvent(tmp_path / "Screenshot 2026-08-06 113045.png"))
