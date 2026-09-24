"""The pets to choose from. Only one of them is on the screen at a time."""

import logging

from virtual_pet.pets.cat import CAT
from virtual_pet.pets.dog import DOG
from virtual_pet.pets.fish import FISH
from virtual_pet.pets.guinea_pig import GUINEA_PIG
from virtual_pet.pets.parakeet import PARAKEET
from virtual_pet.pets.turtle import TURTLE
from virtual_pet.species import Species

ALL_SPECIES = (DOG, CAT, PARAKEET, TURTLE, FISH, GUINEA_PIG)

logger = logging.getLogger(__name__)


def species_by_key(key: str) -> Species:
    """The species saved as `key`; the dog if the key is unknown (e.g. a hand-edited file)."""
    for species in ALL_SPECIES:
        if species.key == key:
            return species
    logger.warning("Unknown pet %r, using the dog instead", key)
    return DOG
