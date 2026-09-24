# Virtual Pet

A little pixel-art pet that lives on your desktop: a dog, a cat or a maritaca (a green
Brazilian parakeet). It moves around on its own, sits when you click it and goes
wherever you drag it, but never off the screen.

## How to play

| Action | What happens |
| --- | --- |
| Leave it alone | It moves around the screen, resting now and then. The dog and the cat walk; the maritaca flies. |
| Left click | It sits and stays put. Click again and it goes back to roaming. |
| Drag | You carry it anywhere on the screen (including another monitor). |
| Right click | Menu: its name, Sit/Walk (Sit/Fly for the maritaca), Settings… and Quit. |
| Hover | Shows its name. |

On the first run you choose your pet and give it a name. Settings let you rename it or
swap it for another kind of pet. There is only ever one pet on the screen: choosing a
new one replaces the current one, in the same spot. The pet remembers which animal it
is, its name, where you left it and whether it was sitting.

## Requirements

- Linux with an X11 or Wayland desktop (tested on KDE Plasma 6, Wayland).
- Python 3.12+ and [uv](https://docs.astral.sh/uv/).
- On Wayland, XWayland must be available (it is by default on KDE Plasma and GNOME).
  Debian/Ubuntu also need `libxcb-cursor0` for Qt's X11 backend.

## Running

```bash
uv run virtual-pet
```

To install it as a regular command (`virtual-pet`) for your user:

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
├── pet_window.py   # transparent, frameless, always-on-top window and mouse handling
├── species.py      # what makes a kind of pet: colors, animations, gait, flying or not
├── sprites.py      # pixel-art building blocks shared by all pets
└── pets/
    ├── dog.py      # each pet's pixel art, palette and animations
    ├── cat.py
    └── parakeet.py # the maritaca
```

Each pet is drawn as text grids, one character per pixel, colored through its
species' palette. Edit the grids to redraw a pet. The tests check that every frame
of every pet keeps the same size and stands on the same ground line (except when
carried or flying).

### Agent skills

`.claude/skills/` holds the project-scoped agent skills, pinned in `skills-lock.json`:

- `modern-python` ([Trail of Bits](https://github.com/trailofbits/skills)): uv, ruff, ty and pytest setup.
- `qt-ui-design` ([The Qt Company](https://github.com/TheQtCompanyRnD/agent-skills)): UI design and audit guidance.
- `tdd` ([Matt Pocock](https://github.com/mattpocock/skills)): test-first red → green loop.
