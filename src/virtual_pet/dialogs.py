"""The small dialog used to adopt a pet on first run and to change it later."""

from typing import NamedTuple

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
)

from virtual_pet.config import MAX_NAME_LENGTH, normalize_name
from virtual_pet.pets import ALL_SPECIES, DOG
from virtual_pet.species import Species
from virtual_pet.sprites import FRAME_HEIGHT, FRAME_WIDTH

MIN_WIDTH = 340  # room for the title bar and for the longest name
ICON_SIZE = QSize(FRAME_WIDTH * 2, FRAME_HEIGHT * 2)
# The chosen pet gets a thick border in the system's highlight color: not just a shade change.
PET_BUTTON_STYLE = """
QToolButton { border: 1px solid palette(mid); border-radius: 6px; padding: 4px 8px; }
QToolButton:checked { border: 3px solid palette(highlight); padding: 2px 6px; }
"""


class PetChoice(NamedTuple):
    """A kind of pet and the name it answers to."""

    species: Species
    name: str


class PetDialog(QDialog):
    """Asks which pet to have and what to call it; confirming needs a name."""

    def __init__(
        self,
        *,
        title: str,
        message: str,
        confirm_text: str,
        current: PetChoice | None = None,
        hint: str = "",
    ) -> None:
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)  # above the pet, which is on top
        self.setMinimumWidth(MIN_WIDTH)
        self.setStyleSheet(PET_BUTTON_STYLE)
        current = current or PetChoice(DOG, "")

        picker = QHBoxLayout()
        self._pet_buttons: list[tuple[QToolButton, Species]] = []
        for species in ALL_SPECIES:
            button = _pet_button(species)
            button.setChecked(species is current.species)
            picker.addWidget(button)
            self._pet_buttons.append((button, species))

        self._name_field = QLineEdit(current.name)
        self._name_field.setMaxLength(MAX_NAME_LENGTH)
        self._name_field.setPlaceholderText("e.g. Buddy")
        self._name_field.textChanged.connect(self._update_confirm_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._confirm_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._confirm_button.setText(confirm_text)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Pet:", picker)
        form.addRow("&Name:", self._name_field)
        layout = QVBoxLayout(self)
        if message:
            layout.addWidget(QLabel(message))
        layout.addLayout(form)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)
        layout.addWidget(buttons)
        self._update_confirm_button()

    def choice(self) -> PetChoice:
        """The chosen pet and its tidied-up name."""
        species = next((s for button, s in self._pet_buttons if button.isChecked()), DOG)
        return PetChoice(species, normalize_name(self._name_field.text()))

    def _update_confirm_button(self) -> None:
        self._confirm_button.setEnabled(bool(self.choice().name))


def _pet_button(species: Species) -> QToolButton:
    """A picture of the pet with its name under it; only one of these can be checked."""
    button = QToolButton()
    button.setText(species.label)
    image = species.image(species.portrait).scaled(ICON_SIZE)  # nearest neighbor: stays crisp
    button.setIcon(QIcon(QPixmap.fromImage(image)))
    button.setIconSize(ICON_SIZE)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    button.setCheckable(True)
    button.setAutoExclusive(True)
    return button


def ask_for_new_pet() -> PetChoice | None:
    """Ask which pet to adopt and its name; None if the user closes the dialog."""
    dialog = PetDialog(
        title="Welcome!",
        message="A new friend wants to live on your desktop!\nChoose your pet and give it a name.",
        confirm_text="Adopt",
        hint=(
            "Tip: click your pet to make it sit (click again to let it roam), "
            "drag it anywhere on the screen, and right-click it for more options."
        ),
    )
    return dialog.choice() if dialog.exec() == QDialog.DialogCode.Accepted else None


def ask_for_changes(current: PetChoice) -> PetChoice | None:
    """Let the user rename the pet or swap it for another one; None if cancelled."""
    dialog = PetDialog(
        title="Settings",
        message="You can have one pet at a time: choosing another one replaces it.",
        confirm_text="Save",
        current=current,
    )
    return dialog.choice() if dialog.exec() == QDialog.DialogCode.Accepted else None
