"""The pet's brain: where it walks, when it rests and how it reacts to the user.

This module is plain Python (no Qt) so the behavior can be tested in isolation.
Positions are the top-left corner of the pet's window, in screen coordinates.
"""

import math
import random
from dataclasses import dataclass
from enum import Enum, auto

REST_TIME = (1.5, 5.0)  # seconds standing still between strolls, unless the gait says
LANDING_REST_TIME = (0.5, 1.2)  # seconds before strolling after appearing or being put down
MAX_TICK = 0.1  # longer gaps (e.g. waking up from sleep) are not simulated
THROW_SPEED = 1400.0  # pixels per second the pet must be moving at when let go to be thrown
MAX_THROW_SPEED = 2000.0  # a faster flick is thrown at this speed
THROW_FRICTION = 2500.0  # pixels per second squared slowing a thrown pet until it stops
BOUNCE = 0.2  # share of its speed a pet thrown at the usual strength keeps after hitting a wall
DEFAULT_THROW_STRENGTH = (
    100  # percent of the usual strength a pet is thrown with: it scales its speed and its bounce
)
THROW_STRENGTH_RANGE = (25, 225)  # the least and the most the settings allow
STOP_SPEED = 40.0  # a thrown pet slower than this stops
PETTING_TIME = 1.5  # seconds a pet being stroked keeps still


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
    rest: tuple[float, float] = REST_TIME  # seconds standing still between strolls


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
    """State machine of a pet that strolls around, sits or turns on command and can be carried."""

    def __init__(  # noqa: PLR0913 - the state it starts in, as keywords with defaults
        self,
        area: Area,
        position: tuple[float, float],
        *,
        sitting: bool = False,
        facing: Facing = Facing.RIGHT,
        rng: random.Random | None = None,
        gait: Gait = DEFAULT_GAIT,
    ) -> None:
        self._area = area
        self._gait = gait
        self._x, self._y = area.clamp(*position)
        self._sitting = sitting
        self._carried = False
        self._velocity: tuple[float, float] | None = None  # set while a thrown pet is in flight
        self._bounce = BOUNCE  # of the throw in flight: the stronger, the more
        self._facing = facing
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
    def flying(self) -> bool:
        """Whether the pet was thrown and hasn't come to rest yet."""
        return self._velocity is not None

    @property
    def activity(self) -> Activity:
        if self._carried or self._velocity is not None:
            return Activity.CARRIED
        if self._sitting:
            return Activity.SITTING
        if self._target is not None:
            return Activity.WALKING
        return Activity.STANDING

    def tick(self, seconds: float) -> None:
        """Advance the simulation by `seconds`."""
        if self._carried:
            return
        seconds = min(max(seconds, 0.0), MAX_TICK)
        if self._velocity is not None:
            self._fly(seconds, self._velocity)
            return
        if self._sitting:
            return
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
            self._end_stroll()
        else:
            self._x += dx / distance * step
            self._y += dy / distance * step

    def toggle_sitting(self) -> None:
        """Sit down and stay if roaming; get up if sitting (what a click on the pet does)."""
        self._sitting = not self._sitting
        self._target = None
        self._rest_left = 0.0  # when getting up, go for a stroll immediately

    def pet(self) -> None:
        """The user strokes the pet: a roaming pet stops and keeps still a moment, a sitting one
        stays sitting. Nothing happens to one that is carried or flying."""
        if self._carried or self._velocity is not None:
            return
        self._target = None
        self._rest_left = max(self._rest_left, PETTING_TIME)

    def turn_around(self) -> None:
        """Face the other way; a walking pet takes the rest of its stroll that way.

        The stroll is mirrored, so it keeps its slope. A wall in the way ends it early, and at
        once if the pet is against that wall: then it only turns to face it.
        """
        self._facing = Facing.LEFT if self._facing is Facing.RIGHT else Facing.RIGHT
        if self._target is None:
            return
        target_x, target_y = self._target
        dx = target_x - self._x
        if dx == 0:  # a stroll straight up or down, in an area no wider than the window
            return
        wall = self._area.left if dx > 0 else self._area.right
        room = abs(wall - self._x)
        if room == 0:
            self._end_stroll()
        elif room < abs(dx):
            rise = (target_y - self._y) * room / abs(dx)
            self._target = self._area.clamp(wall, self._y + rise)
        else:
            self._target = self._area.clamp(self._x - dx, target_y)

    def pick_up(self) -> None:
        """The user grabbed the pet."""
        self._carried = True
        self._velocity = None
        self._target = None

    def move_to(self, x: float, y: float) -> None:
        """Place the pet as close to (x, y) as its area allows."""
        self._x, self._y = self._area.clamp(x, y)

    def put_down(
        self,
        velocity: tuple[float, float] = (0.0, 0.0),
        throw_strength: int = DEFAULT_THROW_STRENGTH,
    ) -> None:
        """The user let go: back to sitting or, after a short pause, to strolling.

        Let go while moving at `velocity` (pixels per second) faster than `THROW_SPEED`, the pet
        is thrown instead: it flies, still looking carried, until it comes to rest. It takes off at
        `throw_strength` percent of that speed, and bounces off walls in proportion to it.
        """
        self._carried = False
        self._rest_left = self._rng.uniform(*LANDING_REST_TIME)
        speed = math.hypot(*velocity)
        if speed >= THROW_SPEED:
            scale = min(speed, MAX_THROW_SPEED) / speed * throw_strength / 100
            self._velocity = (velocity[0] * scale, velocity[1] * scale)
            self._bounce = BOUNCE * throw_strength / 100

    def set_area(self, area: Area) -> None:
        """Switch to a new allowed area (another screen, a resolution change...)."""
        self._area = area
        self._x, self._y = area.clamp(self._x, self._y)
        if self._target is not None:
            self._target = area.clamp(*self._target)

    def set_gait(self, gait: Gait) -> None:
        """Move the way another kind of pet does, from now on."""
        self._gait = gait

    def _fly(self, seconds: float, velocity: tuple[float, float]) -> None:
        """Move a thrown pet: it slows down by friction and a wall sends it back, weakly."""
        vx, vy = velocity
        speed = math.hypot(vx, vy)
        slower = max(speed - THROW_FRICTION * seconds, 0.0) / speed
        vx, vy = vx * slower, vy * slower
        x, y = self._x + vx * seconds, self._y + vy * seconds
        if x < self._area.left or x > self._area.right:
            vx = -vx * self._bounce
        if y < self._area.top or y > self._area.bottom:
            vy = -vy * self._bounce
        self._x, self._y = self._area.clamp(x, y)
        if math.hypot(vx, vy) < STOP_SPEED:
            self._velocity = None
            self._rest_left = self._rng.uniform(*LANDING_REST_TIME)
        else:
            self._velocity = (vx, vy)

    def _end_stroll(self) -> None:
        """Stop walking and rest a while before the next stroll."""
        self._target = None
        self._rest_left = self._rng.uniform(*self._gait.rest)

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
