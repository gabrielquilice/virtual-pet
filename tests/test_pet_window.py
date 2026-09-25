import random

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QTextDocumentFragment

from virtual_pet import i18n
from virtual_pet.behavior import Facing
from virtual_pet.pet_window import PetWindow
from virtual_pet.pets import CAT, COCKATIEL, DOG, FISH, PARAKEET, RABBIT, SNAKE, TURTLE

LEFT = Qt.MouseButton.LeftButton
BODY = QPoint(46, 46)  # a point on the dog's body, in window coordinates


@pytest.fixture
def screen(qapp) -> QRect:
    return qapp.primaryScreen().availableGeometry()


@pytest.fixture
def make_window(qtbot):
    def make(species=DOG, **options) -> PetWindow:
        window = PetWindow("Rex", species, rng=random.Random(1), **options)
        qtbot.addWidget(window)
        return window

    return make


def test_window_floats_on_top_without_frame_taskbar_entry_or_focus(make_window):
    flags = make_window().windowFlags()

    for flag in (
        Qt.WindowType.FramelessWindowHint,
        Qt.WindowType.WindowStaysOnTopHint,
        Qt.WindowType.Tool,
        Qt.WindowType.WindowDoesNotAcceptFocus,
        Qt.WindowType.X11BypassWindowManagerHint,
    ):
        assert flags & flag == flag


def test_first_appearance_is_at_the_bottom_center_of_the_screen(make_window, screen):
    window = make_window()

    assert window.geometry().bottom() == screen.bottom()
    assert abs(window.geometry().center().x() - screen.center().x()) <= 1


def test_reappears_where_it_was_left(make_window):
    window = make_window(position=(120, 90))

    assert window.pos() == QPoint(120, 90)


def test_position_on_a_disconnected_monitor_falls_back_to_the_main_screen(make_window, screen):
    window = make_window(position=(5000, 5000))

    assert screen.contains(window.geometry())


@pytest.fixture
def shown_window(make_window, qtbot):
    window = make_window(position=(300, 300))
    window.show()
    qtbot.waitExposed(window)
    return window


def test_clicking_the_dog_makes_it_sit_and_clicking_again_makes_it_walk(shown_window, qtbot):
    with qtbot.waitSignal(shown_window.state_changed):
        qtbot.mouseClick(shown_window, LEFT, pos=BODY)
    sat_down = shown_window.sitting
    qtbot.mouseClick(shown_window, LEFT, pos=BODY)

    assert sat_down
    assert not shown_window.sitting


def test_dragged_dog_stays_where_it_is_dropped(shown_window, qtbot):
    qtbot.mousePress(shown_window, LEFT, pos=BODY)
    qtbot.mouseMove(shown_window, BODY + QPoint(-100, 50))
    with qtbot.waitSignal(shown_window.state_changed):
        qtbot.mouseRelease(shown_window, LEFT, pos=BODY)

    assert shown_window.pos() == QPoint(200, 350)
    assert not shown_window.sitting  # a drag is not a click


def test_dog_cannot_be_dragged_off_the_screen(shown_window, qtbot, screen):
    qtbot.mousePress(shown_window, LEFT, pos=BODY)
    qtbot.mouseMove(shown_window, BODY + QPoint(-2000, -2000))
    qtbot.mouseRelease(shown_window, LEFT, pos=BODY)

    assert shown_window.pos() == screen.topLeft()


def test_dog_wanders_around_by_itself(make_window):
    window = make_window(position=(300, 300))

    for _ in range(200):
        window.advance(0.05)

    assert window.pos() != QPoint(300, 300)


def test_sitting_dog_stays_put(make_window):
    window = make_window(position=(300, 300), sitting=True)

    for _ in range(200):
        window.advance(0.05)

    assert window.pos() == QPoint(300, 300)


def menu_texts(window: PetWindow) -> list[str]:
    return [action.text() for action in window.context_menu().actions() if not action.isSeparator()]


def trigger(window: PetWindow, text: str) -> None:
    menu = window.context_menu()
    next(action for action in menu.actions() if action.text() == text).trigger()


def shown_text(rich_or_plain_text: str) -> str:
    return QTextDocumentFragment.fromHtml(rich_or_plain_text).toPlainText()


def test_hovering_the_dog_shows_its_name(make_window):
    window = make_window()
    before = shown_text(window.toolTip())

    window.set_name("Luna")

    assert (before, shown_text(window.toolTip())) == ("Rex", "Luna")


@pytest.mark.parametrize("name", ["Tom & Jerry", "<Rex>"])
def test_names_are_shown_exactly_as_typed(make_window, name):
    window = make_window()

    window.set_name(name)
    title = window.context_menu().actions()[0]

    assert shown_text(window.toolTip()) == name
    assert title.iconText() == name  # the menu text without mnemonic markers


def test_menu_shows_the_name_and_what_the_dog_can_do(make_window):
    window = make_window()

    assert menu_texts(window) == ["Rex", "Sit", "Turn around", "Hide", "Settings…", "Quit"]


def test_menu_offers_a_walk_to_a_sitting_dog(make_window):
    window = make_window(sitting=True)

    assert "Walk" in menu_texts(window)


def test_menu_can_make_the_dog_sit(make_window, qtbot):
    window = make_window()

    with qtbot.waitSignal(window.state_changed):
        trigger(window, "Sit")

    assert window.sitting


def test_menu_can_turn_the_dog_around(make_window):
    window = make_window()
    before = window.grab().toImage()

    trigger(window, "Turn around")

    assert window.facing is Facing.LEFT
    assert window.grab().toImage() == before.flipped(Qt.Orientation.Horizontal)


@pytest.mark.parametrize(
    ("text", "signal_name"),
    [("Hide", "hide_requested"), ("Settings…", "settings_requested"), ("Quit", "quit_requested")],
)
def test_menu_forwards_hide_settings_and_quit_to_the_app(make_window, qtbot, text, signal_name):
    window = make_window()

    with qtbot.waitSignal(getattr(window, signal_name)):
        trigger(window, text)


def test_the_pet_can_be_swapped_for_another_one_in_the_same_spot(make_window):
    window = make_window(position=(300, 300))

    window.set_species(CAT)

    assert (window.species, window.pos()) == (CAT, QPoint(300, 300))


def test_swapped_pet_shows_up_in_its_own_colors(make_window):
    window = make_window(position=(300, 300))

    window.set_species(PARAKEET)
    image = window.grab().toImage()

    y = next(y for y, row in enumerate(PARAKEET.portrait) if "B" in row)
    x = PARAKEET.portrait[y].index("B")
    assert image.pixelColor(x * 3 + 1, y * 3 + 1).name() == "#4cae4f"  # green feathers


@pytest.mark.parametrize("flyer", [PARAKEET, COCKATIEL], ids=lambda species: species.key)
def test_menu_offers_a_flight_to_a_sitting_bird(make_window, flyer):
    window = make_window(species=flyer, sitting=True)

    assert "Fly" in menu_texts(window)


@pytest.mark.parametrize("swimmer", [TURTLE, FISH], ids=lambda species: species.key)
def test_menu_offers_a_swim_to_a_sitting_swimmer(make_window, swimmer):
    window = make_window(species=swimmer, sitting=True)

    assert "Swim" in menu_texts(window)


def test_menu_offers_to_coil_up_a_roaming_snake(make_window):
    window = make_window(species=SNAKE)

    assert menu_texts(window) == ["Rex", "Coil up", "Turn around", "Hide", "Settings…", "Quit"]


def test_menu_offers_a_slither_to_a_coiled_snake(make_window):
    window = make_window(species=SNAKE, sitting=True)

    assert "Slither" in menu_texts(window)


def test_menu_offers_a_hop_to_a_sitting_rabbit(make_window):
    window = make_window(species=RABBIT, sitting=True)

    assert "Hop" in menu_texts(window)


def test_the_menu_speaks_portuguese(make_window):
    i18n.use_language("pt_BR")

    roaming = menu_texts(make_window(species=SNAKE))
    coiled = menu_texts(make_window(species=SNAKE, sitting=True))
    sitting_rabbit = menu_texts(make_window(species=RABBIT, sitting=True))

    assert roaming == ["Rex", "Enrolar-se", "Virar", "Ocultar", "Configurações…", "Sair"]
    assert coiled[1] == "Rastejar"
    assert sitting_rabbit[1] == "Saltitar"
