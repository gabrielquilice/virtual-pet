"""The small transparent window above the pet where the hearts of a stroke float."""

import functools
from collections.abc import Sequence
from typing import override

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from virtual_pet import hearts, sprites


@functools.cache
def _image(frame: sprites.Frame) -> QImage:
    return sprites.draw(frame, hearts.PALETTE)


class HeartWindow(QWidget):
    """As wide as the pet's window, and shown right above it. Clicks go through it."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.X11BypassWindowManagerHint,  # see PetWindow: never takes the focus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(hearts.WIDTH * sprites.PIXEL_SIZE, hearts.HEIGHT * sprites.PIXEL_SIZE)
        self._hearts: Sequence[hearts.Heart] = ()

    def set_hearts(self, shown: Sequence[hearts.Heart]) -> None:
        """Draw these hearts, if they are not the ones already drawn."""
        if tuple(shown) != tuple(self._hearts):
            self._hearts = shown
            self.update()

    def place_above(self, pet: QRect, screen: QRect) -> None:
        """Sit right above the pet's window, or at the top of the screen where it has no room
        (then the hearts float over the pet)."""
        self.move(pet.x(), max(screen.top(), pet.y() - self.height()))

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        with QPainter(self) as painter:
            for heart in self._hearts:
                image = _image(heart.frame)
                painter.setOpacity(heart.opacity)
                target = QRect(
                    heart.x * sprites.PIXEL_SIZE,
                    heart.y * sprites.PIXEL_SIZE,
                    image.width() * sprites.PIXEL_SIZE,
                    image.height() * sprites.PIXEL_SIZE,
                )
                painter.drawImage(target, image)
