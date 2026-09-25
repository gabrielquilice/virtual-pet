"""The frameless, transparent, always-on-top window where the pet lives."""

import html
import random
import time
from typing import override

from PySide6.QtCore import QCoreApplication, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import (
    QContextMenuEvent,
    QGuiApplication,
    QHideEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QScreen,
    QShowEvent,
)
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from virtual_pet import sprites
from virtual_pet.behavior import Activity, Area, Facing, PetBehavior
from virtual_pet.species import Species

WALKING_TICK_MS = 33  # about 30 updates per second, for smooth movement
RESTING_TICK_MS = 100  # enough for tail wags and blinks, and easier on the battery
BLINK_INTERVAL = (2.0, 6.0)  # seconds between blinks
BLINK_DURATION = 0.15  # seconds


class PetWindow(QWidget):
    """Shows the pet above every other window and lets the user play with it.

    Left click: sit down / get up. Left drag: carry the pet somewhere else.
    Right click: menu with the pet's name, sit/walk (or fly, swim, coil up/slither), turn
    around, hide, settings and quit.
    """

    state_changed = Signal()  # the user moved the pet, made it sit/get up or turned it
    hide_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(  # noqa: PLR0913 - the state it starts in, as keywords with defaults
        self,
        name: str,
        species: Species,
        *,
        position: tuple[int, int] | None = None,
        sitting: bool = False,
        facing: Facing = Facing.RIGHT,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # no taskbar entry
            | Qt.WindowType.WindowDoesNotAcceptFocus  # never steals the keyboard...
            # ...which X11 window managers only fully respect for windows they don't manage:
            # otherwise clicking the pet would still take focus away from the user's app.
            | Qt.WindowType.X11BypassWindowManagerHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)  # even though never active
        self.setFixedSize(
            sprites.FRAME_WIDTH * sprites.PIXEL_SIZE, sprites.FRAME_HEIGHT * sprites.PIXEL_SIZE
        )
        self._name = ""
        self.set_name(name)
        self._species = species

        self._rng = rng if rng is not None else random.Random()  # noqa: S311 - not security related
        area, start = self._starting_point(position)
        self._behavior = PetBehavior(
            area, start, sitting=sitting, facing=facing, rng=self._rng, gait=species.gait
        )
        self._activity = self._behavior.activity
        self._animation_time = 0.0
        self._until_blink = self._rng.uniform(*BLINK_INTERVAL)
        self._frame: sprites.Frame = ()
        self._blinking = False
        self._press_position: QPoint | None = None  # where a left-button press started
        self._grab_offset = QPoint()  # cursor position relative to the window's corner
        self._dragging = False

        self._last_tick = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(RESTING_TICK_MS)
        self._timer.timeout.connect(self._on_timer)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._watch_screens()
        self._sync()

    @property
    def sitting(self) -> bool:
        """Whether the pet was told to sit."""
        return self._behavior.sitting

    @property
    def facing(self) -> Facing:
        """Which way the pet looks."""
        return self._behavior.facing

    @property
    def species(self) -> Species:
        return self._species

    def set_species(self, species: Species) -> None:
        """Swap the pet for another kind of animal, in the same spot."""
        self._species = species
        self._behavior.set_gait(species.gait)
        self._frame = ()  # force a redraw with the new look
        self._sync()

    def set_name(self, name: str) -> None:
        """Show a new name on hover and in the menu."""
        self._name = name
        # As rich text, a name like "<Rex>" isn't mistaken for markup (and it shows in bold).
        self.setToolTip(f"<b>{html.escape(name)}</b>")

    def context_menu(self) -> QMenu:
        """The menu shown on right click."""
        menu = QMenu(self)
        title = menu.addAction(self._name.replace("&", "&&"))  # "&" would mark a shortcut
        title.setEnabled(False)
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        menu.addSeparator()
        toggle_text = self._species.roam_label if self.sitting else self._species.sit_label
        toggle_text = QCoreApplication.translate("PetWindow", toggle_text)
        menu.addAction(toggle_text).triggered.connect(self._toggle_sitting)
        menu.addAction(self.tr("Turn around")).triggered.connect(self._turn_around)
        menu.addAction(self.tr("Hide")).triggered.connect(self.hide_requested)
        menu.addAction(self.tr("Settings…")).triggered.connect(self.settings_requested)
        menu.addSeparator()
        menu.addAction(self.tr("Quit")).triggered.connect(self.quit_requested)
        return menu

    def advance(self, seconds: float) -> None:
        """Let `seconds` of the pet's life go by: walk, rest, animate, blink."""
        self._behavior.tick(seconds)
        self._animation_time += seconds
        self._until_blink -= seconds
        if self._until_blink < -BLINK_DURATION:
            self._until_blink = self._rng.uniform(*BLINK_INTERVAL)
        self._sync()

    @override
    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._last_tick = time.monotonic()
        self._timer.start()

    @override
    def hideEvent(self, event: QHideEvent) -> None:
        self._timer.stop()
        super().hideEvent(event)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        with QPainter(self) as painter:
            image = self._species.image(self._frame, blinking=self._blinking)
            painter.drawImage(self.rect(), image)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        if self._dragging:  # the previous drag never got its release (e.g. a broken grab)
            self._behavior.put_down()
        self._press_position = event.globalPosition().toPoint()
        self._grab_offset = self._press_position - self.pos()
        self._dragging = False

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_position is None:
            super().mouseMoveEvent(event)
            return
        cursor = event.globalPosition().toPoint()
        if not self._dragging:
            if (cursor - self._press_position).manhattanLength() < QApplication.startDragDistance():
                return  # still just a click
            self._dragging = True
            self._behavior.pick_up()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        screen = QGuiApplication.screenAt(cursor) or self.screen()
        self._behavior.set_area(self._area_on(screen))
        corner = cursor - self._grab_offset
        self._behavior.move_to(corner.x(), corner.y())
        self._sync()

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press_position is None:
            super().mouseReleaseEvent(event)
            return
        dragged, self._dragging, self._press_position = self._dragging, False, None
        if not dragged:
            self._toggle_sitting()
            return
        self._behavior.put_down()
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._sync()
        self.state_changed.emit()

    @override
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self._timer.stop()  # the pet waits while its menu is open
        menu = self.context_menu()
        menu.exec(event.globalPos())
        menu.deleteLater()
        self._last_tick = time.monotonic()
        if self.isVisible():
            self._timer.start()

    def _toggle_sitting(self) -> None:
        self._behavior.toggle_sitting()
        self._sync()
        self.state_changed.emit()

    def _turn_around(self) -> None:
        self._behavior.turn_around()
        self._sync()
        self.state_changed.emit()

    def _on_timer(self) -> None:
        now = time.monotonic()
        self.advance(now - self._last_tick)
        self._last_tick = now

    def _sync(self) -> None:
        """Bring the window's position and picture in line with the pet's state."""
        x, y = self._behavior.position
        position = QPoint(round(x), round(y))
        if position != self.pos():
            self.move(position)

        activity = self._behavior.activity
        if activity is not self._activity:
            self._activity, self._animation_time = activity, 0.0
        interval = WALKING_TICK_MS if activity is Activity.WALKING else RESTING_TICK_MS
        if self._timer.interval() != interval:
            self._timer.setInterval(interval)
        frame = self._species.animations[activity].frame_at(self._animation_time)
        if self._behavior.facing is Facing.LEFT:
            frame = sprites.mirrored(frame)
        blinking = self._until_blink <= 0 and activity is not Activity.CARRIED
        if frame != self._frame:
            # Clicks on the transparent parts of the window reach whatever is behind it.
            self.setMask(sprites.silhouette(frame, sprites.PIXEL_SIZE))
        if (frame, blinking) != (self._frame, self._blinking):
            self._frame, self._blinking = frame, blinking
            self.update()

    def _watch_screens(self) -> None:
        """Keep the pet on screen when monitors are plugged, unplugged or resized."""
        app = QGuiApplication.instance()
        if not isinstance(app, QGuiApplication):
            return
        for screen in app.screens():
            self._on_screen_added(screen)
        app.screenAdded.connect(self._on_screen_added)
        app.screenRemoved.connect(self._on_screen_removed)

    def _on_screen_added(self, screen: QScreen) -> None:
        screen.availableGeometryChanged.connect(self._fit_to_screen)

    def _on_screen_removed(self, _screen: QScreen) -> None:
        QTimer.singleShot(0, self, self._fit_to_screen)  # once Qt is done removing it

    def _fit_to_screen(self) -> None:
        center = self.geometry().center()
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        self._behavior.set_area(self._area_on(screen))
        self._sync()

    def _area_on(self, screen: QScreen) -> Area:
        """Where the window may go on `screen` without any part of it leaving the screen."""
        available = screen.availableGeometry()
        return Area(
            left=available.left(),
            top=available.top(),
            right=available.left() + available.width() - self.width(),
            bottom=available.top() + available.height() - self.height(),
        )

    def _starting_point(self, saved: tuple[int, int] | None) -> tuple[Area, tuple[float, float]]:
        if saved is not None:
            screen = QGuiApplication.screenAt(QPoint(*saved))
            if screen is not None:
                return self._area_on(screen), saved
        area = self._area_on(QGuiApplication.primaryScreen())
        return area, ((area.left + area.right) / 2, area.bottom)  # on the "floor", centered
