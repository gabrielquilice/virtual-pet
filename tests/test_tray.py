import pytest
from PySide6.QtWidgets import QSystemTrayIcon

from virtual_pet import i18n
from virtual_pet.icon import app_icon
from virtual_pet.tray import PetTray

Reason = QSystemTrayIcon.ActivationReason


@pytest.fixture
def tray(qapp):  # noqa: ARG001 - a tray icon needs the app
    tray = PetTray()
    yield tray
    tray.hide()


def menu_texts(tray: PetTray) -> list[str]:
    """The menu's items as shown, without the "&" that marks shortcuts."""
    return [
        action.iconText() for action in tray.contextMenu().actions() if not action.isSeparator()
    ]


def trigger(tray: PetTray, text: str) -> None:
    next(action for action in tray.contextMenu().actions() if action.iconText() == text).trigger()


def test_the_tray_icon_is_the_apps_paw_print(tray):
    assert tray.icon().pixmap(32).toImage() == app_icon().pixmap(32).toImage()


def test_the_icon_shows_up_only_when_asked_to(tray):
    before = tray.isVisible()

    tray.show_for("Rex")

    assert (before, tray.isVisible()) == (False, True)


def test_the_icon_says_whose_it_is_and_what_a_click_does(tray):
    tray.show_for("Rex")

    assert tray.toolTip() == "Click to show Rex"
    assert menu_texts(tray) == ["Show Rex", "Quit"]


@pytest.mark.parametrize("name", ["Tom & Jerry", "<Rex>", "100%1"])
def test_names_are_shown_exactly_as_typed_in_the_tray(tray, name):
    tray.show_for(name)

    assert tray.toolTip() == f"Click to show {name}"
    assert menu_texts(tray)[0] == f"Show {name}"


@pytest.mark.parametrize("reason", [Reason.Trigger, Reason.DoubleClick])
def test_clicking_the_icon_asks_for_the_pet(tray, qtbot, reason):
    tray.show_for("Rex")

    with qtbot.waitSignal(tray.show_requested):
        tray.activated.emit(reason)


def test_opening_the_icons_menu_does_not_bring_the_pet_back(tray, qtbot):
    tray.show_for("Rex")

    with qtbot.assertNotEmitted(tray.show_requested):
        tray.activated.emit(Reason.Context)


@pytest.mark.parametrize(
    ("text", "signal_name"), [("Show Rex", "show_requested"), ("Quit", "quit_requested")]
)
def test_the_icons_menu_can_show_the_pet_or_quit(tray, qtbot, text, signal_name):
    tray.show_for("Rex")

    with qtbot.waitSignal(getattr(tray, signal_name)):
        trigger(tray, text)


def test_the_icon_speaks_portuguese(tray):
    i18n.use_language("pt_BR")

    tray.show_for("Rex")

    assert tray.toolTip() == "Clique para mostrar Rex"
    assert menu_texts(tray) == ["Mostrar Rex", "Sair"]
