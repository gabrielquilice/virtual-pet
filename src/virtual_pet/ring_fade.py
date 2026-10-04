"""How the blue-ringed octopus shows its rings: they fade in as it keeps still, out as it moves.

This module is plain Python (no Qt), like behavior.py. A species that fades has its palettes in
steps: the first, its usual one, shows the rings at their brightest, each next one fainter, and
the last hides them in the color of its body. The whole pet shows the same step.
"""

from virtual_pet.behavior import Activity

FADE_TIME = 1.0  # seconds for the rings to come or go entirely


class RingFade:
    """Which step of the fade the pet shows, as it walks, keeps still or is carried."""

    def __init__(self, steps: int, width: int) -> None:
        self._last = steps - 1  # the step with no rings
        self._width = width
        self._faded = 0.0  # how far the rings have faded: 0 at their brightest, 1 gone

    @property
    def columns(self) -> tuple[int, ...]:
        """The step of each column, as ColorChange gives each column's coloring."""
        return (round(self._faded * self._last),) * self._width

    def tick(self, seconds: float, activity: Activity) -> None:
        """Let `seconds` go by doing `activity`."""
        target = 1.0 if activity is Activity.WALKING else 0.0
        change = max(seconds, 0.0) / FADE_TIME
        if self._faded < target:
            self._faded = min(self._faded + change, target)
        else:
            self._faded = max(self._faded - change, target)
