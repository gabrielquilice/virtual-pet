"""The app's icon: a cream paw print on a rounded orange tile, drawn smooth at any size."""

from functools import cache
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap

SILHOUETTE = Path(__file__).with_name("paw.png")  # the paw's shape, in its alpha channel
TILE, RIM, PAW = QColor("#dc9a57"), QColor("#3b2518"), QColor("#f7ead5")  # the dog's colors
SIZES = (16, 22, 24, 32, 48, 64, 128, 256)  # the icon theme's usual sizes, for the AppImage
TRAY_AT_200_PERCENT = 44  # the tray's 22 px on a screen scaled to 200%
FIRM_UP_TO, CONTRAST = 32, 1.6  # small icons get steeper edges, which keep the toes apart


@cache
def icon_image(size: int) -> QImage:
    """The icon, `size` pixels wide, laid out on a grid of 32 units."""
    unit = size / 32
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    with QPainter(image) as painter:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Whole pixels for the margin and the rim, so a thin rim stays one sharp pixel.
        margin = rim = max(1, round(unit))
        inset = margin + rim / 2
        tile = QPainterPath()
        side = size - 2 * inset
        tile.addRoundedRect(QRectF(inset, inset, side, side), 3.5 * unit, 3.5 * unit)
        painter.fillPath(tile, TILE)
        painter.setPen(QPen(RIM, rim))
        painter.drawPath(tile)
        paw = _paw(round(24 * unit), firm=size <= FIRM_UP_TO)
        left = round((size - paw.width()) / 2)
        top = round((size - paw.height()) / 2 + 0.3 * unit)  # a bit low, as the pad is heavy
        painter.drawImage(left, top, paw)
    return image


def app_icon() -> QIcon:
    """The icon of the app's windows and of its tray icon, in every size it is drawn at."""
    icon = QIcon()
    for size in (*SIZES, TRAY_AT_200_PERCENT):
        icon.addPixmap(QPixmap.fromImage(icon_image(size)))
    return icon


def _paw(width: int, *, firm: bool) -> QImage:
    """The paw in its color, `width` pixels wide; `firm` steepens its edges."""
    silhouette = _silhouette()
    height = round(width * silhouette.height() / silhouette.width())
    shape = silhouette.scaled(
        width,
        height,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if firm:
        shape = _firmer(shape)
    paw = QImage(shape.size(), QImage.Format.Format_ARGB32_Premultiplied)
    paw.fill(Qt.GlobalColor.transparent)
    with QPainter(paw) as painter:
        painter.drawImage(0, 0, shape)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(paw.rect(), PAW)  # the paw's color, where the shape is
    return paw


def _firmer(shape: QImage) -> QImage:
    """The shape with steeper edges: its alpha pulled away from the middle, by CONTRAST."""
    firm = shape.convertToFormat(QImage.Format.Format_ARGB32)
    for y in range(firm.height()):
        for x in range(firm.width()):
            color = firm.pixelColor(x, y)
            color.setAlphaF(min(1.0, max(0.0, (color.alphaF() - 0.5) * CONTRAST + 0.5)))
            firm.setPixelColor(x, y, color)
    return firm


@cache
def _silhouette() -> QImage:
    silhouette = QImage(str(SILHOUETTE))
    if silhouette.isNull():
        msg = f"the paw's silhouette is missing: {SILHOUETTE}"
        raise FileNotFoundError(msg)
    return silhouette
