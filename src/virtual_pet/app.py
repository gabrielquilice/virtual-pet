"""Entry point: prepares Qt, lets the user adopt a pet on first run and sets it loose."""

import logging
import os
import signal
import sys
from collections.abc import MutableMapping
from pathlib import Path

from PySide6.QtCore import QDir, QLockFile, QStandardPaths, QTimer
from PySide6.QtWidgets import QApplication

from virtual_pet.config import Config, ConfigStore
from virtual_pet.dialogs import PetChoice, ask_for_changes, ask_for_new_pet
from virtual_pet.icon import app_icon
from virtual_pet.pet_window import PetWindow
from virtual_pet.pets import species_by_key

APP_NAME = "virtual-pet"
APP_DISPLAY_NAME = "Virtual Pet"

logger = logging.getLogger(__name__)


class PetController:
    """Keeps the pet's window, the settings dialog and the saved config in sync."""

    def __init__(self, store: ConfigStore, config: Config) -> None:
        self._store = store
        self._config = config
        self.window = PetWindow(
            config.pet_name or "",
            species_by_key(config.species),
            position=config.position,
            sitting=config.sitting,
        )
        self.window.state_changed.connect(self.save)
        self.window.settings_requested.connect(self.open_settings)
        self.window.quit_requested.connect(QApplication.quit)

    def save(self) -> None:
        """Remember which pet it is, its name, where it is and whether it sits."""
        position = self.window.pos()
        self._config.species = self.window.species.key
        self._config.position = (position.x(), position.y())
        self._config.sitting = self.window.sitting
        save_config(self._store, self._config)

    def open_settings(self) -> None:
        """Let the user rename the pet or swap it for another one (there is only ever one)."""
        current = PetChoice(self.window.species, self._config.pet_name or "")
        choice = ask_for_changes(current)
        if choice is None or choice == current:
            return
        self._config.pet_name = choice.name
        self.window.set_name(choice.name)
        self.window.set_species(choice.species)
        self.save()


def save_config(store: ConfigStore, config: Config) -> None:
    """Save the config; failing to do so is reported but never stops the pet."""
    try:
        store.save(config)
    except OSError as error:
        logger.warning("Could not save settings to %s: %s", store.path, error)


def ensure_pet(store: ConfigStore) -> Config | None:
    """Load the config, asking which pet to adopt, and its name, on the first run.

    Returns None when the user closes the adoption dialog without choosing.
    """
    config = store.load()
    if config.pet_name is None:
        choice = ask_for_new_pet()
        if choice is None:
            return None
        config.pet_name, config.species = choice.name, choice.species.key
        save_config(store, config)
    return config


def config_path() -> Path:
    """Where the settings live: ~/.config/virtual-pet/config.json on Linux."""
    folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericConfigLocation)
    return Path(folder) / APP_NAME / "config.json"


def prefer_xwayland(environ: MutableMapping[str, str], platform: str = sys.platform) -> None:
    """On Linux Wayland sessions, make Qt run the pet through XWayland.

    Wayland does not let applications place their own windows or keep them above
    the others, and a desktop pet needs both; X11 (XWayland) allows them.
    A platform explicitly chosen by the user (other than Wayland) is respected.
    """
    if not platform.startswith("linux") or "WAYLAND_DISPLAY" not in environ:
        return
    if "DISPLAY" in environ and environ.get("QT_QPA_PLATFORM", "wayland").startswith("wayland"):
        environ["QT_QPA_PLATFORM"] = "xcb"


def keep_gtk_off_opengl(environ: MutableMapping[str, str]) -> None:
    """Stop GTK from starting OpenGL, which the pet never uses.

    On GNOME-like desktops Qt styles the dialogs through GTK, and GTK starts OpenGL on
    its own, loading the system's GPU driver: about 50 MB more memory for a pet that
    draws without OpenGL. A GDK_GL value set by the user is respected.
    """
    environ.setdefault("GDK_GL", "disable")


def acquire_single_instance_lock() -> QLockFile | None:
    """Lock held while the pet runs; None if another pet is already running."""
    folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
    lock = QLockFile(str(Path(folder or QDir.tempPath()) / f"{APP_NAME}.lock"))
    lock.setStaleLockTime(0)  # held for the whole run: only a dead owner makes it stale
    return lock if lock.tryLock(0) else None


def quit_on_termination_signals(app: QApplication) -> None:
    """Close gracefully (saving the pet's state) on Ctrl+C or a termination request."""

    def request_quit(*_: object) -> None:
        # exit() also ends a dialog's event loop (quit() only works inside app.exec()), and the
        # zero timer makes a signal that arrives before any event loop runs count once one does.
        QTimer.singleShot(0, lambda: QApplication.exit(0))

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, request_quit)
    # Python runs signal handlers only when it gets control back from Qt, so wake it regularly.
    heartbeat = QTimer(app)
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start(250)


def main() -> int:
    """Run the virtual pet until the user quits it."""
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    prefer_xwayland(os.environ)
    keep_gtk_off_opengl(os.environ)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)  # closing a dialog must not end the app
    quit_on_termination_signals(app)
    if app.platformName().startswith("wayland"):
        logger.warning("Running on native Wayland: without XWayland the pet can't move around.")

    lock = acquire_single_instance_lock()
    if lock is None:
        logger.warning("%s is already running.", APP_DISPLAY_NAME)
        return 1

    store = ConfigStore(config_path())
    config = ensure_pet(store)
    if config is None:
        return 0
    controller = PetController(store, config)
    app.aboutToQuit.connect(controller.save)
    controller.window.show()
    return app.exec()
