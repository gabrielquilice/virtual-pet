import importlib.util
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "appimage" / "build.py"


def load_build_script():
    """appimage/build.py, which is a script rather than a module of the package."""
    spec = importlib.util.spec_from_file_location("appimage_build", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load_build_script()


@pytest.mark.parametrize(
    ("tags", "dirty", "expected"),
    [
        (["v0.2.0"], False, "0.2.0"),  # the release
        ([], False, "0.2.0+g1a2b3c4"),  # a commit after it, or one not tagged yet
        (["v0.2.0"], True, "0.2.0+g1a2b3c4.dirty"),  # the release with uncommitted changes
        (["v0.1.0-screenshots", "demo"], False, "0.2.0+g1a2b3c4"),  # not release tags
    ],
)
def test_only_a_clean_checkout_of_the_release_tag_gets_the_plain_version(tags, dirty, expected):
    assert build.version_name("0.2.0", tags, "1a2b3c4", dirty=dirty) == expected


@pytest.mark.parametrize("tags", [["v0.3.0"], ["v0.2.0", "v0.3.0"]])
def test_a_release_tag_that_is_not_the_version_stops_the_build(tags):
    with pytest.raises(SystemExit, match=r"tagged .*v0\.3\.0.*pyproject\.toml says 0\.2\.0"):
        build.version_name("0.2.0", tags, "1a2b3c4", dirty=False)


@pytest.fixture
def checkout(tmp_path, monkeypatch) -> Path:
    """A git repository with one commit, whatever the user's git settings."""
    for name in [name for name in os.environ if name.startswith("GIT_")]:
        monkeypatch.delenv(name)  # a git hook's GIT_DIR would point git at this project
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)  # no signing, hooks or other identity
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    git(tmp_path, "init", "--quiet")
    (tmp_path / "pet.txt").write_text("Rex", encoding="utf-8")
    git(tmp_path, "add", "pet.txt")
    git(tmp_path, "commit", "--quiet", "--message", "Adopt Rex")
    return tmp_path


def git(folder: Path, *args: str) -> None:
    identity = ["-c", "user.name=Pet", "-c", "user.email=pet@example.com"]
    subprocess.run([shutil.which("git"), *identity, *args], cwd=folder, check=True)


def test_the_version_comes_from_the_checkout(checkout):
    before = build.release_version("0.2.0", checkout)
    git(checkout, "tag", "--annotate", "v0.2.0", "--message", "Virtual Pet 0.2.0")
    released = build.release_version("0.2.0", checkout)
    (checkout / "notes.txt").write_text("not in git", encoding="utf-8")
    untracked = build.release_version("0.2.0", checkout)
    (checkout / "pet.txt").write_text("Luna", encoding="utf-8")
    changed = build.release_version("0.2.0", checkout)

    assert re.fullmatch(r"0\.2\.0\+g[0-9a-f]{7,}", before)
    assert (released, untracked) == ("0.2.0", "0.2.0")  # files git doesn't track don't count
    assert changed == f"{before}.dirty"
