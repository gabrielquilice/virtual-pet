import json
from datetime import date
from typing import Self

import pytest

from virtual_pet.update_check import (
    DISABLE_VARIABLE,
    LATEST_RELEASE_API,
    RELEASE_PAGE,
    BackgroundCheck,
    CheckFailed,
    DevBuild,
    UpdateAvailable,
    UpToDate,
    check_for_update,
    daily_check_due,
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


@pytest.fixture
def latest_tag(monkeypatch):
    def fake(tag_name: str | None):
        def urlopen(request, timeout):  # noqa: ARG001 - matching urllib's signature
            assert request.full_url == LATEST_RELEASE_API
            return FakeResponse({} if tag_name is None else {"tag_name": tag_name})

        monkeypatch.setattr("virtual_pet.update_check.urllib.request.urlopen", urlopen)

    return fake


def test_a_newer_release_is_offered(latest_tag):
    latest_tag("v0.5.0")

    assert check_for_update("0.4.0") == UpdateAvailable("0.5.0", RELEASE_PAGE)


def test_the_same_release_is_up_to_date(latest_tag):
    latest_tag("v0.4.0")

    assert check_for_update("0.4.0") == UpToDate()


def test_a_newer_local_version_than_the_release_is_up_to_date(latest_tag):
    latest_tag("v0.4.0")

    assert check_for_update("0.5.0") == UpToDate()


def test_version_numbers_compare_numerically_not_lexically(latest_tag):
    latest_tag("v0.10.0")  # "0.10.0" < "0.9.0" as plain strings, but it is the newer release

    assert check_for_update("0.9.0") == UpdateAvailable("0.10.0", RELEASE_PAGE)


def test_a_dev_build_is_never_compared(monkeypatch):
    def urlopen(*_args, **_kwargs):
        pytest.fail("a dev build shouldn't reach the network")

    monkeypatch.setattr("virtual_pet.update_check.urllib.request.urlopen", urlopen)

    assert check_for_update("0.4.0+gabc1234.dirty") == DevBuild()


def test_a_network_error_is_reported(monkeypatch):
    def urlopen(*_args, **_kwargs):
        raise OSError

    monkeypatch.setattr("virtual_pet.update_check.urllib.request.urlopen", urlopen)

    assert check_for_update("0.4.0") == CheckFailed()


def test_a_response_without_a_tag_name_is_reported(latest_tag):
    latest_tag(None)

    assert check_for_update("0.4.0") == CheckFailed()


def test_unreadable_json_is_reported(monkeypatch):
    class BadResponse(FakeResponse):
        def __init__(self) -> None:
            self._body = b"not json"

    monkeypatch.setattr(
        "virtual_pet.update_check.urllib.request.urlopen", lambda *_a, **_k: BadResponse()
    )

    assert check_for_update("0.4.0") == CheckFailed()


def test_the_daily_check_is_due_once_per_day(monkeypatch):
    monkeypatch.delenv(DISABLE_VARIABLE)

    assert daily_check_due(None, date(2026, 10, 3))
    assert daily_check_due("2026-10-02", date(2026, 10, 3))
    assert not daily_check_due("2026-10-03", date(2026, 10, 3))


def test_the_daily_check_can_be_turned_off_by_the_environment():
    assert not daily_check_due(None, date(2026, 10, 3))  # conftest sets the variable


def test_a_background_check_hands_its_result_back_to_the_main_thread(qtbot, latest_tag):
    latest_tag("v0.5.0")
    check = BackgroundCheck("0.4.0")

    with qtbot.waitSignal(check.finished, timeout=5000) as blocker:
        check.start()

    assert blocker.args == [UpdateAvailable("0.5.0", RELEASE_PAGE)]
