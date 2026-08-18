# Ladybug enclosure 🐞

A 3D-printed ladybug that hides the electronics under its shell and looks
**straight down** at whatever it's standing over. Legs are Lego-style stacking
blocks, so the same body works at 2 cm or 15 cm off the ground.

**Part 1 (here): the belly** — [`ladybug_belly.py`](ladybug_belly.py), a
parametric FreeCAD script. [`make_drawing.py`](make_drawing.py) generates a
dimensioned top/bottom drawing from the same parameters.
**Part 2 (also here): the domed elytra shell** — `build_shell()` in the same
script, so the seal dimensions can never drift apart.

![drawing](drawing.png)
![preview](preview.png)

The IR board's geometry was pulled **straight out of the Altium file** (see
[`irboard_extracted.png`](irboard_extracted.png)) — outline, mount holes,
sensor and connector positions are manufacturing-exact.

## How the real hardware mounts

Everything lives **inside** the body. Measured off the actual boards:

| Part | Where it goes | How |
|---|---|---|
| **IR board** (batwing X, 81 × 98.4 — exact from the PcbDoc) | **Flush on the floor** — two M3 screws through its real holes (0,−6.5)/(0,−29.1) into floor pilots clamp it down | The floor has **wing-shaped windows that the LED fields fill tightly** — only the diode zones and the light sensor are open. The centre strip (logo, mount holes, the JST pins, the sensor legs) stays over solid floor, and the board **seals its own opening**: LEDs drop into the windows, the sensor into its hole, the JST pin fields into through-pockets. Silicone/foam on the strip makes it airtight |
| **Light sensor** (VT90N1 at (0,+6.3) — from the PcbDoc) | Its own Ø8 window in the solid strip | Reads ambient light straight down |
| **Camera** (Pi V2 **or** V3 — same 21 × 12.5 mm holes) | **Inside the board's camera slot** (37 mm wide, camera is 25) on 3 mm posts | Lens looks down a Ø12 hole that clears both V2 and V3 barrels, ringed by a baffle collar so IR can't glare into it |
| **Main trap PCB** (82 × 40, holes 58 × 23 — exact from its PcbDoc) | Across the body on 10 mm posts above the flush IR board | Upper posts stand in the camera slot, lower ones below the board's bottom edge; the **Pi Zero stacks onto the trap PCB's own 58 × 23 pattern** |

> **Sealing:** one rectangular **clear acrylic sheet (106 × 96 × 2 mm)** sits in a
> **frame under the floor**, its face 2 mm down — clear of the LED domes and
> pins hanging through — and closes every floor opening in one go. Cheap to buy,
> two straight cuts to make.

The board keeps **~1.5–6 mm wiggle room** to the cavity wall all the way round —
it drops in flat and lifts out without a fight.

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
| `belly` | 135 × 185 × 53 mm | ~195 cm³ |
| `shell` | 136 × 186 × 58 mm | ~176 cm³ |
| `leg_segment` | 9.5 × 9.5 × 33 mm (25 + peg) | 1.8 cm³ |
| `leg_segment_half` | 9.5 × 9.5 × 20.5 mm | 0.7 cm³ |
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

1. **The clear sheet.** Cut a 106 × 96 mm rectangle of 2 mm acrylic (round
   the corners roughly to R8 with a file), bed it into the under-floor frame on
   a bead of clear silicone. That seals every floor opening at once.
2. **A vent.** A fully sealed box breathes with temperature and sucks moisture
   past any seal. Stick a small square of PTFE/Gore vent tape over a 3 mm hole
   drilled high on a side wall, or accept the (slightly leaky) cable gland as
   your vent.

## Printing

| Part | Qty | Notes |
|---|---|---|
| `belly` | 1 | Print as-is, belly down. The leg bosses are the only overhang and they're short — no supports needed. |
| `shell` | 1 | Print as modelled (skirt ring down). The dome is self-supporting; the groove bridges are ~3 mm — fine. Red filament, black spots with a marker (or pause-and-swap). |
| `leg_segment` | 20 (4 legs × 5) | 25 mm each — 5 per leg ≈ 12.5 cm legs. |
| `leg_segment_half` | 4–8 | 12.5 mm fine-adjust blocks for slopes. |
| `foot` | 4 | Print peg-up. |

0.2 mm layers, 3 perimeters, 20–30 % infill. **PETG or ASA if it lives
outdoors** — PLA sags in a sun-baked enclosure. TPU feet grip better and damp
vibration.

> **Print one `leg_segment` + one `foot` first** and check the peg grip. Too
> loose → lower `fit` (0.15). Too tight → raise it (0.25–0.30). Printer
> tolerance varies more than the model does; this one number is the whole trick.

## Height adjustment (the Lego bit)

**Four legs, tilted 14° outward like a tripod** — the belly sockets are angled,
so the taller you stack, the wider the stance. Every `leg_segment` adds **25 mm**
along the leg:

```
belly socket (14° out) → [block] → [block] → ... → [foot]
```

| Blocks per leg | Leg length | Ground clearance | Feet spread |
|---|---|---|---|
| 2 | 56 mm | 54 mm | +14 mm/side |
| 3 | 81 mm | 79 mm | +20 mm/side |
| 4 | 106 mm | 103 mm | +26 mm/side |
| **5** | **131 mm ≈ 12.5 cm** | **127 mm** | **+32 mm/side** |

- **Square pegs** mean the legs can't rotate — the splay angle stays put.
- Stack the downhill legs taller (use the half blocks) to stand level on a slope.

**Camera height is your focus knob.** The IMX708 won't focus closer than ~10 cm,
so print enough segments to bracket 10–20 cm.

## Fitting your hardware

Everything is in the `PARAMS` block at the top of the script — change a number,
re-run. The ones you'll actually touch:

| Param | What it does |
|---|---|
| `body_len`, `body_wid` | Overall footprint |
| `ir_outline` | The exact batwing outline (auto-extracted from `IRarray-v6.1.pcbdoc`) |
| `ir_mounts`, `sensor_pos` | Exact centreline holes + VT90N1 spot (from the PcbDoc) |
| `win_inset`, `win_xmin` | Wing-window fit: rim width and solid-strip width |
| `cam_pos`, `cam_lens_d` | Camera lens hole (Ø12 clears V2 and V3) |
| `sheet_w/l/r/th` | The one-piece clear sealing sheet |
| `main_posts`, `main_post_h` | Trap-PCB standoffs (58 × 23 pattern, from its PcbDoc) |
| `leg_splay`, `leg_seg_h` | Tripod angle and block height |
| `fit` | Leg peg tightness |
| `skirt_th`, `skirt_gap`, `tongue_w`, `tongue_h` | The seal — part 2 must match these |

> ⚠️ Before printing the belly, measure and set: `ir_mounts` (the two
> centreline holes), `sensor_pos`, and check the notch/outline against your
> PCB. Everything else is dimensioned from the real hardware.
> The legs are safe to print right now.

### Internal layout (bottom → top)

| Z from floor top | What |
|---|---|
| 0–3 mm | Floor, with wing windows + sensor + lens holes; clear sheet in the rebate below |
| 3 mm | Camera posts — lens reaches down into its hole, baffle collar around it |
| −2 mm | Clear sheet in the under-floor frame (LED domes and pins stop ~1 mm above it) |
| 0–3 mm | Floor — **IR board clamped flush on top**, sealing its own openings |
| 6 mm | Camera board on 3 mm posts, lens down through the floor |
| 13 mm | **Main trap PCB** on 10 mm posts; the Pi Zero stacks onto it above |
| 33 mm | Seat level — the shell's skirt lands here |

## Still to design

- [x] The domed **elytra shell** — seven-spot dome with eye bumps, skirt +
      groove matched to the belly, four M3 tabs over the belly ears.
      (The centre split line defeated the CAD kernel — draw it with a marker.)
- [ ] Lens hood / dew shield around the camera port.
- [ ] Head with the "eyes" as vent detail.
