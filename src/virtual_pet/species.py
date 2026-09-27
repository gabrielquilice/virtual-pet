"""A kind of pet: how it looks, how it gets around and what it is called."""

import functools
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from PySide6.QtGui import QImage

from virtual_pet.behavior import Activity, Gait
from virtual_pet.i18n import QT_TRANSLATE_NOOP
from virtual_pet.sprites import EYE, EYE_SHINE, Animation, Frame, draw_columns

BODY = "B"  # palette key of the main fur/feather color (it covers the eye when blinking)
DARKEST = "N"  # palette key of the darkest detail (a closed eye is drawn with it)


class Locomotion(Enum):
    """How a kind of pet roams (its WALKING animation); the value is the menu text for it."""

    WALK = QT_TRANSLATE_NOOP("PetWindow", "Walk")
    FLY = QT_TRANSLATE_NOOP("PetWindow", "Fly")
    SWIM = QT_TRANSLATE_NOOP("PetWindow", "Swim")
    SLITHER = QT_TRANSLATE_NOOP("PetWindow", "Slither")
    HOP = QT_TRANSLATE_NOOP("PetWindow", "Hop")
    CRAWL = QT_TRANSLATE_NOOP("PetWindow", "Crawl")


@dataclass(frozen=True, eq=False)  # each species is one of a kind: compared by identity
class Species:
    """Everything that makes a dog a dog, a cat a cat..."""

    key: str  # stored in the settings file
    label: str  # shown to the user, translated in the "Species" context
    palette: Mapping[str, str]  # art character -> color; must define BODY and DARKEST
    animations: Mapping[Activity, Animation]
    gait: Gait
    locomotion: Locomotion = Locomotion.WALK
    # Menu text for making it sit (whatever sitting looks like for it), like the roam label.
    sit_label: str = QT_TRANSLATE_NOOP("PetWindow", "Sit")
    # Other palettes it can turn, like the chameleon, defining the same characters as `palette`.
    colorings: tuple[Mapping[str, str], ...] = ()

    @property
    def roam_label(self) -> str:
        """Menu text for letting the pet move around again, translated in "PetWindow"."""
        return self.locomotion.value

    @property
    def portrait(self) -> Frame:
        """The frame that stands for this species in dialogs."""
        return self.animations[Activity.STANDING].frames[0]

    @property
    def palettes(self) -> tuple[Mapping[str, str], ...]:
        """Its usual palette, then the colorings it can turn (see color_change.py)."""
        return (self.palette, *self.colorings)

    def image(
        self, frame: Frame, *, blinking: bool = False, colors: tuple[int, ...] | None = None
    ) -> QImage:
        """Draw a frame in this species' colors, one image pixel per art pixel.

        `colors` gives each column's palette, as an index into `palettes`; None is the usual one.
        """
        return _render(self, frame, blinking=blinking, colors=colors)


@functools.lru_cache(maxsize=1024)  # a color wave goes through many column combinations
def _render(
    species: Species, frame: Frame, *, blinking: bool, colors: tuple[int, ...] | None
) -> QImage:
    palettes = [dict(palette) for palette in species.palettes]
    if blinking:
        for palette in palettes:
            palette |= {EYE: palette[BODY], EYE_SHINE: palette[DARKEST]}
    return draw_columns(frame, palettes, colors or (0,) * len(frame[0]))
