import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QTextDocumentFragment
from PySide6.QtWidgets import QComboBox, QLineEdit, QToolButton

from virtual_pet.app import (
    PetController,
    config_path,
    ensure_pet,
    keep_gtk_off_opengl,
    prefer_xwayland,
)
from virtual_pet.config import Config, ConfigStore
from virtual_pet.pets import DOG, PARAKEET

LEFT = Qt.MouseButton.LeftButton
BODY = QPoint(46, 46)


def shown_name(controller: PetController) -> str:
    return QTextDocumentFragment.fromHtml(controller.window.toolTip()).toPlainText()


@pytest.fixture
def answer_dialog(qapp):
    """Schedule an answer for the next modal dialog.

    Picks `pet` (by its label) and `language` (by its code) if given, types `name` and
    confirms; cancels if `name` is None.
    """
    timers = []

    def answer(name: str | None, pet: str | None, language: str | None) -> None:
        dialog = qapp.activeModalWidget()
        if dialog is None:
            return
        if name is None:
            dialog.reject()
            return
        if pet is not None:
            next(
                button for button in dialog.findChildren(QToolButton) if button.text() == pet
            ).click()
        if language is not None:
            field = dialog.findChild(QComboBox)
            field.setCurrentIndex(field.findData(language))
        dialog.findChild(QLineEdit).setText(name)
        dialog.accept()

    def schedule(name: str | None, pet: str | None = None, language: str | None = None) -> None:
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: answer(name, pet, language))
        timer.start(0)
        timers.append(timer)

    yield schedule
    for timer in timers:
        timer.stop()


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}, "xcb"),
        ({"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0", "QT_QPA_PLATFORM": "wayland"}, "xcb"),
        (
            {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0", "QT_QPA_PLATFORM": "offscreen"},
            "offscreen",
        ),
        ({"DISPLAY": ":0"}, None),  # plain X11 session
        ({"WAYLAND_DISPLAY": "wayland-0"}, None),  # XWayland is not available
    ],
)
def test_wayland_sessions_run_the_pet_through_xwayland(environ, expected):
    prefer_xwayland(environ, platform="linux")

    assert environ.get("QT_QPA_PLATFORM") == expected


def test_other_systems_are_left_alone():
    environ = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}

    prefer_xwayland(environ, platform="win32")

    assert "QT_QPA_PLATFORM" not in environ


def test_gtk_is_kept_off_opengl():
    environ = {}

    keep_gtk_off_opengl(environ)

    assert environ["GDK_GL"] == "disable"


def test_a_gtk_opengl_choice_made_by_the_user_is_respected():
    environ = {"GDK_GL": "always"}

    keep_gtk_off_opengl(environ)

    assert environ["GDK_GL"] == "always"


def test_settings_live_in_the_user_config_folder():
    assert config_path().parts[-2:] == ("virtual-pet", "config.json")


def test_first_run_asks_for_the_name_and_remembers_it(tmp_path, answer_dialog):
    store = ConfigStore(tmp_path / "config.json")

    answer_dialog("  Rex ")
    config = ensure_pet(store, store.load())

    assert config == Config(pet_name="Rex", species="dog")
    assert store.load() == Config(pet_name="Rex", species="dog")


def test_first_run_can_adopt_a_cat(tmp_path, answer_dialog):
    store = ConfigStore(tmp_path / "config.json")

    answer_dialog("Mimi", pet="Cat")
    config = ensure_pet(store, store.load())

    assert config == Config(pet_name="Mimi", species="cat")
    assert store.load() == Config(pet_name="Mimi", species="cat")


def test_closing_the_first_run_dialog_quits_without_saving(tmp_path, answer_dialog):
    store = ConfigStore(tmp_path / "config.json")

    answer_dialog(None)

    assert ensure_pet(store, store.load()) is None
    assert not store.path.exists()


def test_later_runs_do_not_ask_for_the_name_again(tmp_path, answer_dialog):
    store = ConfigStore(tmp_path / "config.json")
    store.save(Config(pet_name="Rex", sitting=True))

    answer_dialog(None)  # would cancel a dialog, if one were (wrongly) shown

    assert ensure_pet(store, store.load()) == Config(pet_name="Rex", sitting=True)


@pytest.fixture
def store(tmp_path) -> ConfigStore:
    return ConfigStore(tmp_path / "config.json")


@pytest.fixture
def controller(store, qtbot) -> PetController:
    controller = PetController(store, Config(pet_name="Rex", position=(300, 300)))
    qtbot.addWidget(controller.window)
    return controller


def test_where_the_dog_is_and_whether_it_sits_are_remembered(controller, store, qtbot):
    controller.window.show()
    qtbot.waitExposed(controller.window)

    qtbot.mouseClick(controller.window, LEFT, pos=BODY)

    assert store.load() == Config(pet_name="Rex", position=(300, 300), sitting=True)


def test_renaming_in_settings_updates_the_dog_and_is_remembered(controller, store, answer_dialog):
    answer_dialog("Luna")
    controller.window.settings_requested.emit()

    assert shown_name(controller) == "Luna"
    assert store.load().pet_name == "Luna"


def test_swapping_the_pet_replaces_it_and_is_remembered(controller, store, answer_dialog):
    window = controller.window

    answer_dialog("Rex", pet="Maritaca")
    window.settings_requested.emit()

    assert (controller.window, window.species) == (window, PARAKEET)  # still one pet, now a bird
    assert store.load().species == "parakeet"


def test_an_unknown_saved_pet_shows_up_as_the_dog(store, qtbot):
    controller = PetController(store, Config(pet_name="Rex", species="dragon"))
    qtbot.addWidget(controller.window)

    assert controller.window.species is DOG


def test_choosing_a_language_in_settings_translates_the_menu_and_is_remembered(
    controller, store, answer_dialog
):
    answer_dialog("Rex", language="pt_BR")
    controller.window.settings_requested.emit()

    menu = [action.text() for action in controller.window.context_menu().actions()]
    assert [text for text in menu if text] == ["Rex", "Sentar", "Configurações…", "Sair"]
    assert store.load().language == "pt_BR"


def test_cancelling_the_settings_keeps_the_name(controller, answer_dialog):
    answer_dialog(None)
    controller.window.settings_requested.emit()

    assert shown_name(controller) == "Rex"


def test_unwritable_settings_do_not_crash_the_pet(tmp_path, qtbot, caplog):
    not_a_folder = tmp_path / "file"
    not_a_folder.write_text("")
    controller = PetController(ConfigStore(not_a_folder / "config.json"), Config(pet_name="Rex"))
    qtbot.addWidget(controller.window)

    controller.save()

    assert "Could not save" in caplog.text


@pytest.fixture
def pet_environment(tmp_path) -> dict[str, str]:
    """Environment for running the real app offscreen, with an already named, sitting dog."""
    config_home = tmp_path / "config"
    (config_home / "virtual-pet").mkdir(parents=True)
    (config_home / "virtual-pet" / "config.json").write_text(
        json.dumps(
            {"pet_name": "Rex", "species": "cat", "position": {"x": 100, "y": 200}, "sitting": True}
        ),
        encoding="utf-8",
    )
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    return {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "XDG_CONFIG_HOME": str(config_home),
        "XDG_RUNTIME_DIR": str(runtime),
    }


@pytest.fixture
def pet_command() -> list[str]:
    """The app from these sources, or the built app named by VIRTUAL_PET_EXECUTABLE."""
    executable = os.environ.get("VIRTUAL_PET_EXECUTABLE")
    return [executable] if executable else [sys.executable, "-m", "virtual_pet"]


@pytest.fixture
def start_pet(pet_environment, pet_command):
    """Start the real app and wait until it holds its single-instance lock."""
    started: list[subprocess.Popen[bytes]] = []

    def start(**options) -> subprocess.Popen[bytes]:
        pet = subprocess.Popen(pet_command, env=pet_environment, **options)
        started.append(pet)
        lock = Path(pet_environment["XDG_RUNTIME_DIR"], "virtual-pet.lock")
        deadline = time.monotonic() + 15
        while not lock.exists() and pet.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        return pet

    yield start
    for pet in started:
        if pet.poll() is None:
            pet.kill()
            pet.wait()


@pytest.mark.process
def test_pet_quits_gracefully_and_remembers_its_state(pet_environment, start_pet):
    pet = start_pet()

    pet.send_signal(signal.SIGTERM)

    assert pet.wait(timeout=10) == 0
    saved = Path(pet_environment["XDG_CONFIG_HOME"], "virtual-pet", "config.json")
    assert json.loads(saved.read_text(encoding="utf-8")) == {
        "pet_name": "Rex",
        "species": "cat",
        "position": {"x": 100, "y": 200},
        "sitting": True,
        "language": None,
    }


@pytest.mark.process
def test_the_translations_are_found(pet_environment, start_pet):
    config = Path(pet_environment["XDG_CONFIG_HOME"], "virtual-pet", "config.json")
    config.write_text(json.dumps({"pet_name": "Rex", "language": "pt_BR"}), encoding="utf-8")
    pet = start_pet(stderr=subprocess.PIPE)

    pet.send_signal(signal.SIGTERM)
    _, errors = pet.communicate(timeout=10)

    assert pet.returncode == 0
    assert b"Could not load" not in errors


@pytest.mark.process
def test_only_one_pet_runs_at_a_time(pet_environment, pet_command, start_pet):
    first = start_pet()
    try:
        second = subprocess.run(pet_command, env=pet_environment, timeout=10, check=False)
        first_still_running = first.poll() is None
    finally:
        first.terminate()
        first_exit_code = first.wait(timeout=10)

    assert second.returncode == 1
    assert first_still_running
    assert first_exit_code == 0


@pytest.mark.process
def test_ctrl_c_during_the_first_run_dialog_quits(pet_environment, start_pet):
    Path(pet_environment["XDG_CONFIG_HOME"], "virtual-pet", "config.json").unlink()
    pet = start_pet()  # shows the naming dialog, as nobody has named the dog yet

    pet.send_signal(signal.SIGINT)

    assert pet.wait(timeout=10) == 0
    assert not Path(pet_environment["XDG_CONFIG_HOME"], "virtual-pet", "config.json").exists()
