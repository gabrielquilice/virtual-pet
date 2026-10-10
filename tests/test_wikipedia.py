import json
from typing import Self
from urllib.parse import unquote

import pytest

from virtual_pet.pets import ALL_SPECIES
from virtual_pet.wikipedia import (
    TITLES,
    Article,
    ArticleLoader,
    article_url,
    fetch_article,  # the real one, bound before conftest's stub replaces the module's
    wiki_language,
)

SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/Cockatiel"
PICTURE_URL = "https://upload.wikimedia.org/thumb/cockatiel.jpg"
SUMMARY = {
    "type": "standard",
    "title": "Cockatiel",
    "description": "Species of bird",
    "extract": "The cockatiel is a bird.",
    "thumbnail": {"source": PICTURE_URL},
}
PICTURE = b"not really a jpeg"


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self, size: int = -1) -> bytes:
        return self._body[:size] if size >= 0 else self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


@pytest.fixture
def server(monkeypatch):
    """Wikipedia's answers by address: a body, or an exception to raise; `asked` has the rest."""

    class Server:
        def __init__(self) -> None:
            self.answers: dict[str, bytes | Exception] = {}
            self.asked: list = []

        def says(self, url: str, body: dict | bytes | Exception) -> None:
            self.answers[url] = json.dumps(body).encode() if isinstance(body, dict) else body

    fake = Server()

    def urlopen(request, timeout):  # noqa: ARG001 - matching urllib's signature
        fake.asked.append(request)
        answer = fake.answers[request.full_url]
        if isinstance(answer, Exception):
            raise answer
        return FakeResponse(answer)

    monkeypatch.setattr("virtual_pet.wikipedia.urllib.request.urlopen", urlopen)
    return fake


def test_every_species_has_an_article_in_every_language():
    keys = {species.key for species in ALL_SPECIES}

    assert {language: set(titles) for language, titles in TITLES.items()} == {
        "en": keys,
        "pt": keys,
    }


def test_the_wikipedia_follows_the_interface_language_and_falls_back_to_english():
    codes = ("en", "pt_BR", "pt", "de_DE")

    assert [wiki_language(code) for code in codes] == ["en", "pt", "pt", "en"]


def test_the_article_address_is_that_of_the_page_in_the_languages_wikipedia():
    assert article_url("guinea_pig", "en") == "https://en.wikipedia.org/wiki/Guinea_pig"
    assert unquote(article_url("guinea_pig", "pt_BR")) == (
        "https://pt.wikipedia.org/wiki/Porquinho-da-índia"
    )


def test_the_article_comes_with_its_picture(server):
    server.says(SUMMARY_URL, SUMMARY)
    server.says(PICTURE_URL, PICTURE)

    assert fetch_article("cockatiel", "en") == Article(
        "Cockatiel",
        "Species of bird",
        "The cockatiel is a bird.",
        "https://en.wikipedia.org/wiki/Cockatiel",
        PICTURE,
    )


def test_wikipedia_is_told_who_is_asking(server):
    server.says(SUMMARY_URL, SUMMARY)
    server.says(PICTURE_URL, PICTURE)

    fetch_article("cockatiel", "en")

    agents = {request.get_header("User-agent") for request in server.asked}
    assert all(agent.startswith("VirtualPet/") and "github.com" in agent for agent in agents)


def test_the_article_is_read_in_the_interface_language(server):
    url = "https://pt.wikipedia.org/api/rest_v1/page/summary/Calopsita"
    server.says(url, {**SUMMARY, "title": "Calopsita", "thumbnail": {}})

    article = fetch_article("cockatiel", "pt_BR")

    assert article is not None
    assert article.title == "Calopsita"
    assert article.image is None


def test_a_failing_picture_leaves_the_text(server):
    server.says(SUMMARY_URL, SUMMARY)
    server.says(PICTURE_URL, OSError("offline"))

    article = fetch_article("cockatiel", "en")

    assert article is not None
    assert (article.extract, article.image) == ("The cockatiel is a bird.", None)


def test_a_picture_from_anywhere_but_wikimedia_is_not_fetched(server):
    elsewhere = {"source": "https://example.com/cockatiel.jpg"}
    server.says(SUMMARY_URL, {**SUMMARY, "thumbnail": elsewhere})

    article = fetch_article("cockatiel", "en")

    assert article is not None
    assert article.image is None
    assert [request.full_url for request in server.asked] == [SUMMARY_URL]


@pytest.mark.parametrize(
    "answer",
    [
        OSError("offline"),
        b"<html>not json</html>",
        {"type": "disambiguation", "title": "Cockatiel", "extract": "may refer to"},
        {"type": "standard", "title": "Cockatiel"},
        {**SUMMARY, "extract": "  "},
    ],
    ids=["offline", "not json", "disambiguation", "no extract", "empty extract"],
)
def test_an_article_that_cannot_be_had_is_none(server, answer):
    server.says(SUMMARY_URL, answer)

    assert fetch_article("cockatiel", "en") is None


ARTICLE = Article("Cockatiel", "Species of bird", "A bird.", "https://example.org", None)


def test_the_loader_hands_over_an_article_and_remembers_it(qtbot, monkeypatch):
    calls = []

    def fake(species_key, language):
        calls.append((species_key, language))
        return ARTICLE

    monkeypatch.setattr("virtual_pet.wikipedia.fetch_article", fake)
    loader = ArticleLoader("pt_BR")

    with qtbot.waitSignal(loader.loaded) as signal:
        loader.request("cockatiel")

    assert signal.args == ["cockatiel", ARTICLE]
    assert loader.cached("cockatiel") == ARTICLE
    assert calls == [("cockatiel", "pt_BR")]


def test_the_loader_does_not_remember_a_failure(qtbot):
    loader = ArticleLoader("en")  # conftest's stub can't have any article

    with qtbot.waitSignal(loader.loaded) as signal:
        loader.request("cockatiel")

    assert signal.args == ["cockatiel", None]
    assert loader.cached("cockatiel") is None


def test_the_loader_asks_once_for_a_request_in_progress(qtbot, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "virtual_pet.wikipedia.fetch_article", lambda *args: calls.append(args) or ARTICLE
    )
    loader = ArticleLoader("en")

    with qtbot.waitSignal(loader.loaded):
        loader.request("owl")
        loader.request("owl")

    assert len(calls) == 1
