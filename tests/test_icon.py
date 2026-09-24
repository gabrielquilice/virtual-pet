import pytest
from PySide6.QtGui import QColor

from virtual_pet import icon


def rgb(image, x: int, y: int) -> tuple[int, int, int, int]:
    color = image.pixelColor(x, y)
    return color.red(), color.green(), color.blue(), color.alpha()


def opaque(color: QColor) -> tuple[int, int, int, int]:
    return color.red(), color.green(), color.blue(), 255


@pytest.mark.parametrize("size", [*icon.SIZES, icon.TRAY_AT_200_PERCENT])
def test_the_icon_is_drawn_at_any_size(size):
    image = icon.icon_image(size)

    assert (image.width(), image.height()) == (size, size)
    assert rgb(image, 0, 0)[3] == 0  # a rounded tile, with a margin around it


def test_the_icon_is_a_paw_on_a_rounded_tile():
    image = icon.icon_image(256)

    assert rgb(image, 0, 0)[3] == 0  # outside the tile
    assert rgb(image, 128, 12) == opaque(icon.RIM)  # its rim, at the top
    assert rgb(image, 128, 30) == opaque(icon.TILE)
    assert rgb(image, 128, 175) == opaque(icon.PAW)  # the middle of the pad
    assert rgb(image, 97, 77) == opaque(icon.PAW)  # the middle of an upper toe
    assert rgb(image, 128, 77) == opaque(icon.TILE)  # between the upper toes


def test_a_thin_rim_stays_one_sharp_pixel():
    image = icon.icon_image(22)

    left_of_the_middle = [rgb(image, x, 11) for x in range(3)]

    assert left_of_the_middle == [(0, 0, 0, 0), opaque(icon.RIM), opaque(icon.TILE)]


@pytest.mark.usefixtures("qapp")  # pixmaps need a running QGuiApplication
def test_windows_and_the_tray_get_the_icon_in_every_size():
    sizes = {size.width() for size in icon.app_icon().availableSizes()}

    assert sizes == {*icon.SIZES, icon.TRAY_AT_200_PERCENT}
