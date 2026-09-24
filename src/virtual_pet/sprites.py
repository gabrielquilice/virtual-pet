"""Pixel-art building blocks shared by every pet (and by the app's icon).

A frame is a grid of characters, one per art pixel ("." is transparent), colored
through the palette of the pet's species. Frames are drawn facing right and
mirrored when the pet faces left. All frames share one canvas size, so the pet's
window never changes size.
"""

import functools
import itertools
import textwrap
from collections.abc import Mapping
from dataclasses import dataclass

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QRegion

type Frame = tuple[str, ...]

FRAME_WIDTH = 32  # art pixels
FRAME_HEIGHT = 27
PIXEL_SIZE = 3  # screen pixels per art pixel

TRANSPARENT = "."
EYE = "E"  # upper half of an open eye; takes the body color while blinking
EYE_SHINE = "H"  # eye highlight; turns dark while blinking, so the eye becomes a line


def art(text: str) -> Frame:
    """Turn an indented block of art rows into a frame."""
    return tuple(textwrap.dedent(text).strip("\n").splitlines())


def draw(frame: Frame, palette: Mapping[str, str]) -> QImage:
    """Paint a frame in the palette's colors, one image pixel per art pixel."""
    colors = {char: QColor(value) for char, value in palette.items()}
    image = QImage(len(frame[0]), len(frame), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    for y, row in enumerate(frame):
        for x, char in enumerate(row):
            if char != TRANSPARENT:
                image.setPixelColor(x, y, colors[char])
    return image


@dataclass(frozen=True)
class Animation:
    """Frames played in a loop at a fixed rate."""

    frames: tuple[Frame, ...]
    fps: float

    def frame_at(self, seconds: float) -> Frame:
        """The frame showing `seconds` after the animation started."""
        return self.frames[int(seconds * self.fps) % len(self.frames)]


@functools.cache
def mirrored(frame: Frame) -> Frame:
    """The same frame facing the other way."""
    return tuple(row[::-1] for row in frame)


@functools.cache
def silhouette(frame: Frame, scale: int) -> QRegion:
    """The region covered by visible pixels, so clicks on empty corners pass through."""
    region = QRegion()
    for y, row in enumerate(frame):
        x = 0
        for visible, run in itertools.groupby(row, key=lambda char: char != TRANSPARENT):
            length = len(list(run))
            if visible:
                region = region.united(QRect(x * scale, y * scale, length * scale, scale))
            x += length
    return region
