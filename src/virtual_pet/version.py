"""The app's version, shown in Settings.

Running from source, it is pyproject.toml's. Built, it is VERSION, a data file the build
writes next to this module: the AppImage's or the Windows zip's own version, with a commit
suffix when it isn't a clean checkout of a release tag (see appimage/build.py).
"""

import tomllib
from pathlib import Path

_BUNDLED = Path(__file__).with_name("VERSION")
_PYPROJECT = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"


def app_version() -> str:
    """The version to show: the build's own once packaged, else pyproject.toml's."""
    if _BUNDLED.exists():
        return _BUNDLED.read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    return pyproject["project"]["version"]
