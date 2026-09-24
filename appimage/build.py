"""Build the pet's AppImage on this machine: dist/VirtualPet-<version>-x86_64.AppImage.

    uv run --group build appimage/build.py

1. PyInstaller bundles the app with the Python and the Qt it runs on (virtual-pet.spec).
2. The bundle goes into an AppDir with its launcher (AppRun), menu entry, icons and the
   licenses of everything it contains.
3. appimagetool packs the AppDir with the AppImage runtime, both pinned downloads.
4. The AppImage runs the app's process tests (the `process` tests in tests/test_app.py).

An AppImage runs where glibc is at least as new as the newest one its files ask for, which
is printed at the end: build on the oldest Linux distribution the AppImage should support.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tomllib
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import qVersion

from virtual_pet.icon import SIZES, icon_image

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "appimage"
WORK = ROOT / "build" / "appimage"
TOOLS = WORK / "tools"  # downloads, kept between builds
DIST = ROOT / "dist"
APP = "virtual-pet"
ARCH = "x86_64"
REPOSITORY = "https://github.com/gabrielquilice/virtual-pet"
COPYRIGHT = "Copyright (C) 2026 Gabriel Quilice"
ICU_MAJOR = "73"  # appimage/licenses/icu/LICENSE is ICU 73.2's
GITHUB = "https://github.com"
PYTHON_BUILDS = f"{GITHUB}/astral-sh/python-build-standalone/releases/download"
GLIBC = re.compile(rb"GLIBC_(\d+)\.(\d+)")


@dataclass(frozen=True)
class Download:
    url: str
    sha256: str


APPIMAGETOOL = Download(
    f"{GITHUB}/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage",
    "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0",
)
RUNTIME = Download(
    f"{GITHUB}/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64",
    "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the pet's AppImage on this machine.")
    parser.add_argument(
        "--skip-tests", action="store_true", help="don't run the process tests on the AppImage"
    )
    parser.add_argument(
        "--allow-missing-licenses",
        action="store_true",
        help="build even if the license of some bundled file was not found",
    )
    args = parser.parse_args()

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    bundle, manifest = run_pyinstaller()
    appdir = make_appdir(bundle)
    missing = add_licenses(appdir / "usr" / "share" / "licenses", manifest, version)
    if missing and not args.allow_missing_licenses:
        sys.exit(
            "No license found for these bundled files (--allow-missing-licenses builds anyway):\n  "
            + "\n  ".join(missing)
        )
    appimage = DIST / f"VirtualPet-{version}-{ARCH}.AppImage"
    pack(appdir, appimage)
    if not args.skip_tests:
        run_process_tests(appimage)
    major, minor = glibc_needed(appdir)
    size = appimage.stat().st_size / 2**20
    print(
        f"\n{appimage.relative_to(ROOT)}: {size:.1f} MiB, runs with glibc {major}.{minor} or newer"
    )


def run_pyinstaller() -> tuple[Path, dict]:
    """Bundle the app; returns the bundle's folder and where each of its files came from."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--log-level=WARN",
            f"--distpath={WORK / 'bundle'}",
            f"--workpath={WORK / 'pyinstaller'}",
            str(HERE / "virtual-pet.spec"),
        ],
        check=True,
    )
    manifest = WORK / "pyinstaller" / APP / "bundled-files.json"
    return WORK / "bundle" / APP, json.loads(manifest.read_text(encoding="utf-8"))


def make_appdir(bundle: Path) -> Path:
    """Lay out the AppDir: the bundle, its launcher, menu entry and icons."""
    appdir = WORK / "VirtualPet.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    shutil.copytree(bundle, appdir / "usr" / "lib" / APP, symlinks=True)
    shutil.copy2(HERE / "AppRun", appdir / "AppRun")
    (appdir / "AppRun").chmod(0o755)
    for folder in (appdir, appdir / "usr" / "share" / "applications"):
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / f"{APP}.desktop", folder)
    for size in SIZES:
        folder = appdir / "usr" / "share" / "icons" / "hicolor" / f"{size}x{size}" / "apps"
        folder.mkdir(parents=True)
        icon_image(size).save(str(folder / f"{APP}.png"))
    icon_image(max(SIZES)).save(str(appdir / f"{APP}.png"))
    (appdir / ".DirIcon").symlink_to(f"{APP}.png")
    return appdir


@dataclass(frozen=True)
class Notice:
    """A third-party component, in THIRD-PARTY-NOTICES.txt."""

    name: str
    license: str
    texts: str  # folder of its license texts, under usr/share/licenses
    source: str


@dataclass
class Package:
    """A package of the build machine's Linux distribution that bundled libraries come from."""

    name: str
    version: str
    license_files: list[Path]
    libraries: set[str] = field(default_factory=set)


# The notice that covers the files of each Python distribution that can end up in the bundle.
DISTRIBUTION_NOTICES = {"pyside6-essentials": "qt", "shiboken6": "qt", "pyinstaller": "pyinstaller"}


def add_licenses(licenses: Path, manifest: dict, version: str) -> list[str]:
    """Put the license texts of everything in the bundle in `licenses`, with an index.

    Returns the bundled files whose license was not found.
    """
    notices, packages, missing = sort_out(manifest)
    copy_license_texts(licenses, notices)
    missing += copy_package_licenses(licenses / "system", packages)
    in_order = [name for name in ("python", "qt", "icu", "pyinstaller") if name in notices]
    index = notice_index(version, [notice(name) for name in in_order], packages)
    (licenses / "THIRD-PARTY-NOTICES.txt").write_text(index, encoding="utf-8")
    return missing


def sort_out(manifest: dict) -> tuple[set[str], dict[str, Package], list[str]]:
    """The notices and system packages that cover the bundled files, and the files left out."""
    notices, packages, missing = {"pyinstaller"}, {}, []  # the bootloader is always there
    owners = distribution_files()
    sources = [Path(entry["source"]) for entry in manifest["binaries"]]
    sources += [Path(module) for module in manifest["modules"]]
    for source in sources:
        origin = origin_of(source, owners)
        if isinstance(origin, Package):
            packages.setdefault(origin.name, origin).libraries.add(source.name)
        elif origin is None:
            missing.append(str(source))
        elif origin == "icu" and not source.name.endswith(f".so.{ICU_MAJOR}"):
            missing.append(f"{source} (appimage/licenses/icu is for ICU {ICU_MAJOR})")
        elif origin != "pet":
            notices.add(origin)
    return notices, packages, missing


def origin_of(source: Path, owners: dict[Path, str]) -> str | Package | None:
    """What covers a bundled file: "pet" (ours), a notice or a system package; None if unknown."""
    resolved = source.resolve()
    if resolved in owners:
        covered_by = DISTRIBUTION_NOTICES.get(owners[resolved])
        return "icu" if covered_by == "qt" and resolved.name.startswith("libicu") else covered_by
    if resolved.is_relative_to(ROOT / "src"):
        return "pet"
    if python_build_tag() and resolved.is_relative_to(Path(sys.base_prefix).resolve()):
        return "python"
    return system_package(source)


def distribution_files() -> dict[Path, str]:
    """Every file installed by a Python distribution in this environment, and its name."""
    owners = {}
    for distribution in importlib.metadata.distributions():
        name = re.sub(r"[-_.]+", "-", distribution.metadata["Name"]).lower()
        for file in distribution.files or ():
            owners[Path(str(distribution.locate_file(file))).resolve()] = name
    return owners


def notice(name: str) -> Notice:
    """The notice of a component that the bundle can contain."""
    if name == "python":
        return Notice(
            f"Python {platform.python_version()} (python-build-standalone {python_build_tag()})"
            " and the libraries built into it (OpenSSL, libffi, SQLite, zlib and others)",
            "Python-2.0 for Python; each library under its own license (LICENSE.<library>.txt)",
            "python",
            "https://www.python.org/downloads/source/ and"
            f" {GITHUB}/astral-sh/python-build-standalone",
        )
    if name == "qt":
        return Notice(
            f"Qt for Python {importlib.metadata.version('pyside6-essentials')}"
            f" (PySide6 and Shiboken6) and Qt {qVersion()}",
            "LGPL-3.0-only; Qt's own third-party parts: https://doc.qt.io/qt-6/licenses-used-in-qt.html",
            "qt",
            "https://download.qt.io/official_releases/QtForPython/ and"
            " https://download.qt.io/official_releases/qt/",
        )
    if name == "icu":
        return Notice(
            "ICU 73.2, the Unicode library inside the Qt for Python wheels",
            "Unicode License Agreement, with the other notices in its text",
            "icu",
            f"{GITHUB}/unicode-org/icu/releases/tag/release-73-2",
        )
    return Notice(
        f"PyInstaller {importlib.metadata.version('pyinstaller')} bootloader and run-time files",
        "GPL-2.0-or-later with the bootloader exception; run-time hooks and modules Apache-2.0",
        "pyinstaller",
        f"{GITHUB}/pyinstaller/pyinstaller",
    )


def copy_license_texts(licenses: Path, notices: set[str]) -> None:
    """The license texts of the pet and of the components with a notice."""
    (licenses / APP).mkdir(parents=True)
    shutil.copy2(ROOT / "LICENSE", licenses / APP)
    for name in notices & {"qt", "icu"}:  # kept in appimage/licenses
        shutil.copytree(HERE / "licenses" / name, licenses / name)
    if "python" in notices:
        shutil.copytree(python_licenses(), licenses / "python")
    pyinstaller = importlib.metadata.distribution("pyinstaller")
    copying = next(file for file in pyinstaller.files or () if file.name == "COPYING.txt")
    (licenses / "pyinstaller").mkdir()
    shutil.copy2(Path(str(pyinstaller.locate_file(copying))), licenses / "pyinstaller")


def copy_package_licenses(folder: Path, packages: dict[str, Package]) -> list[str]:
    """The license texts of the system packages; returns the libraries of those without any."""
    missing = []
    for package in packages.values():
        (folder / package.name).mkdir(parents=True)
        for text in package.license_files:
            shutil.copy(text, folder / package.name / text.name)
        if not package.license_files:
            libraries = sorted(package.libraries)
            missing += [f"{library} ({package.name} has no license files)" for library in libraries]
    return missing


def python_build_tag() -> str | None:
    """The python-build-standalone release of this Python (uv's), or None for another Python."""
    tag = Path(sys.base_prefix, "BUILD")
    return tag.read_text(encoding="utf-8").strip() if tag.is_file() else None


def python_licenses() -> Path:
    """The license texts of this python-build-standalone build: Python's and its libraries'.

    uv installs these builds without the texts, so they come from the matching full build.
    """
    version, tag = platform.python_version(), python_build_tag()
    folder = TOOLS / f"python-{version}+{tag}-licenses"
    if folder.is_dir():
        return folder
    triple = sysconfig.get_config_var("HOST_GNU_TYPE")
    name = f"cpython-{version}+{tag}-{triple}-pgo+lto-full.tar.zst"
    sums = TOOLS / f"python-{tag}-SHA256SUMS"
    download(f"{PYTHON_BUILDS}/{tag}/SHA256SUMS", sums)
    lines = sums.read_text(encoding="utf-8").splitlines()
    expected = {file: digest for digest, file in (line.split() for line in lines)}
    archive = TOOLS / name
    if download(f"{PYTHON_BUILDS}/{tag}/{urllib.parse.quote(name)}", archive) != expected[name]:
        sys.exit(f"{name} does not match the release's SHA256SUMS")
    partial = folder.with_name(folder.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir()
    with tarfile.open(archive, mode="r:zst") as full_build:
        for member in full_build:
            text = full_build.extractfile(member) if member.isfile() else None
            if text and member.name.startswith("python/licenses/"):
                (partial / Path(member.name).name).write_bytes(text.read())
    partial.rename(folder)
    archive.unlink()
    return folder


def system_package(library: Path) -> Package | None:
    """The distribution package that the library comes from, with its license texts."""
    paths = [library, library.resolve()]
    paths += [merged_usr_twin(path) for path in paths]
    for find in (dpkg_package, rpm_package, pacman_package):
        for path in dict.fromkeys(paths):
            if package := find(path):
                return package
    return None


def merged_usr_twin(path: Path) -> Path:
    """The same file seen through the other side of a merged /usr (/lib is /usr/lib)."""
    text = str(path)
    return Path(text.removeprefix("/usr")) if text.startswith("/usr/") else Path("/usr" + text)


def query(*command: str) -> str:
    """The output of a package manager query; "" if it failed or the tool isn't installed."""
    if not shutil.which(command[0]):
        return ""
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def dpkg_package(path: Path) -> Package | None:
    """Debian, Ubuntu and derivatives: the license is the package's copyright file."""
    if not (found := query("dpkg-query", "--search", str(path))):
        return None
    name = found.split(": ")[0].split(", ")[0].split(":")[0]  # "libfoo1:amd64: /usr/lib/…"
    copyright_file = Path("/usr/share/doc", name, "copyright")
    return Package(
        name,
        query("dpkg-query", "--show", "--showformat=${Version}", name),
        [copyright_file] if copyright_file.is_file() else [],
    )


def rpm_package(path: Path) -> Package | None:
    """Fedora, openSUSE and other RPM distributions: the package's license files."""
    found = query(
        "rpm", "--query", "--file", "--queryformat=%{NAME} %{VERSION}-%{RELEASE}\n", str(path)
    )
    if not found:
        return None
    name, version = found.splitlines()[0].split()
    files = [Path(line) for line in query("rpm", "--query", "--licensefiles", name).splitlines()]
    return Package(name, version, [file for file in files if file.is_file()])


def pacman_package(path: Path) -> Package | None:
    """Arch and derivatives: the package's license folder, else the common license texts."""
    if not (name := query("pacman", "--query", "--owns", "--quiet", str(path))):
        return None
    fields = [
        line.split(":", 1) for line in query("pacman", "--query", "--info", name).splitlines()
    ]
    info = {pair[0].strip(): pair[1].strip() for pair in fields if len(pair) == 2}  # noqa: PLR2004
    files = sorted(Path("/usr/share/licenses", name).glob("*"))
    for spdx in info.get("Licenses", "").split():
        files += [
            Path("/usr/share/licenses/spdx", f"{spdx}.txt"),
            Path("/usr/share/licenses/common", spdx, "license.txt"),
        ]
    return Package(name, info.get("Version", ""), [file for file in files if file.is_file()])


def notice_index(version: str, components: list[Notice], packages: dict[str, Package]) -> str:
    """THIRD-PARTY-NOTICES.txt: what the AppImage contains, under which licenses, from where."""
    lines = [
        f"Virtual Pet {version}",
        COPYRIGHT,
        f"License: GPL-3.0-only (texts in {APP}/)",
        f"Source code: {REPOSITORY}",
        "",
        "This AppImage also contains the software below, each under its own license.",
        "The license texts are in the folders named here, next to this file.",
        "",
    ]
    for component in components:
        lines += [
            component.name,
            f"  License: {component.license}",
            f"  Texts: {component.texts}/",
            f"  Source: {component.source}",
            "",
        ]
    if packages:
        distribution = platform.freedesktop_os_release().get("PRETTY_NAME", "Linux")
        lines += [
            f"Libraries from {distribution}, where this AppImage was built. Their source code is",
            "in that distribution's source packages of the same names and versions.",
        ]
        for package in sorted(packages.values(), key=lambda package: package.name):
            libraries = ", ".join(sorted(package.libraries))
            lines.append(
                f"  {package.name} {package.version} ({libraries}): system/{package.name}/"
            )
    return "\n".join(lines) + "\n"


def fetch(tool: Download) -> Path:
    """A pinned download, kept in build/appimage/tools and checked against its SHA-256."""
    path = TOOLS / Path(urllib.parse.urlparse(tool.url).path).name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != tool.sha256:
        digest = download(tool.url, path)
        path.chmod(0o755)
        if digest != tool.sha256:
            path.unlink()
            sys.exit(f"{tool.url} does not match its pinned SHA-256 (see build.py)")
    return path


def download(url: str, path: Path) -> str:
    """Save the URL's content to the path; returns the content's SHA-256."""
    print(f"Downloading {url}")
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with urllib.request.urlopen(url) as response, path.open("wb") as file:  # noqa: S310 (https only)
        while chunk := response.read(2**20):
            digest.update(chunk)
            file.write(chunk)
    return digest.hexdigest()


def pack(appdir: Path, appimage: Path) -> None:
    """Pack the AppDir into the AppImage with the pinned runtime."""
    appimage.parent.mkdir(exist_ok=True)
    subprocess.run(
        [
            str(fetch(APPIMAGETOOL)),
            "--appimage-extract-and-run",  # appimagetool is an AppImage too: this spares it FUSE
            "--no-appstream",
            f"--runtime-file={fetch(RUNTIME)}",
            str(appdir),
            str(appimage),
        ],
        env={**os.environ, "ARCH": ARCH},
        check=True,
    )


def run_process_tests(appimage: Path) -> None:
    """Start the AppImage the way tests/test_app.py starts the app from source."""
    subprocess.run(
        [sys.executable, "-m", "pytest", "--no-cov", "-m", "process", "tests/test_app.py"],
        cwd=ROOT,
        env={**os.environ, "VIRTUAL_PET_EXECUTABLE": str(appimage)},
        check=True,
    )


def glibc_needed(folder: Path) -> tuple[int, int]:
    """The newest glibc version that the ELF files in the folder ask for."""
    versions = {(2, 0)}
    for path in folder.rglob("*"):
        if path.is_file() and not path.is_symlink():
            content = path.read_bytes()
            if content.startswith(b"\x7fELF"):
                versions |= {(int(major), int(minor)) for major, minor in GLIBC.findall(content)}
    return max(versions)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)  # the tool that failed has already said why
