"""The interface in the user's language: English, as in the code, or one of its translations.

The translations are Qt Linguist files in translations/: a .ts file per language, which Qt
Linguist edits, and the .qm file compiled from it, which is what the app loads. Qt's own
texts, like the Cancel button or the menu of a text field, come translated with PySide6.
"""

import logging
import re
from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QGuiApplication

ENGLISH = "en"  # the language of the texts in the code
LANGUAGES = {ENGLISH: "English", "pt_BR": "Português (Brasil)"}  # each named in itself
FOLDER = Path(__file__).with_name("translations")
MARKER = re.compile(r"%([1-9])")  # where a value goes into a text: %1, %2…, as in Qt

logger = logging.getLogger(__name__)
_installed: list[QTranslator] = []  # removed again when the language changes


def QT_TRANSLATE_NOOP(context: str, text: str) -> str:  # noqa: N802, ARG001 - lupdate's name
    """Mark a text that is translated in `context` where it is shown, not where it is defined.

    lupdate finds texts by this name; PySide6's own QT_TRANSLATE_NOOP returns an `object`.
    """
    return text


APP_DISPLAY_NAME = QT_TRANSLATE_NOOP("App", "Virtual Pet")  # Qt ends the window titles with it


def arg(text: str, *values: str) -> str:
    """Put `values` into a translated text's %1, %2…, like Qt's QString::arg.

    Qt Linguist warns when a translation loses a marker. All of them are filled in at once,
    so a value holding a marker, like a pet named "100%2", stays as it is.
    """
    return MARKER.sub(lambda marker: values[int(marker.group(1)) - 1], text)


def resolve(chosen: str | None, system: Iterable[str]) -> str:
    """The language to show: the chosen one, else the first of the system's that there is."""
    if chosen in LANGUAGES:
        return chosen
    for tag in system:
        code = tag.replace("-", "_")
        if code in LANGUAGES:
            return code
        base = code.split("_")[0]
        closest = [known for known in LANGUAGES if known.split("_")[0] == base]
        if closest:
            return closest[0]
    return ENGLISH


def use_language(chosen: str | None) -> str:
    """Show the interface in `chosen` (None: the system's language) from now on.

    Returns the language it is shown in. Texts already on the screen keep their language, but
    the pet's menu and dialogs are built each time they open, so they switch at once, and so
    does the app's name at the end of their titles.
    """
    app = QCoreApplication.instance()
    if app is None:
        msg = "the interface's language is set once the app exists"
        raise RuntimeError(msg)
    language = resolve(chosen, QLocale.system().uiLanguages())
    while _installed:
        translator = _installed.pop()
        app.removeTranslator(translator)
        translator.deleteLater()
    if language != ENGLISH:
        _install_translations(app, language)
    QGuiApplication.setApplicationDisplayName(QCoreApplication.translate("App", APP_DISPLAY_NAME))
    return language


def _install_translations(app: QCoreApplication, language: str) -> None:
    """Install the pet's translation to `language` and Qt's own."""
    qt_folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    for name, folder in (("virtual_pet", str(FOLDER)), ("qtbase", qt_folder)):
        translator = QTranslator(app)
        if translator.load(f"{name}_{language}", folder):
            app.installTranslator(translator)
            _installed.append(translator)
        else:
            logger.warning("Could not load the %s translation %s from %s", language, name, folder)
