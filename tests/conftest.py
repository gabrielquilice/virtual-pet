import os

import pytest
from PySide6.QtCore import QCoreApplication

from virtual_pet import i18n

# Widgets are exercised on Qt's virtual "offscreen" screen, so tests never open real windows.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
# No test, nor a process test's app, reaches GitHub; the ones for the check turn it back on.
os.environ["VIRTUAL_PET_NO_UPDATE_CHECK"] = "1"


@pytest.fixture(autouse=True)
def english_interface():
    """Every test starts in English, whatever language an earlier test switched to."""
    yield
    if QCoreApplication.instance() is not None:
        i18n.use_language(i18n.ENGLISH)


@pytest.fixture(autouse=True)
def private_config_folder(tmp_path, monkeypatch):
    """Nothing a test does reaches the user's own settings, such as their autostart folder."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))


@pytest.fixture(autouse=True)
def no_wikipedia(monkeypatch):
    """No test reaches Wikipedia: an article can't be had, unless the test brings its own."""
    monkeypatch.setattr("virtual_pet.wikipedia.fetch_article", lambda *_: None)
