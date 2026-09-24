# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A pixel-art desktop pet (dog, cat, maritaca, sea turtle, fish or guinea pig) written in Python 3.12+ with PySide6 (Qt 6), managed with uv. The stack is cross-platform, but the app is currently built and tested for Linux only (KDE Plasma 6 on Wayland, through XWayland). The scope is deliberately small: the pet roams on its own, a click makes it sit (another click lets it roam), it can be dragged anywhere but never off the screen, and its right-click menu offers Sit/Walk (Sit/Fly for the maritaca, Sit/Swim for the sea turtle and the fish), Settings… (name and species) and Quit. It ships as an x86-64 Linux AppImage, built locally by `appimage/build.py` (there is no CI workflow). Run from source on Debian/Ubuntu, Qt's X11 backend needs `libxcb-cursor0`; the AppImage bundles it.

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
VIRTUAL_PET_EXECUTABLE=$PWD/dist/VirtualPet-0.1.0-x86_64.AppImage uv run pytest -m process --no-cov
                             # the process tests against a built AppImage
```

Add dependencies with `uv add` or `uv add --group dev`. Dev tools live in `[dependency-groups]`; PyInstaller is in the `build` group.

## Architecture

- **`behavior.py`** is the pet's brain, in plain Python with no Qt.
  - `PetBehavior` is a small state machine. `Activity` is derived from flags in this order: carried, sitting, walking (has a target), standing.
  - Positions are the window's top-left corner. `Area` is the allowed range for that corner: the screen's available geometry minus the window size. Every move is clamped to it, which is how "never off the screen" is enforced.
  - `Gait` (speed, max slope, stroll length) comes from the species. `tick()` caps dt at 0.1 s so the pet doesn't teleport after a system sleep.
- **`config.py`** holds `Config` and `ConfigStore`, also plain Python.
  - Writes are atomic: a temp file, then replace.
  - Loading tolerates bad files and fields and falls back to defaults. Settings without a species keep the dog.
- **Art pipeline: `sprites.py`, `species.py`, `pets/`, `icon.py`**
  - A frame is a text grid, one character per art pixel ("." is transparent). Every frame of every species shares one 32×27 canvas, so the window never resizes. Frames face right and are mirrored at runtime.
  - `sprites.draw(frame, palette)` paints a frame one image pixel per art pixel, for the pets and the icon.
  - `Species` bundles key, label, palette, animations per `Activity`, gait and `locomotion`. It renders frames in its palette through a `functools.cache` keyed on the species' identity.
  - `Locomotion` says how the pet roams, which is what its WALKING animation shows. Its value is the menu text for roaming again ("Walk", "Fly", "Swim").
  - `icon.py` is the app's icon, a 32×32 paw print in the dog's colors. `icon_image(size)` only takes whole multiples of 32, so its pixels stay sharp. `app_icon()` is every window's icon, and the AppImage's icons come from `SIZES` (32 to 256).
  - Blinking recolors "E" pixels with the palette's "B" and "H" pixels with "N", so every palette must define B and N.
  - `pets/__init__.py` has `ALL_SPECIES` and `species_by_key()`; unknown keys become the dog. The maritaca is `parakeet` in code and settings and "Maritaca" in the UI. Its WALKING animation is flying.
  - The sea turtle is `turtle` in code and settings and "Sea Turtle" in the UI. The fish is a betta, `fish` in code, settings and file name, and "Fish" in the UI.
  - Both swim: their WALKING animation is swimming. They float in place while STANDING, and only touch the ground when SITTING, which is resting on the bottom.
  - The guinea pig is `guinea_pig` in code, settings and file name, and "Guinea Pig" in the UI. It walks, and its SITTING animation is lying down like a loaf.
- **`pet_window.py`**: `PetWindow` is a frameless, translucent, always-on-top window with `X11BypassWindowManagerHint`.
  - Why unmanaged: Qt always advertises `WM_TAKE_FOCUS`, so KWin activates a managed window when clicked and takes focus from the user's app.
  - `setMask(silhouette)` follows each frame, so clicks around the pet reach the window below.
  - The timer runs at 33 ms only while walking, 100 ms otherwise. `advance(seconds)` is the public tick that tests drive.
  - Click versus drag is decided by `QApplication.startDragDistance()`. While dragging, the allowed area is the screen under the cursor.
  - It only emits `state_changed`, `settings_requested` and `quit_requested`; it never persists anything.
- **`dialogs.py`**: `PetDialog` is the adoption dialog on first run and the Settings dialog.
  - The pets are a grid of checkable buttons, `PETS_PER_ROW` (3) per row, all as wide as the widest one. In a `QGridLayout`, fixed-width buttons of different widths squeeze their column to the narrowest and cut the longer names.
  - The buttons are children of the dialog from the start, so its style sheet's padding counts when they are measured.
- **`app.py`**
  - On Linux Wayland sessions it sets `QT_QPA_PLATFORM=xcb` (when XWayland is available and no non-Wayland platform was chosen), because Wayland forbids self-positioning and always-on-top.
  - It sets `GDK_GL=disable` unless the user set it. On GNOME-like desktops Qt draws its dialogs with the GTK theme, and GTK would otherwise start OpenGL and load the system's GPU driver (Mesa and LLVM, about 50 MB) that the pet never uses.
  - Single instance: a `QLockFile` in the runtime dir, with `setStaleLockTime(0)`.
  - SIGINT/SIGTERM trigger `QTimer.singleShot(0, QApplication.exit)`, because Qt 6's `quit()` does nothing outside `app.exec()`, for example during the first-run dialog. A heartbeat timer lets the Python signal handlers run.
  - `ensure_pet()` shows the adoption dialog on first run.
  - `PetController` wires the window signals to `dialogs.ask_for_changes()`. It saves to `~/.config/virtual-pet/config.json` (`GenericConfigLocation`, respects `$XDG_CONFIG_HOME`) after every user interaction and on quit.
- **`appimage/`** builds the AppImage on the developer's machine.
  - `virtual-pet.spec` (PyInstaller) keeps the xcb, wayland and offscreen platforms and the platform themes (GTK 3, XDG portal). It drops the other Qt plugins (embedded displays, VNC, networking, input devices, image formats other than SVG), the QtNetwork and QtDBus modules and Qt's translations.
  - The spec also leaves out the libraries in the AppImage project's excludelist (glibc, libstdc++, GL, core X11/xcb, fontconfig, freetype, harfbuzz, zlib…), then every library that no extension module, plugin or libpython still links to. It stops if the machine lacks a library that isn't in that list, and writes `bundled-files.json` with the source of every bundled binary and module.
  - `build.py` first starts itself again in `build/appimage/venv`, through `UV_PROJECT_ENVIRONMENT` and `uv run --managed-python --locked --group build`. So the bundle always embeds uv's python-build-standalone Python, whatever the dev `.venv` runs on. Homebrew's Python, for example, isn't portable and has no package licenses.
  - `build.py` then runs PyInstaller and lays out the AppDir: `AppRun` (`exec`, so signals reach the pet), the `.desktop` file, the icons and the licenses. It packs the AppDir with appimagetool and the type2 runtime, pinned by URL and SHA-256 and cached in `build/appimage/tools/`. Then it runs `pytest -m process` against the AppImage and prints the glibc version the AppImage needs.
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
  - the lowest visible row is 25 for sitting, for standing unless the species swims, and for walking only if the species walks;
  - every frame contains the E and H eye pixels.
- Identifiers, file names, comments, docs and UI strings are in English. The user writes in Portuguese.
- Commits follow Conventional Commits (`type(scope): summary`) in English, with a short body and a `Co-Authored-By` trailer for the Claude model that made the change.
- New or changed pet art, and the app icon, must be shown to the user as images first: enlarged poses, plus real size on dark and light backgrounds. Wait for approval before it touches the code. The gray tabby cat (redrawn with a round head in profile, dark eyes and a short muzzle, kicking when carried), the sea turtle (brown shell, green skin), the betta (blue body, red fins) and the tricolor guinea pig (ginger with a white blaze and band, a black patch, big dark eyes) are the designs the user approved, and the paw print is the icon the user chose.
- The AppImage is x86-64 Linux only. PyInstaller doesn't cross-compile, and the window behavior is untested elsewhere.
- The project is GPL-3.0-only: the full text is in `LICENSE`, the copyright notice in the README's License section, and `pyproject.toml` declares it. Code or art copied into the program needs a GPL-3.0-compatible license, and every third-party file keeps its license text next to it.
- Agent skills are project-scoped in `.claude/skills/` and pinned in `skills-lock.json`.
  - Install only trusted skills, and never with `-g`: `npx skills add <owner/repo> --skill <name> -a claude-code -y --copy`.
  - A personal skill in `~/.claude/skills` with the same name overrides the project one.
  - Each skill's folder carries its upstream license. `npx skills` copies only the skill's folder and wipes it on every reinstall or update. The `LICENSE` files of `tdd` and `modern-python` come from the root of their repos, so restore them with `git restore` after an update.

## Testing and live checks

- `tests/conftest.py` forces Qt's offscreen platform, a single 800×800 virtual screen. The "This plugin does not support setting window masks" messages it prints are expected. `filterwarnings = "error"` is on.
- `tests/test_app.py` also starts the real app in subprocesses, with temporary `XDG_CONFIG_HOME` and `XDG_RUNTIME_DIR`. It waits for the lock file to exist before sending signals. Those tests are marked `process`, and `VIRTUAL_PET_EXECUTABLE` makes them start a built app (the AppImage) instead of `python -m virtual_pet`.
- Trying the app on the real desktop:
  - Set those same two variables to temporary dirs, so the user's settings and lock stay untouched.
  - `xwininfo` and `xprop` inspect the window through XWayland: expect `Override Redirect State: yes` and an unchanged `_NET_ACTIVE_WINDOW`.
  - Take screenshots with `spectacle -b -n -f -o file.png`, without `QT_QPA_PLATFORM=offscreen` in its environment, and crop them to the pet's area.
