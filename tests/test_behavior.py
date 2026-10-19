import math
import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from virtual_pet.behavior import PETTING_TIME, Activity, Area, Facing, Gait, PetBehavior

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


def rests_between_strolls(pet: PetBehavior, strolls: int) -> list[float]:
    """How long the pet stands still after each of its next strolls."""
    rests: list[float] = []
    rest = None  # seconds since the last stroll ended
    was_walking = False
    for _ in range(100_000):
        walking = pet.activity is Activity.WALKING
        if walking and rest is not None:
            rests.append(rest)
            if len(rests) == strolls:
                return rests
            rest = None
        elif was_walking and not walking:
            rest = 0.0
        if rest is not None:
            rest += 0.05
        was_walking = walking
        pet.tick(0.05)
    pytest.fail("the pet stopped strolling")


def test_pauses_last_as_long_as_the_gait_rests():
    gait = Gait(speed=200, max_slope=0.4, distance=(80, 120), rest=(4.0, 8.0))
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(16), gait=gait)

    rests = rests_between_strolls(pet, 10)

    assert all(4.0 - 0.1 <= rest <= 8.0 + 0.1 for rest in rests)


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


def walk_to_the_end_of_the_stroll(pet: PetBehavior) -> None:
    for _ in range(1000):
        if pet.activity is not Activity.WALKING:
            return
        pet.tick(0.05)
    pytest.fail("the pet never stopped walking")


def test_turned_standing_pet_faces_the_other_way_and_back():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(16))

    pet.turn_around()
    turned = pet.facing
    pet.turn_around()

    assert (turned, pet.facing) == (Facing.LEFT, Facing.RIGHT)
    assert (pet.activity, pet.position) == (Activity.STANDING, (500, 300))


def test_sitting_pet_turns_where_it_sits():
    pet = PetBehavior(SCREEN, (300, 200), sitting=True, rng=random.Random(17))

    pet.turn_around()
    run(pet, 30)

    assert (pet.activity, pet.facing, pet.position) == (Activity.SITTING, Facing.LEFT, (300, 200))


def test_turned_walking_pet_takes_the_rest_of_its_stroll_the_other_way():
    turned, twin = (PetBehavior(SCREEN, (500, 300), rng=random.Random(18)) for _ in range(2))
    for pet in (turned, twin):
        start_walking(pet)
        run(pet, 0.5)
    facing, (x, _) = turned.facing, turned.position

    turned.turn_around()
    walk_to_the_end_of_the_stroll(turned)
    walk_to_the_end_of_the_stroll(twin)  # where the stroll would have ended

    assert turned.facing is not facing
    assert turned.position == pytest.approx((2 * x - twin.position[0], twin.position[1]))


def slope(start: tuple[float, float], end: tuple[float, float]) -> float:
    return abs((end[1] - start[1]) / (end[0] - start[0]))


def test_pet_turned_toward_a_close_wall_walks_up_to_it_at_the_same_slope():
    pet = PetBehavior(SCREEN, (0, 300), rng=random.Random(19))
    start_walking(pet)  # away from the wall behind it
    start = pet.position
    run(pet, 0.5)
    turned_at = pet.position

    pet.turn_around()
    walk_to_the_end_of_the_stroll(pet)

    assert (pet.position[0], pet.facing) == (SCREEN.left, Facing.LEFT)
    assert slope(turned_at, pet.position) == pytest.approx(slope(start, turned_at))


def test_pet_turned_against_a_wall_stops_to_face_it():
    pet = PetBehavior(SCREEN, (0, 300), rng=random.Random(20))
    start_walking(pet)  # away from the wall behind it

    pet.turn_around()

    assert (pet.activity, pet.facing, pet.position) == (Activity.STANDING, Facing.LEFT, (0, 300))


def test_pet_strolling_straight_up_or_down_keeps_going_when_turned():
    column = Area(left=100, top=0, right=100, bottom=600)  # no wider than the pet's window
    turned, twin = (PetBehavior(column, (100, 300), rng=random.Random(21)) for _ in range(2))
    for pet in (turned, twin):
        start_walking(pet)
    facing = turned.facing

    turned.turn_around()
    walk_to_the_end_of_the_stroll(turned)
    walk_to_the_end_of_the_stroll(twin)

    assert turned.facing is not facing
    assert turned.position == twin.position != (100, 300)


@given(
    seed=st.integers(0, 2**32),
    width=st.integers(0, 1920),
    height=st.integers(0, 1080),
    start=st.tuples(st.floats(-5000, 5000), st.floats(-5000, 5000)),
    steps=st.lists(st.tuples(st.floats(0, 0.5), st.booleans()), max_size=300),
)
def test_turning_never_takes_the_pet_off_its_area(seed, width, height, start, steps):
    area = Area(left=100, top=50, right=100 + width, bottom=50 + height)
    pet = PetBehavior(area, start, rng=random.Random(seed))

    for seconds, turn in steps:
        if turn:
            pet.turn_around()
        pet.tick(seconds)
        assert_inside(pet, area)


def throw(pet: PetBehavior, velocity: tuple[float, float]) -> None:
    pet.pick_up()
    pet.put_down(velocity)


def test_pet_let_go_slowly_is_not_thrown():
    pet = PetBehavior(SCREEN, (500, 300), sitting=True, rng=random.Random(10))

    throw(pet, (100, 50))

    assert not pet.flying
    assert pet.activity is Activity.SITTING


def test_thrown_pet_stays_carried_while_it_glides_and_stops_where_friction_leaves_it():
    pet = PetBehavior(SCREEN, (300, 300), rng=random.Random(11))

    throw(pet, (1600, -300))
    pet.tick(0.05)

    assert pet.flying
    assert pet.activity is Activity.CARRIED

    while pet.flying:
        pet.tick(0.05)

    x, y = pet.position
    assert 300 < x < SCREEN.right  # it went the way it was thrown, and stopped before the wall
    assert y < 300  # and did not fall to the floor


def test_thrown_pet_hardly_bounces_off_a_wall():
    pet = PetBehavior(SCREEN, (900, 300), rng=random.Random(12))

    throw(pet, (2000, 0))
    while pet.flying:
        pet.tick(0.05)

    assert SCREEN.right - 200 < pet.position[0] <= SCREEN.right


def test_thrown_sitting_pet_keeps_sitting_once_landed():
    pet = PetBehavior(SCREEN, (500, 300), sitting=True, rng=random.Random(13))

    throw(pet, (-900, -900))
    run(pet, 10)

    assert pet.activity is Activity.SITTING


def test_thrown_roaming_pet_strolls_again_after_landing():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(14))

    throw(pet, (900, -300))
    run(pet, 10)
    landed = pet.position
    run(pet, 10)

    assert pet.position != landed


def test_grabbing_a_flying_pet_catches_it():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(15))

    throw(pet, (900, -300))
    pet.tick(0.05)
    pet.pick_up()
    held = pet.position
    run(pet, 2)

    assert not pet.flying
    assert pet.position == held


@given(
    vx=st.floats(-10_000, 10_000),
    vy=st.floats(-10_000, 10_000),
    x=st.floats(0, 1000),
    y=st.floats(0, 600),
)
def test_thrown_pet_never_leaves_its_area_and_always_comes_to_rest(vx, vy, x, y):
    pet = PetBehavior(SCREEN, (x, y), rng=random.Random(16))

    throw(pet, (vx, vy))
    for _ in range(600):
        pet.tick(0.05)
        left, top = pet.position
        assert SCREEN.left <= left <= SCREEN.right
        assert SCREEN.top <= top <= SCREEN.bottom

    assert not pet.flying


def test_throw_strength_scales_how_fast_the_pet_takes_off():
    slow = PetBehavior(SCREEN, (300, 300), rng=random.Random(17))
    fast = PetBehavior(SCREEN, (300, 300), rng=random.Random(17))

    slow.pick_up()
    slow.put_down((1600, 0), 50)
    fast.pick_up()
    fast.put_down((1600, 0), 200)
    for pet in (slow, fast):
        while pet.flying:
            pet.tick(0.05)

    assert slow.position[0] < fast.position[0]


def test_a_stronger_throw_bounces_off_a_wall_harder():
    def bounce_back(strength: int) -> float:
        pet = PetBehavior(SCREEN, (990, 300), rng=random.Random(18))
        pet.pick_up()
        pet.put_down((1600, 0), strength)
        while pet.flying:
            pet.tick(0.05)
        return SCREEN.right - pet.position[0]

    assert bounce_back(50) < bounce_back(100) < bounce_back(200)


def test_a_walking_pet_stops_when_stroked_and_waits_before_walking_again():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(2))
    while pet.activity is not Activity.WALKING:
        pet.tick(0.05)

    pet.pet()

    assert pet.activity is Activity.STANDING
    stopped_at = pet.position
    run(pet, PETTING_TIME - 0.1)
    assert pet.position == stopped_at
    run(pet, 20)
    assert pet.position != stopped_at


def test_a_sitting_pet_keeps_sitting_when_stroked():
    pet = PetBehavior(SCREEN, (300, 200), sitting=True, rng=random.Random(1))

    pet.pet()
    run(pet, 5)

    assert pet.activity is Activity.SITTING
    assert pet.position == (300, 200)


def test_a_carried_pet_is_not_stroked():
    pet = PetBehavior(SCREEN, (300, 200), rng=random.Random(1))
    pet.pick_up()

    pet.pet()
    pet.put_down()

    assert pet.activity is Activity.STANDING


def test_a_flying_pet_is_not_stopped_by_a_stroke():
    pet = PetBehavior(SCREEN, (300, 200), rng=random.Random(1))
    pet.pick_up()
    pet.put_down((1800.0, 0.0))

    pet.pet()

    assert pet.flying


OPEN_WATER = Area(left=0, top=0, right=100_000, bottom=100_000)  # no wall within any stroll


def horizontal_moves(pet: PetBehavior, seconds: float) -> list[tuple[float, Facing]]:
    """Each tick's horizontal move of a walking pet and the way it faces then."""
    moves = []
    for _ in range(round(seconds / 0.05)):
        before = pet.position[0]
        pet.tick(0.05)
        if pet.activity is Activity.WALKING and pet.position[0] != before:
            moves.append((pet.position[0] - before, pet.facing))
    return moves


@pytest.mark.parametrize(
    ("backward", "toward"), [(1.0, False), (0.0, True)], ids=["away", "toward"]
)
def test_strolls_face_away_from_their_target_only_when_taken_backward(backward, toward):
    gait = Gait(speed=100, distance=(80, 120), rest=(0.1, 0.2), backward=backward)
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(30), gait=gait)

    moves = horizontal_moves(pet, 60)

    assert len(moves) > 100
    for dx, facing in moves:
        assert facing is (Facing.RIGHT if (dx > 0) == toward else Facing.LEFT)


def test_a_gait_that_goes_backward_part_of_the_time_does_it_that_often():
    gait = Gait(speed=100, distance=(80, 120), rest=(0.1, 0.2), backward=0.77)
    pet = PetBehavior(OPEN_WATER, (50_000, 50_000), rng=random.Random(31), gait=gait)
    strolls = backward = 0
    was_walking = False

    for _ in range(40_000):
        before = pet.position[0]
        pet.tick(0.05)
        walking = pet.activity is Activity.WALKING
        if walking and not was_walking:
            strolls += 1
            pet.tick(0.05)  # the first step shows which way it faces
            moved = pet.position[0] - before
            backward += (moved > 0) == (pet.facing is Facing.LEFT)
        was_walking = walking

    assert strolls > 1000
    assert backward / strolls == pytest.approx(0.77, abs=0.04)


def test_a_turned_pet_keeps_going_backward():
    gait = Gait(speed=100, distance=(200, 240), backward=1.0)
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(32), gait=gait)
    start_walking(pet)
    run(pet, 0.5)
    (dx, facing), *_ = horizontal_moves(pet, 0.05)

    pet.turn_around()
    (turned_dx, turned_facing), *_ = horizontal_moves(pet, 0.05)

    assert turned_dx * dx < 0  # it heads the other way...
    assert turned_facing is not facing  # ...still facing away from where it goes
    assert turned_facing is (Facing.LEFT if turned_dx > 0 else Facing.RIGHT)


@pytest.mark.parametrize("seed", range(6))
def test_a_pet_swapped_in_mid_backward_stroll_faces_where_it_goes(seed):
    backward = Gait(speed=100, distance=(200, 240), backward=1.0)
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(seed), gait=backward)
    start_walking(pet)
    run(pet, 0.5)

    pet.set_gait(Gait(speed=100, distance=(200, 240)))

    (dx, facing), *_ = horizontal_moves(pet, 0.05)
    assert facing is (Facing.RIGHT if dx > 0 else Facing.LEFT)


def test_a_gait_without_backward_strolls_leaves_the_random_sequence_alone():
    rng = random.Random(33)
    pet = PetBehavior(SCREEN, (500, 300), rng=rng)
    start_walking(pet)

    replica = random.Random(33)
    replica.uniform(0.5, 1.2)  # the rest it starts with
    replica.uniform(80.0, 320.0)  # the stroll's length,
    replica.choice((-1.0, 1.0))  # its direction
    replica.uniform(-0.4, 0.4)  # and its slope: nothing is drawn for the backward share
    assert rng.getstate() == replica.getstate()


def distances_per_slice(pet: PetBehavior, seconds: float, slices: int, step: float) -> list[float]:
    """How far a pet that has just set off gets in each of `slices` equal parts of `seconds`."""
    start_walking(pet)
    ticks_per_slice = round(seconds / slices / step)
    result = []
    for _ in range(slices):
        before = pet.position
        for _ in range(ticks_per_slice):
            pet.tick(step)
        result.append(math.dist(before, pet.position))
    return result


@pytest.mark.parametrize("step", [0.01, 0.05, 0.1])
def test_a_pulsing_pet_covers_its_speed_times_the_pulse_in_each_pulse(step):
    gait = Gait(speed=30, max_slope=0.0, distance=(300, 300), pulse=2.0)  # 5 pulses of 60 px

    covered = distances_per_slice(pulsed_pet_with(gait), 6.0, 3, step)

    assert covered == pytest.approx([30 * 2.0] * 3)


def pulsed_pet_with(gait: Gait) -> PetBehavior:
    return PetBehavior(OPEN_WATER, (50_000, 50_000), rng=random.Random(34), gait=gait)


def test_a_pulsing_pet_is_slowest_as_a_pulse_begins_and_fastest_halfway_through():
    gait = Gait(speed=30, max_slope=0.4, distance=(5000, 6000), pulse=2.0)

    eighths = distances_per_slice(pulsed_pet_with(gait), 2.0, 8, 0.05)  # eighths of a pulse

    assert eighths.index(min(eighths)) in (0, 7)
    assert eighths.index(max(eighths)) in (3, 4)
    assert eighths[0] == pytest.approx(eighths[7])  # it slows down as it sped up
    assert eighths[3] == pytest.approx(eighths[4])
    assert max(eighths) > 5 * min(eighths)


def test_a_pulsing_pet_does_not_go_by_the_length_of_its_ticks():
    gait = Gait(speed=30, max_slope=0.4, distance=(5000, 6000), pulse=2.0)

    fine, coarse = (
        distances_per_slice(pulsed_pet_with(gait), 1.0, 1, step)[0] for step in (0.01, 0.1)
    )

    assert fine == pytest.approx(coarse)


def test_a_new_stroll_starts_a_new_pulse():
    gait = Gait(speed=30, max_slope=0.0, distance=(60, 60), rest=(0.1, 0.2), pulse=2.0)
    pet = PetBehavior(OPEN_WATER, (50_000, 50_000), rng=random.Random(35), gait=gait)
    firsts = []

    for _ in range(3):
        start_walking(pet)
        before = pet.position
        pet.tick(0.1)
        firsts.append(math.dist(before, pet.position))
        walk_to_the_end_of_the_stroll(pet)

    assert firsts == pytest.approx([firsts[0]] * 3)
    assert firsts[0] < 30 * 0.1 / 2  # each one sets off slowly


def test_turning_around_does_not_restart_the_pulse():
    gait = Gait(speed=30, max_slope=0.4, distance=(5000, 6000), pulse=2.0)
    turned, twin = (pulsed_pet_with(gait) for _ in range(2))
    for pet in (turned, twin):
        start_walking(pet)
        run(pet, 1.0)  # halfway through the pulse, at its fastest

    turned.turn_around()
    before = [turned.position, twin.position]
    run(turned, 0.2)
    run(twin, 0.2)

    assert math.dist(before[0], turned.position) == pytest.approx(
        math.dist(before[1], twin.position)
    )
    assert math.dist(before[0], turned.position) > 30 * 0.2  # still surging


def test_without_a_pulse_a_pet_moves_the_same_distance_whenever_it_is():
    gait = Gait(speed=30, max_slope=0.4, distance=(5000, 6000))

    covered = distances_per_slice(pulsed_pet_with(gait), 2.0, 8, 0.05)

    assert covered == pytest.approx([30 * 0.25] * 8)


PULSING = Gait(speed=30, max_slope=0.5, distance=(60, 240), rest=(0.1, 0.5), pulse=2.0)
TICK = 0.01


class Stroll:
    """How a stroll went: how long it took, how far it got and how fast it moved at its end."""

    def __init__(self, seconds: float = 0.0) -> None:
        self.seconds = seconds
        self.path = 0.0
        self.last_speed = 0.0  # in the tick it ended in


def strolls_of(pet: PetBehavior, seconds: float, *, under_way: float | None = None) -> list[Stroll]:
    """The strolls the pet takes in `seconds`, measured from the tick each one starts on.

    If one is under way, `under_way` is how long ago it started, and it is the first to count.
    """
    result: list[Stroll] = []
    stroll = None if under_way is None else Stroll(under_way)
    for _ in range(round(seconds / TICK)):
        before = pet.position
        pet.tick(TICK)
        if stroll is not None:
            moved = math.dist(before, pet.position)
            stroll.seconds += TICK
            stroll.path += moved
            stroll.last_speed = moved / TICK
            if pet.activity is not Activity.WALKING:
                result.append(stroll)
                stroll = None
        elif pet.activity is Activity.WALKING:
            stroll = Stroll()
    return result


def assert_ends_as_a_pulse_does(stroll: Stroll, gait: Gait = PULSING) -> None:
    """The stroll lasted whole pulses, to within a tick, and was at its slowest when it ended."""
    assert gait.pulse is not None
    pulses = round(stroll.seconds / gait.pulse)
    assert pulses >= 1
    assert stroll.seconds == pytest.approx(pulses * gait.pulse, abs=TICK + 1e-9)
    assert stroll.last_speed < 0.25 * gait.speed * 1.5  # the peak is 1.85 times its mean speed


def test_a_pulsing_pets_strolls_each_last_whole_pulses_and_end_at_their_slowest():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(40), gait=PULSING)

    strolls = strolls_of(pet, 1200)  # walls included: some targets are clamped

    assert len(strolls) > 150
    for stroll in strolls:
        assert_ends_as_a_pulse_does(stroll)


def test_the_mean_speed_of_a_pulsing_strolls_stays_near_the_gaits():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(41), gait=PULSING)

    strolls = strolls_of(pet, 1200)

    means = [stroll.path / stroll.seconds for stroll in strolls]
    assert len(strolls) > 150
    assert all(0.5 * PULSING.speed <= mean <= 1.5 * PULSING.speed for mean in means)
    assert sum(means) / len(means) == pytest.approx(PULSING.speed, rel=0.1)


def pet_strolling_right_toward_a_wall_behind_it(seed: int) -> PetBehavior:
    """A pulsing pet a little way into a long stroll to the right, in an area whose left wall is
    near, so that turning it around sends it toward that wall with less room than it has left."""
    area = Area(left=380, top=0, right=1000, bottom=600)
    gait = Gait(speed=30, max_slope=0.0, distance=(200, 240), rest=(0.1, 0.5), pulse=2.0)
    for offset in range(100):
        pet = PetBehavior(area, (500, 300), rng=random.Random(seed + offset), gait=gait)
        start_walking(pet)
        pet.tick(0.05)
        if pet.position[0] > 500:
            return pet
    pytest.fail("no pet strolled to the right")


def test_a_stroll_a_wall_shortens_still_ends_as_a_pulse_does():
    pet = pet_strolling_right_toward_a_wall_behind_it(42)
    run(pet, 0.5)  # 0.55 s into the stroll
    pet.turn_around()

    stroll, *_ = strolls_of(pet, 20, under_way=0.55)

    assert stroll.path < 200  # it got to the wall, so the stroll was shortened
    assert_ends_as_a_pulse_does(stroll, Gait(speed=30, pulse=2.0))


def test_a_stroll_that_a_smaller_area_shortens_still_ends_as_a_pulse_does():
    pet = pet_strolling_right_toward_a_wall_behind_it(43)
    run(pet, 0.5)
    x = pet.position[0]

    pet.set_area(Area(left=380, top=0, right=x + 60, bottom=600))
    stroll, *_ = strolls_of(pet, 20, under_way=0.55)

    assert stroll.path == pytest.approx(60, abs=0.5)  # up to the new wall
    assert_ends_as_a_pulse_does(stroll, Gait(speed=30, pulse=2.0))


def test_a_stroll_under_way_when_the_pet_starts_to_pulse_ends_as_a_pulse_does():
    steady = Gait(speed=30, max_slope=0.0, distance=(200, 240), rest=(0.1, 0.5))
    pet = PetBehavior(OPEN_WATER, (50_000, 50_000), rng=random.Random(44), gait=steady)
    start_walking(pet)
    run(pet, 0.55)

    pet.set_gait(Gait(speed=30, max_slope=0.0, distance=(200, 240), pulse=2.0))
    stroll, *_ = strolls_of(pet, 20, under_way=0.55)

    assert_ends_as_a_pulse_does(stroll, Gait(speed=30, pulse=2.0))


def test_a_pulsing_pet_stopped_by_the_user_stops_at_once():
    pet = PetBehavior(SCREEN, (500, 300), rng=random.Random(45), gait=PULSING)
    start_walking(pet)
    run(pet, 1.0)  # in the middle of a surge

    pet.toggle_sitting()

    assert pet.activity is Activity.SITTING
    here = pet.position
    run(pet, 5)
    assert pet.position == here
