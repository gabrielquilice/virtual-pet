import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QToolButton,
)

from virtual_pet import dialogs, i18n
from virtual_pet.article_card import ArticleCard
from virtual_pet.dialogs import PetChoice, PetDialog, Preferences, SettingsDialog
from virtual_pet.pets import CAT, PARAKEET
from virtual_pet.update_check import CheckFailed, DevBuild, UpdateAvailable, UpToDate
from virtual_pet.version import app_version
from virtual_pet.wikipedia import Article

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
        ("Rabbit", False),
        ("Cockatiel", False),
        ("Fox", False),
        ("Snail", False),
        ("Frog", False),
        ("Chameleon", False),
        ("Chicken", False),
        ("Octopus", False),
        ("Owl", False),
    ]


def test_pets_are_offered_in_rows_of_four(dialog):
    dialog.show()
    rows = {}
    for button in sorted(pet_buttons(dialog), key=lambda button: (button.y(), button.x())):
        rows.setdefault(button.y(), []).append(button.text())

    assert list(rows.values()) == [
        ["Dog", "Cat", "Maritaca", "Sea Turtle"],
        ["Fish", "Guinea Pig", "Penguin", "Snake"],
        ["Rabbit", "Cockatiel", "Fox", "Snail"],
        ["Frog", "Chameleon", "Chicken", "Octopus"],
        ["Owl"],
    ]


def test_every_pet_card_has_the_same_size(dialog):
    dialog.show()

    sizes = {(button.width(), button.height()) for button in pet_buttons(dialog)}
    assert len(sizes) == 1


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


@pytest.fixture
def settings(qtbot):
    dialog = SettingsDialog(Preferences(PetChoice(CAT, "Mimi"), "pt_BR"))
    qtbot.addWidget(dialog)
    return dialog


def language_field(dialog: PetDialog) -> QComboBox | None:
    return dialog.findChild(QComboBox)


def test_settings_offer_the_languages_with_the_current_one_chosen(settings):
    field = language_field(settings)

    offered = [field.itemText(index) for index in range(field.count())]

    assert offered == ["System default", "English", "Português (Brasil)"]
    assert field.currentText() == "Português (Brasil)"


def test_settings_can_go_back_to_the_system_language(settings):
    language_field(settings).setCurrentIndex(0)

    assert settings.preferences() == Preferences(PetChoice(CAT, "Mimi"), None)


def test_settings_keep_the_pet_choices_of_the_pet_dialog(settings, qtbot):
    qtbot.mouseClick(pet_button(settings, "Maritaca"), LEFT)

    assert settings.preferences() == Preferences(PetChoice(PARAKEET, "Mimi"), "pt_BR")


def test_an_unknown_saved_language_shows_as_the_system_default(qtbot):
    dialog = SettingsDialog(Preferences(PetChoice(CAT, "Mimi"), "tlh"))
    qtbot.addWidget(dialog)

    assert language_field(dialog).currentText() == "System default"


def test_the_first_run_dialog_asks_for_no_language(dialog):
    assert language_field(dialog) is None


def starts_field(dialog: PetDialog) -> QCheckBox:
    return dialog.findChild(QCheckBox)


def test_the_first_run_offers_to_start_with_the_system_unchecked(dialog):
    field = starts_field(dialog)

    assert (field.text(), field.isChecked(), dialog.starts_with_system()) == (
        "&Show the pet when the system starts",
        False,
        False,
    )


def test_the_first_run_can_start_with_the_system(dialog, qtbot):
    field = starts_field(dialog)

    qtbot.mouseClick(field, LEFT, pos=QPoint(5, field.height() // 2))  # on the box itself

    assert dialog.starts_with_system()


def test_settings_show_whether_the_pet_starts_with_the_system(qtbot):
    dialog = SettingsDialog(Preferences(PetChoice(CAT, "Mimi"), None, starts_with_system=True))
    qtbot.addWidget(dialog)

    starts_field(dialog).setChecked(False)

    assert dialog.preferences() == Preferences(
        PetChoice(CAT, "Mimi"), None, starts_with_system=False
    )


def test_settings_ask_for_the_language_before_starting_with_the_system(settings):
    form = settings.findChild(QFormLayout)
    fields = [form.itemAt(row, QFormLayout.ItemRole.FieldRole).widget() for row in range(5)]

    # the throw speed's field is a layout, not a widget
    assert fields[2:] == [language_field(settings), None, starts_field(settings)]


def test_settings_show_the_app_version(settings):
    assert app_version() in [label.text() for label in settings.findChildren(QLabel)]


def update_button(dialog: SettingsDialog) -> QPushButton:
    return next(button for button in dialog.findChildren(QPushButton) if "Update" in button.text())


def update_box(dialog: SettingsDialog) -> QMessageBox:
    return dialog.findChild(QMessageBox)


def test_checking_for_updates_reenables_the_button_and_reports_the_result(settings, monkeypatch):
    monkeypatch.setattr(dialogs, "check_for_update", lambda _version: UpToDate())

    update_button(settings).click()

    assert update_button(settings).isEnabled()
    assert update_button(settings).text() == "Check for Updates"
    assert update_box(settings).text() == "You have the latest version."


def test_the_button_checks_even_when_the_daily_check_is_off_or_done(settings, monkeypatch):
    calls = []
    monkeypatch.setenv("VIRTUAL_PET_NO_UPDATE_CHECK", "1")  # as conftest does for every test
    monkeypatch.setattr(
        dialogs, "check_for_update", lambda version: calls.append(version) or UpToDate()
    )

    update_button(settings).click()

    assert calls == [app_version()]


def test_an_available_update_offers_a_button_that_opens_it(settings, monkeypatch):
    monkeypatch.setattr(
        dialogs,
        "check_for_update",
        lambda _version: UpdateAvailable("0.9.0", "https://example.com/releases/latest"),
    )
    opened = []
    monkeypatch.setattr(
        dialogs.QDesktopServices, "openUrl", lambda url: opened.append(url.toString())
    )

    update_button(settings).click()
    box = update_box(settings)

    assert box.text().endswith("\n0.9.0")  # the number on a line of its own, centered
    label = box.findChild(QLabel, "qt_msgbox_label")
    assert label.alignment() == Qt.AlignmentFlag.AlignCenter
    get_it = next(b for b in box.buttons() if b.text() == "Get It")
    get_it.click()
    assert opened == ["https://example.com/releases/latest"]


def test_a_dev_build_cannot_be_compared(settings, monkeypatch):
    monkeypatch.setattr(dialogs, "check_for_update", lambda _version: DevBuild())

    update_button(settings).click()

    assert update_box(settings).text() == "This isn't a release build: nothing to compare it to."


def test_a_failed_check_is_reported(settings, monkeypatch):
    monkeypatch.setattr(dialogs, "check_for_update", lambda _version: CheckFailed())

    update_button(settings).click()

    assert update_box(settings).text() == "Could not check for updates."


def test_the_settings_speak_portuguese(qtbot):
    i18n.use_language("pt_BR")
    dialog = SettingsDialog(Preferences(PetChoice(CAT, "Mimi"), "pt_BR"))
    qtbot.addWidget(dialog)
    buttons = dialog.findChild(QDialogButtonBox)

    assert dialog.windowTitle() == "Configurações"
    assert [button.text() for button in pet_buttons(dialog)] == [
        "Cachorro",
        "Gato",
        "Maritaca",
        "Tartaruga-marinha",
        "Peixe",
        "Porquinho-da-índia",
        "Pinguim",
        "Cobra",
        "Coelho",
        "Calopsita",
        "Raposa",
        "Caracol",
        "Sapo",
        "Camaleão",
        "Galinha",
        "Polvo",
        "Coruja",
    ]
    assert {"&Nome:", "&Idioma:", "Versão:"} <= {
        label.text() for label in dialog.findChildren(QLabel)
    }
    assert [button.text() for button in buttons.buttons()] == ["Salvar", "Cancelar"]
    assert language_field(dialog).itemText(0) == "Padrão do sistema"


@pytest.mark.parametrize("language", ["en", "pt_BR"])
def test_the_pet_cards_never_overlap_or_leave_the_dialog(qtbot, language):
    # The offscreen screen is 800 pixels wide, and Qt opens a window at most 2/3 as wide.
    i18n.use_language(language)
    dialog = PetDialog(title="", message="", confirm_text="")
    qtbot.addWidget(dialog)
    dialog.show()

    cards = [button.geometry() for button in pet_buttons(dialog)]
    overlapping = [
        (a.topLeft(), b.topLeft())
        for i, a in enumerate(cards)
        for b in cards[i + 1 :]
        if a.intersects(b)
    ]
    outside = [card.topLeft() for card in cards if not dialog.rect().contains(card)]
    assert (overlapping, outside) == ([], [])


def test_settings_slider_shows_and_returns_the_throw_strength(qtbot):
    dialog = SettingsDialog(Preferences(PetChoice(CAT, "Mimi"), None, throw_strength=150))
    qtbot.addWidget(dialog)

    assert dialog._throw_field.value() == 150  # noqa: SLF001
    assert dialog._throw_label.text() == "150%"  # noqa: SLF001

    dialog._throw_field.setValue(180)  # noqa: SLF001

    assert dialog._throw_label.text() == "180%"  # noqa: SLF001
    assert dialog.preferences().throw_strength == 180


def test_clicking_the_throw_strength_groove_jumps_to_that_spot(qtbot):
    dialog = SettingsDialog(Preferences(PetChoice(CAT, "Mimi"), None))
    qtbot.addWidget(dialog)
    dialog.show()
    slider = dialog._throw_field  # noqa: SLF001
    assert slider.value() == 100

    qtbot.mouseClick(slider, Qt.MouseButton.LeftButton, pos=QPoint(slider.width() - 8, 8))

    assert slider.value() > 215  # not one page step from 100

    qtbot.mouseClick(slider, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))

    assert slider.value() < 35


def test_the_dialog_cannot_be_resized_or_maximized(dialog):
    dialog.show()

    assert dialog.minimumSize() == dialog.maximumSize() == dialog.sizeHint()
    dialog.setWindowState(Qt.WindowState.WindowMaximized)
    assert dialog.size() == dialog.sizeHint()


CTRL = Qt.KeyboardModifier.ControlModifier
COCKATIEL_ARTICLE = Article(
    "Cockatiel", "Species of bird", "The cockatiel is a bird.", "https://example.org/c", None
)


def article_card(dialog: PetDialog) -> ArticleCard | None:
    return dialog.findChild(ArticleCard)


def card_text(card: ArticleCard) -> str:
    return " | ".join(
        label.text() for label in card.findChildren(QLabel) if label.isVisibleTo(card)
    )


def test_the_dialog_tells_how_to_learn_about_a_pet(dialog):
    texts = [label.text() for label in dialog.findChildren(QLabel)]

    assert "Hold Ctrl and click an animal to learn more" in texts


def test_ctrl_click_opens_the_article_without_choosing_the_pet(dialog, qtbot, monkeypatch):
    monkeypatch.setattr("virtual_pet.wikipedia.fetch_article", lambda *_: COCKATIEL_ARTICLE)
    dialog.show()

    qtbot.mouseClick(pet_button(dialog, "Cockatiel"), LEFT, CTRL)

    qtbot.waitUntil(lambda: "The cockatiel is a bird." in card_text(article_card(dialog)))
    assert dialog.choice().species.key == "dog"
    assert not pet_button(dialog, "Cockatiel").isChecked()
    assert "Species of bird" in card_text(article_card(dialog))


def test_a_plain_click_chooses_the_pet_and_opens_no_article(dialog, qtbot):
    dialog.show()

    qtbot.mouseClick(pet_button(dialog, "Cockatiel"), LEFT)

    assert dialog.choice().species.key == "cockatiel"
    assert article_card(dialog) is None


def test_the_article_says_it_is_loading_and_then_that_it_failed(dialog, qtbot):
    dialog.show()

    qtbot.mouseClick(pet_button(dialog, "Owl"), LEFT, CTRL)
    assert "Loading…" in card_text(article_card(dialog))

    qtbot.waitUntil(lambda: "Couldn't load the article" in card_text(article_card(dialog)))
    assert "Open on Wikipedia" in card_text(article_card(dialog))


def test_the_card_links_to_the_article_with_the_license(dialog, qtbot):
    dialog.show()

    qtbot.mouseClick(pet_button(dialog, "Owl"), LEFT, CTRL)

    footer = next(
        label.text()
        for label in article_card(dialog).findChildren(QLabel)
        if "href" in label.text()
    )
    assert "https://en.wikipedia.org/wiki/Tropical_screech_owl" in footer
    assert "CC BY-SA" in footer


def test_escape_closes_the_card(dialog, qtbot):
    dialog.show()
    qtbot.mouseClick(pet_button(dialog, "Owl"), LEFT, CTRL)
    card = article_card(dialog)

    qtbot.keyClick(card, Qt.Key.Key_Escape)

    assert not card.isVisible()


def test_the_card_stays_on_the_screen(dialog, qtbot):
    dialog.show()
    qtbot.mouseClick(pet_button(dialog, "Owl"), LEFT, CTRL)

    area = dialog.screen().availableGeometry()
    assert area.contains(article_card(dialog).geometry())


def test_a_long_article_is_not_cut_off(dialog, qtbot, monkeypatch):
    long = Article("Dog", "", "A sentence about dogs. " * 60, "https://example.org", None)
    monkeypatch.setattr("virtual_pet.wikipedia.fetch_article", lambda *_: long)
    dialog.show()

    qtbot.mouseClick(pet_button(dialog, "Dog"), LEFT, CTRL)

    card = article_card(dialog)
    qtbot.waitUntil(lambda: "A sentence about dogs." in card_text(card))
    text = next(label for label in card.findChildren(QLabel) if label.text() == long.extract)
    assert text.height() >= text.heightForWidth(text.width())


def test_following_the_link_opens_the_article_and_closes_the_card(dialog, qtbot, monkeypatch):
    opened = []
    monkeypatch.setattr(
        "virtual_pet.article_card.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString()),
    )
    dialog.show()
    qtbot.mouseClick(pet_button(dialog, "Owl"), LEFT, CTRL)
    card = article_card(dialog)
    footer = next(label for label in card.findChildren(QLabel) if "href" in label.text())

    footer.linkActivated.emit("https://en.wikipedia.org/wiki/Tropical_screech_owl")

    assert opened == ["https://en.wikipedia.org/wiki/Tropical_screech_owl"]
    assert not card.isVisible()
