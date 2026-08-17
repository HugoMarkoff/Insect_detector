# Ladybug enclosure 🐞

A 3D-printed ladybug that hides the electronics under its shell and looks
**straight down** at whatever it's standing over. Legs are Lego-style stacking
blocks, so the same body works at 3 cm or 15 cm off the ground.

Part 1 (here): **base tray + legs** — [`ladybug_base.scad`](ladybug_base.scad).
Part 2 (next): the domed elytra shell.

## Why this shape works

- The **dome** is the natural place for the Pi, trap board and battery — tall,
  round, and it sheds rain.
- The **belly** becomes the optical bench: three downward windows (camera, IR
  illuminator, light sensor) all aimed at the same patch of ground.
- Six legs → a stable tripod-of-pairs even on uneven ground, and they double as
  the height adjustment for framing/macro distance.

## Printing

| Part | Qty | Notes |
|---|---|---|
| `base` | 1 | Print **as modelled** (belly down). No supports needed — the leg bosses are the only overhang and they're short. |
| `leg_segment` | 12–24 | Tiny and fast. Print a big batch; that's your height kit. |
| `foot` | 6 | Print peg-up (as modelled). |

Suggested: 0.2 mm layers, 3 perimeters, 20–30 % infill. PETG or ASA if it lives
outdoors (PLA sags in a hot enclosure/sun); PLA is fine indoors.

**Print the fit-test first:** one `leg_segment` + one `foot`, and check the peg
grip. Too loose → lower `fit` (e.g. 0.15). Too tight → raise it (0.25–0.30).
Printers vary more than the model does; this one number is the whole trick.

## Height adjustment (the "Lego" bit)

Each socket under the belly takes a square peg. Every `leg_segment` adds
**12 mm** (`leg_seg_h`) and has a peg on top / socket underneath, so they chain:

```
belly socket
   ↑ peg
 [ segment ]   ← add or remove these
   ↑ peg
 [ segment ]
   ↑ peg
 [  foot   ]
```

- **Shortest:** foot straight into the belly → ~2 cm ground clearance.
- **Each extra segment:** +12 mm. Six segments ≈ 9 cm.
- Square pegs mean the legs **can't spin** — a round peg would let the body
  wander out of level.

Mixed heights are fine (and useful on a slope): just stack the downhill legs
taller.

## Fitting your hardware

Everything is a variable at the top of the `.scad` file — open it, change the
number, re-render. The ones you'll almost certainly touch:

| Variable | What it does |
|---|---|
| `body_len`, `body_wid` | Overall belly footprint |
| `cam_d/x/y`, `ir_d/x/y`, `ldr_d/x/y` | Diameter and position of each downward window |
| `post_xy`, `post_h` | Board standoff positions/height — **set these to your board's real hole pattern** |
| `rim_h` | Wall height; raise it if the stack is tall |
| `fit` | Leg peg tightness (see above) |

> The optics and standoff numbers shipped here are **placeholders**. Measure the
> camera module, IR board and your PCB holes, then set them before printing the
> base. The legs are safe to print immediately.

## Exporting STLs

Open in [OpenSCAD](https://openscad.org/), set `part =` at the top to
`"base"`, `"leg_segment"` or `"foot"`, press **F6** (render), then **Export → STL**.

From the command line:

```bash
openscad -D 'part="base"'        -o ladybug_base.stl  ladybug_base.scad
openscad -D 'part="leg_segment"' -o leg_segment.stl   ladybug_base.scad
openscad -D 'part="foot"'        -o foot.stl          ladybug_base.scad
```

## Still to design

- [ ] The domed **elytra shell** (part 2) — split down the middle wing line, with
      the classic spots as raised bumps, and a lip that seats on the tray shoulder.
- [ ] Cable path / gland for power in.
- [ ] Optional clear window or lens hood around the camera port to keep dew off.
- [ ] A little head with the "eyes" as vents.
