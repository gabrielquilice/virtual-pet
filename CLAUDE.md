# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A pixel-art desktop pet (dog, cat, maritaca, sea turtle, fish, guinea pig, penguin or snake) written in Python 3.12+ with PySide6 (Qt 6), managed with uv. The stack is cross-platform, but the app is currently built and tested for Linux only (KDE Plasma 6 on Wayland, through XWayland). The scope is deliberately small: the pet roams on its own, a click makes it sit (another click lets it roam), it can be dragged anywhere but never off the screen, and its right-click menu offers Sit/Walk (Sit/Fly for the maritaca, Sit/Swim for the sea turtle and the fish, Coil up/Slither for the snake), Hide, Settings… (name, species and language) and Quit. Hide puts the pet away in the system tray, or, on desktops without one, until the app is opened again. The interface is in English or Brazilian Portuguese, in which the app is called Pet Virtual. It ships as an x86-64 Linux AppImage, built locally by `appimage/build.py` (there is no CI workflow). Run from source on Debian/Ubuntu, Qt's X11 backend needs `libxcb-cursor0`; the AppImage bundles it.

## Commands

```bash
uv sync                      # .venv with runtime and dev dependencies
uv run virtual-pet           # run the app (same as: uv run python -m virtual_pet)
uv run pytest                # full suite on Qt's offscreen platform; fails below 80% coverage
uv run pytest tests/test_behavior.py::test_sitting_pet_stays_where_it_is --no-cov
                             # a single test: --no-cov, otherwise the coverage gate fails the run
uv run ruff check . && uv run ruff format --check .
uv run ty check src/
uv run appimage/build.py     # dist/VirtualPet-<version>-x86_64.AppImage, then its process tests
uv version --bump minor      # a release: then commit it as chore(release): X.Y.Z and tag it vX.Y.Z
VIRTUAL_PET_EXECUTABLE=$PWD/dist/VirtualPet-<version>-x86_64.AppImage uv run pytest -m process --no-cov
                             # the process tests against a built AppImage
uv run pyside6-lupdate src/virtual_pet/*.py src/virtual_pet/pets/*.py -locations none -no-obsolete \
    -ts src/virtual_pet/translations/virtual_pet_pt_BR.ts
                             # after changing UI texts: new ones come in unfinished, gone ones go
uv run pyside6-lrelease src/virtual_pet/translations/virtual_pet_pt_BR.ts   # the .qm the app loads
uv run python -c "from virtual_pet.icon import icon_image; icon_image(256).save('docs/icon.png')"
                             # after changing the icon: the README's picture of it
```

Add dependencies with `uv add` or `uv add --group dev`. Dev tools live in `[dependency-groups]`; PyInstaller is in the `build` group.

## Architecture

- **`behavior.py`** is the pet's brain, in plain Python with no Qt.
  - `PetBehavior` is a small state machine. `Activity` is derived from flags in this order: carried, sitting, walking (has a target), standing.
  - Positions are the window's top-left corner. `Area` is the allowed range for that corner: the screen's available geometry minus the window size. Every move is clamped to it, which is how "never off the screen" is enforced.
  - `Gait` (speed, max slope, stroll length) comes from the species. `tick()` caps dt at 0.1 s so the pet doesn't teleport after a system sleep.
- **`config.py`** holds `Config` and `ConfigStore`, also plain Python. `Config.language` is the interface's language: a code, or None (the default) to follow the system.
  - Writes are atomic: a temp file, then replace.
  - Loading tolerates bad files and fields and falls back to defaults. Settings without a species keep the dog.
- **Art pipeline: `sprites.py`, `species.py`, `pets/`, `icon.py`**
  - A frame is a text grid, one character per art pixel ("." is transparent). Every frame of every species shares one 32×27 canvas, so the window never resizes. Frames face right and are mirrored at runtime.
  - `sprites.draw(frame, palette)` paints a frame one image pixel per art pixel.
  - `Species` bundles key, label, palette, animations per `Activity`, gait, `locomotion` and `sit_label`. It renders frames in its palette through a `functools.cache` keyed on the species' identity.
  - `Locomotion` says how the pet roams, which is what its WALKING animation shows. Its value is the menu text for roaming again ("Walk", "Fly", "Swim", "Slither").
  - `sit_label` is the menu text for sitting down: "Sit", except the snake's "Coil up".
  - `icon.py` draws the app's icon at any size, smooth (antialiased) rather than pixel art: a cream paw, whose shape is the alpha channel of `paw.png`, on a rounded orange tile with a dark rim, in the dog's colors. It is laid out on a grid of 32 units. The margin and the rim are whole pixels, so at 22 px the rim is one sharp pixel, and up to 32 px the paw's edges get extra contrast, which keeps the toes apart. `icon_image(size)` is cached. The README shows it from `docs/icon.png`, drawn at 256 px, and `tests/test_icon.py` fails while that picture differs from what `icon_image(256)` draws.
  - `app_icon()`, the icon of every window and of the tray, holds `SIZES` (the icon theme's usual sizes, 16 to 256 px, which the AppImage installs) and 44 px, the tray's 22 px at 200%.
  - Blinking recolors "E" pixels with the palette's "B" and "H" pixels with "N", so every palette must define B and N.
  - `pets/__init__.py` has `ALL_SPECIES` and `species_by_key()`; unknown keys become the dog. The maritaca is `parakeet` in code and settings and "Maritaca" in the UI. Its WALKING animation is flying.
  - The sea turtle is `turtle` in code and settings and "Sea Turtle" in the UI. The fish is a betta, `fish` in code, settings and file name, and "Fish" in the UI.
  - Both swim: their WALKING animation is swimming. They float in place while STANDING, and only touch the ground when SITTING, which is resting on the bottom.
  - The guinea pig is `guinea_pig` in code, settings and file name, and "Guinea Pig" in the UI. It walks, and its SITTING animation is lying down like a loaf.
  - The penguin is a gentoo, `penguin` in code, settings and file name, and "Penguin" in the UI. It walks (waddles), and its SITTING animation is sitting back on its tail with its toes up, only two rows lower than standing.
  - The penguin's "B" is white, not the black of its head: its eye sits in the white band over it, so blinking closes the eye into a line instead of hiding it.
  - The snake is `snake` in code, settings and file name, and "Snake" in the UI, in the colors of an emerald tree boa. It slithers: its WALKING animation is a wave running from behind the neck to the tail while the raised head keeps still. Its SITTING animation is coiled up in two turns with the head resting on top.
- **`pet_window.py`**: `PetWindow` is a frameless, translucent, always-on-top window with `X11BypassWindowManagerHint`.
  - Why unmanaged: Qt always advertises `WM_TAKE_FOCUS`, so KWin activates a managed window when clicked and takes focus from the user's app.
  - `setMask(silhouette)` follows each frame, so clicks around the pet reach the window below.
  - The timer runs at 33 ms only while walking, 100 ms otherwise. `advance(seconds)` is the public tick that tests drive.
  - Click versus drag is decided by `QApplication.startDragDistance()`. While dragging, the allowed area is the screen under the cursor.
  - It only emits `state_changed`, `hide_requested`, `settings_requested` and `quit_requested`; it never persists anything. Hidden, it doesn't roam: `hideEvent` stops its timer.
- **`tray.py`**: `PetTray` is the app's paw print (`app_icon()`) in the system tray, shown only while the pet hides. A click or double click emits `show_requested`, and its menu has "Show <name>" (the default action) and "Quit". Its `QMenu` has no parent, as a tray icon isn't a widget.
  - Qt shows it over D-Bus, as a StatusNotifierItem, where a watcher runs (KDE Plasma, GNOME with the AppIndicator extension), else in the X11 (XEmbed) tray. `QSystemTrayIcon.isSystemTrayAvailable()` says whether there is either; the offscreen platform has neither.
- **`instance.py`**: one pet at a time. `acquire_lock()` is a `QLockFile` in the runtime folder, with `setStaleLockTime(0)`.
  - The lock's holder listens on a Unix socket next to it (`virtual-pet.socket`, mode 0600), watched by a `QSocketNotifier`. A connection is a request to show the pet: nothing is read. The next lock holder replaces a socket left by a crash.
  - A second start, which can't get the lock, connects (`ask_to_show()`), logs "already running: it was asked to show the pet" and exits 0. If nothing answers, it logs "already running" and exits 1.
- **`i18n.py`** shows the interface in English, the language of the texts in the code, or in a translation.
  - Translations are Qt Linguist files in `src/virtual_pet/translations/`: `virtual_pet_<code>.ts`, edited in Qt Linguist, and the `.qm` that `pyside6-lrelease` compiles from it and the app loads. Both are committed. `LANGUAGES` maps each code to the language's name in itself.
  - `use_language(code)` replaces the installed translators: the app's `.qm` and Qt's own `qtbase_<code>.qm`, which translates Qt's texts (the Cancel button, a text field's context menu). None follows the system (`QLocale.system().uiLanguages()`, the closest language, else English). A file that fails to load is logged as "Could not load".
  - It also sets the app's display name, `APP_DISPLAY_NAME` ("Virtual Pet", "Pet Virtual" in Portuguese). On X11 Qt ends every window title with it ("Settings — Virtual Pet"), and an untitled window, like the pet's, gets just the name. `APP_NAME` in `app.py` ("virtual-pet") names the settings folder, the lock and the X11 window class, and is never translated.
  - Texts with values in them use Qt's markers, `%1`, `%2`…, which `arg(text, *values)` fills in all at once (so a pet named "100%2" stays as it is). Qt Linguist warns when a translation drops a marker, and so does `tests/test_i18n.py`.
  - Texts are marked with `self.tr()` in a class, `QCoreApplication.translate(context, text)` elsewhere, or `QT_TRANSLATE_NOOP(context, text)` where a module-level value is defined (the one in `i18n.py`, typed `str`; PySide6's returns `object`, and lupdate goes by the name): species labels ("Species" context), the menu's roam and sit texts ("PetWindow") and the app's name ("App"). Those are translated where they are shown. PySide6's `self.tr()` uses the class it is written in as the context, as lupdate does, even when a subclass calls it.
- **`dialogs.py`**: `PetDialog` is the adoption dialog on first run. `SettingsDialog` is the same plus a Language field ("System default", then each language by its own name). `ask_for_changes()` takes and returns `Preferences(pet, language)`.
  - The pets are a grid of checkable buttons, `PETS_PER_ROW` (4) per row, so the eight pets make two rows. Every button gets the size of the largest one: in a `QGridLayout`, fixed-width buttons of different widths squeeze their column to the narrowest and cut the longer names.
  - The buttons are children of the dialog from the start, so its style sheet's padding counts when they are measured.
  - The layout's `SetMinimumSize` keeps the dialog at least as large as its contents. Qt opens a window at most 2/3 as wide as the screen, and without that (or with an explicit minimum width, which turns the layout's minimum off) the cards overlapped with the longer Portuguese names on the 800-pixel test screen.
- **`app.py`**
  - On Linux Wayland sessions it sets `QT_QPA_PLATFORM=xcb` (when XWayland is available and no non-Wayland platform was chosen), because Wayland forbids self-positioning and always-on-top.
  - It sets `GDK_GL=disable` unless the user set it. On GNOME-like desktops Qt draws its dialogs with the GTK theme, and GTK would otherwise start OpenGL and load the system's GPU driver (Mesa and LLVM, about 50 MB) that the pet never uses.
  - `main()` takes the lock (`instance.py`) and listens for later starts at once, even during the first run's dialog (whose requests are dropped), so a later start always gets an answer. A `finally` closes the socket.
  - SIGINT/SIGTERM trigger `QTimer.singleShot(0, QApplication.exit)`, because Qt 6's `quit()` does nothing outside `app.exec()`, for example during the first-run dialog. A heartbeat timer lets the Python signal handlers run.
  - `main()` applies the saved language before `ensure_pet()` shows the adoption dialog on first run. The controller applies a language chosen in Settings at once: the menu and the dialogs are built each time they open. The language is never applied outside `main()` and the Settings, so the tests don't follow the machine's language.
  - `PetController.hide_pet()` hides the window and, where there is a system tray, shows the tray icon; it asks at each hide, as a tray can come and go. Without a tray nothing shows (the user asked for no message): opening the app again brings the pet back. `show_pet()`, from the tray or a later start, undoes the hiding. Hiding isn't saved: each start shows the pet. The controller takes `tray_available`, so tests choose whether there is a tray.
  - `PetController` wires the window signals to `dialogs.ask_for_changes()`. It saves to `~/.config/virtual-pet/config.json` (`GenericConfigLocation`, respects `$XDG_CONFIG_HOME`) after every user interaction and on quit.
- **`appimage/`** builds the AppImage on the developer's machine.
  - `virtual-pet.spec` (PyInstaller) keeps the xcb, wayland and offscreen platforms and the platform themes (GTK 3, XDG portal). It drops the other Qt plugins (embedded displays, VNC, networking, input devices, image formats other than SVG), PySide6's QtNetwork and QtDBus modules (QtGui's own D-Bus code, which puts the tray icon on KDE's panel, links `libQt6DBus`, which stays, with `libdbus-1`), and Qt's translations except `qtbase_<code>.qm` for each language the pet has a `.qm` for. It bundles the app's `.qm` files and `paw.png` as data. The license check doesn't look at data files: the app's are GPL, and Qt's are covered by the Qt notice.
  - The spec also leaves out the libraries in the AppImage project's excludelist (glibc, libstdc++, GL, core X11/xcb, fontconfig, freetype, harfbuzz, zlib…), then every library that no extension module, plugin or libpython still links to. It stops if the machine lacks a library that isn't in that list, and writes `bundled-files.json` with the source of every bundled binary and module.
  - `build.py` first starts itself again in `build/appimage/venv`, through `UV_PROJECT_ENVIRONMENT` and `uv run --managed-python --locked --group build`. So the bundle always embeds uv's python-build-standalone Python, whatever the dev `.venv` runs on. Homebrew's Python, for example, isn't portable and has no package licenses.
  - The AppImage is named after `pyproject.toml`'s version only when built from a clean checkout of the release tag, `v<version>`. Any other build adds `+g<commit>` (and `.dirty` for uncommitted changes to tracked files; untracked files don't count), and a release tag on the commit that isn't that version stops the build. `pack()` passes the version to appimagetool as `$VERSION`, which it writes into the AppDir's menu entry as `X-AppImage-Version`.
  - `build.py` then runs PyInstaller and lays out the AppDir: `AppRun` (`exec`, so signals reach the pet), the `.desktop` file (its name, description and keywords also in Portuguese), the icons and the licenses. It packs the AppDir with appimagetool and the type2 runtime, pinned by URL and SHA-256 and cached in `build/appimage/tools/`. Then it runs `pytest -m process` against the AppImage and prints the glibc version the AppImage needs.
  - Licenses: every bundled file must be covered by a notice or a system package, or the build stops.
    - `DISTRIBUTION_NOTICES` maps Python distributions to notices; a new dependency that lands in the bundle needs an entry.
    - System libraries get their package's license files (dpkg, rpm or pacman). dpkg and pacman get one query for all the files: `dpkg-query --search` reads every package's file list on each call, so a query per file takes minutes on a desktop. Package queries, `ldd` in the spec and downloads have timeouts, so nothing hangs silently.
    - uv's Python (python-build-standalone) gets the texts from the matching full build, checked against the release's SHA256SUMS.
    - `appimage/licenses/` holds the texts no package provides: LGPL-3.0 for Qt for Python, and ICU 73.2's license. The build stops if the bundled ICU's major version changes.

## Invariants and conventions

- Only one pet is ever on screen: one window in one app instance. Changing the species in Settings swaps the pet in the same window and spot.
- `tests/test_species.py` enforces the art invariants for every species:
  - all frames are 32×27;
  - they use only palette characters;
  - the lowest visible row is 25 for sitting, for standing unless the species swims, and for walking only if the species walks or slithers;
  - every frame contains the E and H eye pixels.
- Identifiers, file names, comments and docs are in English. UI texts are written in English in the code and translated in `src/virtual_pet/translations/` (Brazilian Portuguese so far). The user writes in Portuguese.
- Commits follow Conventional Commits (`type(scope): summary`) in English, with a short body and a `Co-Authored-By` trailer for the Claude model that made the change.
- The version is static in `pyproject.toml`, as the `modern-python` skill advises, not derived from git. A release is the `uv version --bump` commit, `chore(release): X.Y.Z`, with an annotated tag `vX.Y.Z` on it; the README's Releasing section has the commands.
- New or changed pet art, and the app icon, must be shown to the user as images first: enlarged poses, plus real size on dark and light backgrounds. Wait for approval before it touches the code. The gray tabby cat (redrawn with a round head in profile, dark eyes and a short muzzle, kicking when carried), the sea turtle (brown shell, green skin), the betta (blue body, red fins), the tricolor guinea pig (ginger with a white blaze and band, a black patch, big dark eyes), the gentoo penguin (black and white, an orange bill and feet, a white band over the eye, sitting back on its tail rather than squashed) and the green snake (white marks on the back, a yellow belly, the head at the end of a diagonal neck rather than on top of a vertical one, the eye below a row of green and no mouth line) are the designs the user approved, and the smooth cream paw on the rounded orange tile is the icon the user chose (it replaced a 32×32 pixel-art paw, and pixel-art versions of the new paw were turned down).
- The AppImage is x86-64 Linux only. PyInstaller doesn't cross-compile, and the window behavior is untested elsewhere.
- The project is GPL-3.0-only: the full text is in `LICENSE`, the copyright notice in the README's License section, and `pyproject.toml` declares it. Code or art copied into the program needs a GPL-3.0-compatible license, and every third-party file keeps its license text next to it.
- Agent skills are project-scoped in `.claude/skills/` and pinned in `skills-lock.json`.
  - Install only trusted skills, and never with `-g`: `npx skills add <owner/repo> --skill <name> -a claude-code -y --copy`.
  - A personal skill in `~/.claude/skills` with the same name overrides the project one.
  - Each skill's folder carries its upstream license. `npx skills` copies only the skill's folder and wipes it on every reinstall or update. The `LICENSE` files of `tdd` and `modern-python` come from the root of their repos, so restore them with `git restore` after an update.

## Testing and live checks

- `tests/conftest.py` forces Qt's offscreen platform, a single 800×800 virtual screen. The "This plugin does not support setting window masks" messages it prints are expected. `filterwarnings = "error"` is on. It puts the interface back in English after every test.
- `tests/test_i18n.py` runs `pyside6-lupdate` and `pyside6-lrelease` from the venv. It fails while a text in the code is untranslated (lupdate marks it "unfinished") or a translation's text is gone from the code ("vanished"), and while a `.qm` differs from what its `.ts` compiles to.
- `tests/test_tray.py` and the controller's tests say whether there is a tray (`tray_available`): the offscreen platform has none. `tests/test_instance.py` checks the lock and the socket in `tmp_path`.
- `tests/test_build.py` loads `appimage/build.py` as a script (not a module of the package) and checks how it names the version, partly in a throwaway git repository shielded from the user's git settings (`GIT_CONFIG_GLOBAL`, `GIT_*` variables).
- `tests/test_app.py` also starts the real app in subprocesses, with temporary `XDG_CONFIG_HOME` and `XDG_RUNTIME_DIR`. It waits for the lock and the socket to exist before sending signals or starting the app again. Those tests are marked `process`, and `VIRTUAL_PET_EXECUTABLE` makes them start a built app (the AppImage) instead of `python -m virtual_pet`. One starts the app in Portuguese and fails on "Could not load", so a bundle missing a `.qm` is caught.
- Trying the app on the real desktop:
  - Set those same two variables to temporary dirs, so the user's settings and lock stay untouched.
  - `xwininfo` and `xprop` inspect the window through XWayland: expect `Override Redirect State: yes` and an unchanged `_NET_ACTIVE_WINDOW`.
  - While the pet hides, `busctl --user get-property org.kde.StatusNotifierWatcher /StatusNotifierWatcher org.kde.StatusNotifierWatcher RegisteredStatusNotifierItems` lists its tray icon among the others.
  - Take screenshots with `spectacle -b -n -f -o file.png`, without `QT_QPA_PLATFORM=offscreen` in its environment, and crop them to the pet's area.
