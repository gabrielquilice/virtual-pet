"""The app's icon: a paw print on a rounded tile, drawn like the pets."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QImage, QPixmap

from virtual_pet.sprites import art, draw

ICON = art("""
    ................................
    ....KKKKKKKKKKKKKKKKKKKKKKKK....
    ...KBBBBBBBBBBBBBBBBBBBBBBBBK...
    ..KBBBBBBBBBBBBBBBBBBBBBBBBBBK..
    .KBBBBBBBBBBBBBBBBBBBBBBBBBBBBK.
    .KBBBBBBBBBBDBBBBBBDBBBBBBBBBBK.
    .KBBBBBBBBBDWDBBBBDWDBBBBBBBBBK.
    .KBBBBBBBBDWWWDBBDWWWDBBBBBBBBK.
    .KBBBBBBBDWWWWWDDWWWWWDBBBBBBBK.
    .KBBBBBBBDWWWWWDDWWWWWDBBBBBBBK.
    .KBBBBBDDBDWWWDBBDWWWDBDDBBBBBK.
    .KBBBBDWWDDWWWDBBDWWWDDWWDBBBBK.
    .KBBBDWWWWDDDDBBBBDDDDWWWWDBBBK.
    .KBBBDWWWWDBBBBBBBBBBDWWWWDBBBK.
    .KBBBDWWWWDBBBBBBBBBBDWWWWDBBBK.
    .KBBBDWWWWDBBDDDDDDBBDWWWWDBBBK.
    .KBBBBDWWDBDDWWWWWWDDBDWWDBBBBK.
    .KBBBBBDDBDWWWWWWWWWWDBDDBBBBBK.
    .KBBBBBBBDWWWWWWWWWWWWDBBBBBBBK.
    .KBBBBBBBDWWWWWWWWWWWWDBBBBBBBK.
    .KBBBBBBBDWWWWWWWWWWWWDBBBBBBBK.
    .KBBBBBBBDWWWWWWWWWWWWDBBBBBBBK.
    .KBBBBBBBDWWWWWWWWWWWWDBBBBBBBK.
    .KBBBBBBBDWWWWWWWWWWWWDBBBBBBBK.
    .KBBBBBBBBDWWWWWWWWWWDBBBBBBBBK.
    .KBBBBBBBBBDDWWWWWWDDBBBBBBBBBK.
    .KBBBBBBBBBBBDDDDDDBBBBBBBBBBBK.
    .KBBBBBBBBBBBBBBBBBBBBBBBBBBBBK.
    ..KBBBBBBBBBBBBBBBBBBBBBBBBBBK..
    ...KBBBBBBBBBBBBBBBBBBBBBBBBK...
    ....KKKKKKKKKKKKKKKKKKKKKKKK....
    ................................
""")

PALETTE = {  # the dog's colors
    "K": "#3b2518",  # tile outline
    "B": "#dc9a57",  # tile
    "D": "#a4622f",  # pad outlines
    "W": "#f7ead5",  # pads
}

SIZES = (32, 64, 128, 256)  # whole multiples of the art, so its pixels stay square and sharp


def icon_image(size: int) -> QImage:
    """The icon at `size` pixels, which must be a whole multiple of the art's size."""
    if size % len(ICON):
        msg = f"icon size must be a multiple of {len(ICON)}, not {size}"
        raise ValueError(msg)
    return draw(ICON, PALETTE).scaled(
        size, size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation
    )


def app_icon() -> QIcon:
    """The icon of the app's windows, in every size it is drawn at."""
    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(QPixmap.fromImage(icon_image(size)))
    return icon
