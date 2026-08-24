import pytest
from PIL import Image, ImageDraw, ImageFont

from screenshot_labeler.ocr import extract_text, is_available, summarize_for_prompt


def font(size=48):
    for candidate in ("arial.ttf", "segoeui.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    pytest.skip("no truetype font available on this machine")


def text_image(path, lines, size=(1000, 400)):
    image = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(image)
    y = 30
    for line, points in lines:
        draw.text((30, y), line, fill=(0, 0, 0), font=font(points))
        y += points + 24
    image.save(path, "PNG")
    return path


class TestIsAvailable:
    def test_reports_windows_ocr_availability(self):
        assert is_available() is True


class TestExtractText:
    def test_reads_plain_text_from_an_image(self, tmp_path):
        source = text_image(tmp_path / "shot.png", [("Sustainable Concrete", 60)])

        assert "Sustainable Concrete" in extract_text(source)

    def test_reads_multiple_lines(self, tmp_path):
        source = text_image(
            tmp_path / "shot.png",
            [("Google Search Console", 54), ("Page Indexing Report", 44)],
        )

        result = extract_text(source)

        assert "Google Search Console" in result
        assert "Page Indexing" in result

    def test_returns_empty_for_an_image_with_no_text(self, tmp_path):
        source = tmp_path / "blank.png"
        Image.new("RGB", (600, 400), (120, 140, 160)).save(source, "PNG")

        assert extract_text(source) == ""

    def test_returns_empty_for_an_unreadable_file(self, tmp_path):
        source = tmp_path / "broken.png"
        source.write_bytes(b"not actually a png")

        assert extract_text(source) == ""

    def test_returns_empty_for_a_missing_file(self, tmp_path):
        assert extract_text(tmp_path / "nope.png") == ""


class TestSummarizeForPrompt:
    def test_keeps_short_text_intact(self):
        assert summarize_for_prompt("Gmail Inbox") == "Gmail Inbox"

    def test_collapses_runs_of_whitespace(self):
        assert summarize_for_prompt("Gmail   \n\n  Inbox") == "Gmail Inbox"

    def test_truncates_very_long_text(self):
        result = summarize_for_prompt("word " * 500, max_chars=200)

        assert len(result) <= 200

    def test_prefers_the_beginning_where_titles_live(self):
        result = summarize_for_prompt("TITLE HERE " + ("filler " * 300), max_chars=100)

        assert result.startswith("TITLE HERE")

    def test_returns_empty_for_empty_input(self):
        assert summarize_for_prompt("") == ""
