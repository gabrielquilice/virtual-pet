"""The pet's brain: where it walks, when it rests and how it reacts to the user.

This module is plain Python (no Qt) so the behavior can be tested in isolation.
Positions are the top-left corner of the pet's window, in screen coordinates.
"""

import math
import random
from dataclasses import dataclass
from enum import Enum, auto

REST_TIME = (1.5, 5.0)  # seconds standing still between strolls
LANDING_REST_TIME = (0.5, 1.2)  # seconds before strolling after appearing or being put down
MAX_TICK = 0.1  # longer gaps (e.g. waking up from sleep) are not simulated


class Activity(Enum):
    """What the pet is doing right now; it decides which animation is shown."""

    STANDING = auto()
    WALKING = auto()
    SITTING = auto()
    CARRIED = auto()


class Facing(Enum):
    """Which way the pet looks. Sprites are drawn facing right."""

    LEFT = auto()
    RIGHT = auto()


@dataclass(frozen=True)
class Gait:
    """How a kind of pet gets around."""

    speed: float = 45.0  # pixels per second
    max_slope: float = 0.4  # steepest stroll (vertical / horizontal); low values suit side views
    distance: tuple[float, float] = (80.0, 320.0)  # length range of a single stroll


DEFAULT_GAIT = Gait()


@dataclass(frozen=True)
class Area:
    """Rectangle the pet's top-left corner may occupy (bounds are inclusive)."""

    left: float
    top: float
    right: float
    bottom: float

    def clamp(self, x: float, y: float) -> tuple[float, float]:
        """Closest point to (x, y) inside the area (its top-left corner if it is empty)."""
        return (max(self.left, min(x, self.right)), max(self.top, min(y, self.bottom)))


class PetBehavior:
    """State machine of a pet that strolls around, sits on command and can be carried."""

    def __init__(
        self,
        area: Area,
        position: tuple[float, float],
        *,
        sitting: bool = False,
        rng: random.Random | None = None,
        gait: Gait = DEFAULT_GAIT,
    ) -> None:
        self._area = area
        self._gait = gait
        self._x, self._y = area.clamp(*position)
        self._sitting = sitting
        self._carried = False
        self._facing = Facing.RIGHT
        self._rng = rng if rng is not None else random.Random()  # noqa: S311 - not security related
        self._target: tuple[float, float] | None = None
        self._rest_left = self._rng.uniform(*LANDING_REST_TIME)

    @property
    def position(self) -> tuple[float, float]:
        return (self._x, self._y)

    @property
    def facing(self) -> Facing:
        return self._facing

    @property
    def sitting(self) -> bool:
        """Whether the user told the pet to sit (it keeps sitting after being carried)."""
        return self._sitting

    @property
    def activity(self) -> Activity:
        if self._carried:
            return Activity.CARRIED
        if self._sitting:
            return Activity.SITTING
        if self._target is not None:
            return Activity.WALKING
        return Activity.STANDING

    def tick(self, seconds: float) -> None:
        """Advance the simulation by `seconds`."""
        if self._sitting or self._carried:
            return
        seconds = min(max(seconds, 0.0), MAX_TICK)
        target = self._target
        if target is None:
            self._rest_left -= seconds
            if self._rest_left <= 0:
                self._start_stroll()
            return
        dx, dy = target[0] - self._x, target[1] - self._y
        distance = math.hypot(dx, dy)
        step = self._gait.speed * seconds
        if distance <= step:
            self._x, self._y = target
            self._target = None
            self._rest_left = self._rng.uniform(*REST_TIME)
        else:
            self._x += dx / distance * step
            self._y += dy / distance * step

    def toggle_sitting(self) -> None:
        """Sit down and stay if roaming; get up if sitting (what a click on the pet does)."""
        self._sitting = not self._sitting
        self._target = None
        self._rest_left = 0.0  # when getting up, go for a stroll immediately

    def pick_up(self) -> None:
        """The user grabbed the pet."""
        self._carried = True
        self._target = None

    def move_to(self, x: float, y: float) -> None:
        """Place the pet as close to (x, y) as its area allows."""
        self._x, self._y = self._area.clamp(x, y)

    def put_down(self) -> None:
        """The user let go: back to sitting or, after a short pause, to strolling."""
        self._carried = False
        self._rest_left = self._rng.uniform(*LANDING_REST_TIME)

    def set_area(self, area: Area) -> None:
        """Switch to a new allowed area (another screen, a resolution change...)."""
        self._area = area
        self._x, self._y = area.clamp(self._x, self._y)
        if self._target is not None:
            self._target = area.clamp(*self._target)

    def set_gait(self, gait: Gait) -> None:
        """Move the way another kind of pet does, from now on."""
        self._gait = gait

    def _start_stroll(self) -> None:
        gait = self._gait
        distance = self._rng.uniform(*gait.distance)
        direction = self._rng.choice((-1.0, 1.0))
        rise = self._rng.uniform(-gait.max_slope, gait.max_slope) * distance
        target = self._area.clamp(self._x + direction * distance, self._y + rise)
        if abs(target[0] - self._x) < gait.distance[0] / 2:
            # A wall is close on that side: head the other way instead.
            target = self._area.clamp(self._x - direction * distance, self._y + rise)
        self._target = target
        if target[0] != self._x:
            self._facing = Facing.RIGHT if target[0] > self._x else Facing.LEFT
