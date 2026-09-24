import os

import pytest
from PySide6.QtCore import QCoreApplication

from virtual_pet import i18n

# Widgets are exercised on Qt's virtual "offscreen" screen, so tests never open real windows.
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(autouse=True)
def english_interface():
    """Every test starts in English, whatever language an earlier test switched to."""
    yield
    if QCoreApplication.instance() is not None:
        i18n.use_language(i18n.ENGLISH)
