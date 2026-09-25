"""Build the pet for Windows on this Linux machine: dist/VirtualPet-<version>-windows-x64.zip.

    uv run windows/build.py

PyInstaller doesn't cross-compile, so it runs on Windows' own Python under Wine, in the
build's own Wine prefix, build/windows/wine (the user's ~/.wine is never touched). There:

1. The build gets Windows' Python (python-build-standalone, pinned below) and has uv install
   the Windows wheels of uv.lock's packages (Qt for Python, PyInstaller) in a folder for it.
2. PyInstaller bundles the app with that Python and Qt (virtual-pet.spec).
3. The bundle gets the licenses of everything it contains and goes into the zip.
4. The bundle starts under Wine, in Portuguese: it must take its lock, load its
   translations and answer a second start.

Qt's Core asks Windows for its ICU, icuuc.dll (Windows has it since 10 version 1903), which
Wine lacks. So the Wine prefix gets a stub of the functions Qt takes from it, which all
return 0: Qt only uses them for text encodings other than UTF-8, which the pet never needs.
The stub never goes in the bundle. And Wine isn't Windows: the test shows that the bundle
is complete, not that the pet behaves on a Windows desktop.

The version is the AppImage's, from pyproject.toml and the checkout (appimage/build.py).
"""

import argparse
import getpass
import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import time
import tomllib
import zipfile
from pathlib import Path
from types import ModuleType

from PySide6.QtCore import QBuffer, QByteArray, QIODevice

from virtual_pet.icon import icon_image

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "windows"
WORK = ROOT / "build" / "windows"
TOOLS = WORK / "tools"  # downloads, kept between builds
PREFIX = WORK / "wine"
PACKAGES = WORK / "site-packages"  # the Windows wheels, for Windows' Python
DIST = ROOT / "dist"
PLATFORM = "x86_64-pc-windows-msvc"
PYTHON_VERSION, PYTHON_RELEASE = "3.14.7", "20260901"  # the python-build-standalone bundled
PYTHON = f"cpython-{PYTHON_VERSION}+{PYTHON_RELEASE}-{PLATFORM}"
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 256)  # Windows' icon sizes at 100 to 200% scale
# The Visual C++ runtime, which Python and Qt for Python ship for themselves.
MSVC_RUNTIME = re.compile(r"(vcruntime|msvcp|concrt|vccorlib)140(_\w+)?\.dll", re.IGNORECASE)
STARTUP_TIMEOUT = 60  # seconds for the pet to start under Wine
WINE_TIMEOUT = 1800  # seconds for any Wine command, the bundling included


def load_appimage_build() -> ModuleType:
    """appimage/build.py, whose version naming, downloads and notices this build shares."""
    spec = importlib.util.spec_from_file_location("appimage_build", ROOT / "appimage" / "build.py")
    if spec is None or spec.loader is None:
        sys.exit("appimage/build.py is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = load_appimage_build()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the pet for Windows, with Wine.")
    parser.add_argument("--skip-tests", action="store_true", help="don't start the bundle")
    parser.add_argument(
        "--allow-missing-licenses",
        action="store_true",
        help="build even if the license of some bundled file was not found",
    )
    args = parser.parse_args()
    missing_tools = [tool for tool in ("uv", "wine", "wineboot", "wineserver") if not which(tool)]
    if missing_tools:
        sys.exit(f"The Windows build needs {', '.join(missing_tools)} (Wine: the wine package)")

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    release = pyproject["project"]["version"]
    version = common.release_version(release)
    if version != release:
        print(f"Building {version}: not a clean checkout of tag v{release}")
    common.step("1/4 Setting up Windows' Python and Qt under Wine")
    python = windows_python()
    install_packages()
    prepare_wine()
    common.step("2/4 Bundling the pet with PyInstaller")
    write_icon(WORK / "virtual-pet.ico")
    write_version_info(WORK / "version-info.txt", release, version)
    bundle, manifest = run_pyinstaller(python)
    common.step("3/4 Gathering the licenses and zipping the bundle")
    missing = add_licenses(bundle / "licenses", manifest, version)
    if missing and not args.allow_missing_licenses:
        sys.exit(
            "No license found for these bundled files (--allow-missing-licenses builds anyway):\n  "
            + "\n  ".join(missing)
        )
    archive = DIST / f"VirtualPet-{version}-windows-x64.zip"
    zip_folder(bundle, archive)
    if not args.skip_tests:
        common.step("4/4 Starting the bundle under Wine")
        run_smoke_test(bundle)
    size = archive.stat().st_size / 2**20
    print(f"\n{archive.relative_to(ROOT)}: {size:.1f} MiB, for 64-bit Windows 10 (1903) or 11")


def which(tool: str) -> str:
    """The tool's path; "" if it isn't installed."""
    return shutil.which(tool) or ""


def wine_environment(**variables: str) -> dict[str, str]:
    """The environment of Wine commands: the build's prefix, and no display at all.

    Without a display nothing Wine starts can show up on the user's desktop; the pet runs
    on Qt's offscreen platform. Wine's Mono and Gecko, which it offers to install, are off,
    and so is its menu builder, which would put the prefix's programs and file types in the
    user's menus and file associations.
    """
    environment = {
        **os.environ,
        "WINEPREFIX": str(PREFIX),
        "WINEDEBUG": "-all",
        "WINEDLLOVERRIDES": "mscoree,mshtml,winemenubuilder.exe=",
        **variables,
    }
    for display in ("DISPLAY", "WAYLAND_DISPLAY"):
        environment.pop(display, None)
    return environment


def windows_path(path: Path) -> str:
    """How Windows programs under Wine see a path of this machine: on drive Z."""
    return "Z:" + str(path).replace("/", "\\")


def linux_path(path: str) -> Path:
    """The file of this machine that a Windows path under Wine names."""
    drive, rest = path[0].lower(), path[2:].replace("\\", "/")
    if drive == "z":
        return Path(rest)
    return PREFIX / "dosdevices" / f"{drive}:" / rest.lstrip("/")


def windows_python() -> Path:
    """Windows' python.exe, from python-build-standalone, kept in build/windows/tools."""
    folder = TOOLS / PYTHON
    if not (folder / "python.exe").is_file():
        archive = common.python_build_file(f"{PYTHON}-install_only.tar.gz", TOOLS)
        partial = folder.with_name(folder.name + ".partial")
        shutil.rmtree(partial, ignore_errors=True)
        with tarfile.open(archive) as build:
            build.extractall(partial, filter="data")
        shutil.rmtree(folder, ignore_errors=True)
        (partial / "python").rename(folder)
        partial.rmdir()
    return folder / "python.exe"


def install_packages() -> None:
    """Have uv install the Windows wheels of uv.lock's runtime and build packages."""
    requirements = WORK / "requirements.txt"
    uv = which("uv")
    subprocess.run(
        [
            uv,
            "export",
            f"--project={ROOT}",
            "--locked",
            "--no-dev",
            "--group=build",
            "--no-emit-project",
            "--quiet",
            f"--output-file={requirements}",
        ],
        check=True,
    )
    shutil.rmtree(PACKAGES, ignore_errors=True)
    python_version = ".".join(PYTHON_VERSION.split(".")[:2])
    subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--quiet",
            f"--target={PACKAGES}",
            f"--python-platform={PLATFORM}",
            f"--python-version={python_version}",
            "--require-hashes",
            f"--requirement={requirements}",
        ],
        check=True,
    )


def prepare_wine() -> None:
    """Make the build's Wine prefix, if it isn't there yet, and give it Qt's ICU stub."""
    if not (PREFIX / "system.reg").is_file():
        print(f"Making the Wine prefix {PREFIX.relative_to(ROOT)}", flush=True)
        subprocess.run(
            ["wineboot", "--init"], env=wine_environment(), check=True, timeout=WINE_TIMEOUT
        )
    qt_core = PACKAGES / "PySide6" / "Qt6Core.dll"
    functions = imported_functions(qt_core, "icuuc.dll")
    system = PREFIX / "drive_c" / "windows" / "system32"
    (system / "icuuc.dll").write_bytes(stub_dll("icuuc.dll", functions))


def imported_functions(library: Path, dll: str) -> list[str]:
    """The functions `library` imports from `dll`, as the pefile of the Windows packages reads."""
    script = (
        "import sys, pefile\n"
        "pe = pefile.PE(sys.argv[1])\n"
        "for entry in pe.DIRECTORY_ENTRY_IMPORT:\n"
        "    if entry.dll.decode().lower() == sys.argv[2]:\n"
        "        print(*(function.name.decode() for function in entry.imports), sep='\\n')\n"
    )
    names = subprocess.run(
        [sys.executable, "-c", script, str(library), dll.lower()],
        env={**os.environ, "PYTHONPATH": str(PACKAGES)},  # pefile is pure Python
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    if not names:
        sys.exit(f"{library.name} imports nothing from {dll}: its stub needs a look")
    return names


def stub_dll(name: str, functions: list[str]) -> bytes:
    """A 64-bit DLL named `name` whose functions all return 0 (xor eax, eax; ret).

    One section holds the code and the export table; the DLL has no entry point, no imports
    and no relocations, as its code is the same wherever it is loaded.
    """
    file_alignment, section_alignment, start = 0x200, 0x1000, 0x1000
    names = sorted(functions)  # the loader looks names up by binary search
    table = start + 16  # the export directory, after the code
    addresses = table + 40
    name_pointers = addresses + 4 * len(names)
    ordinals = name_pointers + 4 * len(names)
    strings = ordinals + 2 * len(names)
    text = name.encode() + b"\0"
    name_addresses = []
    for function in names:
        name_addresses.append(strings + len(text))
        text += function.encode() + b"\0"
    count = len(names)
    section = b"\x31\xc0\xc3".ljust(16, b"\xcc")
    section += struct.pack(
        "<IIHHIIIIIII", 0, 0, 0, 0, strings, 1, count, count, addresses, name_pointers, ordinals
    )
    section += struct.pack(f"<{count}I", *[start] * count)  # every function is the same code
    section += struct.pack(f"<{count}I", *name_addresses)
    section += struct.pack(f"<{count}H", *range(count))
    section += text
    raw_size = -(-len(section) // file_alignment) * file_alignment
    image_size = start + -(-len(section) // section_alignment) * section_alignment

    dos = b"MZ".ljust(0x3C, b"\0") + struct.pack("<I", 0x40)
    dll_characteristics = 0x2022  # executable, large-address aware, a DLL
    coff = struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, 0xF0, dll_characteristics)
    optional = struct.pack(
        "<HBBIIIIIQIIHHHHHHIIIIHHQQQQII",
        *(0x20B, 14, 0, raw_size, 0, 0, 0, start, 0x180000000),  # PE32+, code, no entry
        *(section_alignment, file_alignment, 6, 0, 0, 0, 6, 0, 0, image_size, file_alignment),
        *(0, 3, 0x100, 0x100000, 0x1000, 0x100000, 0x1000, 0, 16),  # console, NX, stack, heap
    )
    directories = struct.pack("<II", table, len(section) - 16).ljust(16 * 8, b"\0")
    section_header = struct.pack(
        "<8sIIIIIIHHI", b".text", len(section), start, raw_size, file_alignment, 0, 0, 0, 0,
        0x60000020,  # code, executable, readable
    )  # fmt: skip
    headers = dos + b"PE\0\0" + coff + optional + directories + section_header
    return headers.ljust(file_alignment, b"\0") + section.ljust(raw_size, b"\0")


def write_icon(path: Path) -> None:
    """The app's icon as a Windows .ico, one PNG per size."""
    images = []
    for size in ICON_SIZES:
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        icon_image(size).save(buffer, "PNG")  # ty: ignore[no-matching-overload] - PySide6 takes str
        images.append((size, data.data()))
    offset = 6 + 16 * len(images)
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = b""
    for size, png in images:
        side = size % 256  # 0 stands for 256
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entries + b"".join(png for _, png in images))


def write_version_info(path: Path, release: str, version: str) -> None:
    """The version resource that Windows shows in the file's properties and Task Manager."""
    numbers = (*map(int, re.findall(r"\d+", release)[:4]), 0, 0, 0, 0)[:4]
    strings = {
        "CompanyName": "Gabriel Quilice",
        "FileDescription": "Virtual Pet",
        "FileVersion": version,
        "InternalName": "VirtualPet",
        "LegalCopyright": f"{common.COPYRIGHT}. GPL-3.0-only.",
        "OriginalFilename": "VirtualPet.exe",
        "ProductName": "Virtual Pet",
        "ProductVersion": version,
    }
    table = ",\n".join(f"      StringStruct({key!r}, {value!r})" for key, value in strings.items())
    path.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3F, flags=0x0,
    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
{table}
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
""",
        encoding="utf-8",
    )


def run_pyinstaller(python: Path) -> tuple[Path, dict]:
    """Bundle the app; returns the bundle's folder and where each of its files came from."""
    subprocess.run(
        [
            "wine",
            windows_path(python),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            f"--distpath={windows_path(WORK / 'bundle')}",
            f"--workpath={windows_path(WORK / 'pyinstaller')}",
            windows_path(HERE / "virtual-pet.spec"),
        ],
        env=wine_environment(PYTHONPATH=windows_path(PACKAGES)),
        check=True,
        timeout=WINE_TIMEOUT,
    )
    manifest = WORK / "pyinstaller" / "virtual-pet" / "bundled-files.json"
    return WORK / "bundle" / "VirtualPet", json.loads(manifest.read_text(encoding="utf-8"))


def add_licenses(licenses: Path, manifest: dict, version: str) -> list[str]:
    """Put the license texts of everything in the bundle in `licenses`, with an index.

    Returns the bundled files whose license was not found.
    """
    notices, missing = {"pyinstaller"}, []  # the bootloader is always there
    owners = distribution_files()
    sources = [entry["source"] for entry in manifest["binaries"]] + manifest["modules"]
    for source in sources:
        origin = origin_of(linux_path(source), owners)
        if origin is None:
            missing.append(source)
        elif origin == "wine":
            missing.append(f"{source} (Wine's own: Windows DLLs must never be bundled)")
        elif origin != "pet":
            notices.add(origin)
    shutil.rmtree(licenses, ignore_errors=True)
    (licenses / "virtual-pet").mkdir(parents=True)
    shutil.copy2(ROOT / "LICENSE", licenses / "virtual-pet" / "LICENSE.txt")
    if "qt" in notices:
        shutil.copytree(ROOT / "appimage" / "licenses" / "qt", licenses / "qt")
    if "python" in notices:
        texts = TOOLS / f"{PYTHON}-licenses"
        shutil.copytree(
            common.full_build_licenses(f"{PYTHON}-pgo-full.tar.zst", texts), licenses / "python"
        )
    (licenses / "pyinstaller").mkdir()
    shutil.copy2(distribution_file("pyinstaller", "COPYING.txt"), licenses / "pyinstaller")
    order = ("python", "qt", "msvc", "pyinstaller")
    index = notice_index(version, [notice(name) for name in order if name in notices])
    (licenses / "THIRD-PARTY-NOTICES.txt").write_text(index, encoding="utf-8")
    return missing


def origin_of(source: Path, owners: dict[Path, str]) -> str | None:
    """What covers a bundled file: "pet" (ours), a notice or "wine"; None if nothing does."""
    resolved = source.resolve()
    if MSVC_RUNTIME.fullmatch(resolved.name):
        return "msvc"
    if resolved in owners:
        return common.DISTRIBUTION_NOTICES.get(owners[resolved])
    if resolved.is_relative_to(ROOT / "src"):
        return "pet"
    if resolved.is_relative_to((TOOLS / PYTHON).resolve()):
        return "python"
    if resolved.is_relative_to(PREFIX.resolve()):
        return "wine"
    return None


def distribution_files() -> dict[Path, str]:
    """Every file of the Windows packages, and the name of the distribution it came in."""
    owners = {}
    for distribution in importlib.metadata.distributions(path=[str(PACKAGES)]):
        name = re.sub(r"[-_.]+", "-", distribution.metadata["Name"]).lower()
        for file in distribution.files or ():
            owners[Path(str(distribution.locate_file(file))).resolve()] = name
    return owners


def distribution(name: str) -> importlib.metadata.Distribution:
    """One of the Windows packages."""
    return next(iter(importlib.metadata.distributions(name=name, path=[str(PACKAGES)])))


def distribution_file(name: str, file_name: str) -> Path:
    """A file of one of the Windows packages, found by its name."""
    package = distribution(name)
    file = next(file for file in package.files or () if file.name == file_name)
    return Path(str(package.locate_file(file)))


def notice(name: str) -> "common.Notice":
    """The notice of a component that the bundle can contain."""
    if name == "python":
        return common.Notice(
            f"Python {PYTHON_VERSION} (python-build-standalone {PYTHON_RELEASE}) and the"
            " libraries built into it (OpenSSL, libffi, SQLite, zlib and others)",
            "Python-2.0 for Python; each library under its own license (LICENSE.<library>.txt)",
            "python",
            "https://www.python.org/downloads/source/ and"
            f" {common.GITHUB}/astral-sh/python-build-standalone",
        )
    if name == "qt":
        return common.Notice(
            f"Qt for Python {distribution('pyside6-essentials').version} (PySide6, Shiboken6"
            " and the Qt they are built on)",
            "LGPL-3.0-only; Qt's own third-party parts: https://doc.qt.io/qt-6/licenses-used-in-qt.html",
            "qt",
            "https://download.qt.io/official_releases/QtForPython/ and"
            " https://download.qt.io/official_releases/qt/",
        )
    if name == "msvc":
        return common.Notice(
            "Microsoft Visual C++ runtime (vcruntime140.dll, msvcp140.dll and the like), as"
            " Python and Qt for Python ship it",
            "Microsoft's terms for redistributing it with programs built by Visual C++; a"
            " system library in the sense of the GPL",
            "",
            "not available; see https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files",
        )
    return common.Notice(
        f"PyInstaller {distribution('pyinstaller').version} bootloader and run-time files",
        "GPL-2.0-or-later with the bootloader exception; run-time hooks and modules Apache-2.0",
        "pyinstaller",
        f"{common.GITHUB}/pyinstaller/pyinstaller",
    )


def notice_index(version: str, components: list["common.Notice"]) -> str:
    """THIRD-PARTY-NOTICES.txt: what the bundle contains, under which licenses, from where."""
    lines = [
        f"Virtual Pet {version}",
        common.COPYRIGHT,
        "License: GPL-3.0-only (text in virtual-pet/)",
        f"Source code: {common.REPOSITORY}",
        "",
        "This program also contains the software below, each under its own license.",
        "The license texts are in the folders named here, next to this file.",
        "",
    ]
    for component in components:
        lines += [component.name, f"  License: {component.license}"]
        if component.texts:
            lines.append(f"  Texts: {component.texts}/")
        lines += [f"  Source: {component.source}", ""]
    return "\r\n".join(lines) + "\r\n"  # Windows' own line breaks, for any text editor


def zip_folder(folder: Path, archive: Path) -> None:
    """Zip the folder, under its own name, in a stable order."""
    archive.parent.mkdir(exist_ok=True)
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zip_:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zip_.write(path, path.relative_to(folder.parent))


def run_smoke_test(bundle: Path) -> None:
    """Start the bundle under Wine for a user whose pet speaks Portuguese.

    It must take its lock, load its translations (Qt's too) and answer a second start.
    """
    local = PREFIX / "drive_c" / "users" / getpass.getuser() / "AppData" / "Local"
    settings = local / "virtual-pet" / "config.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(
        json.dumps({"pet_name": "Rex", "species": "cat", "sitting": True, "language": "pt_BR"}),
        encoding="utf-8",
    )
    lock = local / "Temp" / "virtual-pet.lock"
    lock.unlink(missing_ok=True)
    command = ["wine", windows_path(bundle / "VirtualPet.exe")]
    environment = wine_environment(QT_QPA_PLATFORM="offscreen")
    log = WORK / "smoke-test.log"
    with log.open("w", encoding="utf-8") as output:
        pet = subprocess.Popen(command, env=environment, stdout=output, stderr=output)
        try:
            deadline = time.monotonic() + STARTUP_TIMEOUT
            while not lock.exists() and pet.poll() is None and time.monotonic() < deadline:
                time.sleep(0.2)
            if not lock.exists():
                sys.exit(f"The pet didn't start under Wine (see {log.relative_to(ROOT)})")
            second = subprocess.run(
                command,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=STARTUP_TIMEOUT,
            )
        finally:
            subprocess.run(["wineserver", "--kill"], env=environment, check=False)
            pet.wait(timeout=STARTUP_TIMEOUT)
    text = log.read_text(encoding="utf-8", errors="replace")
    if second.returncode != 0 or "asked to show" not in second.stderr:
        sys.exit(f"A second start didn't reach the pet:\n{second.stderr}")
    if "Could not load" in text or "Traceback" in text:
        sys.exit(f"The pet reported problems under Wine:\n{text}")
    print("The pet started, loaded its translations and answered a second start", flush=True)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)  # the tool that failed has already said why
