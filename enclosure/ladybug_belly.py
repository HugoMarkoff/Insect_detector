"""
Insect Detector - ladybug enclosure, PART 1: the BELLY (bottom tray).

Parametric FreeCAD script. Edit the PARAMS block, run, get STLs.

    "C:\\Program Files\\FreeCAD 1.0\\bin\\FreeCADCmd.exe" ladybug_belly.py
    (or paste into FreeCAD's Python console / View > Panels > Python console)

What it builds
--------------
  belly        - the tray: downward camera + IR windows, board standoffs,
                 six Lego-style leg sockets, and the waterproof shell seat
  leg_segment  - one +12 mm stacking block (print a pile of them)
  foot         - the bottom pad

Waterproofing: the shell is a LID that lifts straight off. Rain runs down the
shell, off its skirt, and drips clear of the joint - it never crosses the seal:

      shell skirt (part 2)
        |  ||                     <- skirt hangs OUTSIDE, over the rebate
        |  ||   __ tongue         <- belly tongue rises INSIDE the skirt
        |  ||  |  |                  into a matching groove in the shell
     ___|  ||__|  |___ seat + gutter (weep notches drain any splash back out)
    |     belly wall     |
    |                    |
     \__ shoulder: skirt bottom edge stops here, water drips off __/

So water has to climb up a 8 mm gap and over a 6 mm tongue to get in. It won't.
"""
import math
import os
import sys

import FreeCAD as App
import Part

# =====================================================================
# PARAMS - everything you'd want to change lives here (millimetres)
# =====================================================================
P = {
    # --- overall body ---
    "body_len":      130.0,   # front-back (Y)
    "body_wid":      100.0,   # left-right (X)
    "head_rx":        32.0,   # the little head bump, half-width
    "head_ry":        13.0,   # ... and how far it reaches forward
    "floor_th":        3.0,
    "rim_h":          22.0,   # wall height above the floor, up to the seat

    # --- shell interface (the "lift-off lid" seal) ---
    "skirt_th":        2.4,   # thickness of the shell's skirt (part 2 must match)
    "skirt_gap":       0.35,  # clearance so the lid drops on without forcing
    "shoulder_drop":   8.0,   # how far the skirt overlaps down the outside
    "gutter_w":        3.0,   # drain channel between tongue and skirt
    "tongue_w":        2.6,   # sealing tongue thickness
    "tongue_h":        6.0,   # ... and height (this is the labyrinth depth)
    "weep_angles":  [30, 150, 210, 330],   # drain notches (deg, 0 = +X)
    "weep_w":          3.0,

    # --- downward optics: PLACEHOLDERS, measure your hardware! ---
    # Camera (defaults ~ Pi Camera Module 3: 25x24 mm board, holes 21 x 12.5)
    "cam_pos":      (0.0, 12.0),
    "cam_hole_d":   15.0,     # clear hole the lens looks through
    "cam_glass_d":  24.0,     # rebate underneath for a clear disc (glue in)
    "cam_glass_th":  2.0,
    "cam_post_dx":  21.0,
    "cam_post_dy":  12.5,
    # IR illuminator board
    "ir_pos":       (0.0, -32.0),
    "ir_hole_d":    20.0,
    "ir_glass_d":   28.0,
    "ir_glass_th":   2.0,
    "ir_post_dx":   19.0,
    "ir_post_dy":   19.0,
    # light sensor (LDR) - small window, kept away from the IR spill
    "ldr_pos":      (30.0, 12.0),
    "ldr_hole_d":    5.0,
    # shared standoff geometry
    "post_h":        4.0,
    "post_d":        6.0,
    "post_pilot_d":  2.1,     # M2.5 self-tap
    # light baffle between camera and IR (stops IR washing out the image).
    # Deliberately SHORT + partial-width: the optics live on the floor under it,
    # the main board sits on taller posts above it (a mezzanine).
    "baffle_y":    -10.0,
    "baffle_th":     2.4,
    "baffle_h":     14.0,
    "baffle_halfw": 34.0,

    # --- main board standoffs (set to YOUR pcb hole pattern) ---
    # post height clears the baffle + the camera/IR boards below
    "pcb_posts":   [(36.0, 34.0), (-36.0, 34.0), (36.0, -14.0), (-36.0, -14.0)],
    "pcb_post_h":   17.0,
    "pcb_pilot_d":   2.6,     # M3 self-tap

    # --- Lego-style legs ---
    "leg_pos":     [(34.0, 40.0), (-34.0, 40.0),
                    (40.0,  0.0), (-40.0,  0.0),
                    (32.0,-42.0), (-32.0,-42.0)],
    "socket_od":    13.0,     # boss under the belly
    "socket_drop":  12.0,     # how far it hangs below the floor
    "socket_sq":     7.4,     # square hole (square = legs can't rotate)
    "socket_depth": 10.0,     # BLIND - never cut through into the dry side
    "leg_seg_h":    12.0,     # <- one segment = +12 mm of height
    "leg_out":       9.5,     # outer size of a leg block
    "peg_sq":        7.0,
    "peg_h":         8.0,
    "fit":           0.20,    # peg clearance: smaller = tighter. TUNE THIS.
    "foot_h":        6.0,
    "foot_d":       14.0,

    # --- lid screw ears (outside the seal, so they can't leak) ---
    "ear_angles":  [40, 140, 220, 320],
    "ear_d":         9.0,
    "ear_pilot_d":   2.6,
    "ear_h":         6.0,

    # --- cable entry (fit a gland or seal with silicone) ---
    "gland_d":      12.0,
    "gland_boss_d": 20.0,
    "gland_z":      12.0,
}

Z = App.Vector(0, 0, 1)


# =====================================================================
# helpers
# =====================================================================
def ellipse_solid(cx, cy, rx, ry, z0, h):
    """A vertical elliptical prism. Handles rx<ry (Part.Ellipse wants major>=minor)."""
    if rx <= 0.01 or ry <= 0.01:
        return None
    swap = rx < ry
    a, b = (ry, rx) if swap else (rx, ry)
    ell = Part.Ellipse(App.Vector(0, 0, 0), a, b)
    face = Part.Face(Part.Wire([ell.toShape()]))
    sol = face.extrude(App.Vector(0, 0, h))
    if swap:
        sol.rotate(App.Vector(0, 0, 0), Z, 90)
    sol.translate(App.Vector(cx, cy, z0))
    return sol


def outline_solid(inset, z0, h):
    """The ladybug footprint (body ellipse + head bump), shrunk by `inset`."""
    p = P
    body = ellipse_solid(0, 0, p["body_wid"] / 2.0 - inset, p["body_len"] / 2.0 - inset, z0, h)
    head_y = p["body_len"] / 2.0 - 6.0
    head = ellipse_solid(0, head_y, p["head_rx"] - inset, p["head_ry"] - inset, z0, h)
    if body is None:
        return head
    if head is None:
        return body
    return body.fuse(head).removeSplitter()


def zlevels():
    p = P
    seat_z = p["floor_th"] + p["rim_h"]
    return {
        "seat_z": seat_z,
        "shoulder_z": seat_z - p["shoulder_drop"],
        "tongue_top": seat_z + p["tongue_h"],
        "inset_rebate": p["skirt_th"] + p["skirt_gap"],
        "inset_tongue": p["skirt_th"] + p["skirt_gap"] + p["gutter_w"],
        "inset_cavity": p["skirt_th"] + p["skirt_gap"] + p["gutter_w"] + p["tongue_w"],
    }


def post(x, y, z0, h, d, pilot_d, pilot_depth):
    """A standoff with a self-tap pilot hole down the middle."""
    s = Part.makeCylinder(d / 2.0, h, App.Vector(x, y, z0))
    hole = Part.makeCylinder(pilot_d / 2.0, pilot_depth + 0.1,
                             App.Vector(x, y, z0 + h - pilot_depth))
    return s.cut(hole)


def four_posts(cx, cy, dx, dy, z0, h, d, pilot_d):
    out = None
    for sx in (-1, 1):
        for sy in (-1, 1):
            s = post(cx + sx * dx / 2.0, cy + sy * dy / 2.0, z0, h, d, pilot_d, h - 1.0)
            out = s if out is None else out.fuse(s)
    return out


# =====================================================================
# the belly
# =====================================================================
def build_belly():
    p, L = P, zlevels()
    floor_th = p["floor_th"]

    # ---- shell: lower body, then the rebate the skirt slides over, then tongue
    solid = outline_solid(0.0, 0.0, L["shoulder_z"])
    solid = solid.fuse(outline_solid(L["inset_rebate"], L["shoulder_z"], p["shoulder_drop"]))
    tongue = outline_solid(L["inset_tongue"], L["seat_z"], p["tongue_h"]).cut(
        outline_solid(L["inset_cavity"], L["seat_z"] - 1, p["tongue_h"] + 2))
    solid = solid.fuse(tongue)

    # ---- leg bosses hanging below the floor
    for (x, y) in p["leg_pos"]:
        solid = solid.fuse(Part.makeCylinder(
            p["socket_od"] / 2.0, p["socket_drop"] + floor_th,
            App.Vector(x, y, -p["socket_drop"])))

    # ---- screw ears (outside the seal)
    A, B = p["body_wid"] / 2.0, p["body_len"] / 2.0
    ears = []
    for ang in p["ear_angles"]:
        t = math.radians(ang)
        ex, ey = A * math.cos(t), B * math.sin(t)
        e = Part.makeCylinder(p["ear_d"] / 2.0, p["ear_h"],
                              App.Vector(ex, ey, L["shoulder_z"] - p["ear_h"]))
        inner = Part.makeCylinder(p["ear_d"] / 2.0, p["ear_h"],
                                  App.Vector(ex * 0.86, ey * 0.86, L["shoulder_z"] - p["ear_h"]))
        solid = solid.fuse(e.fuse(inner))          # blends the ear into the wall
        ears.append((ex, ey))

    # ---- cable gland boss (on the back, below the skirt line)
    gy = -B - 3.0
    boss = Part.makeCylinder(p["gland_boss_d"] / 2.0, 10.0,
                             App.Vector(0, gy, p["gland_z"]), App.Vector(0, 1, 0))
    solid = solid.fuse(boss)

    # ---- hollow it out
    solid = solid.cut(outline_solid(L["inset_cavity"], floor_th,
                                    L["tongue_top"] - floor_th + 2))

    # ---- downward optical windows: through-hole + rebate for a clear disc
    for pos, hole_d, glass_d, glass_th in (
            (p["cam_pos"], p["cam_hole_d"], p["cam_glass_d"], p["cam_glass_th"]),
            (p["ir_pos"],  p["ir_hole_d"],  p["ir_glass_d"],  p["ir_glass_th"])):
        x, y = pos
        solid = solid.cut(Part.makeCylinder(hole_d / 2.0, floor_th + 2, App.Vector(x, y, -1)))
        solid = solid.cut(Part.makeCylinder(glass_d / 2.0, glass_th, App.Vector(x, y, 0)))
    lx, ly = p["ldr_pos"]
    solid = solid.cut(Part.makeCylinder(p["ldr_hole_d"] / 2.0, floor_th + 2, App.Vector(lx, ly, -1)))

    # ---- blind square leg sockets (open downward only - the dry side stays sealed)
    for (x, y) in p["leg_pos"]:
        s = p["socket_sq"]
        cut = Part.makeBox(s, s, p["socket_depth"] + 0.01,
                           App.Vector(x - s / 2.0, y - s / 2.0, -p["socket_drop"] - 0.01))
        solid = solid.cut(cut)

    # ---- weep notches: drain the gutter outward, under the skirt
    ring = outline_solid(-1.0, L["seat_z"] - 1.5, 3.0).cut(
        outline_solid(L["inset_tongue"], L["seat_z"] - 2.0, 5.0))
    spokes = None
    for ang in p["weep_angles"]:
        bx = Part.makeBox(400, p["weep_w"], 5.0,
                          App.Vector(-200, -p["weep_w"] / 2.0, L["seat_z"] - 2.0))
        bx.rotate(App.Vector(0, 0, 0), Z, ang)
        spokes = bx if spokes is None else spokes.fuse(bx)
    solid = solid.cut(ring.common(spokes))

    # ---- ear pilot holes
    for (ex, ey) in ears:
        solid = solid.cut(Part.makeCylinder(p["ear_pilot_d"] / 2.0, p["ear_h"],
                                            App.Vector(ex, ey, L["shoulder_z"] - p["ear_h"] + 0.5)))

    # ---- cable gland bore
    solid = solid.cut(Part.makeCylinder(p["gland_d"] / 2.0, 40.0,
                                        App.Vector(0, gy - 1, p["gland_z"]), App.Vector(0, 1, 0)))

    # ---- internal furniture: standoffs + light baffle
    solid = solid.fuse(four_posts(p["cam_pos"][0], p["cam_pos"][1], p["cam_post_dx"],
                                  p["cam_post_dy"], floor_th, p["post_h"], p["post_d"],
                                  p["post_pilot_d"]))
    solid = solid.fuse(four_posts(p["ir_pos"][0], p["ir_pos"][1], p["ir_post_dx"],
                                  p["ir_post_dy"], floor_th, p["post_h"], p["post_d"],
                                  p["post_pilot_d"]))
    for (x, y) in p["pcb_posts"]:
        solid = solid.fuse(post(x, y, floor_th, p["pcb_post_h"], p["post_d"],
                                p["pcb_pilot_d"], p["pcb_post_h"] - 1.0))

    bw = p["baffle_halfw"]
    baffle = Part.makeBox(bw * 2.0, p["baffle_th"], p["baffle_h"],
                          App.Vector(-bw, p["baffle_y"] - p["baffle_th"] / 2.0, floor_th))
    cavity = outline_solid(L["inset_cavity"] + 0.01, floor_th, p["baffle_h"])
    solid = solid.fuse(baffle.common(cavity))

    return solid.removeSplitter()


# =====================================================================
# legs: peg on top, socket underneath -> they stack like Lego
# =====================================================================
def _peg(z0):
    """Square peg with a small lead-in taper. It starts 0.6 mm BELOW z0 so it
    overlaps its parent solid - shapes that merely touch fuse into a 2-solid
    compound, which slicers dislike."""
    p = P
    s, t = p["peg_sq"], p["peg_sq"] * 0.86          # slight taper = easy start
    bot = Part.makeBox(s, s, 0.01, App.Vector(-s / 2.0, -s / 2.0, z0 - 0.6))
    top = Part.makeBox(t, t, 0.01, App.Vector(-t / 2.0, -t / 2.0, z0 + p["peg_h"]))
    return Part.makeLoft([bot.Faces[0].OuterWire, top.Faces[0].OuterWire], True)


def build_leg_segment():
    p = P
    o, h = p["leg_out"], p["leg_seg_h"]
    body = Part.makeBox(o, o, h, App.Vector(-o / 2.0, -o / 2.0, 0))
    body = body.fuse(_peg(h))
    s = p["peg_sq"] + p["fit"]
    sock = Part.makeBox(s, s, p["peg_h"] + 0.6, App.Vector(-s / 2.0, -s / 2.0, -0.01))
    return body.cut(sock).removeSplitter()


def build_foot():
    p = P
    f = Part.makeCone(p["foot_d"] / 2.0, p["leg_out"] / 2.0, p["foot_h"], App.Vector(0, 0, 0))
    f = f.fuse(_peg(p["foot_h"]))
    return f.removeSplitter()


# =====================================================================
# run
# =====================================================================
def export(shape, name, outdir):
    path = os.path.join(outdir, name + ".stl")
    try:
        import MeshPart
        m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.08,
                                   AngularDeflection=0.35, Relative=False)
        m.write(path)
    except Exception:
        shape.exportStl(path)
    return path


def main():
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")
    if not os.path.isdir(outdir):
        os.makedirs(outdir)

    doc = App.newDocument("ladybug")
    parts = [("belly", build_belly()),
             ("leg_segment", build_leg_segment()),
             ("foot", build_foot())]

    ok = True
    for name, shape in parts:
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = shape
        bb = shape.BoundBox
        single = shape.isValid() and len(shape.Solids) == 1
        ok = ok and single
        print("%-12s  %6.1f x %6.1f x %6.1f mm   printable=%s  volume=%.1f cm3"
              % (name, bb.XLength, bb.YLength, bb.ZLength, single, shape.Volume / 1000.0))
        if not single:
            print("   !! not a single closed solid (%d solids, valid=%s) - fix before printing"
                  % (len(shape.Solids), shape.isValid()))
        print("              -> " + export(shape, name, outdir))

    doc.recompute()
    doc.saveAs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ladybug.FCStd"))
    print("saved ladybug.FCStd")


main()
