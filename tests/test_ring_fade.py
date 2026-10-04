import pytest

from virtual_pet.behavior import Activity
from virtual_pet.ring_fade import FADE_TIME, RingFade

WIDTH = 32
STEPS = 11  # palettes: the rings at their brightest (0), fainter and fainter, gone (10)
SHOWN, GONE = 0, STEPS - 1


def make(steps: int = STEPS) -> RingFade:
    return RingFade(steps, WIDTH)


def run(fade: RingFade, seconds: float, activity: Activity, step: float = 0.1) -> None:
    for _ in range(round(seconds / step)):
        fade.tick(step, activity)


def step_of(fade: RingFade) -> int:
    columns = fade.columns
    assert columns == (columns[0],) * WIDTH  # the rings fade all over the pet at once
    return columns[0]


def test_it_starts_with_its_rings_shown():
    assert step_of(make()) == SHOWN


def test_walking_its_rings_fade_out():
    fade = make()

    run(fade, FADE_TIME / 2, Activity.WALKING)
    assert SHOWN < step_of(fade) < GONE

    run(fade, FADE_TIME / 2, Activity.WALKING)
    assert step_of(fade) == GONE


@pytest.mark.parametrize("activity", [Activity.STANDING, Activity.SITTING, Activity.CARRIED])
def test_keeping_still_or_carried_its_rings_fade_back_in(activity):
    fade = make()
    run(fade, FADE_TIME, Activity.WALKING)

    run(fade, FADE_TIME / 2, activity)
    assert SHOWN < step_of(fade) < GONE

    run(fade, FADE_TIME / 2, activity)
    assert step_of(fade) == SHOWN


def test_a_fade_turns_back_from_wherever_it_got():
    fade = make()
    run(fade, FADE_TIME * 0.4, Activity.WALKING)
    faded = step_of(fade)

    run(fade, FADE_TIME * 0.2, Activity.STANDING)

    assert SHOWN < step_of(fade) < faded


def test_a_long_gap_ends_the_fade_without_overshooting():
    fade = make()

    fade.tick(10, Activity.WALKING)
    assert step_of(fade) == GONE

    fade.tick(10, Activity.STANDING)
    assert step_of(fade) == SHOWN


def test_a_pet_with_one_palette_never_fades():
    fade = make(steps=1)

    run(fade, FADE_TIME, Activity.WALKING)

    assert step_of(fade) == 0
