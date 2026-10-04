"""Whether a newer version exists on GitHub: checked when the user asks, in Settings, and in the
background once a day, the first time the pet starts that day.

A plain GET to the GitHub API, with the standard library: the AppImage leaves QtNetwork out
on purpose (see appimage/virtual-pet.spec), so this doesn't bring it back.
"""

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from datetime import date

from PySide6.QtCore import QObject, QThreadPool, Signal

REPOSITORY = "gabrielquilice/virtual-pet"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASE_PAGE = f"https://github.com/{REPOSITORY}/releases/latest"
TIMEOUT = 5  # seconds
DISABLE_VARIABLE = "VIRTUAL_PET_NO_UPDATE_CHECK"  # set by the tests: none reaches GitHub
DEV_BUILD = re.compile(r"\+g")  # appimage/build.py's suffix for a build that isn't a release


@dataclass(frozen=True)
class UpdateAvailable:
    """A newer release exists."""

    version: str
    url: str


@dataclass(frozen=True)
class UpToDate:
    """This build is the latest release."""


@dataclass(frozen=True)
class DevBuild:
    """This build isn't a release: there is nothing to compare it to."""


@dataclass(frozen=True)
class CheckFailed:
    """The check couldn't reach GitHub or make sense of its answer."""


UpdateCheck = UpdateAvailable | UpToDate | DevBuild | CheckFailed


def check_for_update(version: str) -> UpdateCheck:
    """Whether `version` (this build's own) is behind the latest release on GitHub."""
    if DEV_BUILD.search(version):
        return DevBuild()
    try:
        request = urllib.request.Request(
            LATEST_RELEASE_API, headers={"Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - https, fixed URL
            latest = json.loads(response.read())["tag_name"].removeprefix("v")
    except (OSError, ValueError, KeyError):
        return CheckFailed()
    if _numbers(latest) > _numbers(version):
        return UpdateAvailable(latest, RELEASE_PAGE)
    return UpToDate()


def _numbers(version: str) -> tuple[int, ...]:
    """A version's numbers, so 0.10.0 sorts after 0.9.0 (a plain string comparison wouldn't)."""
    return tuple(int(part) for part in re.findall(r"\d+", version))


def daily_check_due(last_check: str | None, today: date) -> bool:
    """Whether the pet hasn't looked for a new version today yet."""
    return last_check != today.isoformat() and DISABLE_VARIABLE not in os.environ


class BackgroundCheck(QObject):
    """A check for updates off the main thread: `finished` carries its result back to it."""

    finished = Signal(object)  # an UpdateCheck
    _done = Signal(object)

    def __init__(self, version: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._version = version
        self._done.connect(self.finished)  # queued: emitted from the pool's thread

    def start(self) -> None:
        QThreadPool.globalInstance().start(lambda: self._done.emit(check_for_update(self._version)))
