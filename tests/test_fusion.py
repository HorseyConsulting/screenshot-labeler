"""OCR text feeding into the vision prompt -- the fusion the whole design rests on."""

from PIL import Image

from screenshot_labeler.labeler import Labeler, build_prompt


def write_png(path, size=(800, 600)):
    Image.new("RGB", size, (30, 60, 90)).save(path, "PNG")
    return path


class FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeMessage:
    def __init__(self, text):
        self.content = [FakeBlock(text)]
        self.stop_reason = "end_turn"


class FakeMessages:
    def __init__(self, text):
        self._text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeMessage(self._text)


class FakeClient:
    def __init__(self, text="Cloudflare Security Rules"):
        self.messages = FakeMessages(text)


def prompt_text_of(client):
    blocks = client.messages.calls[0]["messages"][0]["content"]
    return next(b["text"] for b in blocks if b["type"] == "text")


class TestBuildPrompt:
    def test_plain_instruction_when_there_is_no_ocr_text(self):
        assert "OCR" not in build_prompt("", ocr_ran=False)

    def test_includes_the_ocr_text_verbatim(self):
        prompt = build_prompt("Security rules Secure your domain", ocr_ran=True)

        assert "Security rules Secure your domain" in prompt

    def test_tells_the_model_the_text_came_from_ocr(self):
        prompt = build_prompt("Gmail Inbox with several unread messages", ocr_ran=True)

        assert "OCR" in prompt


class TestLabelerUsesOcr:
    def test_passes_ocr_text_into_the_prompt(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        client = FakeClient()
        labeler = Labeler(client, model="m", ocr_reader=lambda p: "Security rules Cloudflare")

        labeler.label(source)

        assert "Security rules Cloudflare" in prompt_text_of(client)

    def test_works_when_ocr_finds_nothing(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        client = FakeClient()
        labeler = Labeler(client, model="m", ocr_reader=lambda p: "")

        assert labeler.label(source) == "Cloudflare Security Rules"
        # OCR ran and found nothing -- that fact is now itself passed along.
        assert "do not quote" in prompt_text_of(client).lower()

    def test_a_failing_ocr_engine_does_not_break_labeling(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        client = FakeClient()

        def broken(_path):
            raise RuntimeError("ocr exploded")

        labeler = Labeler(client, model="m", ocr_reader=broken)

        assert labeler.label(source) == "Cloudflare Security Rules"

    def test_ocr_can_be_turned_off(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        client = FakeClient()
        labeler = Labeler(client, model="m", ocr_reader=lambda p: "should not appear")

        labeler.label(source, use_ocr=False)

        assert "should not appear" not in prompt_text_of(client)


class FakeCompleted:
    def __init__(self, stdout="Cloudflare Security Rules"):
        self.stdout = stdout
        self.returncode = 0
        self.stderr = ""


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        return FakeCompleted()

    @property
    def prompt(self):
        return " ".join(self.calls[0])


class TestCliLabelerUsesOcr:
    def test_passes_ocr_text_into_the_prompt(self, tmp_path):
        from screenshot_labeler.cli_labeler import CliLabeler

        source = write_png(tmp_path / "shot.png")
        runner = RecordingRunner()
        labeler = CliLabeler(run=runner, ocr_reader=lambda p: "Security rules Cloudflare")

        labeler.label(source)

        assert "Security rules Cloudflare" in runner.prompt

    def test_a_failing_ocr_engine_does_not_break_labeling(self, tmp_path):
        from screenshot_labeler.cli_labeler import CliLabeler

        def broken(_path):
            raise RuntimeError("ocr exploded")

        source = write_png(tmp_path / "shot.png")
        labeler = CliLabeler(run=RecordingRunner(), ocr_reader=broken)

        assert labeler.label(source) == "Cloudflare Security Rules"


class TestAntiHallucinationHint:
    """When OCR finds nothing, that is evidence there IS no legible text."""

    def test_warns_against_inventing_text_when_ocr_found_nothing(self):
        prompt = build_prompt("", ocr_ran=True)

        assert "do not" in prompt.lower()
        assert "cannot" in prompt.lower() or "can't" in prompt.lower()

    def test_warns_when_ocr_found_only_a_fragment(self):
        prompt = build_prompt("400", ocr_ran=True)

        assert "do not" in prompt.lower()

    def test_stays_silent_when_ocr_was_never_run(self):
        assert build_prompt("", ocr_ran=False) == "Name this screenshot."

    def test_uses_the_reference_block_when_ocr_found_real_text(self):
        prompt = build_prompt("Security rules Secure your domain with actions", ocr_ran=True)

        assert "Security rules Secure your domain" in prompt

    def test_labeler_signals_that_ocr_ran_even_when_it_found_nothing(self, tmp_path):
        source = write_png(tmp_path / "shot.png")
        client = FakeClient()
        Labeler(client, model="m", ocr_reader=lambda p: "").label(source)

        assert "do not" in prompt_text_of(client).lower()


class TestEmptyOcrDoesNotCauseRefusal:
    """OCR failing is not evidence the image is unreadable to the model."""

    def test_tells_the_model_to_still_produce_a_name(self):
        prompt = build_prompt("", ocr_ran=True).lower()

        assert "still" in prompt

    def test_explicitly_forbids_refusing_just_because_ocr_was_empty(self):
        prompt = build_prompt("", ocr_ran=True).lower()

        assert "unknown" in prompt
