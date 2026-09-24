"""The pet's icon in the system tray, where a hidden pet waits to be shown again."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from virtual_pet.i18n import arg
from virtual_pet.icon import app_icon

# A click, and the double click some trays send instead. The right click opens the menu.
SHOWING_CLICKS = {
    QSystemTrayIcon.ActivationReason.Trigger,
    QSystemTrayIcon.ActivationReason.DoubleClick,
}


class PetTray(QSystemTrayIcon):
    """The app's paw print in the system tray while the pet hides: a click brings it back.

    On KDE Plasma, and GNOME with the AppIndicator extension, Qt shows it through D-Bus
    (StatusNotifierItem), and elsewhere in the older X11 tray, if the desktop has one.
    """

    show_requested = Signal()
    quit_requested = Signal()

    def __init__(self) -> None:
        super().__init__(app_icon())
        self._menu = QMenu()  # a tray icon isn't a widget, so it can't be the menu's parent
        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)

    def show_for(self, name: str) -> None:
        """Show the icon for the pet called `name`, in the interface's current language."""
        self.setToolTip(arg(self.tr("Click to show %1"), name))
        self._menu.clear()
        show = self._menu.addAction(arg(self.tr("Show %1"), name.replace("&", "&&")))
        show.triggered.connect(self.show_requested)
        self._menu.setDefaultAction(show)  # in bold: what a click on the icon does
        self._menu.addSeparator()
        self._menu.addAction(self.tr("Quit")).triggered.connect(self.quit_requested)
        self.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in SHOWING_CLICKS:
            self.show_requested.emit()
