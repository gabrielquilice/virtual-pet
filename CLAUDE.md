# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A pixel-art desktop pet (dog, cat or maritaca) written in Python 3.12+ with PySide6 (Qt 6), managed with uv. The stack is cross-platform, but the app is currently built and tested for Linux only (KDE Plasma 6 on Wayland, through XWayland). The scope is deliberately small: the pet roams on its own, a click makes it sit (another click lets it roam), it can be dragged anywhere but never off the screen, and its right-click menu offers Sit/Walk (Sit/Fly for the maritaca), Settings… (name and species) and Quit. On Debian/Ubuntu, Qt's X11 backend needs `libxcb-cursor0`.

## Commands

```bash
uv sync                      # .venv with runtime and dev dependencies
uv run virtual-pet           # run the app (same as: uv run python -m virtual_pet)
uv run pytest                # full suite on Qt's offscreen platform; fails below 80% coverage
uv run pytest tests/test_behavior.py::test_sitting_pet_stays_where_it_is --no-cov
                             # a single test: --no-cov, otherwise the coverage gate fails the run
uv run ruff check . && uv run ruff format --check .
uv run ty check src/
```

Add dependencies with `uv add` or `uv add --group dev`. Dev tools live in `[dependency-groups]`.

## Architecture

- **`behavior.py`** is the pet's brain, in plain Python with no Qt.
  - `PetBehavior` is a small state machine. `Activity` is derived from flags in this order: carried, sitting, walking (has a target), standing.
  - Positions are the window's top-left corner. `Area` is the allowed range for that corner: the screen's available geometry minus the window size. Every move is clamped to it, which is how "never off the screen" is enforced.
  - `Gait` (speed, max slope, stroll length) comes from the species. `tick()` caps dt at 0.1 s so the pet doesn't teleport after a system sleep.
- **`config.py`** holds `Config` and `ConfigStore`, also plain Python.
  - Writes are atomic: a temp file, then replace.
  - Loading tolerates bad files and fields and falls back to defaults. Settings without a species keep the dog.
- **Art pipeline: `sprites.py`, `species.py`, `pets/`**
  - A frame is a text grid, one character per art pixel ("." is transparent). Every frame of every species shares one 32×27 canvas, so the window never resizes. Frames face right and are mirrored at runtime.
  - `Species` bundles key, label, palette, animations per `Activity`, gait and `flies`. It renders frames in its palette through a `functools.cache` keyed on the species' identity.
  - Blinking recolors "E" pixels with the palette's "B" and "H" pixels with "N", so every palette must define B and N.
  - `pets/__init__.py` has `ALL_SPECIES` and `species_by_key()`; unknown keys become the dog. The maritaca is `parakeet` in code and settings and "Maritaca" in the UI. Its WALKING animation is flying.
- **`pet_window.py`**: `PetWindow` is a frameless, translucent, always-on-top window with `X11BypassWindowManagerHint`.
  - Why unmanaged: Qt always advertises `WM_TAKE_FOCUS`, so KWin activates a managed window when clicked and takes focus from the user's app.
  - `setMask(silhouette)` follows each frame, so clicks around the pet reach the window below.
  - The timer runs at 33 ms only while walking, 100 ms otherwise. `advance(seconds)` is the public tick that tests drive.
  - Click versus drag is decided by `QApplication.startDragDistance()`. While dragging, the allowed area is the screen under the cursor.
  - It only emits `state_changed`, `settings_requested` and `quit_requested`; it never persists anything.
- **`app.py`**
  - On Linux Wayland sessions it sets `QT_QPA_PLATFORM=xcb` (when XWayland is available and no non-Wayland platform was chosen), because Wayland forbids self-positioning and always-on-top.
  - Single instance: a `QLockFile` in the runtime dir, with `setStaleLockTime(0)`.
  - SIGINT/SIGTERM trigger `QTimer.singleShot(0, QApplication.exit)`, because Qt 6's `quit()` does nothing outside `app.exec()`, for example during the first-run dialog. A heartbeat timer lets the Python signal handlers run.
  - `ensure_pet()` shows the adoption dialog on first run.
  - `PetController` wires the window signals to `dialogs.ask_for_changes()`. It saves to `~/.config/virtual-pet/config.json` (`GenericConfigLocation`, respects `$XDG_CONFIG_HOME`) after every user interaction and on quit.

## Invariants and conventions

- Only one pet is ever on screen: one window in one app instance. Changing the species in Settings swaps the pet in the same window and spot.
- `tests/test_species.py` enforces the art invariants for every species:
  - all frames are 32×27;
  - they use only palette characters;
  - the lowest visible row is 25 for standing and sitting, and for walking unless the species flies;
  - every frame contains the E and H eye pixels.
- Identifiers, file names, comments, docs and UI strings are in English. The user writes in Portuguese.
- Commits follow Conventional Commits (`type(scope): summary`) in English, with a short body and a `Co-Authored-By` trailer for the Claude model that made the change.
- New or changed pet art must be shown to the user as images first: enlarged poses, plus real size on dark and light backgrounds. Wait for approval before it touches the code. The current gray tabby cat is the one the user chose to keep.
- Agent skills are project-scoped in `.claude/skills/` and pinned in `skills-lock.json`.
  - Install only trusted skills, and never with `-g`: `npx skills add <owner/repo> --skill <name> -a claude-code -y --copy`.
  - A personal skill in `~/.claude/skills` with the same name overrides the project one.
  - Each skill's folder carries its upstream license. `npx skills` copies only the skill's folder and wipes it on every reinstall or update. The `LICENSE` files of `tdd` and `modern-python` come from the root of their repos, so restore them with `git restore` after an update.

## Testing and live checks

- `tests/conftest.py` forces Qt's offscreen platform, a single 800×800 virtual screen. The "This plugin does not support setting window masks" messages it prints are expected. `filterwarnings = "error"` is on.
- `tests/test_app.py` also starts the real app in subprocesses, with temporary `XDG_CONFIG_HOME` and `XDG_RUNTIME_DIR`. It waits for the lock file to exist before sending signals.
- Trying the app on the real desktop:
  - Set those same two variables to temporary dirs, so the user's settings and lock stay untouched.
  - `xwininfo` and `xprop` inspect the window through XWayland: expect `Override Redirect State: yes` and an unchanged `_NET_ACTIVE_WINDOW`.
  - Take screenshots with `spectacle -b -n -f -o file.png`, without `QT_QPA_PLATFORM=offscreen` in its environment, and crop them to the pet's area.
