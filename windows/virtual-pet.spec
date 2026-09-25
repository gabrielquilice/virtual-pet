# PyInstaller spec of the pet's Windows bundle (windows/build.py runs it, under Wine).
#
# The bundle keeps what the pet needs on Windows and leaves out:
# - the Qt plugins the pet never loads (it keeps the Windows platform, the offscreen one for
#   the build's test, and the styles), and Qt's own translations into languages the pet
#   doesn't speak;
# - then every DLL that nothing left in the bundle links to (OpenGL, the unused parts of
#   the C++ runtime...).
# PyInstaller never bundles Windows' own DLLs, and neither does it here: under Wine, they
# would be Wine's. It also writes bundled-files.json, where each collected binary and Python
# module came from, so that build.py can ship the license of everything in the bundle.

import json
import re
from pathlib import Path, PurePath

from PyInstaller.depend.bindepend import get_imports

ROOT = Path(SPECPATH).parent
SOURCES = ROOT / "src"
WORK = ROOT / "build" / "windows"  # the icon and version resource, made by build.py
TRANSLATIONS = SOURCES / "virtual_pet" / "translations"
# Qt's translation of its own texts (the Cancel button...) into each language the pet speaks.
QT_TRANSLATIONS = {
    f"PySide6/translations/qtbase_{path.stem.removeprefix('virtual_pet_')}.qm"
    for path in TRANSLATIONS.glob("virtual_pet_*.qm")
}

PLUGINS = re.compile(r"PySide6/plugins/")
WANTED_PLUGINS = re.compile(r"PySide6/plugins/(platforms/q(windows|offscreen)\.dll|styles/)")


def posix(dest):
    """A bundle path with forward slashes, as PyInstaller writes them with Windows' own."""
    return PurePath(dest).as_posix()


def wanted(dest):
    return not PLUGINS.match(posix(dest)) or WANTED_PLUGINS.match(posix(dest))


def linked_from(roots, candidates):
    """Names of the candidate libraries that the roots load, directly or not (any case)."""
    by_name = {Path(dest).name.lower(): src for dest, src, _ in candidates}
    found, pending = set(), [src for _, src, _ in roots]
    while pending:
        for name, _ in get_imports(pending.pop()):
            name = Path(name).name.lower()
            if name in by_name and name not in found:
                found.add(name)
                pending.append(by_name[name])
    return found


a = Analysis(
    [str(SOURCES / "virtual_pet" / "__main__.py")],
    pathex=[str(SOURCES)],
    datas=[
        (str(TRANSLATIONS / "*.qm"), "virtual_pet/translations"),
        (str(SOURCES / "virtual_pet" / "paw.png"), "virtual_pet"),  # the icon's paw
    ],
    excludes=["PySide6.QtDBus"],  # QtNetwork stays: Windows' show requests use its local socket
)

binaries = [entry for entry in a.binaries if wanted(entry[0])]
roots = [
    (dest, src, kind)
    for dest, src, kind in binaries
    if kind == "EXTENSION"
    or PLUGINS.match(posix(dest))
    or re.fullmatch(r"python3\d*\.dll", Path(dest).name.lower())
]
linked = linked_from(roots, binaries)
a.binaries = [entry for entry in binaries if entry in roots or Path(entry[0]).name.lower() in linked]

a.datas = [
    (dest, src, kind)
    for dest, src, kind in a.datas
    if not posix(dest).startswith("PySide6/translations/") or posix(dest) in QT_TRANSLATIONS
]

Path(workpath, "bundled-files.json").write_text(
    json.dumps(
        {
            "binaries": [{"path": posix(dest), "source": src} for dest, src, _ in a.binaries],
            "modules": sorted({src for _, src, _ in a.pure + a.scripts if src}),
        },
        indent=1,
    ),
    encoding="utf-8",
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VirtualPet",
    console=False,  # a desktop app: no console window
    icon=str(WORK / "virtual-pet.ico"),
    version=str(WORK / "version-info.txt"),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="VirtualPet")
