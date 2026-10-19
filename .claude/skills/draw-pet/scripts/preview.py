"""Preview a pet's art and movement before it goes into the app, for the user to approve.

Usage, from the project's root:

    uv run python .claude/skills/draw-pet/scripts/preview.py DRAFT_OR_KEY --out DIR
        [--with KEY,KEY] [--seconds 20] [--seed 1]

DRAFT_OR_KEY is a draft species module (a .py file that builds a `virtual_pet.species.Species`,
named SPECIES or the only one in it) or the key of a pet already in the app (to compare a redraw
with it). It writes three files into DIR:

- sheet.png: every distinct frame of each animation enlarged, then one frame of each at real
  size (3 screen pixels per art pixel) on a dark and a light desktop, next to the pets named by
  --with for scale.
- loops.gif: each animation playing at its own speed, enlarged.
- scene.gif: the pet at real size on a dark and a light desktop, driven by the app's own
  PetBehavior with its gait for --seconds (strolls, rests, backward strolls, pulses), then told to
  sit, then carried along. The movement is the app's, not an imitation of it.

GIFs are assembled with ffmpeg; without it, a GIF's frames are left in a folder next to it.
Colorings (a species' extra palettes) are not shown: every frame is in the usual palette.
"""

import argparse
import importlib.util
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter

from virtual_pet import sprites
from virtual_pet.behavior import Activity, Area, Facing, PetBehavior
from virtual_pet.pets import ALL_SPECIES, species_by_key
from virtual_pet.species import Species

APP = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
SCALE = sprites.PIXEL_SIZE  # real size: screen pixels per art pixel
DARK, LIGHT, PANEL, SHEET = "#1e1e1e", "#f4f4f4", "#5d6d7e", "#2f3640"
INK = "#dfe6e9"
STEP = 0.05  # seconds per GIF frame (20 per second)
BLINK_INTERVAL = (2.0, 6.0)  # as in pet_window.py


def load_species(source: str) -> Species:
    """A pet already in the app, by key, or the Species a draft module builds."""
    path = Path(source)
    if not path.suffix:
        species = species_by_key(source)
        if species.key != source:
            sys.exit(f"No pet has the key {source!r}")
        return species
    spec = importlib.util.spec_from_file_location("draft_pet", path)
    if spec is None or spec.loader is None:
        sys.exit(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if isinstance(getattr(module, "SPECIES", None), Species):
        return module.SPECIES
    found = [value for value in vars(module).values() if isinstance(value, Species)]
    if len(found) != 1:
        sys.exit(f"{path} must build one Species (or name it SPECIES); it builds {len(found)}")
    return found[0]


def picture(species: Species, frame: sprites.Frame, scale: int, *, blink: int = 0) -> QImage:
    image = species.image(frame, blink=blink)
    return image.scaled(
        image.width() * scale,
        image.height() * scale,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )


def label(painter: QPainter, x: int, y: int, text: str, color: str = INK) -> None:
    painter.setPen(QColor(color))
    painter.drawText(x, y, text)


def distinct(frames: tuple[sprites.Frame, ...]) -> list[sprites.Frame]:
    seen: list[sprites.Frame] = []
    for frame in frames:
        if frame not in seen:
            seen.append(frame)
    return seen


def sheet(species: Species, others: list[Species], path: Path) -> None:
    big, gap, per_row = 7, 14, 4
    w, h = sprites.FRAME_WIDTH, sprites.FRAME_HEIGHT
    cells = [
        (activity, i, len(distinct(species.animations[activity].frames)), frame)
        for activity in Activity
        for i, frame in enumerate(distinct(species.animations[activity].frames), start=1)
    ]
    rows = math.ceil(len(cells) / per_row)
    cell_w, cell_h = w * big + gap, h * big + 34
    real_w = (len(Activity) + len(others)) * (w * SCALE + 12) + 40
    real_h = h * SCALE + 16
    width = max(per_row * cell_w + gap, real_w)
    image = QImage(width, rows * cell_h + 2 * real_h + 60, QImage.Format.Format_ARGB32)
    image.fill(QColor(SHEET))
    with QPainter(image) as painter:
        painter.setFont(QFont("Sans", 10))
        for n, (activity, i, count, frame) in enumerate(cells):
            x, y = gap + (n % per_row) * cell_w, 8 + (n // per_row) * cell_h
            label(painter, x, y + 14, f"{activity.name} {i}/{count}")
            painter.fillRect(x, y + 22, w * big, h * big, QColor(PANEL))
            painter.drawImage(x, y + 22, picture(species, frame, big))
        top = rows * cell_h + 22
        label(
            painter,
            gap,
            top,
            "Real size, on a dark and a light desktop; "
            + (", ".join(o.key for o in others) + " for scale" if others else ""),
        )
        for k, background in enumerate((DARK, LIGHT)):
            y = top + 10 + k * real_h
            painter.fillRect(0, y, width, real_h, QColor(background))
            x = 16
            for activity in Activity:
                painter.drawImage(
                    x, y + 8, picture(species, species.animations[activity].frames[0], SCALE)
                )
                x += w * SCALE + 12
            x += 16
            for other in others:
                painter.drawImage(x, y + 8, picture(other, other.portrait, SCALE))
                x += w * SCALE + 12
    image.save(str(path))


def write_gif(frames: list[QImage], path: Path) -> None:
    """Assemble frames shown STEP seconds each into a looping GIF."""
    with tempfile.TemporaryDirectory() as folder:
        for n, frame in enumerate(frames):
            frame.save(str(Path(folder) / f"f{n:05d}.png"))
        if shutil.which("ffmpeg"):
            subprocess.run(
                [
                    "ffmpeg",
                    "-loglevel",
                    "error",
                    "-y",
                    "-framerate",
                    str(round(1 / STEP)),
                    "-i",
                    str(Path(folder) / "f%05d.png"),
                    "-filter_complex",
                    "split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=none",
                    "-loop",
                    "0",
                    str(path),
                ],
                check=True,
            )
            return
        kept = path.with_suffix("")
        shutil.copytree(folder, kept, dirs_exist_ok=True)
        print(f"No ffmpeg to make {path.name}: its frames, {STEP} s each, are in {kept}")


def loops(species: Species, path: Path) -> None:
    big, gap = 6, 16
    w, h = sprites.FRAME_WIDTH * big, sprites.FRAME_HEIGHT * big
    animations = species.animations
    longest = max(len(a.frames) / a.fps for a in animations.values())
    total = max(4.0, min(12.0, 2 * longest))
    frames = []
    for n in range(round(total / STEP)):
        image = QImage(len(Activity) * (w + gap) + gap, h + 44, QImage.Format.Format_ARGB32)
        image.fill(QColor(PANEL))
        with QPainter(image) as painter:
            painter.setFont(QFont("Sans", 11))
            for i, activity in enumerate(Activity):
                animation = animations[activity]
                x = gap + i * (w + gap)
                label(painter, x, 22, f"{activity.name} ({animation.fps:g} fps)")
                painter.drawImage(x, 36, picture(species, animation.frame_at(n * STEP), big))
        frames.append(image)
    write_gif(frames, path)


class Eyes:
    """Blinks as PetWindow schedules them."""

    def __init__(self, species: Species, rng: random.Random) -> None:
        self.species, self.rng = species, rng
        self.until = rng.uniform(*BLINK_INTERVAL)

    def step(self, seconds: float, activity: Activity) -> int:
        self.until -= seconds
        if self.until < -self.species.blink_time:
            self.until = self.rng.uniform(*BLINK_INTERVAL)
        if self.until <= 0 and activity is not Activity.CARRIED and self.species.blink:
            return self.species.blink_step(-self.until)
        return 0


class Clock:
    """The animation's clock, which PetWindow restarts whenever the activity changes."""

    def __init__(self) -> None:
        self.activity: Activity | None = None
        self.seconds = 0.0

    def read(self, activity: Activity) -> float:
        if activity is not self.activity:
            self.activity, self.seconds = activity, 0.0
        return self.seconds


def scene(species: Species, path: Path, seconds: float, seed: int) -> None:
    width, strip = 640, 210
    win_w, win_h = sprites.FRAME_WIDTH * SCALE, sprites.FRAME_HEIGHT * SCALE
    area = Area(0, 28, width - win_w, strip - win_h)
    rng = random.Random(seed)
    pet = PetBehavior(area, ((width - win_w) / 2, (strip - win_h) / 2), rng=rng, gait=species.gait)
    eyes = Eyes(species, rng)
    frames: list[QImage] = []
    clock = Clock()

    def shoot(caption: str) -> None:
        activity = pet.activity
        frame = species.animations[activity].frame_at(clock.read(activity))
        if pet.facing is Facing.LEFT:
            frame = sprites.mirrored(frame)
        pic = picture(species, frame, SCALE, blink=eyes.step(STEP, activity))
        image = QImage(width, 2 * strip, QImage.Format.Format_ARGB32)
        with QPainter(image) as painter:
            painter.setFont(QFont("Sans", 10))
            for k, background in enumerate((DARK, LIGHT)):
                painter.fillRect(0, k * strip, width, strip, QColor(background))
                x, y = pet.position
                painter.drawImage(round(x), round(y) + k * strip, pic)
            label(painter, 10, 18, caption)
        frames.append(image)
        clock.seconds += STEP

    def run(
        duration: float, caption: Callable[[float], str], act: Callable[[], None] = lambda: None
    ) -> None:
        for _ in range(round(duration / STEP)):
            before = pet.position[0]
            act()
            pet.tick(STEP)
            shoot(caption(pet.position[0] - before))

    def roaming(dx: float) -> str:
        if pet.activity is not Activity.WALKING or dx == 0:
            return f"{pet.activity.name.lower()}"
        backward = (dx > 0) == (pet.facing is Facing.LEFT)
        return f"walking ({species.roam_label})" + (", backward" if backward else "")

    run(seconds, roaming)
    pet.toggle_sitting()
    run(5.0, lambda _dx: f"told to sit: {species.sit_label}")
    pet.pick_up()
    start = pet.position
    ticks = round(3.0 / STEP)
    path_points = iter(
        [
            (
                start[0] + 120 * math.sin(math.pi * i / ticks),
                start[1] - 40 * math.sin(2 * math.pi * i / ticks),
            )
            for i in range(ticks)
        ]
    )
    run(3.0, lambda _dx: "carried", lambda: pet.move_to(*next(path_points)))
    write_gif(frames, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "source", help="a draft species module (.py) or the key of a pet in the app"
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="folder for sheet.png, loops.gif, scene.gif"
    )
    parser.add_argument(
        "--with",
        dest="others",
        default=",".join(s.key for s in ALL_SPECIES[:4]),
        help="keys of pets shown beside it at real size, for scale ('' for none; default: four)",
    )
    parser.add_argument(
        "--seconds", type=float, default=20.0, help="seconds of roaming in the scene"
    )
    parser.add_argument("--seed", type=int, default=1, help="random seed for the scene's strolls")
    args = parser.parse_args()
    species = load_species(args.source)
    others = [
        s for key in args.others.split(",") if key for s in ALL_SPECIES if s.key == key.strip()
    ]
    args.out.mkdir(parents=True, exist_ok=True)
    sheet(species, others, args.out / "sheet.png")
    loops(species, args.out / "loops.gif")
    scene(species, args.out / "scene.gif", args.seconds, args.seed)
    print(f"Wrote {args.out / 'sheet.png'}, {args.out / 'loops.gif'} and {args.out / 'scene.gif'}")


if __name__ == "__main__":
    main()
