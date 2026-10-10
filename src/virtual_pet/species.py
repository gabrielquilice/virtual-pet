"""A kind of pet: how it looks, how it gets around and what it is called."""

import functools
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto

from PySide6.QtGui import QImage

from virtual_pet.behavior import Activity, Gait
from virtual_pet.i18n import QT_TRANSLATE_NOOP
from virtual_pet.sprites import EYE, EYE_SHINE, Animation, Frame, draw_columns

BODY = "B"  # palette key of the main fur/feather color (it covers the eye when blinking)
DARKEST = "N"  # palette key of the darkest detail (a closed eye is drawn with it)


@dataclass(frozen=True)
class BlinkStep:
    """How a pet's eye looks for a moment of a blink."""

    look: Mapping[str, str]  # art character -> the palette character it is drawn in meanwhile
    seconds: float


# Most pets blink in one go: the body color over the eye, its shine a dark line across it.
BLINK = (BlinkStep({EYE: BODY, EYE_SHINE: DARKEST}, 0.15),)


class Locomotion(Enum):
    """How a kind of pet roams (its WALKING animation); the value is the menu text for it."""

    WALK = QT_TRANSLATE_NOOP("PetWindow", "Walk")
    FLY = QT_TRANSLATE_NOOP("PetWindow", "Fly")
    SWIM = QT_TRANSLATE_NOOP("PetWindow", "Swim")
    SLITHER = QT_TRANSLATE_NOOP("PetWindow", "Slither")
    HOP = QT_TRANSLATE_NOOP("PetWindow", "Hop")
    CRAWL = QT_TRANSLATE_NOOP("PetWindow", "Crawl")


class ColorShift(Enum):
    """How a species with colorings goes from one to another."""

    WAVES = auto()  # the chameleon: a new coloring runs from head to tail (color_change.py)
    FADE = auto()  # the octopus: its colorings are steps of its rings fading away (ring_fade.py)


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
    # Other palettes it can turn, like the chameleon, defining the same characters as `palette`,
    # and how it goes from one to another.
    colorings: tuple[Mapping[str, str], ...] = ()
    color_shift: ColorShift = ColorShift.WAVES
    # How its eye closes and opens again, step by step, like the owl's lid coming down.
    blink: tuple[BlinkStep, ...] = BLINK

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
        """Its usual palette, then the colorings it can turn (see `color_shift`)."""
        return (self.palette, *self.colorings)

    @property
    def blink_time(self) -> float:
        """How long a blink of its lasts, in seconds."""
        return sum(step.seconds for step in self.blink)

    def blink_step(self, seconds: float) -> int:
        """The step of its blink `seconds` after the blink began, from 1; 0 once it is over."""
        for number, step in enumerate(self.blink, start=1):
            seconds -= step.seconds
            if seconds < 0:
                return number
        return 0

    def image(
        self, frame: Frame, *, blink: int = 0, colors: tuple[int, ...] | None = None
    ) -> QImage:
        """Draw a frame in this species' colors, one image pixel per art pixel.

        `blink` is the step of a blink the eye is at (see `blink_step`); 0 is open.
        `colors` gives each column's palette, as an index into `palettes`; None is the usual one.
        """
        return _render(self, frame, blink=blink, colors=colors)


@functools.lru_cache(maxsize=1024)  # a color wave goes through many column combinations
def _render(
    species: Species, frame: Frame, *, blink: int, colors: tuple[int, ...] | None
) -> QImage:
    palettes = [dict(palette) for palette in species.palettes]
    if blink:
        look = species.blink[blink - 1].look
        for palette in palettes:
            palette |= {char: palette[shown] for char, shown in look.items()}
    return draw_columns(frame, palettes, colors or (0,) * len(frame[0]))
