from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from virtual_pet import sprites
from virtual_pet.behavior import Activity
from virtual_pet.pets import (
    ALL_SPECIES,
    CAT,
    CHAMELEON,
    CHICKEN,
    COCKATIEL,
    DOG,
    FISH,
    FOX,
    FROG,
    GUINEA_PIG,
    OCTOPUS,
    OWL,
    PARAKEET,
    PENGUIN,
    RABBIT,
    SNAIL,
    SNAKE,
    TURTLE,
    WOLF,
    species_by_key,
)
from virtual_pet.species import ColorShift, Locomotion, Species

GROUND_LINE = 25  # row of the outline under the paws
GROUNDED = {  # the poses drawn on the ground line
    Locomotion.WALK: {Activity.STANDING, Activity.WALKING, Activity.SITTING},
    Locomotion.FLY: {Activity.STANDING, Activity.SITTING},  # it takes off to fly
    Locomotion.SWIM: {Activity.SITTING},  # it floats, unless told to rest on the bottom
    Locomotion.SLITHER: {Activity.STANDING, Activity.WALKING, Activity.SITTING},
    Locomotion.HOP: {Activity.STANDING, Activity.WALKING, Activity.SITTING},  # a foot stays down
    Locomotion.CRAWL: {Activity.STANDING, Activity.WALKING, Activity.SITTING},
}
README = Path(__file__).resolve().parent.parent / "README.md"
PICTURES = README.parent / "docs" / "pets"  # the pets table's pictures, one per pet
PICTURE_SCALE = 6  # image pixels per art pixel: the README shows them at half that


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


def test_the_pets_to_choose_from_and_their_names():
    assert [(pet.key, pet.label) for pet in ALL_SPECIES] == [
        ("dog", "Dog"),
        ("cat", "Cat"),
        ("parakeet", "Maritaca"),
        ("turtle", "Sea Turtle"),
        ("fish", "Fish"),
        ("guinea_pig", "Guinea Pig"),
        ("penguin", "Penguin"),
        ("snake", "Snake"),
        ("rabbit", "Rabbit"),
        ("cockatiel", "Cockatiel"),
        ("fox", "Fox"),
        ("wolf", "Wolf"),
        ("snail", "Snail"),
        ("frog", "Frog"),
        ("chameleon", "Chameleon"),
        ("chicken", "Chicken"),
        ("octopus", "Octopus"),
        ("owl", "Owl"),
    ]


def test_pets_are_found_by_the_key_saved_in_the_settings():
    keys = [
        "dog",
        "cat",
        "parakeet",
        "turtle",
        "fish",
        "guinea_pig",
        "penguin",
        "snake",
        "rabbit",
        "cockatiel",
        "fox",
        "wolf",
        "snail",
        "frog",
        "chameleon",
        "chicken",
        "octopus",
        "owl",
    ]

    assert [species_by_key(key) for key in keys] == [
        DOG,
        CAT,
        PARAKEET,
        TURTLE,
        FISH,
        GUINEA_PIG,
        PENGUIN,
        SNAKE,
        RABBIT,
        COCKATIEL,
        FOX,
        WOLF,
        SNAIL,
        FROG,
        CHAMELEON,
        CHICKEN,
        OCTOPUS,
        OWL,
    ]


def test_an_unknown_saved_pet_becomes_the_dog():
    assert species_by_key("dragon") is DOG


def test_each_pet_roams_its_own_way():
    assert [pet.roam_label for pet in ALL_SPECIES] == [
        "Walk",
        "Walk",
        "Fly",
        "Swim",
        "Swim",
        "Walk",
        "Walk",
        "Slither",
        "Hop",
        "Fly",
        "Walk",
        "Walk",
        "Crawl",
        "Hop",
        "Walk",
        "Walk",
        "Crawl",
        "Fly",
    ]


def test_the_snake_coils_up_the_snail_retreats_and_the_octopus_and_owl_rest_where_others_sit():
    assert [pet.sit_label for pet in ALL_SPECIES] == [
        *["Sit"] * 7,
        "Coil up",
        *["Sit"] * 4,
        "Retreat into shell",
        *["Sit"] * 3,
        "Rest",
        "Rest",
    ]


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


@pytest.mark.parametrize("flyer", [PARAKEET, COCKATIEL, OWL], ids=lambda species: species.key)
def test_flying_lifts_birds_off_the_ground(flyer):
    flying = flyer.animations[Activity.WALKING].frames

    assert all(lowest_visible_row(frame) < GROUND_LINE for frame in flying)


def test_a_chicken_stops_to_scratch_the_ground_and_peck_at_it():
    standing = CHICKEN.animations[Activity.STANDING]
    toes = {frame[GROUND_LINE - 1] for frame in standing.frames}  # the row its toes are on
    eyes = [find(frame, sprites.EYE)[1] for frame in standing.frames]
    first_peck = eyes.index(max(eyes))  # its head at its lowest

    assert len(toes) > 1  # its feet move: it scratches
    assert max(eyes) >= GROUND_LINE - 5  # its head comes down to the ground: it pecks
    assert CHICKEN.gait.rest[0] > first_peck / standing.fps  # before it walks off


def owl_pupils(frame: sprites.Frame) -> int:
    """How many of the owl's eyes show: their pupils, each between two yellow pixels."""
    return sum(row.count(sprites.EYE_SHINE + "N" + sprites.EYE_SHINE) for row in frame)


def test_an_owl_turns_its_head_to_look_at_you_and_dozes_off_when_it_rests():
    def eye_pixels(frame: sprites.Frame) -> int:
        return sum(row.count(sprites.EYE) + row.count(sprites.EYE_SHINE) for row in frame)

    standing = OWL.animations[Activity.STANDING].frames
    resting = OWL.animations[Activity.SITTING].frames

    assert {owl_pupils(frame) for frame in standing} == {1, 2}  # in profile, then facing you
    assert all(eye_pixels(frame) < eye_pixels(OWL.portrait) for frame in resting)  # half closed


def test_an_owl_that_stops_looks_at_you_before_it_flies_off():
    standing = OWL.animations[Activity.STANDING]
    facing_you = [i for i, frame in enumerate(standing.frames) if owl_pupils(frame) == 2]

    assert facing_you[0] / standing.fps <= 1  # soon after it stops
    assert OWL.gait.rest[0] >= (facing_you[-1] + 1) / standing.fps  # for as long as it looks


@pytest.mark.parametrize("swimmer", [TURTLE, FISH], ids=lambda species: species.key)
def test_swimmers_float_until_they_rest_on_the_bottom(swimmer):
    floating = [
        frame
        for activity in (Activity.STANDING, Activity.WALKING)
        for frame in swimmer.animations[activity].frames
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

    # tan, gray, green, sage, blue, ginger, white, emerald, warm white, yellow, red-orange,
    # warm gray, grayish beige, leaf green, chameleon green, golden brown, golden yellow, buff
    assert body_colors == [
        "#dc9a57",
        "#a3a8b0",
        "#4cae4f",
        "#6fa582",
        "#2f5fd0",
        "#e08a3c",
        "#f6f6f1",
        "#23a45a",
        "#f2eee6",
        "#f7d64a",
        "#e2632f",
        "#988f85",
        "#cdbfa6",
        "#8fca3c",
        "#3fa34d",
        "#c98b4a",
        "#c79b31",
        "#d8c09a",
    ]


def test_each_coloring_colors_everything_the_usual_palette_does(species):
    for coloring in species.colorings:
        assert set(coloring) == set(species.palette)


def test_the_chameleon_changes_color_in_waves_and_the_octopus_fades_its_rings():
    assert [(pet.key, pet.color_shift) for pet in ALL_SPECIES if pet.colorings] == [
        ("chameleon", ColorShift.WAVES),
        ("octopus", ColorShift.FADE),
    ]


def test_the_octopus_rings_darken_to_brown_then_light_up_blue():
    brightest, *_, gone = OCTOPUS.palettes
    halfway = OCTOPUS.palettes[len(OCTOPUS.palettes) // 2]

    assert brightest["A"] == "#1f63ea"  # blue: how it looks in the dialogs and the README
    assert halfway["A"] == brightest["C"] == "#6b4a08"  # the brown inside a ring
    assert gone["A"] == gone["C"] == gone["B"]  # all yellow


def test_each_column_is_drawn_in_the_coloring_it_is_given():
    frame = CHAMELEON.portrait
    turquoise = CHAMELEON.colorings[0]
    half = sprites.FRAME_WIDTH // 2
    colors = (0,) * half + (1,) * half  # the tail's half green, the head's half turquoise

    image = CHAMELEON.image(frame, colors=colors)

    for y, row in enumerate(frame):
        for x, char in enumerate(row):
            if char != sprites.TRANSPARENT:
                palette = CHAMELEON.palette if x < half else turquoise
                assert image.pixelColor(x, y).name() == palette[char]


def test_a_chameleon_blinks_in_the_color_it_has_turned():
    eye = find(CHAMELEON.portrait, sprites.EYE)
    turquoise = CHAMELEON.colorings[0]

    image = CHAMELEON.image(CHAMELEON.portrait, blinking=True, colors=(1,) * sprites.FRAME_WIDTH)

    assert image.pixelColor(*eye).name() == turquoise["B"]


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


def test_the_readme_shows_each_pet_as_drawn(species):
    shown = QImage(str(PICTURES / f"{species.key}.png"))
    drawn = species.image(species.portrait).scaled(
        sprites.FRAME_WIDTH * PICTURE_SCALE, sprites.FRAME_HEIGHT * PICTURE_SCALE
    )

    # Redrawn art needs its picture drawn again (the command is in CLAUDE.md).
    argb = QImage.Format.Format_ARGB32
    assert shown.convertToFormat(argb) == drawn.convertToFormat(argb)


def test_the_readme_has_a_row_for_each_pet(species):
    assert f'<img src="docs/pets/{species.key}.png"' in README.read_text(encoding="utf-8")


def test_the_readme_pictures_no_pet_that_is_gone():
    pictured = sorted(path.stem for path in PICTURES.glob("*.png"))

    assert pictured == sorted(species.key for species in ALL_SPECIES)
