"""One pet at a time: the lock the running app holds, and how a later start reaches it.

A second start of the app can't get the lock, so it asks the running pet to show itself
(bringing back a pet that hid) through a socket next to the lock, then ends. That is how a
hidden pet comes back on desktops without a system tray: by opening the app again.

The socket is a Unix socket. Python has none on Windows, so there it is a named pipe
(Qt's local socket) named after the socket's path.
"""

import hashlib
import logging
import os
import socket
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QDir, QLockFile, QObject, QSocketNotifier, QStandardPaths, Signal

ASKING_TIMEOUT = 2  # seconds; the running pet's socket takes a connection at once, or never
LONGEST_ADDRESS = 107  # bytes in a Unix socket's address on Linux, less the final NUL
WINDOWS = sys.platform == "win32"

logger = logging.getLogger(__name__)


def runtime_folder() -> Path:
    """Where the lock and the socket go: the user's private runtime folder, else the temp one.

    Windows has no such runtime folder (Qt gives the user's home), so there it is the temp
    folder, which is the user's own too.
    """
    location = QStandardPaths.StandardLocation.RuntimeLocation
    folder = "" if WINDOWS else QStandardPaths.writableLocation(location)
    return Path(folder or QDir.tempPath())


def acquire_lock(path: Path) -> QLockFile | None:
    """The lock held while the pet runs; None if another start of the app holds it."""
    lock = QLockFile(str(path))
    lock.setStaleLockTime(0)  # held for the whole run: only a dead owner makes it stale
    return lock if lock.tryLock(0) else None


class ShowRequests(QObject):
    """Where later starts of the app ask the running pet to show itself.

    Connecting is the request: nothing is read. Only the lock's holder should listen.
    """

    received = Signal()


class SocketShowRequests(ShowRequests):
    """The requests' Unix socket, at the socket's path."""

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


class PipeShowRequests(ShowRequests):
    """The requests' named pipe, on Windows; only the user's own starts can connect to it."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        from PySide6.QtNetwork import QLocalServer  # noqa: PLC0415 - not in the Linux AppImage

        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._accept)
        if not self._server.listen(pipe_name(path)):
            raise OSError(self._server.errorString())

    def close(self) -> None:
        """Stop listening."""
        self._server.close()

    def _accept(self) -> None:
        while connection := self._server.nextPendingConnection():
            connection.abort()
            connection.deleteLater()
            self.received.emit()


def pipe_name(path: Path) -> str:
    """The name of the named pipe standing for the socket at `path`, which a path can't be."""
    return f"{path.name}-{hashlib.sha256(os.fsencode(path)).hexdigest()[:16]}"


def listen_for_show_requests(path: Path) -> SocketShowRequests | PipeShowRequests | None:
    """Listen at `path` for later starts of the app; None, reported, if that can't be done."""
    try:
        return PipeShowRequests(path) if WINDOWS else SocketShowRequests(path)
    except OSError as error:
        logger.warning("Opening the app again won't show the pet: %s", error)
        return None


def ask_to_show(path: Path) -> bool:
    """Ask the pet listening at `path` to show itself; False if no pet answers."""
    if WINDOWS:
        from PySide6.QtNetwork import QLocalSocket  # noqa: PLC0415 - not in the Linux AppImage

        client = QLocalSocket()
        client.connectToServer(pipe_name(path))
        answered = client.waitForConnected(ASKING_TIMEOUT * 1000)
        client.abort()
        return answered
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
