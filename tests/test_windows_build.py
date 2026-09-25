import importlib.util
import struct
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the Windows build runs on Linux")

SCRIPT = Path(__file__).resolve().parent.parent / "windows" / "build.py"


def load_build_script():
    """windows/build.py, which is a script rather than a module of the package."""
    spec = importlib.util.spec_from_file_location("windows_build", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load_build_script()


def exported_names(dll: bytes) -> tuple[str, list[str], set[int]]:
    """The DLL's own name, its exported names and where they point, read as Windows would."""
    pe = struct.unpack_from("<I", dll, 0x3C)[0]
    assert dll[pe : pe + 4] == b"PE\0\0"
    optional = pe + 24
    assert struct.unpack_from("<H", dll, optional)[0] == 0x20B  # PE32+, 64-bit
    export_rva = struct.unpack_from("<I", dll, optional + 112)[0]
    sections = optional + struct.unpack_from("<H", dll, pe + 20)[0]
    _, section_rva, _, raw_offset = struct.unpack_from("<IIII", dll, sections + 8)

    def at(rva: int) -> int:
        return rva - section_rva + raw_offset

    def string(rva: int) -> str:
        start = at(rva)
        return dll[start : dll.index(b"\0", start)].decode()

    fields = struct.unpack_from("<IIHHIIIIIII", dll, at(export_rva))
    name, count, functions, names, ordinals = fields[4], fields[7], *fields[8:]
    name_rvas = struct.unpack_from(f"<{count}I", dll, at(names))
    indexes = struct.unpack_from(f"<{count}H", dll, at(ordinals))
    targets = {struct.unpack_from("<I", dll, at(functions) + 4 * index)[0] for index in indexes}
    return string(name), [string(rva) for rva in name_rvas], {at(rva) for rva in targets}


def test_the_icu_stub_exports_every_function_asked_for_sorted_as_the_loader_expects():
    functions = ["ucnv_open", "ucnv_close", "UCNV_TO_U_CALLBACK_SUBSTITUTE"]

    name, names, _ = exported_names(build.stub_dll("icuuc.dll", functions))

    assert name == "icuuc.dll"
    assert names == sorted(functions)


def test_every_function_of_the_icu_stub_returns_zero():
    dll = build.stub_dll("icuuc.dll", ["ucnv_open", "ucnv_close"])

    _, _, code = exported_names(dll)

    assert [dll[offset : offset + 3] for offset in code] == [b"\x31\xc0\xc3"]  # xor eax,eax; ret


def test_the_windows_icon_holds_every_size_as_png(tmp_path):
    path = tmp_path / "pet.ico"

    build.write_icon(path)

    data = path.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    entries = [struct.unpack_from("<BBBBHHII", data, 6 + 16 * index) for index in range(count)]
    assert (reserved, kind) == (0, 1)
    assert [entry[0] or 256 for entry in entries] == list(build.ICON_SIZES)
    assert all(data[offset : offset + 8] == b"\x89PNG\r\n\x1a\n" for *_, offset in entries)


def test_the_version_resource_names_the_release_and_the_build(tmp_path):
    path = tmp_path / "version-info.txt"

    build.write_version_info(path, "0.3.0", "0.3.0+g1a2b3c4")

    text = path.read_text(encoding="utf-8")
    assert "filevers=(0, 3, 0, 0)" in text
    assert "StringStruct('ProductVersion', '0.3.0+g1a2b3c4')" in text


@pytest.mark.parametrize(
    ("windows", "linux"),
    [
        (
            "Z:\\home\\pet\\site-packages\\PySide6\\Qt6Core.dll",
            "/home/pet/site-packages/PySide6/Qt6Core.dll",
        ),
        ("C:\\windows\\system32\\user32.dll", "{prefix}/dosdevices/c:/windows/system32/user32.dll"),
    ],
)
def test_windows_paths_under_wine_lead_to_the_files_of_this_machine(windows, linux):
    assert build.linux_path(windows) == Path(linux.format(prefix=build.PREFIX))


def test_this_machine_s_files_are_on_wine_s_drive_z():
    assert build.windows_path(Path("/home/pet/src")) == "Z:\\home\\pet\\src"


def test_wine_never_shows_anything_on_the_desktop_nor_touches_the_menus(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

    environment = build.wine_environment()

    assert "DISPLAY" not in environment
    assert "WAYLAND_DISPLAY" not in environment
    assert "winemenubuilder.exe=" in environment["WINEDLLOVERRIDES"]
    assert environment["WINEPREFIX"] == str(build.PREFIX)


def test_the_visual_cpp_runtime_gets_its_own_notice(tmp_path):
    assert build.origin_of(tmp_path / "MSVCP140_1.dll", {}) == "msvc"
    assert build.origin_of(tmp_path / "VCRUNTIME140.dll", {}) == "msvc"


def test_a_dll_of_wine_s_own_is_caught():
    dll = build.PREFIX / "drive_c" / "windows" / "system32" / "user32.dll"

    assert build.origin_of(dll, {}) == "wine"
