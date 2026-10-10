"""The Wikipedia article about a kind of pet, for the card the adoption dialog opens on Ctrl+click.

A plain GET to Wikipedia's REST summary endpoint, with the standard library: the AppImage leaves
QtNetwork out on purpose (see appimage/virtual-pet.spec), as it does for the update check.
"""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThreadPool, Signal

from virtual_pet.version import app_version

REPOSITORY_URL = "https://github.com/gabrielquilice/virtual-pet"
DEFAULT_LANGUAGE = "en"
TIMEOUT = 5  # seconds, for each of the two requests (the summary, then its picture)
MAX_BYTES = 2_000_000  # a summary is a few KB and its thumbnail some tens of KB: this is a guard
IMAGE_HOST_SUFFIX = ".wikimedia.org"  # where Wikipedia keeps its pictures

# The article of each species (its key), per Wikipedia language. The titles are the pages the
# pet stands for, a species where it is one (the maritaca's is Pionus maximiliani) and the
# group where it isn't (the snake, the frog); tests/test_wikipedia.py has one for each pet.
TITLES = {
    "en": {
        "dog": "Dog",
        "cat": "Cat",
        "parakeet": "Scaly-headed parrot",
        "turtle": "Sea turtle",
        "fish": "Betta splendens",
        "guinea_pig": "Guinea pig",
        "penguin": "Gentoo penguin",
        "snake": "Snake",
        "rabbit": "European rabbit",
        "cockatiel": "Cockatiel",
        "fox": "Red fox",
        "snail": "Garden snail",
        "frog": "Frog",
        "chameleon": "Veiled chameleon",
        "chicken": "Chicken",
        "octopus": "Blue-ringed octopus",
        "owl": "Tropical screech owl",
    },
    "pt": {
        "dog": "Cão",
        "cat": "Gato",
        "parakeet": "Pionus maximiliani",
        "turtle": "Tartaruga-marinha",
        "fish": "Betta splendens",
        "guinea_pig": "Porquinho-da-índia",
        "penguin": "Pinguim-gentoo",
        "snake": "Serpente",
        "rabbit": "Coelho-europeu",
        "cockatiel": "Calopsita",
        "fox": "Raposa-vermelha",
        "snail": "Cornu aspersum",
        "frog": "Sapo",
        "chameleon": "Camaleão",
        "chicken": "Galinha",
        "octopus": "Polvo-de-anéis-azuis",
        "owl": "Megascops choliba",
    },
}


@dataclass(frozen=True)
class Article:
    """What the card shows of an article."""

    title: str
    description: str  # Wikipedia's one-line description, e.g. "Species of bird"; may be empty
    extract: str  # the article's opening, in plain text
    url: str  # the article's page
    image: bytes | None  # its thumbnail, as the file Wikipedia serves; None if it has none


def wiki_language(language: str) -> str:
    """The Wikipedia to read for an interface language: its own, else the English one."""
    base = language.split("_", maxsplit=1)[0]
    return base if base in TITLES else DEFAULT_LANGUAGE


def article_url(species_key: str, language: str) -> str:
    """The address of the article about a species, in the Wikipedia for `language`."""
    wiki = wiki_language(language)
    return f"https://{wiki}.wikipedia.org/wiki/{_quote(TITLES[wiki][species_key])}"


def fetch_article(species_key: str, language: str) -> Article | None:
    """The article about a species in `language`'s Wikipedia; None if it can't be had."""
    wiki = wiki_language(language)
    title = TITLES[wiki].get(species_key)
    if title is None:
        return None
    summary_url = f"https://{wiki}.wikipedia.org/api/rest_v1/page/summary/{_quote(title)}"
    try:
        summary = json.loads(_get(summary_url, "application/json"))
        if summary["type"] != "standard":  # not a disambiguation page, say
            return None
        extract = str(summary["extract"]).strip()
        shown_title = str(summary["title"])
        description = str(summary.get("description", ""))
        image = _fetch_image(summary.get("thumbnail", {}).get("source"))
    except (OSError, ValueError, KeyError, AttributeError):
        return None
    if not extract:
        return None
    return Article(shown_title, description, extract, article_url(species_key, language), image)


class ArticleLoader(QObject):
    """Loads articles off the main thread, one at a time per species, and remembers them.

    `loaded` carries the species' key and its article, or None if it couldn't be had (which is
    not remembered, so the next request tries again).
    """

    loaded = Signal(str, object)
    _done = Signal(str, object)

    def __init__(self, language: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._language = language
        self._articles: dict[str, Article] = {}
        self._loading: set[str] = set()
        self._done.connect(self._finish)  # queued: emitted from the pool's thread

    def cached(self, species_key: str) -> Article | None:
        """The article, if it was loaded before."""
        return self._articles.get(species_key)

    def request(self, species_key: str) -> None:
        """Start loading an article, unless that is already going on."""
        if species_key in self._loading:
            return
        self._loading.add(species_key)
        language = self._language

        def load() -> None:
            article = fetch_article(species_key, language)
            try:
                self._done.emit(species_key, article)
            except RuntimeError:  # the dialog closed meanwhile, and took the loader with it
                return

        QThreadPool.globalInstance().start(load)

    def _finish(self, species_key: str, article: Article | None) -> None:
        self._loading.discard(species_key)
        if article is not None:
            self._articles[species_key] = article
        self.loaded.emit(species_key, article)


def _quote(title: str) -> str:
    return urllib.parse.quote(title.replace(" ", "_"))


def _get(url: str, accept: str) -> bytes:
    request = urllib.request.Request(  # noqa: S310 - https, a Wikipedia address
        url,
        headers={
            "Accept": accept,
            # Wikimedia asks for a User-Agent that says who is asking, and how to reach them.
            "User-Agent": f"VirtualPet/{app_version()} ({REPOSITORY_URL})",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
        return response.read(MAX_BYTES)


def _fetch_image(url: object) -> bytes | None:
    """The picture at `url`, if it is one of Wikimedia's; None if there is none or it fails."""
    if not isinstance(url, str):
        return None
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not (parts.hostname or "").endswith(IMAGE_HOST_SUFFIX):
        return None
    try:
        return _get(url, "image/*")
    except OSError:
        return None  # the text alone is still worth showing
