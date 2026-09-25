<p align="center">
  <img src="docs/icon.png" width="128" height="128"
       alt="The app's icon: a cream paw print on a rounded orange tile">
</p>

# Virtual Pet

A little pixel-art pet that lives on your desktop: a dog, a cat, a maritaca (a green
Brazilian parakeet), a sea turtle, a fish (a betta), a guinea pig, a penguin, a snake, a
rabbit, a cockatiel, a fox or a wolf. It moves around on its own, sits when you click it
and goes wherever you drag it, but never off the screen.

## How to play

| Action | What happens |
| --- | --- |
| Leave it alone | It moves around the screen, resting now and then. The dog, the cat, the guinea pig, the penguin, the fox and the wolf walk, the maritaca and the cockatiel fly, the sea turtle and the fish swim (they float while they rest), the snake slithers and the rabbit hops. |
| Left click | It sits and stays put (the guinea pig lies down, the sea turtle and the fish rest on the bottom, the snake coils up, and the wolf howls now and then). Click again and it goes back to roaming. |
| Drag | You carry it anywhere on the screen (including another monitor). |
| Right click | Menu: its name, Sit/Walk (Sit/Fly for the maritaca and the cockatiel, Sit/Swim for the sea turtle and the fish, Coil up/Slither for the snake, Sit/Hop for the rabbit), Turn around, Hide, Settings… and Quit. |
| Turn around (in the menu) | It faces the other way. If it was on the move, it heads that way instead. |
| Hide (in the menu) | It leaves the screen and waits in the system tray: click the paw print there to bring it back, where you left it. On desktops without a tray (GNOME without the AppIndicator extension, for example), open the app again instead. |
| Hover | Shows its name. |

On the first run you choose your pet and give it a name. Settings let you rename it or
swap it for another kind of pet. There is only ever one pet on the screen: choosing a
new one replaces the current one, in the same spot. The pet remembers which animal it
is, its name, where you left it, whether it was sitting and which way it was facing.
Opening the app while it runs starts no second pet: the running one shows itself instead.

The pet speaks English and Brazilian Portuguese, in which the app is called Pet Virtual.
It follows your desktop's language (English if it doesn't speak it), unless you choose a
language in Settings.

## Requirements

- Linux with an X11 or Wayland desktop (tested on KDE Plasma 6, Wayland).
- On Wayland, XWayland must be available (it is by default on KDE Plasma and GNOME).
- From source only: Python 3.12+ and [uv](https://docs.astral.sh/uv/). Debian/Ubuntu
  also need `libxcb-cursor0` for Qt's X11 backend.
- Windows (experimental): 64-bit Windows 10 version 1903 or newer, or Windows 11. The
  Windows build is only tested under Wine, never on Windows itself (see
  [Building for Windows](#building-for-windows)).

## Running

The AppImage (see [Building the AppImage](#building-the-appimage)) is a single file with
the pet, Python and Qt inside, so there is nothing else to install. Make it executable
(downloads lose that bit) and run it, or double-click it in the file manager:

```bash
chmod +x VirtualPet-0.4.0-x86_64.AppImage
./VirtualPet-0.4.0-x86_64.AppImage
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

### On Windows (experimental)

The Windows build is a zip (see [Building for Windows](#building-for-windows)) with a
`VirtualPet` folder: unzip it anywhere and run `VirtualPet.exe` in it. The program isn't
signed, so Windows SmartScreen warns about it the first time ("More info", then "Run
anyway"). From source, `uv run virtual-pet` works as on Linux.

With display scaling that isn't a whole number (125% or 150%, common on Windows laptops),
the pet's pixels come out slightly uneven, some a screen pixel wider than others.

### Why XWayland on Wayland?

Wayland doesn't let applications place their own windows or keep them above others,
and a desktop pet needs both. On Wayland sessions the pet therefore runs through
XWayland automatically. The pet is an unmanaged X11 window, so it stays on top and
never takes the keyboard focus from the application you are using. The window is
shaped to the pet's silhouette, so the empty space around it isn't part of it.

## Settings file

Everything is stored in `~/.config/virtual-pet/config.json` (`$XDG_CONFIG_HOME` is
respected), or on Windows in `%LOCALAPPDATA%\virtual-pet\config.json`. Delete that file
to start over; the next run asks you to adopt a pet again.

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
├── behavior.py     # the pet's brain: roaming, resting, sitting, turning, being carried (no Qt)
├── config.py       # settings file (JSON) loading and saving
├── dialogs.py      # dialogs used to adopt a pet and to change it (and the language) later
├── i18n.py         # the interface in the user's language
├── icon.py         # the app's icon: a cream paw print on a rounded orange tile
├── instance.py     # one pet at a time: the lock, and how opening the app again reaches it
├── paw.png         # the paw's silhouette, which the icon is drawn from
├── pet_window.py   # transparent, frameless, always-on-top window and mouse handling
├── species.py      # what makes a kind of pet: colors, animations, gait, how it roams
├── sprites.py      # pixel-art building blocks shared by all pets
├── tray.py         # the paw print in the system tray while the pet hides
├── translations/   # Qt Linguist files: virtual_pet_<language>.ts and its compiled .qm
└── pets/
    ├── dog.py      # each pet's pixel art, palette and animations
    ├── cat.py
    ├── parakeet.py # the maritaca
    ├── turtle.py   # the sea turtle
    ├── fish.py     # the betta
    ├── guinea_pig.py
    ├── penguin.py  # a gentoo
    ├── snake.py    # in an emerald tree boa's colors
    ├── rabbit.py   # a white bunny that hops
    ├── cockatiel.py # gray, with a yellow crest
    ├── fox.py      # a red fox
    └── wolf.py     # a gray wolf that howls
appimage/
├── build.py            # builds the AppImage (see below)
├── virtual-pet.spec    # PyInstaller: what goes into the bundle
├── AppRun              # starts the bundled pet inside the AppImage
├── virtual-pet.desktop # menu entry
└── licenses/           # license texts the build can't get from the bundled packages
windows/
├── build.py            # builds the Windows zip under Wine (see below)
└── virtual-pet.spec    # PyInstaller: what goes into the Windows bundle
```

Each pet is drawn as text grids, one character per pixel, colored through its
species' palette. Edit the grids to redraw a pet. The tests check that every frame
of every pet keeps the same size and stands on the same ground line (except when
carried or flying, and the swimmers, which float until they sit).

### Translations

The texts in the code are English. Each other language has a Qt Linguist file,
`src/virtual_pet/translations/virtual_pet_<language>.ts`, and the `.qm` compiled from it,
which is what the app loads. After adding or changing texts in the code:

```bash
uv run pyside6-lupdate src/virtual_pet/*.py src/virtual_pet/pets/*.py -locations none \
    -no-obsolete -ts src/virtual_pet/translations/virtual_pet_pt_BR.ts
uv run pyside6-linguist src/virtual_pet/translations/virtual_pet_pt_BR.ts  # translate them
uv run pyside6-lrelease src/virtual_pet/translations/virtual_pet_pt_BR.ts  # the .qm
```

The tests fail while a text is untranslated, or a `.qm` is older than its `.ts`. A new
language needs its code and name in `LANGUAGES` (`i18n.py`) and a `.ts` file, made by
the first command with `-target-language <code>` and the file named after that code.

### Building the AppImage

```bash
uv run appimage/build.py
```

This writes `dist/VirtualPet-<version>-x86_64.AppImage` on the machine that runs it
(see [Releasing](#releasing) for the version in its name).
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

### Building for Windows

```bash
uv run windows/build.py
```

This writes `dist/VirtualPet-<version>-windows-x64.zip` on this Linux machine, with Wine
(the `wine` package on Debian and Ubuntu, or WineHQ's; tested with Wine 11), and names
the version as the AppImage build does.
PyInstaller can't build for another system, so it runs on Windows' own Python under
Wine, in a Wine prefix of the build's own (`build/windows/wine`; `~/.wine` is never
touched, and nothing shows up on the desktop or in its menus):

- The build downloads Windows' Python (python-build-standalone, pinned in
  `windows/build.py`, about 50 MB, and its full build, as much again, for the license texts),
  and uv installs the Windows wheels of `uv.lock`'s packages for it. They stay in
  `build/windows/`.
- PyInstaller bundles the pet with that Python and Qt, in a folder whose `licenses/`
  holds the license texts and `THIRD-PARTY-NOTICES.txt`. As for the AppImage, the build
  stops if it can't find the license of a bundled file.
- The bundle then starts under Wine, in Portuguese: it must load its translations and
  answer a second start (`--skip-tests` skips this).

Qt asks Windows for its ICU library (`icuuc.dll`, part of Windows since 10 version 1903),
which Wine lacks, so the build's Wine prefix gets a stub of it whose functions do nothing.
Qt only uses them for text encodings the pet never needs, and the stub never goes into the
bundle. Wine isn't Windows, though: the test shows that the bundle is complete, not how
the pet behaves on a Windows desktop.

### Releasing

The version is in `pyproject.toml`, and a release is the commit that sets it, tagged
`v<version>`:

```bash
uv version --bump minor        # or patch, or major: changes pyproject.toml and uv.lock
git commit --message "chore(release): 0.5.0" pyproject.toml uv.lock
git tag --annotate v0.5.0 --message "Virtual Pet 0.5.0"
git push --follow-tags
uv run appimage/build.py       # dist/VirtualPet-0.5.0-x86_64.AppImage
uv run windows/build.py        # dist/VirtualPet-0.5.0-windows-x64.zip
```

The build asks git which commit it is building, so it runs in a clone of the repository.
Only a clean checkout of the release's tag makes `VirtualPet-<version>-x86_64.AppImage`.
Any other commit adds itself to the name (`VirtualPet-0.5.0+g1a2b3c4-x86_64.AppImage`),
followed by `.dirty` when files git tracks have uncommitted changes, and a release tag
that isn't the version in `pyproject.toml` stops the build. The version also goes into
the AppImage's menu entry (`X-AppImage-Version`), which AppImage managers show.

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
distribution), each under its own license, listed in its `THIRD-PARTY-NOTICES.txt`. So
does the Windows build (Python, Qt for Python, the Visual C++ runtime and PyInstaller's
bootloader), in its `licenses/THIRD-PARTY-NOTICES.txt`.
