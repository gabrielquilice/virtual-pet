"""A kind of pet: how it looks, how it gets around and what it is called."""

import functools
from collections.abc import Mapping
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage

from virtual_pet.behavior import Activity, Gait
from virtual_pet.sprites import EYE, EYE_SHINE, TRANSPARENT, Animation, Frame

BODY = "B"  # palette key of the main fur/feather color (it covers the eye when blinking)
DARKEST = "N"  # palette key of the darkest detail (a closed eye is drawn with it)


@dataclass(frozen=True, eq=False)  # each species is one of a kind: compared by identity
class Species:
    """Everything that makes a dog a dog, a cat a cat..."""

    key: str  # stored in the settings file
    label: str  # shown to the user
    palette: Mapping[str, str]  # art character -> color; must define BODY and DARKEST
    animations: Mapping[Activity, Animation]
    gait: Gait
    flies: bool = False

    @property
    def roam_label(self) -> str:
        """Menu text for letting the pet move around again."""
        return "Fly" if self.flies else "Walk"

    @property
    def portrait(self) -> Frame:
        """The frame that stands for this species in dialogs."""
        return self.animations[Activity.STANDING].frames[0]

    def image(self, frame: Frame, *, blinking: bool = False) -> QImage:
        """Draw a frame in this species' colors, one image pixel per art pixel."""
        return _render(self, frame, blinking=blinking)


@functools.cache
def _render(species: Species, frame: Frame, *, blinking: bool) -> QImage:
    palette = dict(species.palette)
    if blinking:
        palette |= {EYE: palette[BODY], EYE_SHINE: palette[DARKEST]}
    colors = {char: QColor(value) for char, value in palette.items()}
    image = QImage(len(frame[0]), len(frame), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    for y, row in enumerate(frame):
        for x, char in enumerate(row):
            if char != TRANSPARENT:
                image.setPixelColor(x, y, colors[char])
    return image
