"""One pet at a time: the lock the running app holds, and how a later start reaches it.

A second start of the app can't get the lock, so it asks the running pet to show itself
(bringing back a pet that hid) through a Unix socket next to the lock, then ends. That is
how a hidden pet comes back on desktops without a system tray: by opening the app again.
"""

import logging
import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QDir, QLockFile, QObject, QSocketNotifier, QStandardPaths, Signal

ASKING_TIMEOUT = 2  # seconds; the running pet's socket takes a connection at once, or never
LONGEST_ADDRESS = 107  # bytes in a Unix socket's address on Linux, less the final NUL

logger = logging.getLogger(__name__)


def runtime_folder() -> Path:
    """Where the lock and the socket go: the user's private runtime folder, else the temp one."""
    folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
    return Path(folder or QDir.tempPath())


def acquire_lock(path: Path) -> QLockFile | None:
    """The lock held while the pet runs; None if another start of the app holds it."""
    lock = QLockFile(str(path))
    lock.setStaleLockTime(0)  # held for the whole run: only a dead owner makes it stale
    return lock if lock.tryLock(0) else None


class ShowRequests(QObject):
    """A Unix socket where later starts of the app ask the running pet to show itself.

    Connecting is the request: nothing is read. Only the lock's holder should listen.
    """

    received = Signal()

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        path.unlink(missing_ok=True)  # left by a pet that crashed: the lock says it's gone
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            with _address(path) as address:
                self._server.bind(address)
            path.chmod(0o600)  # only the user's own starts may ask, even in the temp folder
            self._server.listen()
        except OSError:
            self._server.close()
            raise
        self._server.setblocking(False)  # noqa: FBT003 - the standard library's signature
        self._notifier = QSocketNotifier(self._server.fileno(), QSocketNotifier.Type.Read, self)
        self._notifier.activated.connect(self._accept)

    def close(self) -> None:
        """Stop listening and remove the socket."""
        if self._server.fileno() == -1:  # closed already
            return
        self._notifier.setEnabled(False)
        self._server.close()
        self._path.unlink(missing_ok=True)

    def _accept(self) -> None:
        try:
            connection, _ = self._server.accept()
        except OSError:  # taken by an earlier wakeup, or failed: never the pet's problem
            return
        connection.close()
        self.received.emit()


def listen_for_show_requests(path: Path) -> ShowRequests | None:
    """Listen at `path` for later starts of the app; None, reported, if that can't be done."""
    try:
        return ShowRequests(path)
    except OSError as error:
        logger.warning("Opening the app again won't show the pet: %s", error)
        return None


def ask_to_show(path: Path) -> bool:
    """Ask the pet listening at `path` to show itself; False if no pet answers."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(ASKING_TIMEOUT)
        try:
            with _address(path) as address:
                client.connect(address)
        except OSError:
            return False
    return True


@contextmanager
def _address(path: Path) -> Iterator[str]:
    """An address for the socket at `path`, even a path too long to be one.

    A deep runtime folder can make the path longer than a socket's address may be, so
    then its folder is opened and reached through /proc/self/fd, which Linux always has.
    """
    if len(os.fsencode(path)) <= LONGEST_ADDRESS:
        yield str(path)
        return
    folder = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        yield f"/proc/self/fd/{folder}/{path.name}"
    finally:
        os.close(folder)
