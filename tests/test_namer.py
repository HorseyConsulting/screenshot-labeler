from datetime import datetime

import pytest

from screenshot_labeler.namer import (
    build_filename,
    parse_screenshot_name,
    resolve_collision,
    sanitize_label,
)


class TestParseScreenshotName:
    def test_extracts_timestamp_from_windows_screenshot_name(self):
        assert parse_screenshot_name("Screenshot 2026-08-06 113045.png") == datetime(
            2026, 8, 6, 11, 30, 45
        )

    def test_returns_none_for_hand_named_file(self):
        assert parse_screenshot_name("Helmet Livery.png") is None

    def test_returns_none_for_already_labeled_file(self):
        assert parse_screenshot_name("Helmet Livery Editor 2026-08-06.png") is None

    def test_returns_none_for_desktop_ini(self):
        assert parse_screenshot_name("desktop.ini") is None

    def test_accepts_jpg_screenshots(self):
        assert parse_screenshot_name("Screenshot 2026-08-06 113045.jpg") == datetime(
            2026, 8, 6, 11, 30, 45
        )

    def test_rejects_impossible_date(self):
        assert parse_screenshot_name("Screenshot 2026-13-45 999999.png") is None


class TestSanitizeLabel:
    def test_passes_through_a_clean_label(self):
        assert sanitize_label("Helmet Livery Editor") == "Helmet Livery Editor"

    def test_strips_characters_windows_forbids(self):
        assert sanitize_label('a<b>c:d"e/f\\g|h?i*j') == "abcdefghij"

    def test_collapses_whitespace(self):
        assert sanitize_label("  VS   Code\n Traceback  ") == "VS Code Traceback"

    def test_strips_trailing_dots_and_spaces(self):
        assert sanitize_label("Amazon Order...  ") == "Amazon Order"

    def test_strips_surrounding_quotes_the_model_may_add(self):
        assert sanitize_label('"Helmet Livery Editor"') == "Helmet Livery Editor"

    def test_truncates_overlong_labels_at_a_word_boundary(self):
        label = sanitize_label("word " * 40)
        assert len(label) <= 60
        assert not label.endswith(" ")

    def test_rejects_reserved_device_names(self):
        for reserved in ("CON", "con", "PRN", "NUL", "COM1", "LPT9"):
            assert sanitize_label(reserved) == ""

    def test_rejects_label_that_sanitizes_to_nothing(self):
        assert sanitize_label("///???") == ""

    def test_rejects_empty_label(self):
        assert sanitize_label("") == ""


class TestBuildFilename:
    def test_places_label_before_date(self):
        taken = datetime(2026, 8, 6, 11, 30, 45)
        assert (
            build_filename("Helmet Livery Editor", taken, ".png")
            == "Helmet Livery Editor 2026-08-06.png"
        )

    def test_preserves_original_extension(self):
        taken = datetime(2026, 8, 6, 11, 30, 45)
        assert build_filename("F1 Standings", taken, ".jpg") == "F1 Standings 2026-08-06.jpg"

    def test_raises_on_unusable_label(self):
        with pytest.raises(ValueError):
            build_filename("///", datetime(2026, 8, 6, 11, 30, 45), ".png")


class TestResolveCollision:
    def test_returns_name_unchanged_when_free(self, tmp_path):
        assert resolve_collision(tmp_path, "Helmet Livery 2026-08-06.png") == (
            "Helmet Livery 2026-08-06.png"
        )

    def test_appends_counter_when_taken(self, tmp_path):
        (tmp_path / "Helmet Livery 2026-08-06.png").touch()
        assert resolve_collision(tmp_path, "Helmet Livery 2026-08-06.png") == (
            "Helmet Livery 2026-08-06 (2).png"
        )

    def test_counts_up_past_multiple_collisions(self, tmp_path):
        (tmp_path / "Helmet Livery 2026-08-06.png").touch()
        (tmp_path / "Helmet Livery 2026-08-06 (2).png").touch()
        (tmp_path / "Helmet Livery 2026-08-06 (3).png").touch()
        assert resolve_collision(tmp_path, "Helmet Livery 2026-08-06.png") == (
            "Helmet Livery 2026-08-06 (4).png"
        )
