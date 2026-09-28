"""Starting the pet when the user logs in: an XDG autostart entry on Linux, a Run value on Windows.

The entry itself is the setting, not the pet's config: turned off in the desktop's own
settings (Plasma's or GNOME's autostart list, Windows' Startup apps), it shows as off in the
pet's Settings too.

The pet isn't installed anywhere fixed (an AppImage or a zip can be moved), so each start of a
pet that starts with the system writes the entry again with where the pet is now.
"""

import logging
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QStandardPaths

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# Where Windows' Startup apps (Task Manager, Settings) turn a Run value off without removing it.
APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
DESKTOP_EXEC_RESERVED = frozenset(" \t\n\"'\\><~|&;$*?#()`")  # the Desktop Entry spec's list

logger = logging.getLogger(__name__)


class Autostart(Protocol):
    """Whether the pet starts when the user logs in; enabling and disabling raise OSError."""

    def is_enabled(self) -> bool: ...

    def enable(self) -> None:
        """Start this pet, where it is now, when the user logs in."""
        ...

    def disable(self) -> None: ...


def launch_command(
    environ: Mapping[str, str] = os.environ, *, frozen: bool | None = None
) -> list[str]:
    """The command that starts this pet: the AppImage, the bundled exe, or Python and the module."""
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if frozen:
        # In an AppImage the executable lives in a mount that is gone once the pet quits.
        return [environ.get("APPIMAGE") or sys.executable]
    return [sys.executable, "-m", "virtual_pet"]


def desktop_exec(command: Sequence[str]) -> str:
    """A desktop entry's Exec value: arguments quoted as the Desktop Entry spec says."""
    arguments = []
    for argument in command:
        text = argument.replace("%", "%%")  # % starts a field code
        if not text or DESKTOP_EXEC_RESERVED & set(text):
            for character in '\\"`$':
                text = text.replace(character, "\\" + character)
            text = f'"{text}"'
        arguments.append(text)
    # Then the string escape every value gets: a backslash is written as two.
    return " ".join(arguments).replace("\\", "\\\\")


class DesktopEntry:
    """An XDG autostart entry: ~/.config/autostart/<name>.desktop, which desktops run at login."""

    def __init__(self, path: Path, command: Sequence[str]) -> None:
        self.path = path
        self._command = list(command)

    def is_enabled(self) -> bool:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return False
        values = {}
        group = ""
        for line in map(str.strip, lines):
            if line.startswith("["):
                group = line
            elif group == "[Desktop Entry]" and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
        # Hidden is how an entry is turned off; GNOME had its own key for that too.
        return values.get("Hidden") != "true" and values.get("X-GNOME-Autostart-enabled") != "false"

    def enable(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Virtual Pet\n"
            "Name[pt_BR]=Pet Virtual\n"
            "Comment=A little pixel-art pet that lives on your desktop\n"
            "Comment[pt_BR]=Um pequeno pet em pixel art que mora na sua área de trabalho\n"
            f"Exec={desktop_exec(self._command)}\n"
            "Icon=virtual-pet\n"
            "Terminal=false\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def disable(self) -> None:
        self.path.unlink(missing_ok=True)


class Registry(Protocol):
    """The values of keys under HKEY_CURRENT_USER."""

    def get(self, key: str, name: str) -> object | None: ...

    def set_string(self, key: str, name: str, value: str) -> None: ...

    def delete(self, key: str, name: str) -> None:
        """Remove a value; one that isn't there is left alone."""
        ...


class RunValue:
    """A value in the current user's Run key, which Windows starts at login."""

    def __init__(self, name: str, command: Sequence[str], registry: Registry) -> None:
        self._name = name
        self._command = list(command)
        self._registry = registry

    def is_enabled(self) -> bool:
        if self._registry.get(RUN_KEY, self._name) is None:
            return False
        approval = self._registry.get(APPROVED_KEY, self._name)
        # Its first byte is even while the entry is on (2) and odd once turned off (3).
        return not (isinstance(approval, bytes) and approval[:1] and approval[0] % 2)

    def enable(self) -> None:
        # Turned on here, it must start even if Startup apps had turned it off: that goes too.
        self._registry.delete(APPROVED_KEY, self._name)
        self._registry.set_string(RUN_KEY, self._name, subprocess.list2cmdline(self._command))

    def disable(self) -> None:
        self._registry.delete(APPROVED_KEY, self._name)
        self._registry.delete(RUN_KEY, self._name)


if sys.platform == "win32":
    import winreg

    class WindowsRegistry:
        """The current user's registry, through winreg."""

        def get(self, key: str, name: str) -> object | None:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                    return winreg.QueryValueEx(handle, name)[0]
            except FileNotFoundError:
                return None

        def set_string(self, key: str, name: str, value: str) -> None:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as handle:
                winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, value)

        def delete(self, key: str, name: str) -> None:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE
                ) as handle:
                    winreg.DeleteValue(handle, name)
            except FileNotFoundError:
                pass


def system_autostart(name: str) -> Autostart:
    """How this system starts the pet at login, for the pet as it runs now."""
    if sys.platform == "win32":
        return RunValue(name, launch_command(), WindowsRegistry())
    location = QStandardPaths.StandardLocation.GenericConfigLocation
    folder = Path(QStandardPaths.writableLocation(location)) / "autostart"
    return DesktopEntry(folder / f"{name}.desktop", launch_command())


def refresh(autostart: Autostart) -> None:
    """Point an entry that is on at the pet as it runs now: it may have been moved."""
    try:
        if autostart.is_enabled():
            autostart.enable()
    except OSError as error:
        logger.warning("Could not update starting with the system: %s", error)
