"""The small dialogs used to adopt a pet on first run and to change it, or the language, later."""

from typing import NamedTuple

from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from virtual_pet.config import MAX_NAME_LENGTH, normalize_name
from virtual_pet.i18n import LANGUAGES
from virtual_pet.pets import ALL_SPECIES, DOG
from virtual_pet.species import Species
from virtual_pet.sprites import FRAME_HEIGHT, FRAME_WIDTH

ICON_SIZE = QSize(FRAME_WIDTH * 2, FRAME_HEIGHT * 2)
PETS_PER_ROW = 4  # the eight pets in two rows, so the dialog stays compact
SYSTEM_LANGUAGE = ""  # the language field's value for "follow the system"
# The chosen pet gets a thick border in the system's highlight color: not just a shade change.
PET_BUTTON_STYLE = """
QToolButton { border: 1px solid palette(mid); border-radius: 6px; padding: 4px 8px; }
QToolButton:checked { border: 3px solid palette(highlight); padding: 2px 6px; }
"""


class PetChoice(NamedTuple):
    """A kind of pet and the name it answers to."""

    species: Species
    name: str


class Preferences(NamedTuple):
    """What the Settings change: the pet, and the language of the interface."""

    pet: PetChoice
    language: str | None  # None follows the system's language


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
        self.setStyleSheet(PET_BUTTON_STYLE)
        current = current or PetChoice(DOG, "")

        self._pet_buttons = [(_pet_button(species, self), species) for species in ALL_SPECIES]
        hints = [button.sizeHint() for button, _ in self._pet_buttons]
        size = QSize(max(hint.width() for hint in hints), max(hint.height() for hint in hints))
        picker = QGridLayout()
        for index, (button, species) in enumerate(self._pet_buttons):
            button.setChecked(species is current.species)
            button.setFixedSize(size)  # all the size of the largest, so the cards line up
            row, column = divmod(index, PETS_PER_ROW)
            picker.addWidget(button, row, column)

        self._name_field = QLineEdit(current.name)
        self._name_field.setMaxLength(MAX_NAME_LENGTH)
        self._name_field.setPlaceholderText(self.tr("e.g. Buddy"))
        self._name_field.textChanged.connect(self._update_confirm_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._confirm_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._confirm_button.setText(confirm_text)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self._form = QFormLayout()
        self._form.addRow(self.tr("Pet:"), picker)
        self._form.addRow(self.tr("&Name:"), self._name_field)
        layout = QVBoxLayout(self)
        # Never smaller than its contents, which Qt allows otherwise: it opens a window at most
        # 2/3 as wide as the screen, and the pet cards would overlap (longer names, small screen).
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        if message:
            layout.addWidget(QLabel(message))
        layout.addLayout(self._form)
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


class SettingsDialog(PetDialog):
    """The pet dialog plus the language of the interface: the Settings."""

    def __init__(self, current: Preferences) -> None:
        translate = QCoreApplication.translate  # self.tr() needs the dialog to exist
        super().__init__(
            title=translate("SettingsDialog", "Settings"),
            message=translate(
                "SettingsDialog",
                "You can have one pet at a time: choosing another one replaces it.",
            ),
            confirm_text=translate("SettingsDialog", "Save"),
            current=current.pet,
        )
        self._language_field = QComboBox()
        self._language_field.addItem(self.tr("System default"), SYSTEM_LANGUAGE)
        for code, name in LANGUAGES.items():
            self._language_field.addItem(name, code)
        # A language the pet doesn't have (a hand-edited file) shows as the system default.
        self._language_field.setCurrentIndex(
            max(self._language_field.findData(current.language), 0)
        )
        self._form.addRow(self.tr("&Language:"), self._language_field)

    def preferences(self) -> Preferences:
        """The chosen pet, its name and the chosen language (None: the system's)."""
        return Preferences(self.choice(), self._language_field.currentData() or None)


def _pet_button(species: Species, dialog: QWidget) -> QToolButton:
    """A picture of the pet with its name under it; only one of these can be checked."""
    button = QToolButton(dialog)  # in the dialog from the start: its style sheet sizes it
    button.setText(QCoreApplication.translate("Species", species.label))
    image = species.image(species.portrait).scaled(ICON_SIZE)  # nearest neighbor: stays crisp
    button.setIcon(QIcon(QPixmap.fromImage(image)))
    button.setIconSize(ICON_SIZE)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    button.setCheckable(True)
    button.setAutoExclusive(True)
    return button


def ask_for_new_pet() -> PetChoice | None:
    """Ask which pet to adopt and its name; None if the user closes the dialog."""
    translate = QCoreApplication.translate
    dialog = PetDialog(
        title=translate("PetDialog", "Welcome!"),
        message=translate(
            "PetDialog",
            "A new friend wants to live on your desktop!\nChoose your pet and give it a name.",
        ),
        confirm_text=translate("PetDialog", "Adopt"),
        hint=translate(
            "PetDialog",
            "Tip: click your pet to make it sit (click again to let it roam), "
            "drag it anywhere on the screen, and right-click it for more options.",
        ),
    )
    return dialog.choice() if dialog.exec() == QDialog.DialogCode.Accepted else None


def ask_for_changes(current: Preferences) -> Preferences | None:
    """Let the user rename the pet, swap it or change the language; None if cancelled."""
    dialog = SettingsDialog(current)
    return dialog.preferences() if dialog.exec() == QDialog.DialogCode.Accepted else None
