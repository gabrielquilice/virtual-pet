"""The hearts that float above a pet while it is being stroked.

Plain Python, so the timing can be tested without Qt. A burst is one or two hearts: they
appear one after the other, rise a little and fade out. They are drawn in a small window of
their own above the pet's (`heart_window.py`), measured in art pixels.
"""

import random
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from virtual_pet.sprites import Frame, art

PALETTE: Mapping[str, str] = {"O": "#8a1c34", "R": "#e8445f", "H": "#ff9fb0"}

BIG = art("""
    .OO..OO.
    OHHOORRO
    OHRRRRRO
    ORRRRRRO
    .ORRRRO.
    ..ORRO..
    ...OO...
""")
SMALL = art("""
    .OO.OO.
    OHRORRO
    ORRRRRO
    .ORRRO.
    ..ORO..
    ...O...
""")

WIDTH = 32  # art pixels: as wide as the pet's window
HEIGHT = 13  # art pixels: room for the hearts above the pet and the rise
RISE = 3  # art pixels a heart climbs while it lasts: little, it is only floating
LIFE = 1.2  # seconds a heart lasts
FADE = 0.4  # seconds at the end of its life in which it fades out
SECOND_HEART_DELAY = 0.3  # seconds between the first heart appearing and the second
DURATION = SECOND_HEART_DELAY + LIFE  # of a burst of two hearts: how long petting lasts


class Size(Enum):
    BIG = BIG
    SMALL = SMALL


# Where each heart starts, as (x, y) of its top-left corner: the small one first, on the left.
PAIR = ((Size.SMALL, 8, 6), (Size.BIG, 16, 4))
ALONE = {Size.SMALL: (12, 6), Size.BIG: (12, 4)}  # a single heart sits in the middle


@dataclass(frozen=True)
class Heart:
    """A heart as it shows right now."""

    frame: Frame
    x: int  # art pixels from the left of the hearts' window
    y: int  # art pixels from its top
    opacity: float  # 1 solid, 0 gone


@dataclass(frozen=True)
class _Planned:
    size: Size
    x: int
    y: int
    delay: float  # seconds after the burst starts


class HeartBurst:
    """One or two hearts that show up, drift upward and fade, started by `start()`."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng
        self._planned: tuple[_Planned, ...] = ()
        self._time = 0.0

    @property
    def active(self) -> bool:
        """Whether any heart is still to show or showing."""
        return any(self._time < planned.delay + LIFE for planned in self._planned)

    def start(self) -> None:
        """Begin a burst, in place of the one under way: a single heart or a pair."""
        self._time = 0.0
        if self._rng.random() < 0.5:  # noqa: PLR2004 - a coin toss between one heart and two
            size = self._rng.choice(tuple(Size))
            x, y = ALONE[size]
            self._planned = (_Planned(size, x, y, 0.0),)
        else:
            self._planned = tuple(
                _Planned(size, x, y, index * SECOND_HEART_DELAY)
                for index, (size, x, y) in enumerate(PAIR)
            )

    def stop(self) -> None:
        """Drop the hearts at once."""
        self._planned = ()

    def tick(self, seconds: float) -> None:
        """Let `seconds` go by."""
        self._time += seconds

    @property
    def hearts(self) -> tuple[Heart, ...]:
        """The hearts to draw now: those that have appeared and have not yet faded away."""
        shown = []
        for planned in self._planned:
            age = self._time - planned.delay
            if 0 <= age < LIFE:
                rise = round(RISE * age / LIFE)
                opacity = min(1.0, (LIFE - age) / FADE)
                shown.append(Heart(planned.size.value, planned.x, planned.y - rise, opacity))
        return tuple(shown)
