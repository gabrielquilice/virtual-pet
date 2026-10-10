import random

import pytest

from virtual_pet import hearts
from virtual_pet.hearts import HeartBurst


def burst_of(count: int) -> HeartBurst:
    """A started burst of one or two hearts: the seeds are searched, the rng is the app's."""
    for seed in range(100):
        burst = HeartBurst(random.Random(seed))
        burst.start()
        if len(burst.hearts) == count:
            return burst
    pytest.fail(f"no seed gives {count} hearts at once")


def hearts_over_time(burst: HeartBurst, step: float = 0.05) -> list[tuple[hearts.Heart, ...]]:
    snapshots = []
    while burst.active:
        snapshots.append(burst.hearts)
        burst.tick(step)
    return snapshots


@pytest.mark.parametrize("frame", [hearts.BIG, hearts.SMALL])
def test_heart_art_is_a_rectangle_in_the_palette(frame):
    assert len({len(row) for row in frame}) == 1
    assert set("".join(frame)) <= set(hearts.PALETTE) | {"."}


@pytest.mark.parametrize("frame", [hearts.BIG, hearts.SMALL])
def test_hearts_fit_in_their_window_whatever_their_rise(frame):
    for _size, x, y in hearts.PAIR:
        assert x >= 0
        assert x + len(frame[0]) <= hearts.WIDTH
        assert y - hearts.RISE >= 0
        assert y + len(frame) <= hearts.HEIGHT


def test_a_burst_that_was_not_started_shows_nothing():
    burst = HeartBurst(random.Random(1))

    assert not burst.active
    assert burst.hearts == ()


def test_a_burst_is_one_or_two_hearts():
    counts = set()
    for seed in range(50):
        burst = HeartBurst(random.Random(seed))
        burst.start()
        burst.tick(hearts.SECOND_HEART_DELAY + 0.01)
        counts.add(len(burst.hearts))

    assert counts == {1, 2}


def test_the_first_heart_shows_before_the_second():
    for seed in range(50):
        burst = _started(seed)
        first_alone = len(burst.hearts) == 1
        burst.tick(hearts.SECOND_HEART_DELAY + 0.01)
        if first_alone and len(burst.hearts) == 2:
            return
    pytest.fail("no pair found")


def _started(seed: int) -> HeartBurst:
    burst = HeartBurst(random.Random(seed))
    burst.start()
    return burst


def test_a_pair_starts_with_the_small_heart_on_the_left():
    for seed in range(50):
        burst = _started(seed)
        burst.tick(hearts.SECOND_HEART_DELAY + 0.01)
        if len(burst.hearts) == 2:
            first, second = burst.hearts
            assert first.frame == hearts.SMALL
            assert second.frame == hearts.BIG
            assert first.x < second.x
            return
    pytest.fail("no pair found")


def test_a_burst_ends_when_the_last_heart_has_faded():
    burst = burst_of(1)

    burst.tick(hearts.DURATION + 0.01)

    assert not burst.active
    assert burst.hearts == ()


def test_a_heart_fades_out_at_the_end_of_its_life_and_only_then():
    burst = _started(3)
    snapshots = [shown for shown in hearts_over_time(burst) if shown]
    opacities = [shown[0].opacity for shown in snapshots]

    assert opacities[0] == 1.0
    assert opacities == sorted(opacities, reverse=True) or len(snapshots[0]) > 1
    assert min(shown.opacity for snapshot in snapshots for shown in snapshot) < 0.2


def test_a_heart_rises_only_a_little_and_hardly_at_all_while_fading():
    for seed in range(20):
        burst = _started(seed)
        rises: dict[object, list[tuple[float, int]]] = {}
        while burst.active:
            for heart in burst.hearts:
                rises.setdefault(heart.frame, []).append((heart.opacity, heart.y))
            burst.tick(0.02)
        for samples in rises.values():
            ys = [y for _opacity, y in samples]
            assert ys[0] - ys[-1] <= hearts.RISE
            fading = [y for opacity, y in samples if opacity < 1.0]
            assert fading[0] - fading[-1] <= 1


def test_starting_again_begins_a_new_burst():
    burst = burst_of(1)
    burst.tick(hearts.DURATION + 0.01)

    burst.start()

    assert burst.active
    assert burst.hearts


def test_stopping_drops_the_hearts_at_once():
    burst = burst_of(1)

    burst.stop()

    assert not burst.active
    assert burst.hearts == ()
