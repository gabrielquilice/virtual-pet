import random

import pytest

from virtual_pet.behavior import Activity
from virtual_pet.color_change import FIRST_CHANGE, WAVE_SPEED, ColorChange

WIDTH = 32
WAVE_TIME = WIDTH / WAVE_SPEED  # seconds for a wave to run from the head to the tail
USUAL = (0,) * WIDTH


def make(colorings: int = 4, seed: int = 1) -> ColorChange:
    return ColorChange(colorings, WIDTH, random.Random(seed))


def run(change: ColorChange, seconds: float, activity: Activity, step: float = 0.1) -> None:
    for _ in range(round(seconds / step)):
        change.tick(step, activity)


def solid(columns: tuple[int, ...]) -> bool:
    return len(set(columns)) == 1


def test_it_starts_in_its_usual_colors():
    assert make().columns == USUAL


def test_a_pet_with_one_coloring_never_changes():
    change = make(colorings=1)

    run(change, 60, Activity.STANDING)

    assert change.columns == USUAL


@pytest.mark.parametrize("activity", [Activity.STANDING, Activity.SITTING])
def test_standing_still_it_soon_turns_another_color(activity):
    change = make()

    run(change, FIRST_CHANGE + WAVE_TIME + 0.2, activity)

    assert solid(change.columns)
    assert change.columns != USUAL


def test_the_new_color_runs_from_the_head_to_the_tail():
    change = make()
    run(change, FIRST_CHANGE + 0.1, Activity.STANDING)

    run(change, WAVE_TIME / 2, Activity.STANDING)

    columns = change.columns
    new = columns[-1]  # frames face right: the head is on the right
    assert new != 0
    assert columns[: WIDTH // 2 - 2] == (0,) * (WIDTH // 2 - 2)  # the tail half not yet
    assert columns[WIDTH // 2 + 2 :] == (new,) * (WIDTH // 2 - 2)  # the head half already
    assert set(columns) == {0, new}


def test_sitting_it_keeps_changing_color():
    change = make()
    seen = set()

    for _ in range(60):
        run(change, 1, Activity.SITTING)
        if solid(change.columns):
            seen.add(change.columns[0])

    assert len(seen) >= 3


def test_every_change_is_to_a_different_color():
    change = make(colorings=2)  # the only other color is its usual one
    colors = [0]

    for _ in range(600):  # a minute
        change.tick(0.1, Activity.SITTING)
        if solid(change.columns) and change.columns[0] != colors[-1]:
            colors.append(change.columns[0])

    # A wave starts at most 8 s after the last one, and each is a visible change.
    assert len(colors) >= 8
    assert colors[:4] == [0, 1, 0, 1]


def test_walking_again_the_same_wave_brings_back_its_usual_colors():
    change = make()
    run(change, FIRST_CHANGE + WAVE_TIME + 0.2, Activity.STANDING)
    turned = change.columns

    run(change, WAVE_TIME / 2, Activity.WALKING)

    assert change.columns[-1] == 0  # the head first
    assert change.columns[0] == turned[0]  # the tail still in the other color
    run(change, WAVE_TIME / 2 + 0.2, Activity.WALKING)
    assert change.columns == USUAL


def test_walking_it_keeps_its_usual_colors():
    change = make()

    run(change, 30, Activity.WALKING)

    assert change.columns == USUAL


def test_walking_off_in_the_middle_of_a_wave_turns_it_back_from_the_head():
    change = make()
    run(change, FIRST_CHANGE + WAVE_TIME / 2, Activity.STANDING)

    run(change, WAVE_TIME + 0.2, Activity.WALKING)

    assert change.columns == USUAL


def test_carried_its_color_freezes_even_in_the_middle_of_a_wave():
    change = make()
    run(change, FIRST_CHANGE + WAVE_TIME / 2, Activity.STANDING)
    frozen = change.columns

    run(change, 20, Activity.CARRIED)

    assert change.columns == frozen
    assert not solid(frozen)


def test_put_down_the_wave_goes_on_from_where_it_stopped():
    change = make()
    run(change, FIRST_CHANGE + WAVE_TIME / 2, Activity.STANDING)
    run(change, 5, Activity.CARRIED)

    run(change, WAVE_TIME / 2 + 0.2, Activity.STANDING)

    assert solid(change.columns)
    assert change.columns != USUAL


def test_a_long_gap_moves_the_wave_on_without_going_past_the_tail():
    change = make()
    run(change, FIRST_CHANGE + 0.1, Activity.STANDING)

    change.tick(100, Activity.STANDING)

    assert solid(change.columns)
