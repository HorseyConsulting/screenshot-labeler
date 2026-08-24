"""Finding the screenshots folder on machines that are not this one."""

from screenshot_labeler.paths import find_screenshots_dir


class TestFindScreenshotsDir:
    def test_prefers_the_onedrive_folder_when_it_exists(self, tmp_path):
        onedrive = tmp_path / "OneDrive" / "Pictures" / "Screenshots"
        onedrive.mkdir(parents=True)
        (tmp_path / "Pictures" / "Screenshots").mkdir(parents=True)

        assert find_screenshots_dir(home=tmp_path) == onedrive

    def test_falls_back_to_the_plain_pictures_folder(self, tmp_path):
        """The default on any machine without OneDrive redirection."""
        plain = tmp_path / "Pictures" / "Screenshots"
        plain.mkdir(parents=True)

        assert find_screenshots_dir(home=tmp_path) == plain

    def test_returns_the_plain_path_when_neither_exists_yet(self, tmp_path):
        """Windows creates it on the first Win+PrtScn, so name it anyway."""
        assert find_screenshots_dir(home=tmp_path) == tmp_path / "Pictures" / "Screenshots"

    def test_ignores_a_onedrive_folder_without_a_screenshots_subfolder(self, tmp_path):
        (tmp_path / "OneDrive" / "Pictures").mkdir(parents=True)
        plain = tmp_path / "Pictures" / "Screenshots"
        plain.mkdir(parents=True)

        assert find_screenshots_dir(home=tmp_path) == plain
