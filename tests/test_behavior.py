import math
import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from virtual_pet.behavior import Activity, Area, Facing, Gait, PetBehavior

SCREEN = Area(left=0, top=0, right=1000, bottom=600)


def run(pet: PetBehavior, seconds: float, step: float = 0.05) -> None:
    for _ in range(round(seconds / step)):
        pet.tick(step)


def test_sitting_pet_stays_where_it_is():
    pet = PetBehavior(SCREEN, (300, 200), sitting=True, rng=random.Random(1))

    run(pet, 30)

    assert pet.position == (300, 200)
    assert pet.activity is Activity.SITTING


def test_roaming_pet_walks_away_on_its_own():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(2))
    activities = set()

    for _ in range(200):
        pet.tick(0.05)
        activities.add(pet.activity)

    assert Activity.WALKING in activities
    assert pet.position != (500, 300)


def test_roaming_pet_pauses_between_strolls():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(3))
    longest_rest = rest = 0.0

    for _ in range(1200):  # one minute
        before = pet.position
        pet.tick(0.05)
        if pet.activity is Activity.STANDING and pet.position == before:
            rest += 0.05
            longest_rest = max(longest_rest, rest)
        else:
            rest = 0.0

    assert longest_rest >= 1.0


def assert_inside(pet: PetBehavior, area: Area) -> None:
    x, y = pet.position
    assert area.left <= x <= area.right
    assert area.top <= y <= area.bottom


@given(
    seed=st.integers(0, 2**32),
    width=st.integers(0, 1920),
    height=st.integers(0, 1080),
    start=st.tuples(st.floats(-5000, 5000), st.floats(-5000, 5000)),
    ticks=st.lists(st.floats(0, 0.5), max_size=300),
)
def test_roaming_pet_never_leaves_its_area(seed, width, height, start, ticks):
    area = Area(left=100, top=50, right=100 + width, bottom=50 + height)
    pet = PetBehavior(area, start, rng=random.Random(seed))

    assert_inside(pet, area)
    for seconds in ticks:
        pet.tick(seconds)
        assert_inside(pet, area)


def test_clicked_roaming_pet_sits_and_stays():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(4))
    run(pet, 3)

    pet.toggle_sitting()
    spot = pet.position
    run(pet, 30)

    assert pet.activity is Activity.SITTING
    assert pet.position == spot


def test_clicked_sitting_pet_gets_up_and_walks_right_away():
    pet = PetBehavior(SCREEN, (500, 300), sitting=True, rng=random.Random(5))

    pet.toggle_sitting()
    pet.tick(0.05)

    assert pet.activity is Activity.WALKING


def test_carried_pet_cannot_be_moved_off_its_area():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(6))

    pet.pick_up()
    pet.move_to(5000, -900)

    assert pet.activity is Activity.CARRIED
    assert pet.position == (1000, 0)


def test_carried_pet_does_not_walk_while_held():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(7))

    pet.pick_up()
    pet.move_to(200, 100)
    run(pet, 10)

    assert pet.position == (200, 100)


def test_sitting_pet_put_down_keeps_sitting_at_the_new_spot():
    pet = PetBehavior(SCREEN, (500, 300), sitting=True, rng=random.Random(8))

    pet.pick_up()
    pet.move_to(120, 80)
    pet.put_down()
    run(pet, 10)

    assert pet.activity is Activity.SITTING
    assert pet.position == (120, 80)


def test_roaming_pet_put_down_strolls_again_from_the_new_spot():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(9))

    pet.pick_up()
    pet.move_to(120, 80)
    pet.put_down()
    run(pet, 10)

    assert pet.activity is not Activity.CARRIED
    assert pet.position != (120, 80)


def test_pet_stays_inside_when_its_area_shrinks():
    pet = PetBehavior(SCREEN, (900, 500), rng=random.Random(10))
    run(pet, 2)
    smaller = Area(left=0, top=0, right=400, bottom=300)

    pet.set_area(smaller)

    assert_inside(pet, smaller)
    for _ in range(600):
        pet.tick(0.05)
        assert_inside(pet, smaller)


@pytest.mark.parametrize(("start_x", "expected"), [(0, Facing.RIGHT), (1000, Facing.LEFT)])
def test_pet_faces_the_way_it_walks(start_x, expected):
    pet = PetBehavior(SCREEN, (start_x, 300), rng=random.Random(11))

    for _ in range(100):
        pet.tick(0.05)
        if pet.activity is Activity.WALKING:
            break

    assert pet.activity is Activity.WALKING
    assert pet.facing is expected


def test_long_gap_between_ticks_does_not_teleport_the_pet():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(12))
    while pet.activity is not Activity.WALKING:
        pet.tick(0.05)
    before = pet.position

    pet.tick(3600)  # e.g. the computer just woke up from sleep

    assert math.dist(before, pet.position) <= 10


def start_walking(pet: PetBehavior) -> None:
    for _ in range(100):
        pet.tick(0.05)
        if pet.activity is Activity.WALKING:
            return
    pytest.fail("the pet never started walking")


@pytest.mark.parametrize(("speed", "expected_distance"), [(45, 22.5), (80, 40.0)])
def test_pet_moves_at_its_own_speed(speed, expected_distance):
    gait = Gait(speed=speed, max_slope=0.4, distance=(200, 300))
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(13), gait=gait)
    start_walking(pet)
    before = pet.position

    for _ in range(5):  # half a second
        pet.tick(0.1)

    assert math.dist(before, pet.position) == pytest.approx(expected_distance)


def test_strolls_are_never_steeper_than_the_gait_allows():
    area = Area(left=0, top=0, right=100_000, bottom=100_000)
    gait = Gait(speed=100, max_slope=0.25, distance=(80, 320))
    pet = PetBehavior(area, (50_000, 50_000), rng=random.Random(14), gait=gait)
    slopes = []

    for _ in range(2000):
        before = pet.position
        pet.tick(0.05)
        dx, dy = pet.position[0] - before[0], pet.position[1] - before[1]
        if dx:
            slopes.append(abs(dy / dx))

    assert slopes
    assert max(slopes) <= 0.25 + 1e-9


def test_a_new_gait_applies_to_the_ongoing_stroll():
    pet = PetBehavior(
        SCREEN,
        (500, 300),
        rng=random.Random(15),
        gait=Gait(speed=45, max_slope=0.4, distance=(200, 300)),
    )
    start_walking(pet)

    pet.set_gait(Gait(speed=80, max_slope=1.0, distance=(120, 420)))
    before = pet.position
    for _ in range(5):
        pet.tick(0.1)

    assert math.dist(before, pet.position) == pytest.approx(40.0)
