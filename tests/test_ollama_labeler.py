import json

import pytest
from PIL import Image

from screenshot_labeler.ollama_labeler import DEFAULT_OLLAMA_MODEL, OllamaLabeler


def write_png(path, size=(1920, 1080)):
    Image.new("RGB", size, (30, 60, 90)).save(path, "PNG")
    return path


class FakePoster:
    """Stands in for the HTTP call to the local Ollama server."""

    def __init__(self, response=None, raises=None):
        self._response = response if response is not None else {"response": "Gmail Inbox"}
        self._raises = raises
        self.calls = []

    def __call__(self, url, payload, timeout):
        self.calls.append({"url": url, "payload": payload, "timeout": timeout})
        if self._raises is not None:
            raise self._raises
        return self._response

    @property
    def payload(self):
        return self.calls[0]["payload"]


def labeler_for(poster, **kwargs):
    kwargs.setdefault("ocr_reader", lambda path: "")
    return OllamaLabeler(post=poster, **kwargs)


class TestOllamaLabeler:
    def test_returns_the_models_label(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler = labeler_for(FakePoster({"response": "Gmail Inbox"}))

        assert labeler.label(source) == "Gmail Inbox"

    def test_strips_quotes_and_trailing_punctuation(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler = labeler_for(FakePoster({"response": '  "Gmail Inbox."  '}))

        assert labeler.label(source) == "Gmail Inbox"

    def test_returns_empty_when_the_model_cannot_tell(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler = labeler_for(FakePoster({"response": "UNKNOWN"}))

        assert labeler.label(source) == ""

    def test_sends_the_image_as_base64(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        poster = FakePoster()

        labeler_for(poster).label(source)

        images = poster.payload["images"]
        assert len(images) == 1
        assert isinstance(images[0], str) and len(images[0]) > 100

    def test_sends_the_configured_model(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        poster = FakePoster()

        labeler_for(poster, model="qwen2.5vl:3b").label(source)

        assert poster.payload["model"] == "qwen2.5vl:3b"

    def test_defaults_to_the_7b_model(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        poster = FakePoster()

        labeler_for(poster).label(source)

        assert poster.payload["model"] == DEFAULT_OLLAMA_MODEL

    def test_disables_streaming(self, tmp_path):
        """A single JSON object is far easier to handle than a token stream."""
        source = write_png(tmp_path / "shot.png")
        poster = FakePoster()

        labeler_for(poster).label(source)

        assert poster.payload["stream"] is False

    def test_includes_ocr_text_in_the_prompt(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        poster = FakePoster()

        OllamaLabeler(post=poster, ocr_reader=lambda p: "Security rules Cloudflare").label(source)

        assert "Security rules Cloudflare" in poster.payload["prompt"]

    def test_a_failing_ocr_engine_does_not_break_labeling(self, tmp_path):
        source = write_png(tmp_path / "shot.png")

        def broken(_path):
            raise RuntimeError("ocr exploded")

        labeler = OllamaLabeler(post=FakePoster(), ocr_reader=broken)

        assert labeler.label(source) == "Gmail Inbox"

    def test_raises_a_clear_error_when_the_server_is_down(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler = labeler_for(FakePoster(raises=ConnectionRefusedError()))

        with pytest.raises(RuntimeError, match="Ollama"):
            labeler.label(source)

    def test_returns_empty_when_the_response_has_no_text(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler = labeler_for(FakePoster({}))

        assert labeler.label(source) == ""
