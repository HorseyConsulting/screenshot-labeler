"""Locating the user's screenshots folder.

Windows saves Win+PrtScn captures to Pictures\\Screenshots, but OneDrive
redirects the Pictures library when Known Folder Move is on. Which one is real
differs per machine, so it has to be detected rather than assumed.
"""

from __future__ import annotations

from pathlib import Path


def find_screenshots_dir(home: Path | None = None) -> Path:
    """Best guess at where this machine puts screenshots.

    Prefers the OneDrive-redirected folder when it actually exists, since on a
    redirected machine that is where captures really land. Otherwise the plain
    Pictures folder -- returned even if absent, because Windows creates it on
    the first screenshot and naming it is more useful than failing.
    """
    root = home or Path.home()

    redirected = root / "OneDrive" / "Pictures" / "Screenshots"
    if redirected.is_dir():
        return redirected

    return root / "Pictures" / "Screenshots"
