import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QLabel, QLineEdit, QToolButton

from virtual_pet.dialogs import PetChoice, PetDialog
from virtual_pet.pets import CAT, PARAKEET

LEFT = Qt.MouseButton.LeftButton


@pytest.fixture
def dialog(qtbot):
    dialog = PetDialog(title="Welcome!", message="Choose your pet", confirm_text="Adopt")
    qtbot.addWidget(dialog)
    return dialog


def name_field(dialog: PetDialog) -> QLineEdit:
    return dialog.findChild(QLineEdit)


def confirm_button(dialog: PetDialog):
    return dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)


def pet_buttons(dialog: PetDialog) -> list[QToolButton]:
    return dialog.findChildren(QToolButton)


def pet_button(dialog: PetDialog, label: str) -> QToolButton:
    return next(button for button in pet_buttons(dialog) if button.text() == label)


def test_every_pet_is_offered_with_the_dog_preselected(dialog):
    offered = [(button.text(), button.isChecked()) for button in pet_buttons(dialog)]

    assert offered == [
        ("Dog", True),
        ("Cat", False),
        ("Maritaca", False),
        ("Sea Turtle", False),
        ("Fish", False),
        ("Guinea Pig", False),
        ("Penguin", False),
        ("Snake", False),
    ]


def test_pets_are_offered_in_rows_of_three(dialog):
    dialog.show()
    rows = {}
    for button in sorted(pet_buttons(dialog), key=lambda button: (button.y(), button.x())):
        rows.setdefault(button.y(), []).append(button.text())

    assert list(rows.values()) == [
        ["Dog", "Cat", "Maritaca"],
        ["Sea Turtle", "Fish", "Guinea Pig"],
        ["Penguin", "Snake"],
    ]


def test_every_pet_name_fits_on_its_button(dialog):
    dialog.show()

    squeezed = [
        button.text()
        for button in pet_buttons(dialog)
        if button.width() < button.sizeHint().width()
    ]
    assert squeezed == []


def test_choosing_a_pet_and_naming_it(dialog, qtbot):
    qtbot.mouseClick(pet_button(dialog, "Maritaca"), LEFT)
    qtbot.keyClicks(name_field(dialog), "  Kiwi ")

    assert dialog.choice() == PetChoice(PARAKEET, "Kiwi")


def test_only_one_pet_can_be_chosen(dialog, qtbot):
    qtbot.mouseClick(pet_button(dialog, "Cat"), LEFT)
    qtbot.mouseClick(pet_button(dialog, "Maritaca"), LEFT)

    assert [button.text() for button in pet_buttons(dialog) if button.isChecked()] == ["Maritaca"]


def test_confirm_button_waits_for_a_real_name(dialog, qtbot):
    enabled = [confirm_button(dialog).isEnabled()]
    qtbot.keyClicks(name_field(dialog), "   ")
    enabled.append(confirm_button(dialog).isEnabled())
    qtbot.keyClicks(name_field(dialog), "Rex")
    enabled.append(confirm_button(dialog).isEnabled())

    assert enabled == [False, False, True]


def test_confirm_button_uses_the_given_text(dialog):
    assert confirm_button(dialog).text() == "Adopt"


def test_name_cannot_be_longer_than_the_limit(dialog, qtbot):
    qtbot.keyClicks(name_field(dialog), "x" * 40)

    assert len(name_field(dialog).text()) == 24


def test_current_pet_and_name_are_preselected_when_changing_settings(qtbot):
    dialog = PetDialog(
        title="Settings", message="", confirm_text="Save", current=PetChoice(CAT, "Mimi")
    )
    qtbot.addWidget(dialog)

    checked = [button.text() for button in pet_buttons(dialog) if button.isChecked()]

    assert (checked, name_field(dialog).text(), confirm_button(dialog).isEnabled()) == (
        ["Cat"],
        "Mimi",
        True,
    )


def test_hint_explains_how_to_play_with_the_pet(qtbot):
    dialog = PetDialog(title="Welcome!", message="", confirm_text="Adopt", hint="Tip: click it")
    qtbot.addWidget(dialog)

    assert "Tip: click it" in [label.text() for label in dialog.findChildren(QLabel)]
