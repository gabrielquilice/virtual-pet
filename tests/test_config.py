import json

import pytest

from virtual_pet.behavior import Facing
from virtual_pet.config import Config, ConfigStore, normalize_name


def test_first_run_has_no_pet_name_yet(tmp_path):
    store = ConfigStore(tmp_path / "config.json")

    config = store.load()

    assert config == Config(
        pet_name=None,
        species="dog",
        position=None,
        sitting=False,
        facing=Facing.RIGHT,
        language=None,
    )


def test_saved_config_is_loaded_back(tmp_path):
    store = ConfigStore(tmp_path / "virtual-pet" / "config.json")

    saved = Config(
        pet_name="Mimi",
        species="cat",
        position=(120, -40),
        sitting=True,
        facing=Facing.LEFT,
        language="pt_BR",
    )

    store.save(saved)

    assert store.load() == saved


@pytest.mark.parametrize("content", [b"{not json", b"[1, 2]", b"", b'"Rex"', b"\xff\xfe\x00"])
def test_unreadable_config_falls_back_to_defaults(tmp_path, content):
    path = tmp_path / "config.json"
    path.write_bytes(content)

    assert ConfigStore(path).load() == Config()


def test_invalid_values_are_dropped_and_valid_ones_kept(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "pet_name": "Rex",
                "species": 42,
                "position": {"x": "10", "y": True},
                "sitting": "yes",
                "facing": "up",
                "language": ["pt_BR"],
            }
        ),
        encoding="utf-8",
    )

    assert ConfigStore(path).load() == Config(
        pet_name="Rex",
        species="dog",
        position=None,
        sitting=False,
        facing=Facing.RIGHT,
        language=None,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Rex  ", "Rex"),
        ("Sir   Barks\ta Lot", "Sir Barks a Lot"),
        ("   ", ""),
        ("Bartholomew Fluffington III", "Bartholomew Fluffington"),  # capped at 24 characters
    ],
)
def test_names_are_tidied_up(raw, expected):
    assert normalize_name(raw) == expected


def test_blank_stored_name_counts_as_no_name(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"pet_name": "   "}), encoding="utf-8")

    assert ConfigStore(path).load().pet_name is None


def test_saving_again_replaces_the_file_without_leftovers(tmp_path):
    store = ConfigStore(tmp_path / "config.json")

    store.save(Config(pet_name="Rex"))
    store.save(Config(pet_name="Luna", sitting=True))

    assert store.load() == Config(pet_name="Luna", sitting=True)
    assert [path.name for path in tmp_path.iterdir()] == ["config.json"]


def test_settings_from_before_there_was_a_choice_of_pets_keep_the_dog(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"pet_name": "Rex", "sitting": True}), encoding="utf-8")

    assert ConfigStore(path).load().species == "dog"


def test_settings_from_before_there_was_a_choice_of_language_follow_the_system(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"pet_name": "Rex", "species": "cat"}), encoding="utf-8")

    assert ConfigStore(path).load().language is None


def test_settings_from_before_the_pet_could_turn_face_right(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"pet_name": "Rex", "sitting": True}), encoding="utf-8")

    assert ConfigStore(path).load().facing is Facing.RIGHT
