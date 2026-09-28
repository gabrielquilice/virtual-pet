import logging
import sys

import pytest

from virtual_pet.autostart import (
    APPROVED_KEY,
    RUN_KEY,
    DesktopEntry,
    RunValue,
    desktop_exec,
    launch_command,
    refresh,
    system_autostart,
)

COMMAND = ["/home/ana/Apps/VirtualPet.AppImage"]


@pytest.fixture
def entry(tmp_path) -> DesktopEntry:
    return DesktopEntry(tmp_path / "autostart" / "virtual-pet.desktop", COMMAND)


def entry_values(entry: DesktopEntry) -> dict[str, str]:
    lines = entry.path.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line)


def test_a_new_pet_does_not_start_with_the_system(entry):
    assert not entry.is_enabled()


def test_starting_with_the_system_writes_an_autostart_entry(entry):
    entry.enable()

    values = entry_values(entry)
    assert entry.path.read_text(encoding="utf-8").startswith("[Desktop Entry]\n")
    assert (values["Type"], values["Exec"], values["Name[pt_BR]"]) == (
        "Application",
        "/home/ana/Apps/VirtualPet.AppImage",
        "Pet Virtual",
    )
    assert entry.is_enabled()


def test_turning_it_off_removes_the_entry(entry):
    entry.enable()

    entry.disable()
    entry.disable()  # already off: nothing to do

    assert not entry.path.exists()
    assert not entry.is_enabled()


@pytest.mark.parametrize("line", ["Hidden=true", "X-GNOME-Autostart-enabled=false"])
def test_an_entry_the_desktop_turned_off_shows_as_off(entry, line):
    entry.enable()
    entry.path.write_text(entry.path.read_text(encoding="utf-8") + line + "\n", encoding="utf-8")

    assert not entry.is_enabled()


def test_only_the_desktop_entry_group_counts(entry):
    entry.path.parent.mkdir()
    entry.path.write_text(
        "[Desktop Entry]\nExec=pet\n[Desktop Action off]\nHidden=true\n", encoding="utf-8"
    )

    assert entry.is_enabled()


def test_an_unreadable_entry_shows_as_off(entry):
    entry.path.parent.mkdir()
    entry.path.write_bytes(b"\xff\xfe")

    assert not entry.is_enabled()


def test_turning_it_on_again_points_at_the_pet_as_it_is_now(tmp_path):
    path = tmp_path / "virtual-pet.desktop"
    DesktopEntry(path, ["/old/VirtualPet.AppImage"]).enable()

    refresh(DesktopEntry(path, ["/new/VirtualPet.AppImage"]))

    assert entry_values(DesktopEntry(path, []))["Exec"] == "/new/VirtualPet.AppImage"


def test_refreshing_leaves_a_pet_that_does_not_start_with_the_system_alone(entry):
    refresh(entry)

    assert not entry.path.exists()


def test_a_failed_refresh_is_reported(tmp_path, caplog):
    not_a_folder = tmp_path / "file"
    not_a_folder.write_text("")
    entry = DesktopEntry(not_a_folder / "virtual-pet.desktop", COMMAND)
    entry.is_enabled = lambda: True  # ty: ignore[invalid-assignment]

    with caplog.at_level(logging.WARNING):
        refresh(entry)

    assert "Could not update starting with the system" in caplog.text


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (["/usr/bin/python3", "-m", "virtual_pet"], "/usr/bin/python3 -m virtual_pet"),
        (["/home/ana/My Apps/pet"], '"/home/ana/My Apps/pet"'),
        (["/home/ana/100%/pet"], "/home/ana/100%%/pet"),
        (['/a "b" $c`d'], r'"/a \\"b\\" \\$c\\`d"'),
        (["/a\\b"], r'"/a\\\\b"'),
        ([""], '""'),
    ],
)
def test_the_command_is_quoted_as_desktop_entries_want(command, expected):
    assert desktop_exec(command) == expected


def test_from_the_sources_the_pet_is_started_by_python():
    assert launch_command({}, frozen=False) == [sys.executable, "-m", "virtual_pet"]


def test_an_appimage_is_started_from_where_it_is():
    command = launch_command({"APPIMAGE": "/home/ana/Pet.AppImage"}, frozen=True)

    assert command == ["/home/ana/Pet.AppImage"]


def test_a_bundled_pet_is_started_by_its_executable():
    assert launch_command({}, frozen=True) == [sys.executable]


class FakeRegistry:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], object] = {}

    def get(self, key: str, name: str) -> object | None:
        return self.values.get((key, name))

    def set_string(self, key: str, name: str, value: str) -> None:
        self.values[key, name] = value

    def delete(self, key: str, name: str) -> None:
        self.values.pop((key, name), None)


@pytest.fixture
def registry() -> FakeRegistry:
    return FakeRegistry()


@pytest.fixture
def run_value(registry) -> RunValue:
    return RunValue("virtual-pet", [r"C:\Users\Ana\My Apps\VirtualPet.exe"], registry)


def test_on_windows_starting_with_the_system_is_a_run_value(run_value, registry):
    off = run_value.is_enabled()

    run_value.enable()

    assert not off
    assert registry.values == {(RUN_KEY, "virtual-pet"): r'"C:\Users\Ana\My Apps\VirtualPet.exe"'}
    assert run_value.is_enabled()


def test_on_windows_turning_it_off_removes_the_run_value(run_value, registry):
    run_value.enable()

    run_value.disable()

    assert registry.values == {}
    assert not run_value.is_enabled()


@pytest.mark.parametrize(
    ("approval", "enabled"),
    [(b"\x02" + bytes(11), True), (b"\x03" + bytes(11), False), (b"", True)],
)
def test_startup_apps_can_turn_the_run_value_off(run_value, registry, approval, enabled):
    run_value.enable()
    registry.values[APPROVED_KEY, "virtual-pet"] = approval

    assert run_value.is_enabled() is enabled


def test_turning_it_on_here_undoes_turning_it_off_in_startup_apps(run_value, registry):
    run_value.enable()
    registry.values[APPROVED_KEY, "virtual-pet"] = b"\x03" + bytes(11)

    run_value.enable()

    assert (APPROVED_KEY, "virtual-pet") not in registry.values
    assert run_value.is_enabled()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows starts it from the registry")
def test_on_linux_the_entry_goes_in_the_autostart_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    entry = system_autostart("virtual-pet")

    assert isinstance(entry, DesktopEntry)
    assert entry.path == tmp_path / "autostart" / "virtual-pet.desktop"


@pytest.mark.skipif(sys.platform != "win32", reason="the real registry is Windows' (or Wine's)")
def test_on_windows_the_run_value_is_in_the_registry():
    entry = system_autostart("virtual-pet-test")
    assert isinstance(entry, RunValue)
    try:
        entry.enable()
        assert entry.is_enabled()
    finally:
        entry.disable()
    assert not entry.is_enabled()
