import os
import sys

import pytest

from virtual_pet import links

BUNDLE = "/mnt/appimage/usr/lib/virtual-pet/_internal"


@pytest.fixture
def seen(monkeypatch):
    """What the browser launcher sees: each URL with the library path in force at that moment."""
    calls = []
    monkeypatch.setattr(
        links.QDesktopServices,
        "openUrl",
        lambda url: calls.append((url.toString(), os.environ.get("LD_LIBRARY_PATH"))) or True,
    )
    return calls


def frozen_on_linux(monkeypatch, *, original: str | None) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("LD_LIBRARY_PATH", BUNDLE)
    if original is None:
        monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    else:
        monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", original)


def test_a_bundled_app_hands_the_launcher_the_users_library_path(monkeypatch, seen):
    frozen_on_linux(monkeypatch, original="/opt/lib")

    assert links.open_link("https://example.com/")

    assert seen == [("https://example.com/", "/opt/lib")]
    assert os.environ["LD_LIBRARY_PATH"] == BUNDLE  # the app's own is back afterwards


def test_a_bundled_app_with_no_library_path_of_the_user_hands_over_none(monkeypatch, seen):
    frozen_on_linux(monkeypatch, original=None)

    links.open_link("https://example.com/")

    assert seen == [("https://example.com/", None)]
    assert os.environ["LD_LIBRARY_PATH"] == BUNDLE


def test_the_library_path_comes_back_when_the_launcher_fails(monkeypatch):
    frozen_on_linux(monkeypatch, original=None)

    def fail(_url):
        raise RuntimeError

    monkeypatch.setattr(links.QDesktopServices, "openUrl", fail)

    with pytest.raises(RuntimeError):
        links.open_link("https://example.com/")

    assert os.environ["LD_LIBRARY_PATH"] == BUNDLE


def test_running_from_source_leaves_the_environment_alone(monkeypatch, seen):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/lib")

    links.open_link("https://example.com/")

    assert seen == [("https://example.com/", "/opt/lib")]
