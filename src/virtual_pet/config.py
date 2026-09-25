"""The user's settings, stored as a small JSON file."""

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TypeGuard

from virtual_pet.behavior import Facing

MAX_NAME_LENGTH = 24
DEFAULT_SPECIES = "dog"  # also what settings saved before other pets existed get

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Everything the pet remembers between runs."""

    pet_name: str | None = None
    species: str = DEFAULT_SPECIES
    position: tuple[int, int] | None = None
    sitting: bool = False
    facing: Facing = Facing.RIGHT
    language: str | None = None  # of the interface; None follows the system's language


def normalize_name(raw: str) -> str:
    """Tidy a pet name: collapse whitespace, trim it and cap its length."""
    return " ".join(raw.split())[:MAX_NAME_LENGTH].rstrip()


class ConfigStore:
    """Loads and saves a `Config` at a fixed path."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Config:
        """Return the stored config, or the defaults when there is none."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return Config()
        except (OSError, ValueError) as error:
            logger.warning("Ignoring unreadable settings file %s: %s", self.path, error)
            return Config()
        if not isinstance(data, dict):
            logger.warning("Ignoring settings file %s: unexpected content", self.path)
            return Config()
        name, species, language = data.get("pet_name"), data.get("species"), data.get("language")
        return Config(
            pet_name=(normalize_name(name) or None) if isinstance(name, str) else None,
            species=species if isinstance(species, str) and species else DEFAULT_SPECIES,
            position=_position_from_json(data.get("position")),
            sitting=data.get("sitting") is True,
            facing=Facing.LEFT if data.get("facing") == "left" else Facing.RIGHT,
            language=language if isinstance(language, str) and language else None,
        )

    def save(self, config: Config) -> None:
        """Write the config atomically, so a crash never leaves a half-written file."""
        position = config.position
        data = {
            "pet_name": config.pet_name,
            "species": config.species,
            "position": None if position is None else {"x": position[0], "y": position[1]},
            "sitting": config.sitting,
            "facing": config.facing.name.lower(),
            "language": config.language,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(dir=self.path.parent, prefix=".config-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
            Path(temp_name).replace(self.path)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise


def _position_from_json(value: object) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    x, y = value.get("x"), value.get("y")
    if _is_int(x) and _is_int(y):
        return (x, y)
    return None


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)  # JSON true is not a number
