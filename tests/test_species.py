import pytest

from virtual_pet import sprites
from virtual_pet.behavior import Activity
from virtual_pet.pets import ALL_SPECIES, CAT, DOG, PARAKEET, TURTLE, species_by_key
from virtual_pet.species import Locomotion, Species

GROUND_LINE = 25  # row of the outline under the paws
GROUNDED = {  # the poses drawn on the ground line
    Locomotion.WALK: {Activity.STANDING, Activity.WALKING, Activity.SITTING},
    Locomotion.FLY: {Activity.STANDING, Activity.SITTING},  # it takes off to fly
    Locomotion.SWIM: {Activity.SITTING},  # it floats, unless told to rest on the bottom
}


@pytest.fixture(params=ALL_SPECIES, ids=lambda species: species.key)
def species(request) -> Species:
    return request.param


def all_frames(species: Species) -> list[sprites.Frame]:
    return [frame for animation in species.animations.values() for frame in animation.frames]


def find(frame: sprites.Frame, char: str) -> tuple[int, int]:
    for y, row in enumerate(frame):
        if char in row:
            return row.index(char), y
    raise AssertionError(char)


def lowest_visible_row(frame: sprites.Frame) -> int:
    return max(y for y, row in enumerate(frame) if row.strip(sprites.TRANSPARENT))


def test_the_pets_are_a_dog_a_cat_a_maritaca_and_a_sea_turtle():
    assert [(pet.key, pet.label) for pet in ALL_SPECIES] == [
        ("dog", "Dog"),
        ("cat", "Cat"),
        ("parakeet", "Maritaca"),
        ("turtle", "Sea Turtle"),
    ]


def test_pets_are_found_by_the_key_saved_in_the_settings():
    keys = ("dog", "cat", "parakeet", "turtle")

    assert [species_by_key(key) for key in keys] == [DOG, CAT, PARAKEET, TURTLE]


def test_an_unknown_saved_pet_becomes_the_dog():
    assert species_by_key("dragon") is DOG


def test_the_maritaca_flies_and_the_sea_turtle_swims():
    assert [pet.roam_label for pet in ALL_SPECIES] == ["Walk", "Walk", "Fly", "Swim"]


def test_every_activity_has_an_animation(species):
    assert set(species.animations) == set(Activity)


def test_all_frames_share_one_canvas_so_the_window_never_resizes(species):
    sizes = {(len(row), len(frame)) for frame in all_frames(species) for row in frame}

    assert sizes == {(32, 27)}


def test_frames_only_use_colors_from_the_palette(species):
    used = {char for frame in all_frames(species) for row in frame for char in row}

    assert used <= {*species.palette, sprites.TRANSPARENT}


def test_poses_on_the_ground_stand_on_the_ground_line(species):
    ground_lines = {
        lowest_visible_row(frame)
        for activity in GROUNDED[species.locomotion]
        for frame in species.animations[activity].frames
    }

    assert ground_lines == {GROUND_LINE}


def test_flying_lifts_the_maritaca_off_the_ground():
    flying = PARAKEET.animations[Activity.WALKING].frames

    assert all(lowest_visible_row(frame) < GROUND_LINE for frame in flying)


def test_the_sea_turtle_floats_until_it_rests_on_the_bottom():
    floating = [
        frame
        for activity in (Activity.STANDING, Activity.WALKING)
        for frame in TURTLE.animations[activity].frames
    ]

    assert all(lowest_visible_row(frame) < GROUND_LINE for frame in floating)


def test_every_frame_has_an_eye_that_can_blink(species):
    for frame in all_frames(species):
        text = "".join(frame)
        assert sprites.EYE in text
        assert sprites.EYE_SHINE in text


def test_each_pet_is_drawn_in_its_own_colors():
    body_colors = [
        pet.image(pet.portrait).pixelColor(*find(pet.portrait, "B")).name() for pet in ALL_SPECIES
    ]

    assert body_colors == ["#dc9a57", "#a3a8b0", "#4cae4f", "#6fa582"]  # tan, gray, green, sage


def test_rendered_frame_keeps_transparent_background_and_eye_colors():
    image = DOG.image(DOG.portrait)
    eye, shine = find(DOG.portrait, sprites.EYE), find(DOG.portrait, sprites.EYE_SHINE)

    assert (image.width(), image.height()) == (32, 27)
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(*eye).name() == "#221612"
    assert image.pixelColor(*shine).name() == "#ffffff"


def test_blinking_turns_the_eye_into_a_closed_line():
    image = DOG.image(DOG.portrait, blinking=True)
    eye, shine = find(DOG.portrait, sprites.EYE), find(DOG.portrait, sprites.EYE_SHINE)

    assert image.pixelColor(*eye).name() == "#dc9a57"  # fur
    assert image.pixelColor(*shine).name() == "#221612"  # dark line
