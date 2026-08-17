# Ladybug enclosure 🐞

A 3D-printed ladybug that hides the electronics under its shell and looks
**straight down** at whatever it's standing over. Legs are Lego-style stacking
blocks, so the same body works at 2 cm or 15 cm off the ground.

**Part 1 (here): the belly** — [`ladybug_belly.py`](ladybug_belly.py), a
parametric FreeCAD script.
Part 2 (next): the domed elytra shell that lifts off the top.

![preview](preview.png)

## Build it

FreeCAD 1.0+ (free). Either open the script in FreeCAD's Python console, or run
it headless — it writes STLs into `stl/` and a `ladybug.FCStd` you can open and
edit:

```bash
"C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe" ladybug_belly.py
```

It prints a check per part; every one must say `printable=True` (a single closed
solid). Current output:

| Part | Size | Volume |
|---|---|---|
| `belly` | 100 × 140 × 43 mm | ~105 cm³ |
| `leg_segment` | 9.5 × 9.5 × 20 mm | 0.6 cm³ |
| `foot` | 14 × 14 × 14 mm | 0.7 cm³ |

## The waterproof lid ("lift") — how the seal works

The shell is a **lid that lifts straight off**. Water never gets a straight path
in, because the joint is a labyrinth:

```
        shell skirt (part 2)
          |  ||                  skirt hangs OUTSIDE, down over the rebate
          |  ||   __ tongue      belly tongue rises INSIDE the skirt,
          |  ||  |  |            into a matching groove in the shell
       ___|  ||__|  |___         seat + gutter, with weep notches
      |      belly       |
       \__ shoulder: skirt edge stops here, water drips off __/
```

- Rain runs down the shell and **drips off the skirt's bottom edge** at the
  shoulder — below and outside the joint.
- To get in, water would have to climb **8 mm up a gap and over a 6 mm tongue**.
  It can't; gravity is on our side.
- Any splash that does land in the gutter drains out through the **weep
  notches** cut in the top of the rebate wall.
- The **screw ears are outside the seal**, so the fixings can't leak.
- The **leg sockets are blind** — they open downward only and never break
  through the floor into the dry side.

Two things you still add by hand:

1. **Clear discs over the optics.** The camera and IR windows have a rebate
   underneath sized for a clear acrylic/glass disc — glue it in with a bead of
   clear silicone. That seals the only holes in the floor.
2. **A vent.** A fully sealed box breathes with temperature and sucks moisture
   past any seal. Stick a small square of PTFE/Gore vent tape over a 3 mm hole
   drilled high on a side wall, or accept the (slightly leaky) cable gland as
   your vent.

## Printing

| Part | Qty | Notes |
|---|---|---|
| `belly` | 1 | Print as-is, belly down. The leg bosses are the only overhang and they're short — no supports needed. |
| `leg_segment` | 12–24 | Tiny and fast. This is your height kit. |
| `foot` | 6 | Print peg-up. |

0.2 mm layers, 3 perimeters, 20–30 % infill. **PETG or ASA if it lives
outdoors** — PLA sags in a sun-baked enclosure. TPU feet grip better and damp
vibration.

> **Print one `leg_segment` + one `foot` first** and check the peg grip. Too
> loose → lower `fit` (0.15). Too tight → raise it (0.25–0.30). Printer
> tolerance varies more than the model does; this one number is the whole trick.

## Height adjustment (the Lego bit)

Every `leg_segment` adds **12 mm** and has a peg on top / socket underneath:

```
belly socket → [segment] → [segment] → [foot]
```

- Shortest: foot straight into the belly ≈ 2 cm clearance.
- Each segment: +12 mm. Six ≈ 9 cm.
- **Square pegs** mean the legs can't rotate — round ones would let the body
  slowly wander out of level.
- Stack the downhill legs taller to stand level on a slope.

**Camera height is your focus knob.** The IMX708 won't focus closer than ~10 cm,
so print enough segments to bracket 10–20 cm.

## Fitting your hardware

Everything is in the `PARAMS` block at the top of the script — change a number,
re-run. The ones you'll actually touch:

| Param | What it does |
|---|---|
| `body_len`, `body_wid` | Overall footprint |
| `cam_pos`, `cam_hole_d`, `cam_glass_d`, `cam_post_dx/dy` | Camera window + its mounting holes (defaults ≈ Pi Camera Module 3) |
| `ir_pos`, `ir_hole_d`, `ir_post_dx/dy` | IR board window + mounts |
| `ldr_pos`, `ldr_hole_d` | Light-sensor window |
| `pcb_posts`, `pcb_post_h` | Main board standoffs — **set to your real hole pattern** |
| `fit` | Leg peg tightness |
| `skirt_th`, `skirt_gap`, `tongue_w`, `tongue_h` | The seal — part 2 must match these |

> ⚠️ The optics and standoff coordinates shipped here are **placeholders**.
> Measure your camera module, IR board and PCB holes before printing the belly.
> The legs are safe to print right now.

### Internal layout

Optics sit on the floor (camera + IR on their own standoffs, separated by the
light baffle so IR doesn't wash out the image). The main board goes **above**
them on 17 mm posts — a mezzanine. If your board is thick, raise `pcb_post_h`
and `rim_h` together.

## Still to design

- [ ] The domed **elytra shell** — split along the wing line, spots as raised
      bumps, groove matching this tongue, skirt matching this rebate.
- [ ] Lens hood / dew shield around the camera port.
- [ ] Head with the "eyes" as vent detail.
