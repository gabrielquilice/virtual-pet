import logging
import socket
import stat

import pytest

from virtual_pet.instance import acquire_lock, ask_to_show, listen_for_show_requests


def test_only_one_start_of_the_app_gets_the_lock(tmp_path):
    first = acquire_lock(tmp_path / "pet.lock")
    second = acquire_lock(tmp_path / "pet.lock")
    first.unlock()
    third = acquire_lock(tmp_path / "pet.lock")

    assert (first is not None, second, third is not None) == (True, None, True)


@pytest.fixture
def socket_path(tmp_path):
    return tmp_path / "pet.socket"


@pytest.fixture
def listening(socket_path, qapp):  # noqa: ARG001 - the socket is watched by Qt's event loop
    requests = listen_for_show_requests(socket_path)
    yield requests
    requests.close()


def test_a_later_start_asks_the_running_pet_to_show_itself(listening, socket_path, qtbot):
    with qtbot.waitSignal(listening.received, timeout=2000):
        answered = ask_to_show(socket_path)

    assert answered


def test_nobody_answers_where_no_pet_listens(socket_path):
    assert not ask_to_show(socket_path)


def test_a_socket_left_by_a_pet_that_crashed_is_replaced(socket_path, qtbot):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as leftover:
        leftover.bind(str(socket_path))  # closed without removing the file, as in a crash
    requests = listen_for_show_requests(socket_path)

    with qtbot.waitSignal(requests.received, timeout=2000):
        answered = ask_to_show(socket_path)

    requests.close()
    assert answered


@pytest.mark.usefixtures("listening")
def test_only_the_user_can_ask(socket_path):
    assert stat.S_IMODE(socket_path.stat().st_mode) == 0o600


def test_closing_removes_the_socket(listening, socket_path):
    listening.close()

    assert not socket_path.exists()
    assert not ask_to_show(socket_path)


def test_a_socket_that_cant_be_made_is_reported_and_leaves_the_pet_running(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        requests = listen_for_show_requests(tmp_path / "missing folder" / "pet.socket")

    assert requests is None
    assert "Opening the app again won't show the pet" in caplog.text


def test_a_runtime_folder_too_deep_for_a_socket_address_still_works(tmp_path, qtbot):
    folder = tmp_path / ("deep" * 10) / ("er" * 20)
    folder.mkdir(parents=True)
    path = folder / "pet.socket"  # longer than the 107 bytes a socket address holds
    requests = listen_for_show_requests(path)

    with qtbot.waitSignal(requests.received, timeout=2000):
        answered = ask_to_show(path)

    requests.close()
    assert len(str(path).encode()) > 107
    assert answered
    assert not path.exists()
