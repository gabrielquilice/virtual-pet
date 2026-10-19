---
name: draw-pet
description: Rules and process for drawing a new pet or redrawing an existing one in this desktop-pet app (its pixel-art frames, palette, poses, animations and the way it moves). Use it whenever the user asks to draw, design, create or add a pet, species or animal, or to redraw, redesign, fix or rework the look, a pose, an animation or the movement of an existing pet, even when they only name an animal or say that a pet looks or moves wrong. Answer in the language the user writes in.
---

# Drawing a pet

A pet here is a believable animal in 32×27 pixel art. It moves, rests and reacts the way the
real animal does, and the user approves it from images and animations before any code changes.

This skill exists to avoid these common failures:
- A drawing that looks like a monster: a body part that reads as a second head, limbs that read
  as legs.
- Answering "it looks wrong" with near-identical pixel tweaks instead of rethinking from photos.
- Movements that aren't real.
- A part that changes from one pose to the next.
- A round shape that comes out flat-topped.

## Language

- Talk to the user in the language they write in, and keep to it for the whole interaction:
  the explanations, the questions and the captions of what you show.
- Everything written into the project (code, comments, docs, commit messages) is in English.
- Texts shown in the app are written in English in the code and translated through the
  translation files (see "After approval").

## The process

1. **Know exactly what you are drawing.**
   - Name the species, and the breed, morph or color form where it matters.
   - If the request leaves this open and the choice changes the look a lot, ask. Otherwise pick
     the most typical form and say which.
   - For a redraw, first read the docstring of the pet's module in `src/virtual_pet/pets/`. It
     records the look, the poses, the gait and what the user approved or turned down, and a
     turned-down idea must not come back.
   - Render the current art with the preview script (below) as the "before".

2. **Research before drawing.** Collect facts with their sources: they go to the user with the
   design. The research has three parts: photos, proportions, and behavior.
   - **Photos.** Use side-view photos of live animals from Wikimedia Commons, through the
     built-in browser. A species' category lists its files. `https://commons.wikimedia.org/wiki/Special:FilePath/<File name>?width=800`
     opens a file large.
     - Check each photo's species in its categories: a photo of a close relative can mislead.
     - A photo taken at an angle misleads about proportions.
   - **Proportions.** Measure them on a profile photo: the distances from one landmark, as a
     share of the body's length or of a reference radius. Note the markings and the colors,
     with their positions.
   - **Behavior.** Look up how it moves. That covers:
     - its gait;
     - its speed, in body lengths per second;
     - its direction: forward, backward or sideways;
     - whether it moves steadily or in surges, hops or jets;
     - how it rests;
     - what it does while still;
     - what it does when picked up or handled;
     - whether it has eyelids.

     Prefer published studies and aquarium or field observations to pet-care pages. Quote
     numbers.

3. **Design from the research.** Settle each of these from a fact:
   - the silhouette;
   - the palette;
   - the four poses (see the movement rules);
   - the gait.

   Present one coherent design with the reasons behind it, not a menu of variants.

4. **Draw in the scratchpad, never in the repository**, until the user approves. Draft frames
   live in a draft module (a `.py` that builds a `Species`; see "Previewing") or in generator
   scripts, so the test suite stays green while you iterate.

5. **Check your own work** against the checklist at the end before showing anything.

6. **Show it.** Run the preview script and send its files with SendUserFile:
   - the sheet;
   - `loops.gif`;
   - `scene.gif`;
   - the main reference photo next to a large frame.

   Explain the design and the movements in a few lines, with the sources, and ask for approval.
   Movement can't be judged from stills: the GIFs are what show whether it moves like the
   animal.

7. **Iterate on feedback.**
   - When the user says something looks or moves wrong, go back to the references.
   - Rethink that part and everything it touches. Don't offer one- or two-pixel variants.
   - Check whether the same flaw is elsewhere: a flat curve, an inconsistent part.
   - Re-run the preview every round.

8. **Change the code only after the user explicitly approves.** Then follow
   "After approval". If the user wants it implemented by a subagent or another model, first
   export the approved frames and palette to a file, and have it copy them exactly. Check that
   it did.

## Rules for the art

### Format (the tests enforce these)

- **Frames.**
  - Every frame is 32 columns × 27 rows, one character per art pixel.
  - `.` is transparent, and every other character must be in the palette.
  - The app draws each art pixel as 3×3 screen pixels.
  - Frames face right, and the app mirrors them when the pet faces left. Draw the animal in
    profile.
  - A head may turn to the viewer briefly.
- **Ground line, row 25.** The lowest visible row must be 25:
  - for SITTING, always;
  - for STANDING, unless the species swims (a swimmer floats);
  - for WALKING, if it walks, slithers, crawls or hops.

  Flying frames and a swimmer's floating frames stay above row 25.
- **Eye.** Every frame has eye pixels: `E` (`sprites.EYE`) and `H` (`sprites.EYE_SHINE`). The
  usual blink draws E in the palette's `B` and H in its `N`. So:
  - put E where a closed eye shows skin or fur;
  - put H where the closed eye's dark line goes.
- **Palette.**
  - It must define `B`, the body color, and `N`, the darkest.
  - The portrait, STANDING's first frame, must contain a `B` pixel.
  - Each pet's `B` is its own color: tests/test_species.py lists them all.
  - Give every color a short comment saying what it paints.
- **Outline.** It is `K`, a dark color of the pet's own (a dark brown or a navy, not pure
  black). It goes all around the silhouette, so the pet reads on any wallpaper.

### Looks

- **Believable before cute.**
  - Proportions come from the measurements: legs where they attach, the eye where it sits,
    the right number of limbs.
  - Colors come from the photos, simplified to a few tones per area: a base, a shade, and a
    highlight if needed.
- **Size like the others.** Fill the canvas about as much as the existing pets (25–31 columns
  wide or about 20 rows tall), and compare at real size next to them.
- **Readable at real size**, on a dark and on a light desktop alike.
  - The eye must read as an eye: give it contrast and, if needed, a socket in a darker tone.
  - A thin part needs an outline on both sides. When that makes it heavy, draw it in a
    mid-tone with no outline, and say so in the palette's comment.
- **Nothing that reads as something else.** Look at every small detail at real size and ask
  what a stranger would see. Typical misreadings:
  - loose specks read as droppings;
  - dark streaks read as teeth;
  - pointed tips read as claws;
  - a dark slit across a bright eye reads as a visor;
  - a limb drawn bigger than the body makes the animal look bigger than itself.

### Pixel craft

- **Round outlines need hand-tuned runs.** A curve sampled this small comes out as an
  octagon: a long flat top, 45° shoulders, long flat sides. Draw circles and domes in runs that
  shrink gradually, like 6, 2, 1, 1 down to vertical runs of 2 and 3. Check every round
  outline: heads, backs, shells, bellies.
- **Generate, then fix by hand.** A shape can start as smooth geometry sampled to pixels:
  ellipses, spirals, tapered tubes. Then correct runs, details and the eye by hand. The pet's
  module stores that output, and later edits go straight into it. Say so in the module's docstring.
- **Every part is the same in every pose.** Legs, tentacles, ears and tails keep the same
  count, attachment points and size, and only bend, swing or retract. A part that disappears
  needs a reason that shows: retracted, or hidden behind another part.
- **Keep the body's size steady within a loop.** A part that swells to breathe makes the
  other frame look like it shrank.
- **Mind the window gliding along.** The window moves at the pet's speed, so within the
  WALKING loop, nothing that stays put in reality may move backward relative to the ground. A
  rigid part rocking back and forth reads as the pet jolting backward.

## Rules for poses and movement

Each activity's animation shows what the real animal does. Give each of these a fact from the
research.

- **STANDING** is its idle between strolls: what the real animal does when it stops (hovering,
  scratching, looking around). It loops, so keep it calm: a part that moves every other second
  looks restless.
- **WALKING** is its way of getting around, `Locomotion` (Walk, Fly, Swim, Slither, Hop,
  Crawl). The value is also the menu text for roaming.
  - A hopper or a walker keeps a foot on row 25 in every frame.
  - A flyer's wing is in proportion to its body.
- **SITTING** is what it does when told to sit: its real resting posture, which isn't always
  sitting (roosting, coiling, settling on the bottom, retreating into a shell).
  - `sit_label` names it: "Sit", "Rest" and so on.
  - A new label needs translating (PetWindow context).
- **CARRIED** is what it does when picked up. It also shows while the pet is thrown.
  - Check what the real animal does when handled: kicking, flapping, dangling, hiding.
  - Check it is physically possible too: a pose that would stop the animal breathing is wrong.
- **Blinking.** Blink only if the real animal has eyelids.
  - Without them, give the species `blink=()`.
  - A big eye can blink in steps, `Species.blink`, with `BlinkStep(look, seconds)`.
- **Gait** (`behavior.Gait`) is how the pet roams.
  - **speed** in px/s, set against the existing pets' gaits (see `src/virtual_pet/pets/`) and
    against the real animal's relative pace in body lengths per second.
  - **max_slope**: how steep a stroll may run.
  - **distance**: how long a stroll is.
  - **rest**: how long it stands between strolls. It must be long enough for what STANDING
    shows: an action that starts 0.5 s after it stops and lasts 2 s needs a rest of several
    seconds, or it never plays.
  - **backward**: the share of strolls taken facing away from where it goes, for an animal
    that often moves tail- or shell-first. Use the share the research gives.
  - **pulse**: seconds per stroke, for an animal that moves in surges (a jet, maybe a hop or
    a swim stroke).
    - The speed swings with each stroke.
    - Every stroll lasts whole strokes, so it ends at its slowest.
    - The WALKING loop must last exactly one pulse, so the frames stay in step with the surges:
      `len(frames) / fps == gait.pulse`.
  - If the real movement needs something the gait can't express, propose the engine change
    to the user with the evidence. Don't fake it in the frames.
- **Timing** comes from `Animation(frames, fps)`. Repeat a frame to hold it. Make a loop's
  length match the action it shows.

## Previewing

`.claude/skills/draw-pet/scripts/preview.py` renders a draft, or a pet already in the app,
the way the app will. It uses the app's own `Species.image()` and drives the scene with the
app's own `PetBehavior`, so strolls, rests, backward strolls and pulses are the real ones.

```bash
uv run python .claude/skills/draw-pet/scripts/preview.py <draft.py | pet key> --out <scratchpad folder> [--with key1,key2] [--seconds 20] [--seed 1]
```

A draft module builds one `Species`, named `SPECIES` or the only one in the file. It uses
`virtual_pet.sprites.art`, `EYE`, `EYE_SHINE` and `Animation`, and
`virtual_pet.behavior.Activity` and `Gait`, as the modules in `src/virtual_pet/pets/` do. Give it a
key that isn't taken.

`--with` takes the keys of existing pets to show beside it for scale; by default it shows the
first four in `ALL_SPECIES`.

The script writes:

- **`sheet.png`**: every distinct frame of each animation, enlarged and labeled. Below them,
  one frame per animation at real size on a dark and a light desktop, next to the pets passed
  with `--with` for scale.
- **`loops.gif`**: the four animations, each at its own fps, enlarged.
- **`scene.gif`**: the pet at real size on both desktops. It roams for `--seconds`, then is
  told to sit, then is carried along. The caption says when a stroll is taken backward.

It needs ffmpeg for the GIFs. Extra palettes (`Species.colorings`) are not shown. For the photo
comparison, crop the reference photo, flipped to face right, and put it next to a frame
enlarged about 15×. Pillow is not a project dependency: use one that is installed on the
machine, or ffmpeg, to crop and flip.

## Checklist before showing anything

- [ ] All frames are 32×27, with only palette characters, and E and H in every frame.
- [ ] The ground line is right for its locomotion (row 25 where required, above it where not).
- [ ] B and N are defined, there is a B pixel in the portrait, and the body color is not
      another pet's.
- [ ] The proportions match the measured photo, and the markings and colors match the
      references.
- [ ] Every round outline is drawn in shrinking runs: no flat tops, no octagons.
- [ ] Every part is present and the same in every pose, or visibly retracted or hidden.
- [ ] No detail reads as dirt, teeth, claws, a visor or another animal, at real size on both
      backgrounds.
- [ ] Each animation is backed by a researched fact: idle, roaming, resting, handled.
- [ ] Blinking only if it has eyelids.
- [ ] The gait's speed, rest, backward and pulse are set from the research.
- [ ] If it pulses, the WALKING loop lasts exactly one pulse.
- [ ] Every frame was previewed at real size and in motion, in the sheet and both GIFs.

## After approval

Implement the approved art exactly. CLAUDE.md describes the pieces below (the art pipeline,
i18n, the README table and the tests).

1. `src/virtual_pet/pets/<key>.py`:
   - a module docstring describing the animal: its look, each pose and why, its gait, how the
     art was made, and what was turned down along the way (update it on every later redraw);
   - the frames as `art("""…""")` blocks, with a comment over each group;
   - the palette with a comment per color;
   - the `Species`: key, label as `QT_TRANSLATE_NOOP("Species", …)`, animations, gait,
     locomotion, sit_label, and blink if it isn't the default.

   Add it at the end of `ALL_SPECIES` in `pets/__init__.py`.
2. Translations:
   - the label and any new menu text in every `.ts` file in `src/virtual_pet/translations/`,
     using the lupdate and lrelease commands in CLAUDE.md;
   - `wikipedia.py` `TITLES` in each language it has, after checking that each article
     exists and is not a disambiguation page.
3. README: the pets table row and its picture, `docs/pets/<key>.png`, made with the command in
   CLAUDE.md. Also update any other list of pets or menu texts in the README.
4. Tests:
   - add the pet to the lists in `tests/test_species.py` (names, keys, roaming, sit labels,
     swimmers or flyers, body colors) and in `tests/test_dialogs.py` (grid rows, translated
     names);
   - add tests for any new behavior.
5. CLAUDE.md only if the pet needs something that applies beyond it (a new engine feature, a
   new test invariant). Its look and history stay in its docstring.
6. Verify:
   - `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, and
     `uv run ty check src/`;
   - if the movement is new, the real desktop, as in CLAUDE.md's "Trying the app on the real
     desktop".

   Commit only when the user asks.
