import re
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from screenshot_labeler.cli_labeler import CliLabeler


def write_png(path, size=(1920, 1080)):
    Image.new("RGB", size, (30, 60, 90)).save(path, "PNG")
    return path


class FakeCompleted:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def image_path_in(command):
    """Pull the temp image path out of the prompt argument."""
    joined = " ".join(command)
    match = re.search(r"(\S+\.png)", joined)
    return Path(match.group(1)) if match else None


class FakeRunner:
    """Stands in for subprocess.run, recording how it was invoked."""

    def __init__(self, result):
        self._result = result
        self.calls = []
        self.image_existed = None

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        # The temp image must still exist at the moment the CLI would read it.
        image = image_path_in(command)
        self.image_existed = image.exists() if image else False
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def labeler_for(result, **kwargs):
    runner = FakeRunner(result)
    return CliLabeler(run=runner, **kwargs), runner


class TestCliLabeler:
    def test_returns_the_label_from_stdout(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler, _ = labeler_for(FakeCompleted("Stable Trades Racing Helmet\n"))

        assert labeler.label(source) == "Stable Trades Racing Helmet"

    def test_strips_quotes_and_trailing_punctuation(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler, _ = labeler_for(FakeCompleted('  "Gmail Inbox."  \n'))

        assert labeler.label(source) == "Gmail Inbox"

    def test_uses_the_last_line_when_the_cli_is_chatty(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler, _ = labeler_for(FakeCompleted("Reading the image...\nGmail Inbox\n"))

        assert labeler.label(source) == "Gmail Inbox"

    def test_returns_empty_when_the_model_cannot_tell(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler, _ = labeler_for(FakeCompleted("UNKNOWN\n"))

        assert labeler.label(source) == ""

    def test_returns_empty_on_empty_output(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler, _ = labeler_for(FakeCompleted("\n"))

        assert labeler.label(source) == ""

    def test_raises_when_the_cli_exits_nonzero(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler, _ = labeler_for(FakeCompleted("", returncode=1, stderr="not logged in"))

        with pytest.raises(RuntimeError, match="not logged in"):
            labeler.label(source)

    def test_raises_on_timeout(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler, _ = labeler_for(subprocess.TimeoutExpired("claude", 120))

        with pytest.raises(RuntimeError, match="timed out"):
            labeler.label(source)

    def test_passes_the_configured_model(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler, runner = labeler_for(FakeCompleted("Gmail Inbox"), model="sonnet")

        labeler.label(source)

        command, _ = runner.calls[0]
        assert "--model" in command
        assert command[command.index("--model") + 1] == "sonnet"

    def test_runs_in_headless_print_mode(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler, runner = labeler_for(FakeCompleted("Gmail Inbox"))

        labeler.label(source)

        command, _ = runner.calls[0]
        assert "-p" in command

    def test_the_downscaled_image_exists_while_the_cli_runs(self, tmp_path):
        source = write_png(tmp_path / "shot.png", size=(1920, 1080))
        labeler, runner = labeler_for(FakeCompleted("Gmail Inbox"))

        labeler.label(source)

        assert runner.image_existed is True

    def test_cleans_up_its_temp_image_afterwards(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler, runner = labeler_for(FakeCompleted("Gmail Inbox"))

        labeler.label(source)

        command, _ = runner.calls[0]
        assert not image_path_in(command).exists()

    def test_cleans_up_even_when_the_cli_fails(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler, runner = labeler_for(FakeCompleted("", returncode=1, stderr="boom"))

        with pytest.raises(RuntimeError):
            labeler.label(source)

        command, _ = runner.calls[0]
        assert not image_path_in(command).exists()


class TestNoConsoleWindow:
    def test_suppresses_the_console_window_on_windows(self, tmp_path):
        """Under pythonw.exe a child process would otherwise flash a console."""
        source = write_png(tmp_path / "shot.png")
        labeler, runner = labeler_for(FakeCompleted("Gmail Inbox"))

        labeler.label(source)

        _, kwargs = runner.calls[0]
        assert kwargs.get("creationflags") == subprocess.CREATE_NO_WINDOW
