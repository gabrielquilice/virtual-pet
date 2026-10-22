"""Opening a web page in the user's browser."""

import os
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_link(url: str) -> bool:
    """Open `url` in the default browser; False if the desktop couldn't be asked.

    In the AppImage the launcher (`xdg-open`, which on KDE runs `kde-open`) would inherit the
    bundle's `LD_LIBRARY_PATH` and load its Qt instead of the system's, and fail with a symbol
    lookup error. PyInstaller keeps the user's own value in `LD_LIBRARY_PATH_ORIG` (none when
    there was none), so the launcher gets that one, and the app's comes back afterwards.
    """
    if not (getattr(sys, "frozen", False) and sys.platform.startswith("linux")):
        return QDesktopServices.openUrl(QUrl(url))
    bundled = os.environ.get("LD_LIBRARY_PATH")
    users = os.environ.get("LD_LIBRARY_PATH_ORIG")
    _set_library_path(users)
    try:
        return QDesktopServices.openUrl(QUrl(url))
    finally:
        _set_library_path(bundled)


def _set_library_path(value: str | None) -> None:
    if value is None:
        os.environ.pop("LD_LIBRARY_PATH", None)
    else:
        os.environ["LD_LIBRARY_PATH"] = value
