"""The small dialogs used to adopt a pet on first run and to change it, or the language, later."""

from typing import NamedTuple, override

from PySide6.QtCore import QCoreApplication, QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QStyle,
    QStyleOptionSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from virtual_pet.behavior import DEFAULT_THROW_STRENGTH, THROW_STRENGTH_RANGE
from virtual_pet.config import MAX_NAME_LENGTH, normalize_name
from virtual_pet.i18n import LANGUAGES, arg
from virtual_pet.pets import ALL_SPECIES, DOG
from virtual_pet.species import Species
from virtual_pet.sprites import FRAME_HEIGHT, FRAME_WIDTH
from virtual_pet.update_check import (
    CheckFailed,
    DevBuild,
    UpdateAvailable,
    UpdateCheck,
    UpToDate,
    check_for_update,
)
from virtual_pet.version import app_version

ICON_SIZE = QSize(FRAME_WIDTH * 2, FRAME_HEIGHT * 2)
PETS_PER_ROW = 4  # rows of four keep the dialog compact
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


class Adoption(NamedTuple):
    """What the first run asks: the pet, and whether it starts with the system."""

    pet: PetChoice
    starts_with_system: bool


class Preferences(NamedTuple):
    """What the Settings change: the pet, the interface's language, starting with the system."""

    pet: PetChoice
    language: str | None  # None follows the system's language
    starts_with_system: bool = False
    throw_strength: int = DEFAULT_THROW_STRENGTH  # percent of the usual strength of a throw


class PetDialog(QDialog):
    """Asks which pet to have, what to call it and whether it starts with the system.

    Confirming needs a name.
    """

    def __init__(  # noqa: PLR0913 - what it shows and what it starts with, as keywords
        self,
        *,
        title: str,
        message: str,
        confirm_text: str,
        current: PetChoice | None = None,
        hint: str = "",
        starts_with_system: bool = False,
    ) -> None:
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)  # so other windows don't cover it
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
        self._starts_field = QCheckBox(self.tr("&Show the pet when the system starts"))
        self._starts_field.setChecked(starts_with_system)
        self._form.addRow("", self._starts_field)
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

    def starts_with_system(self) -> bool:
        """Whether the pet is to start when the user logs in."""
        return self._starts_field.isChecked()

    def _update_confirm_button(self) -> None:
        self._confirm_button.setEnabled(bool(self.choice().name))


class JumpSlider(QSlider):
    """A horizontal slider whose groove takes the handle straight to where it is clicked, instead
    of stepping a page towards it; a click on the handle itself still drags it."""

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            option = QStyleOptionSlider()
            self.initStyleOption(option)
            style = self.style()
            handle = style.subControlRect(
                QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderHandle, self
            )
            click = event.position().toPoint()
            if not handle.contains(click):
                groove = style.subControlRect(
                    QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderGroove, self
                )
                self.setValue(
                    QStyle.sliderValueFromPosition(
                        self.minimum(),
                        self.maximum(),
                        click.x() - groove.x() - handle.width() // 2,
                        groove.width() - handle.width(),
                    )
                )
        super().mousePressEvent(event)  # on the handle now, so it goes on as a drag


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
            starts_with_system=current.starts_with_system,
        )
        self._language_field = QComboBox()
        self._language_field.addItem(self.tr("System default"), SYSTEM_LANGUAGE)
        for code, name in LANGUAGES.items():
            self._language_field.addItem(name, code)
        # A language the pet doesn't have (a hand-edited file) shows as the system default.
        self._language_field.setCurrentIndex(
            max(self._language_field.findData(current.language), 0)
        )
        self._form.insertRow(2, self.tr("&Language:"), self._language_field)  # before Start

        low, high = THROW_STRENGTH_RANGE
        self._throw_field = JumpSlider(Qt.Orientation.Horizontal)
        self._throw_field.setRange(low, high)
        self._throw_field.setValue(current.throw_strength)
        self._throw_label = QLabel()
        self._throw_label.setMinimumWidth(self._throw_label.fontMetrics().horizontalAdvance("000%"))
        self._throw_field.valueChanged.connect(self._show_throw_strength)
        self._show_throw_strength(self._throw_field.value())
        throw_row = QHBoxLayout()
        throw_row.addWidget(self._throw_field)
        throw_row.addWidget(self._throw_label)
        throw_title = QLabel(self.tr("&Throw strength:"))
        throw_title.setBuddy(self._throw_field)
        self._form.insertRow(3, throw_title, throw_row)  # before Start

        version_row = QHBoxLayout()
        version_row.addWidget(QLabel(app_version()))
        self._update_button = QPushButton(self.tr("Check for Updates"))
        self._update_button.clicked.connect(self._check_for_updates)
        version_row.addWidget(self._update_button)
        self._form.addRow(self.tr("Version:"), version_row)

    def _show_throw_strength(self, percent: int) -> None:
        self._throw_label.setText(f"{percent}%")

    def _check_for_updates(self) -> None:
        original_text = self._update_button.text()
        self._update_button.setEnabled(False)
        self._update_button.setText(self.tr("Checking…"))
        self._update_button.repaint()  # the blocking check below would otherwise hide it
        result = check_for_update(app_version())
        self._update_button.setText(original_text)
        self._update_button.setEnabled(True)
        self._show_update_result(result)

    def _show_update_result(self, result: UpdateCheck) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(self.tr("Check for Updates"))
        box.setWindowModality(Qt.WindowModality.WindowModal)
        match result:
            case UpdateAvailable(version, url):
                box.setIcon(QMessageBox.Icon.Information)
                box.setText(arg(self.tr("Version %1 is available."), version))
                get_it = box.addButton(self.tr("Get It"), QMessageBox.ButtonRole.AcceptRole)
                box.addButton(QMessageBox.StandardButton.Close)
                box.buttonClicked.connect(
                    lambda button: QDesktopServices.openUrl(QUrl(url)) if button is get_it else None
                )
            case UpToDate():
                box.setIcon(QMessageBox.Icon.Information)
                box.setText(self.tr("You have the latest version."))
            case DevBuild():
                box.setIcon(QMessageBox.Icon.Information)
                box.setText(self.tr("This isn't a release build: nothing to compare it to."))
            case CheckFailed():
                box.setIcon(QMessageBox.Icon.Warning)
                box.setText(self.tr("Could not check for updates."))
        self._update_box = box  # kept alive until the user closes it
        box.open()

    def preferences(self) -> Preferences:
        """The chosen pet, its name, the language (None: the system's), starting with it."""
        language = self._language_field.currentData() or None
        return Preferences(
            self.choice(), language, self.starts_with_system(), self._throw_field.value()
        )


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


def ask_for_new_pet(*, starts_with_system: bool = False) -> Adoption | None:
    """Ask which pet to adopt, its name and whether it starts with the system.

    None if the user closes the dialog.
    """
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
        starts_with_system=starts_with_system,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return Adoption(dialog.choice(), dialog.starts_with_system())


def ask_for_changes(current: Preferences) -> Preferences | None:
    """Let the user rename or swap the pet, or change the language or starting with the system.

    None if cancelled.
    """
    dialog = SettingsDialog(current)
    return dialog.preferences() if dialog.exec() == QDialog.DialogCode.Accepted else None
