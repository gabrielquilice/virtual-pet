import pytest
from PySide6.QtGui import QColor

from virtual_pet import icon
from virtual_pet.sprites import TRANSPARENT


def test_icon_is_a_square_of_32_art_pixels():
    assert len(icon.ICON) == 32
    assert all(len(row) == 32 for row in icon.ICON)


def test_icon_uses_only_its_palette():
    assert set("".join(icon.ICON)) - {TRANSPARENT} <= icon.PALETTE.keys()


@pytest.mark.parametrize("size", icon.SIZES)
def test_icon_keeps_sharp_pixels_at_every_size(size):
    image = icon.icon_image(size)

    colors = {image.pixel(x, y) for x in range(size) for y in range(size)}

    assert (image.width(), image.height()) == (size, size)
    assert colors <= {QColor(color).rgba() for color in icon.PALETTE.values()} | {0}


def test_icon_sizes_must_be_whole_multiples_of_the_art():
    with pytest.raises(ValueError, match="multiple of 32"):
        icon.icon_image(48)


@pytest.mark.usefixtures("qapp")  # pixmaps need a running QGuiApplication
def test_windows_get_the_icon_in_every_size():
    sizes = {size.width() for size in icon.app_icon().availableSizes()}

    assert sizes == set(icon.SIZES)
