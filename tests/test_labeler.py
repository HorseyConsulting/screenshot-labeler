import base64
import io

import pytest
from PIL import Image

from screenshot_labeler.labeler import Labeler, prepare_image


def write_png(path, size=(1920, 1080), color=(30, 60, 90)):
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def decode(encoded):
    return Image.open(io.BytesIO(base64.b64decode(encoded)))


class FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeMessage:
    def __init__(self, blocks, stop_reason="end_turn"):
        self.content = blocks
        self.stop_reason = stop_reason


class FakeMessages:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class FakeClient:
    def __init__(self, response):
        self.messages = FakeMessages(response)


def client_returning(text, stop_reason="end_turn"):
    return FakeClient(FakeMessage([FakeBlock(text)], stop_reason))


class TestPrepareImage:
    def test_downscales_a_large_screenshot(self, tmp_path):
        source = write_png(tmp_path / "shot.png", size=(1920, 1080))

        encoded, media_type = prepare_image(source, max_width=1024)

        assert decode(encoded).size == (1024, 576)
        assert media_type == "image/png"

    def test_leaves_a_small_screenshot_at_its_own_size(self, tmp_path):
        source = write_png(tmp_path / "shot.png", size=(800, 600))

        encoded, _ = prepare_image(source, max_width=1024)

        assert decode(encoded).size == (800, 600)

    def test_handles_very_tall_screenshots(self, tmp_path):
        source = write_png(tmp_path / "shot.png", size=(500, 4000))

        encoded, _ = prepare_image(source, max_width=1024)

        assert decode(encoded).size == (500, 4000)


class TestLabeler:
    def test_returns_the_models_label(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler = Labeler(client_returning("Helmet Livery Editor"), model="test-model")

        assert labeler.label(source) == "Helmet Livery Editor"

    def test_strips_surrounding_whitespace_and_punctuation(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler = Labeler(client_returning('  "Helmet Livery Editor."  '), model="m")

        assert labeler.label(source) == "Helmet Livery Editor"

    def test_sends_the_configured_model(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        client = client_returning("Helmet Livery Editor")

        Labeler(client, model="claude-haiku-4-5").label(source)

        assert client.messages.calls[0]["model"] == "claude-haiku-4-5"

    def test_sends_the_image_as_an_image_block(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        client = client_returning("Helmet Livery Editor")

        Labeler(client, model="m").label(source)

        blocks = client.messages.calls[0]["messages"][0]["content"]
        assert any(block["type"] == "image" for block in blocks)

    def test_returns_empty_on_a_refusal(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler = Labeler(client_returning("", stop_reason="refusal"), model="m")

        assert labeler.label(source) == ""

    def test_returns_empty_when_the_model_says_it_cannot_tell(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler = Labeler(client_returning("UNKNOWN"), model="m")

        assert labeler.label(source) == ""

    def test_returns_empty_when_no_text_block_comes_back(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler = Labeler(FakeClient(FakeMessage([])), model="m")

        assert labeler.label(source) == ""

    def test_propagates_api_errors_to_the_caller(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        labeler = Labeler(FakeClient(RuntimeError("api down")), model="m")

        with pytest.raises(RuntimeError):
            labeler.label(source)
