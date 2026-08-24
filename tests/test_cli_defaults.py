"""The default engine must work on a machine with nothing else installed."""

import pytest

from screenshot_labeler.cli import build_parser, resolve_model


def parse(argv):
    return build_parser().parse_args(argv)


class TestDefaultEngine:
    def test_defaults_to_the_local_engine(self):
        """A downloader has Ollama (the installer sets it up) but not Claude Code."""
        assert parse(["--backfill"]).engine == "ollama"

    def test_environment_variable_overrides_the_default(self, monkeypatch):
        monkeypatch.setenv("SCREENSHOT_LABELER_ENGINE", "cli")

        assert parse(["--backfill"]).engine == "cli"

    def test_explicit_flag_wins(self):
        assert parse(["--backfill", "--engine", "api"]).engine == "api"


class TestModelDefaults:
    @pytest.mark.parametrize(
        "engine,expected",
        [("ollama", "qwen2.5vl:7b"), ("cli", "haiku"), ("api", "claude-haiku-4-5")],
    )
    def test_each_engine_has_a_sensible_default_model(self, engine, expected):
        assert resolve_model(engine, None) == expected

    def test_an_explicit_model_overrides_the_default(self):
        assert resolve_model("ollama", "qwen2.5vl:3b") == "qwen2.5vl:3b"
