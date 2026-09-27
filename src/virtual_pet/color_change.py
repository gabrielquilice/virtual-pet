"""How a pet that changes color (the chameleon) does it: in waves from its head to its tail.

This module is plain Python (no Qt), like behavior.py. A species has a few colorings, whole
palettes: the first is its usual one, the others are what it turns while it keeps still. Each
column of its frames shows one coloring. A wave paints the columns in a new one, from the head
(the right edge, as frames face right) to the tail.
"""

import math
import random

from virtual_pet.behavior import Activity

WAVE_SPEED = 16.0  # columns per second: head to tail in 2 s on a 32-column frame
FIRST_CHANGE = 0.5  # seconds keeping still before the first wave
CHANGE_INTERVAL = (4.0, 8.0)  # seconds from one wave to the next while it keeps still


class ColorChange:
    """Which coloring each column shows, as the pet keeps still, walks or is carried."""

    def __init__(self, colorings: int, width: int, rng: random.Random) -> None:
        self._colorings = colorings
        self._columns = [0] * width
        self._target = 0  # the coloring of the last wave, which may still be running
        self._front = 0.0  # the wave has painted the columns from here to the head
        self._until_change = FIRST_CHANGE
        self._rng = rng

    @property
    def columns(self) -> tuple[int, ...]:
        """The coloring of each column, from the tail (left) to the head (right)."""
        return tuple(self._columns)

    def tick(self, seconds: float, activity: Activity) -> None:
        """Let `seconds` go by doing `activity`."""
        if self._colorings <= 1 or activity is Activity.CARRIED:
            return  # carried, it keeps its colors as they are, even in the middle of a wave
        seconds = max(seconds, 0.0)
        if activity is Activity.WALKING:
            self._until_change = FIRST_CHANGE
            if self._target != 0:
                self._start_wave(0)  # back to its usual colors
        else:
            self._until_change -= seconds
            if self._until_change <= 0 and self._front == 0:
                others = [i for i in range(self._colorings) if i != self._target]
                self._start_wave(self._rng.choice(others))
                self._until_change = self._rng.uniform(*CHANGE_INTERVAL)
        self._front = max(self._front - WAVE_SPEED * seconds, 0.0)
        for x in range(math.ceil(self._front), len(self._columns)):
            self._columns[x] = self._target

    def _start_wave(self, coloring: int) -> None:
        self._target = coloring
        self._front = float(len(self._columns))
