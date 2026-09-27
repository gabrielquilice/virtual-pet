import tomllib
from pathlib import Path

from virtual_pet import version

ROOT = Path(__file__).resolve().parent.parent


def test_the_version_comes_from_pyproject_toml_when_there_is_no_build():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert version.app_version() == pyproject["project"]["version"]


def test_a_bundled_version_file_wins_over_pyprojects(tmp_path, monkeypatch):
    bundled = tmp_path / "VERSION"
    bundled.write_text("1.2.3+gabc1234.dirty\n", encoding="utf-8")
    monkeypatch.setattr(version, "_BUNDLED", bundled)

    assert version.app_version() == "1.2.3+gabc1234.dirty"
