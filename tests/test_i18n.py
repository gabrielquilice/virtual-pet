import logging
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication

from virtual_pet import i18n

TRANSLATED = [code for code in i18n.LANGUAGES if code != i18n.ENGLISH]
SOURCES = sorted(str(path) for path in Path(i18n.__file__).parent.rglob("*.py"))


def pyside_tool(name: str) -> str:
    return str(Path(sys.executable).with_name(f"pyside6-{name}"))  # installed with PySide6


@pytest.mark.parametrize(
    ("chosen", "system", "expected"),
    [
        ("pt_BR", ["en-US"], "pt_BR"),  # the user's choice wins
        ("en", ["pt-BR"], "en"),
        (None, ["pt-BR", "en-US"], "pt_BR"),  # otherwise the system's language
        (None, ["pt-PT"], "pt_BR"),  # or the closest one there is
        (None, ["de-DE", "pt-BR"], "pt_BR"),  # the first one there is
        (None, ["de-DE"], "en"),  # English when there is none of them
        ("tlh", ["pt-BR"], "pt_BR"),  # a choice that doesn't exist (a hand-edited file)
    ],
)
def test_the_language_shown(chosen, system, expected):
    assert i18n.resolve(chosen, system) == expected


def test_the_languages_on_offer_are_named_in_themselves():
    assert i18n.LANGUAGES == {"en": "English", "pt_BR": "Português (Brasil)"}


def texts() -> tuple[str, str]:
    """A text of the pet's and one of Qt's own (the Cancel button)."""
    translate = QCoreApplication.translate
    return translate("PetWindow", "Quit"), translate("QPlatformTheme", "Cancel")


@pytest.mark.usefixtures("qapp")
def test_the_interface_can_switch_to_portuguese_and_back():
    used = [i18n.use_language("pt_BR")]
    portuguese = texts()
    used.append(i18n.use_language("en"))

    assert used == ["pt_BR", "en"]
    assert (portuguese, texts()) == (("Sair", "Cancelar"), ("Quit", "Cancel"))


@pytest.mark.usefixtures("qapp")
def test_the_app_is_named_in_the_language_shown():
    names = []
    for language in ("pt_BR", "en"):
        i18n.use_language(language)
        names.append(QGuiApplication.applicationDisplayName())  # ends the window titles

    assert names == ["Pet Virtual", "Virtual Pet"]


@pytest.mark.usefixtures("qapp")
def test_a_missing_translation_is_reported_and_leaves_english(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(i18n, "FOLDER", tmp_path)

    with caplog.at_level(logging.WARNING):
        i18n.use_language("pt_BR")

    assert "Could not load the pt_BR translation" in caplog.text
    assert texts()[0] == "Quit"


@pytest.mark.parametrize("language", TRANSLATED)
def test_every_text_in_the_code_is_translated(language, tmp_path):
    ts = tmp_path / "check.ts"
    shutil.copy(i18n.FOLDER / f"virtual_pet_{language}.ts", ts)

    command = [pyside_tool("lupdate"), *SOURCES, "-locations", "none", "-ts", str(ts)]
    subprocess.run(command, check=True, capture_output=True)

    messages = ET.parse(ts).getroot().iter("message")  # noqa: S314 - our own file
    # lupdate marks the texts new in the code "unfinished", and those gone from it "vanished".
    pending = [
        message.findtext("source")
        for message in messages
        if message.find("translation").get("type")
    ]
    assert pending == []


@pytest.mark.parametrize("language", TRANSLATED)
def test_the_compiled_translation_matches_its_source(language, tmp_path):
    compiled = tmp_path / "check.qm"
    source = i18n.FOLDER / f"virtual_pet_{language}.ts"

    subprocess.run(
        [pyside_tool("lrelease"), str(source), "-qm", str(compiled)],
        check=True,
        capture_output=True,
    )

    assert compiled.read_bytes() == source.with_suffix(".qm").read_bytes()
