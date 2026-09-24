# Virtual Pet

A little pixel-art pet that lives on your desktop: a dog, a cat, a maritaca (a green
Brazilian parakeet) or a sea turtle. It moves around on its own, sits when you click it
and goes wherever you drag it, but never off the screen.

## How to play

| Action | What happens |
| --- | --- |
| Leave it alone | It moves around the screen, resting now and then. The dog and the cat walk, the maritaca flies and the sea turtle swims (it floats while it rests). |
| Left click | It sits and stays put (the sea turtle rests on the bottom). Click again and it goes back to roaming. |
| Drag | You carry it anywhere on the screen (including another monitor). |
| Right click | Menu: its name, Sit/Walk (Sit/Fly for the maritaca, Sit/Swim for the sea turtle), Settings… and Quit. |
| Hover | Shows its name. |

On the first run you choose your pet and give it a name. Settings let you rename it or
swap it for another kind of pet. There is only ever one pet on the screen: choosing a
new one replaces the current one, in the same spot. The pet remembers which animal it
is, its name, where you left it and whether it was sitting.

## Requirements

- Linux with an X11 or Wayland desktop (tested on KDE Plasma 6, Wayland).
- On Wayland, XWayland must be available (it is by default on KDE Plasma and GNOME).
- From source only: Python 3.12+ and [uv](https://docs.astral.sh/uv/). Debian/Ubuntu
  also need `libxcb-cursor0` for Qt's X11 backend.

## Running

The AppImage (see [Building the AppImage](#building-the-appimage)) is a single file with
the pet, Python and Qt inside, so there is nothing else to install. Make it executable
(downloads lose that bit) and run it, or double-click it in the file manager:

```bash
chmod +x VirtualPet-0.1.0-x86_64.AppImage
./VirtualPet-0.1.0-x86_64.AppImage
```

It runs on x86-64 Linux distributions whose glibc is at least as new as the build
machine's. Like every AppImage it mounts itself with FUSE, which common desktop
distributions have; where it is missing, `--appimage-extract-and-run` works too, but then
Ctrl+C or logging out stops the pet without saving where it was.

From source:

```bash
uv run virtual-pet
```

To install it from source as a regular command (`virtual-pet`) for your user:

```bash
uv tool install .
```

Only one copy of the app runs at a time. Quit it from the pet's right-click menu (or
with Ctrl+C when started from a terminal).

### Why XWayland on Wayland?

Wayland doesn't let applications place their own windows or keep them above others,
and a desktop pet needs both. On Wayland sessions the pet therefore runs through
XWayland automatically. The pet is an unmanaged X11 window, so it stays on top and
never takes the keyboard focus from the application you are using. The window is
shaped to the pet's silhouette, so the empty space around it isn't part of it.

## Settings file

Everything is stored in `~/.config/virtual-pet/config.json` (`$XDG_CONFIG_HOME` is
respected). Delete that file to start over; the next run asks you to adopt a pet again.

## Development

```bash
uv sync                    # create .venv with runtime and dev dependencies
uv run pytest              # tests (offscreen, no windows pop up) + coverage report
uv run ruff check .        # lint
uv run ruff format .       # format
uv run ty check src/       # type check
```

### Project layout

```
src/virtual_pet/
├── app.py          # entry point: Qt setup, first run, single instance, saving
├── behavior.py     # the pet's brain: roaming, resting, sitting, being carried (no Qt)
├── config.py       # settings file (JSON) loading and saving
├── dialogs.py      # dialog used to adopt a pet and to change it later
├── icon.py         # the app's icon: a paw print, drawn like the pets
├── pet_window.py   # transparent, frameless, always-on-top window and mouse handling
├── species.py      # what makes a kind of pet: colors, animations, gait, how it roams
├── sprites.py      # pixel-art building blocks shared by all pets
└── pets/
    ├── dog.py      # each pet's pixel art, palette and animations
    ├── cat.py
    ├── parakeet.py # the maritaca
    └── turtle.py   # the sea turtle
appimage/
├── build.py            # builds the AppImage (see below)
├── virtual-pet.spec    # PyInstaller: what goes into the bundle
├── AppRun              # starts the bundled pet inside the AppImage
├── virtual-pet.desktop # menu entry
└── licenses/           # license texts the build can't get from the bundled packages
```

Each pet is drawn as text grids, one character per pixel, colored through its
species' palette. Edit the grids to redraw a pet. The tests check that every frame
of every pet keeps the same size and stands on the same ground line (except when
carried or flying, and the sea turtle, which floats until it sits).

### Building the AppImage

```bash
uv run appimage/build.py
```

This writes `dist/VirtualPet-<version>-x86_64.AppImage` on the machine that runs it.
The build runs in its own environment, `build/appimage/venv`, which uv sets up from
`uv.lock` with its own Python (python-build-standalone), whatever Python the project's
`.venv` uses (Homebrew's or the distribution's, for example). The AppImage embeds the
Python it is built with, and uv's builds are made to run on other distributions and come
with the license texts of the libraries built into them.
PyInstaller bundles the pet with that Python and Qt, leaving
out what every desktop Linux already has (the AppImage project's
[excludelist](https://github.com/AppImageCommunity/pkg2appimage/blob/master/excludelist)).
The bundle goes into an AppDir with the launcher, menu entry, icons and licenses, and
appimagetool packs it. The finished AppImage then runs the app's process tests
(`--skip-tests` skips them).

- The AppImage needs glibc at least as new as the build machine's (the build prints the
  version), so build on the oldest distribution it should run on, for example in a
  [distrobox](https://distrobox.it/) container.
- The build machine needs the libraries that go into the bundle: on Debian/Ubuntu
  `libxcb-cursor0`, and GTK 3 for Qt's GTK theme. The build stops and names any that
  are missing.
- The first build downloads uv's Python if it isn't installed yet (about 35 MB),
  appimagetool and the AppImage runtime (pinned versions, checked by SHA-256) and, for
  the license texts of uv's Python, that Python's full build (about 130 MB). The tools
  and texts stay in `build/appimage/tools/`.
- Everything in the AppImage comes with its license: the texts and an index,
  `THIRD-PARTY-NOTICES.txt`, are in its `usr/share/licenses/`. The build stops if it
  can't find the license of a bundled file (`--allow-missing-licenses` builds anyway).

### Agent skills

`.claude/skills/` holds the project-scoped agent skills, pinned in `skills-lock.json`.
They are unmodified third-party copies, each with its license in its folder:

- `modern-python` ([Trail of Bits](https://github.com/trailofbits/skills), CC BY-SA 4.0): uv, ruff, ty and pytest setup.
- `qt-ui-design` ([The Qt Company](https://github.com/TheQtCompanyRnD/agent-skills), BSD-3-Clause): UI design and audit guidance.
- `tdd` ([Matt Pocock](https://github.com/mattpocock/skills), MIT): test-first red → green loop.

## License

Copyright (C) 2026 Gabriel Quilice

Virtual Pet is free software: you can redistribute it and/or modify it under the terms
of the GNU General Public License, version 3, as published by the Free Software
Foundation. It is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See [LICENSE](LICENSE) for the full text.

The agent skills in `.claude/skills/` keep their own licenses (see
[Agent skills](#agent-skills)). The AppImage also contains third-party software (Python,
Qt for Python, ICU, PyInstaller's bootloader and libraries of the build machine's
distribution), each under its own license, listed in its `THIRD-PARTY-NOTICES.txt`.
