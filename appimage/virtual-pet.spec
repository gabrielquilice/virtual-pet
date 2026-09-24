# PyInstaller spec of the pet's bundle, the payload of the AppImage (appimage/build.py runs it).
#
# The bundle keeps what the pet needs on X11/XWayland and Wayland desktops, Qt's GTK theme
# included, and leaves out:
# - the Qt modules, plugins and translations the pet never loads (its UI is English only);
# - the libraries every desktop Linux has (the AppImage project's excludelist);
# - then every library that nothing left in the bundle links to.
# It also writes bundled-files.json, where each collected binary and Python module came from,
# so that build.py can ship the license of everything in the bundle.

import json
import re
import subprocess
from pathlib import Path

from PyInstaller.depend.bindepend import get_imports

SOURCES = Path(SPECPATH).parent / "src"

UNUSED_PLUGINS = re.compile(
    r"PySide6/Qt/plugins/("
    r"egldeviceintegrations/"  # embedded displays (EGLFS)
    r"|generic/"  # raw input devices (evdev, TUIO)
    r"|networkinformation/|tls/"  # networking
    # platforms: keeps xcb, wayland and offscreen (for the tests)
    r"|platforms/libq(eglfs|linuxfb|minimal|minimalegl|vkkhrdisplay|vnc)\.so"
    r"|wayland-graphics-integration-client/"  # OpenGL and Vulkan on Wayland
    r"|imageformats/libq(?!svg)\w+\.so"  # PNG is built into Qt; SVG draws the icon theme
    r")"
)

# Libraries assumed present on every desktop Linux, taken from the AppImage project's list:
# https://github.com/AppImageCommunity/pkg2appimage/blob/master/excludelist
SYSTEM_LIBRARIES = {
    # the GNU C library (PyInstaller never bundles it either)
    "ld-linux.so.2", "ld-linux-x86-64.so.2", "libanl.so.1", "libBrokenLocale.so.1",
    "libcidn.so.1", "libc.so.6", "libdl.so.2", "libm.so.6", "libmvec.so.1",
    "libnss_compat.so.2", "libnss_dns.so.2", "libnss_files.so.2", "libnss_hesiod.so.2",
    "libnss_nisplus.so.2", "libnss_nis.so.2", "libpthread.so.0", "libresolv.so.2",
    "librt.so.1", "libthread_db.so.1", "libutil.so.1",
    # C++ runtime, graphics drivers and the display servers' client libraries
    "libstdc++.so.6", "libgcc_s.so.1", "libGL.so.1", "libEGL.so.1", "libGLdispatch.so.0",
    "libGLX.so.0", "libOpenGL.so.0", "libdrm.so.2", "libglapi.so.0", "libgbm.so.1",
    "libxcb.so.1", "libX11.so.6", "libX11-xcb.so.1", "libxcb-dri2.so.0", "libxcb-dri3.so.0",
    "libwayland-client.so.0",
    # fonts, sound and the rest of the base system
    "libfontconfig.so.1", "libfreetype.so.6", "libharfbuzz.so.0", "libfribidi.so.0",
    "libasound.so.2", "libjack.so.0", "libpipewire-0.3.so.0", "libcom_err.so.2",
    "libexpat.so.1", "libgpg-error.so.0", "libICE.so.6", "libSM.so.6", "libusb-1.0.so.0",
    "libuuid.so.1", "libz.so.1", "libgmp.so.10",
}  # fmt: skip


def wanted(dest):
    return not UNUSED_PLUGINS.search(dest) and Path(dest).name not in SYSTEM_LIBRARIES


def linked_from(roots, candidates):
    """Names of the candidate libraries that the roots load, directly or not."""
    by_name = {Path(dest).name: src for dest, src, _ in candidates}
    found, pending = set(), [src for _, src, _ in roots]
    while pending:
        for name, _ in get_imports(pending.pop()):
            name = Path(name).name
            if name in by_name and name not in found:
                found.add(name)
                pending.append(by_name[name])
    return found


def unresolved(path):
    """Names of the libraries that the file needs and this machine lacks."""
    ldd = subprocess.run(["ldd", path], capture_output=True, text=True, check=False).stdout
    return {line.split()[0] for line in ldd.splitlines() if "=> not found" in line}


a = Analysis(
    [str(SOURCES / "virtual_pet" / "__main__.py")],
    pathex=[str(SOURCES)],
    excludes=["PySide6.QtNetwork", "PySide6.QtDBus"],  # collected by PySide6's hook, never used
)

binaries = [entry for entry in a.binaries if wanted(entry[0])]
roots = [
    (dest, src, kind)
    for dest, src, kind in binaries
    if kind == "EXTENSION" or "/plugins/" in dest or dest.startswith("libpython")
]
linked = linked_from(roots, binaries)
a.binaries = [entry for entry in binaries if entry in roots or Path(entry[0]).name in linked]

lacking = set().union(*(unresolved(src) for _, src, _ in a.binaries)) - SYSTEM_LIBRARIES
if lacking:
    raise SystemExit(
        "The bundle needs libraries this machine lacks; install them and build again: "
        + ", ".join(sorted(lacking))
    )

kept = {dest for dest, _, _ in a.binaries}
a.datas = [
    (dest, src, kind)
    for dest, src, kind in a.datas
    if not dest.startswith("PySide6/Qt/translations/") and (kind != "SYMLINK" or src in kept)
]

Path(workpath, "bundled-files.json").write_text(
    json.dumps(
        {
            "binaries": [{"path": dest, "source": src} for dest, src, _ in a.binaries],
            "modules": sorted({src for _, src, _ in a.pure + a.scripts if src}),
        },
        indent=1,
    ),
    encoding="utf-8",
)

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="virtual-pet", upx=False)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="virtual-pet")
