"""The card that pops up over a pet's button in the adoption dialog with its Wikipedia article."""

import html
from typing import override

from PySide6.QtCore import QCoreApplication, QPoint, QRect, QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeyEvent, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from virtual_pet.wikipedia import Article, ArticleLoader, article_url

CARD_WIDTH = 380
IMAGE_SIZE = QSize(120, 120)  # the most a thumbnail takes; it keeps its proportions
GAP = 4  # between the button and the card


class ArticleCard(QFrame):
    """A popup with an article's picture, title and opening, and a link to the rest of it.

    It closes on a click anywhere else or on Escape, as a popup does. While the article loads it
    says so, and if it can't be had it says that instead; either way it links to the page.
    """

    def __init__(
        self, species_key: str, loader: ArticleLoader, language: str, parent: QWidget
    ) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self._species_key = species_key
        self._url = article_url(species_key, language)
        self._anchor = QRect()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        self.setFixedWidth(CARD_WIDTH)

        self._image = QLabel()
        self._image.setFixedSize(IMAGE_SIZE)
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title = QLabel()
        self._title.setWordWrap(True)
        self._title.setTextFormat(Qt.TextFormat.PlainText)
        self._description = QLabel()
        self._description.setWordWrap(True)
        self._description.setTextFormat(Qt.TextFormat.PlainText)
        titles = QVBoxLayout()
        titles.addWidget(self._title)
        titles.addWidget(self._description)
        titles.addStretch()
        top = QHBoxLayout()
        top.addWidget(self._image)
        top.addLayout(titles, 1)

        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setTextFormat(Qt.TextFormat.PlainText)
        self._footer = QLabel()
        self._footer.linkActivated.connect(self._open_article)
        self._footer.setTextFormat(Qt.TextFormat.RichText)
        self._footer.setWordWrap(True)

        self._layout = QVBoxLayout(self)
        layout = self._layout
        layout.addLayout(top)
        layout.addWidget(self._text)
        layout.addWidget(self._footer)

        self._footer.setText(self._footer_html())
        article = loader.cached(species_key)
        if article is None:
            self._show_waiting(QCoreApplication.translate("ArticleCard", "Loading…"))
            loader.loaded.connect(self._article_arrived)
            loader.request(species_key)
        else:
            self._show(article)

    def show_next_to(self, anchor: QWidget) -> None:
        """Open the card under `anchor`, or over it where there is no room below."""
        self._anchor = QRect(anchor.mapToGlobal(QPoint(0, 0)), anchor.size())
        self._place()
        self.show()

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def _open_article(self, url: str) -> None:
        """Open the article in the browser; the card has done its job."""
        QDesktopServices.openUrl(QUrl(url))
        self.close()

    def _article_arrived(self, species_key: str, article: object) -> None:
        if species_key != self._species_key:
            return
        if isinstance(article, Article):
            self._show(article)
        else:
            self._show_waiting(
                QCoreApplication.translate(
                    "ArticleCard", "Couldn't load the article. Check your connection."
                )
            )
        self._place()

    def _show(self, article: Article) -> None:
        self._title.setText(article.title)
        font = self._title.font()
        font.setBold(True)
        font.setPointSizeF(font.pointSizeF() * 1.25)
        self._title.setFont(font)
        self._description.setText(article.description)
        self._description.setVisible(bool(article.description))
        self._text.setText(article.extract)
        pixmap = QPixmap()
        if article.image is not None and pixmap.loadFromData(article.image):
            self._image.setPixmap(
                pixmap.scaled(
                    IMAGE_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self._image.show()
        else:
            self._image.hide()

    def _show_waiting(self, message: str) -> None:
        """Nothing of the article yet (or ever): just a note, and the link below."""
        self._image.hide()
        self._title.setText("")
        self._description.hide()
        self._text.setText(message)

    def _footer_html(self) -> str:
        translate = QCoreApplication.translate
        link = translate("ArticleCard", "Open on Wikipedia")
        source = translate("ArticleCard", "Text from Wikipedia, under the CC BY-SA license.")
        return (
            f'<a href="{html.escape(self._url)}">{html.escape(link)}</a><br>{html.escape(source)}'
        )

    def _place(self) -> None:
        """Under the button, as far left as it fits on its screen; over it if there is no room."""
        # Wrapped text is as tall as its width makes it, which adjustSize() doesn't ask for.
        self._layout.invalidate()  # the text just changed: its cached sizes are the old ones
        self._layout.activate()
        frame = 2 * self.frameWidth()  # the layout has the width inside the frame
        size = QSize(CARD_WIDTH, self._layout.totalHeightForWidth(CARD_WIDTH - frame) + frame)
        self.setFixedHeight(size.height())
        screen = QGuiApplication.screenAt(self._anchor.center()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        x = min(max(self._anchor.left(), area.left()), area.right() - size.width() + 1)
        y = self._anchor.bottom() + GAP
        if y + size.height() > area.bottom() + 1:
            y = max(self._anchor.top() - GAP - size.height(), area.top())
        self.setGeometry(x, y, size.width(), size.height())
