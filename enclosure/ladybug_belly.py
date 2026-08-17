"""
Insect Detector - ladybug enclosure, PART 1: the BELLY (bottom tray).

Parametric FreeCAD script. Edit PARAMS, run, get STLs.

    "C:\\Program Files\\FreeCAD 1.0\\bin\\FreeCADCmd.exe" ladybug_belly.py

Built around the real hardware:
  * IR board  = the "batwing" PCB, ~100 x 80 mm, LEDs + light sensor on its
    BOTTOM face, with a top-centre NOTCH where the camera looks through.
    -> It mounts UNDER the floor (LEDs point straight down, unobstructed). The
       floor stays solid & waterproof except one small camera hole.
  * Camera    = Raspberry Pi Camera (V2 or V3 - same 21 x 12.5 mm holes). It
    mounts INSIDE on standoffs; only the lens pokes down through a 12 mm hole
    that clears both V2 and V3 lenses. The hole lines up with the IR notch.
  * Light sensor is ON the IR board (bottom face) - no separate window.

Waterproofing: the shell is a lift-off lid (skirt over rebate + tongue-in-groove
labyrinth, weep-drained). The only floor penetration is the camera hole, sealed
with a clear disc in a rebate. IR board lives outside/below - it's an emitter
board, conformal-coat it; the legs lift it clear of the ground.
"""
import math
import os

import FreeCAD as App
import Part

Z = App.Vector(0, 0, 1)

# =====================================================================
# PARAMS  (millimetres)
# =====================================================================
P = {
    # --- overall body (sized to sit over the 100 x 80 IR board) ---
    "body_len":      150.0,   # front-back (Y)
    "body_wid":      116.0,   # left-right (X)
    "head_rx":        36.0,
    "head_ry":        15.0,
    "floor_th":        3.0,
    "rim_h":          24.0,

    # --- shell interface (the waterproof "lift" - part 2 must match) ---
    "skirt_th":        2.4,
    "skirt_gap":       0.35,
    "shoulder_drop":   8.0,
    "gutter_w":        3.0,
    "tongue_w":        2.6,
    "tongue_h":        6.0,
    "weep_angles":  [30, 150, 210, 330],
    "weep_w":          3.0,

    # --- IR board: batwing outline (board-local, centre origin, +Y = notch) ---
    # Trace of the real board (~100 wide x 80 tall). Adjust to your exact PCB.
    "ir_outline": [
        (0, -40), (30, -22), (44, -2), (46, 2), (50, 6), (50, 32), (42, 40),
        (16, 40), (16, 18), (-16, 18), (-16, 40), (-42, 40), (-50, 32),
        (-50, 6), (-46, 2), (-44, -2), (-30, -22),
    ],
    "ir_center":    (0.0, 0.0),    # where the board sits in the belly
    "ir_boss_drop":  6.0,          # board hangs this far below the floor
    "ir_boss_od":    8.0,
    "ir_pilot_d":    2.6,          # M3 self-tap, from below
    # IR board mount holes (board-local) - PLACEHOLDER, set to your real holes:
    "ir_mounts":  [(0, 10), (0, -24), (34, 4), (-34, 4)],
    "ir_recess_d":   1.0,          # shallow locating pocket on the underside

    # --- camera (V2 / V3): lens-only through-hole + mount ---
    "cam_pos":      (0.0, 27.0),   # over the IR notch
    "cam_lens_d":   12.0,          # clears BOTH V2 and V3 lens barrels
    "cam_hole_dx":  21.0,          # V2/V3 mount holes: 21 x 12.5 mm
    "cam_hole_dy":  12.5,
    "cam_post_h":    3.0,          # short: lets the lens reach into the hole
    "cam_post_d":    6.0,
    "cam_pilot_d":   2.2,          # M2
    "collar_od":    16.0,          # baffle ring around the lens (kills IR glare)
    "collar_id":    12.5,
    "collar_h":      6.0,
    "disc_d":       18.0,          # clear sealing disc, glued in underside rebate
    "disc_th":       2.0,

    # --- main board (Pi) standoffs - set to YOUR hole pattern ---
    "pcb_posts":   [(30, -46), (-30, -46), (30, -14), (-30, -14)],
    "pcb_post_h":    6.0,
    "pcb_pilot_d":   2.6,

    # --- Lego-style legs ---
    "leg_pos":     [(40, 46), (-40, 46), (46, 0), (-46, 0), (38, -48), (-38, -48)],
    "socket_od":    13.0,
    "socket_drop":  12.0,
    "socket_sq":     7.4,
    "socket_depth": 10.0,          # blind - never breaks into the dry side
    "leg_seg_h":    12.0,          # one segment = +12 mm of height
    "leg_out":       9.5,
    "peg_sq":        7.0,
    "peg_h":         8.0,
    "fit":           0.20,         # peg clearance - TUNE THIS on a test print
    "foot_h":        6.0,
    "foot_d":       14.0,

    # --- lid screw ears (outside the seal) ---
    "ear_angles":  [40, 140, 220, 320],
    "ear_d":         9.0,
    "ear_pilot_d":   2.6,
    "ear_h":         6.0,

    # --- cable gland ---
    "gland_d":      12.0,
    "gland_boss_d": 20.0,
    "gland_z":      12.0,
}


# =====================================================================
# helpers
# =====================================================================
def ellipse_solid(cx, cy, rx, ry, z0, h):
    if rx <= 0.01 or ry <= 0.01:
        return None
    swap = rx < ry
    a, b = (ry, rx) if swap else (rx, ry)
    face = Part.Face(Part.Wire([Part.Ellipse(App.Vector(0, 0, 0), a, b).toShape()]))
    sol = face.extrude(App.Vector(0, 0, h))
    if swap:
        sol.rotate(App.Vector(0, 0, 0), Z, 90)
    sol.translate(App.Vector(cx, cy, z0))
    return sol


def outline_solid(inset, z0, h):
    p = P
    body = ellipse_solid(0, 0, p["body_wid"] / 2.0 - inset, p["body_len"] / 2.0 - inset, z0, h)
    head = ellipse_solid(0, p["body_len"] / 2.0 - 6.0, p["head_rx"] - inset, p["head_ry"] - inset, z0, h)
    if body is None:
        return head
    if head is None:
        return body
    return body.fuse(head).removeSplitter()


def ir_prism(z0, h, grow=0.0):
    """The batwing IR-board footprint as a vertical prism (optionally grown)."""
    p = P
    pts = p["ir_outline"]
    if grow:                                   # offset outward by scaling from centroid
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        rad = max(math.hypot(x - cx, y - cy) for x, y in pts)
        s = (rad + grow) / rad
        pts = [(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in pts]
    ox, oy = p["ir_center"]
    vs = [App.Vector(ox + x, oy + y, z0) for x, y in pts]
    vs.append(vs[0])
    sol = Part.Face(Part.makePolygon(vs)).extrude(App.Vector(0, 0, h))
    return sol


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
    s = Part.makeCylinder(d / 2.0, h, App.Vector(x, y, z0))
    hole = Part.makeCylinder(pilot_d / 2.0, pilot_depth + 0.1, App.Vector(x, y, z0 + h - pilot_depth))
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
    ft = p["floor_th"]
    cx, cy = p["cam_pos"]

    # ---- shell: body + rebate + tongue
    solid = outline_solid(0.0, 0.0, L["shoulder_z"])
    solid = solid.fuse(outline_solid(L["inset_rebate"], L["shoulder_z"], p["shoulder_drop"]))
    tongue = ir = outline_solid(L["inset_tongue"], L["seat_z"], p["tongue_h"]).cut(
        outline_solid(L["inset_cavity"], L["seat_z"] - 1, p["tongue_h"] + 2))
    solid = solid.fuse(tongue)

    # ---- leg bosses
    for (x, y) in p["leg_pos"]:
        solid = solid.fuse(Part.makeCylinder(p["socket_od"] / 2.0, p["socket_drop"] + ft,
                                             App.Vector(x, y, -p["socket_drop"])))

    # ---- screw ears
    A, B = p["body_wid"] / 2.0, p["body_len"] / 2.0
    ears = []
    for ang in p["ear_angles"]:
        t = math.radians(ang)
        ex, ey = A * math.cos(t), B * math.sin(t)
        e = Part.makeCylinder(p["ear_d"] / 2.0, p["ear_h"], App.Vector(ex, ey, L["shoulder_z"] - p["ear_h"]))
        inner = Part.makeCylinder(p["ear_d"] / 2.0, p["ear_h"], App.Vector(ex * 0.86, ey * 0.86, L["shoulder_z"] - p["ear_h"]))
        solid = solid.fuse(e.fuse(inner))
        ears.append((ex, ey))

    # ---- cable gland boss
    gy = -B - 3.0
    solid = solid.fuse(Part.makeCylinder(p["gland_boss_d"] / 2.0, 10.0, App.Vector(0, gy, p["gland_z"]), App.Vector(0, 1, 0)))

    # ---- hollow the cavity
    solid = solid.cut(outline_solid(L["inset_cavity"], ft, L["tongue_top"] - ft + 2))

    # ---- camera lens hole (through the floor) + clear-disc rebate underneath
    solid = solid.cut(Part.makeCylinder(p["cam_lens_d"] / 2.0, ft + 2, App.Vector(cx, cy, -1)))
    solid = solid.cut(Part.makeCylinder(p["disc_d"] / 2.0, p["disc_th"], App.Vector(cx, cy, 0)))

    # ---- shallow batwing locating recess on the underside (board can't spin)
    solid = solid.cut(ir_prism(-p["ir_recess_d"], p["ir_recess_d"] + 0.01, grow=0.3))

    # ---- IR-board standoff bosses. AFTER the recess cut, so the recess can't
    #      slice them off the body (that would leave detached solids).
    for (mx, my) in p["ir_mounts"]:
        bx, by = p["ir_center"][0] + mx, p["ir_center"][1] + my
        solid = solid.fuse(Part.makeCylinder(p["ir_boss_od"] / 2.0, p["ir_boss_drop"] + ft,
                                             App.Vector(bx, by, -p["ir_boss_drop"])))

    # ---- blind square leg sockets (downward only)
    for (x, y) in p["leg_pos"]:
        s = p["socket_sq"]
        solid = solid.cut(Part.makeBox(s, s, p["socket_depth"] + 0.01,
                                       App.Vector(x - s / 2.0, y - s / 2.0, -p["socket_drop"] - 0.01)))

    # ---- weep notches drain the gutter outward
    ring = outline_solid(-1.0, L["seat_z"] - 1.5, 3.0).cut(outline_solid(L["inset_tongue"], L["seat_z"] - 2.0, 5.0))
    spokes = None
    for ang in p["weep_angles"]:
        bx = Part.makeBox(400, p["weep_w"], 5.0, App.Vector(-200, -p["weep_w"] / 2.0, L["seat_z"] - 2.0))
        bx.rotate(App.Vector(0, 0, 0), Z, ang)
        spokes = bx if spokes is None else spokes.fuse(bx)
    solid = solid.cut(ring.common(spokes))

    # ---- pilot holes: ears, IR bosses, gland
    for (ex, ey) in ears:
        solid = solid.cut(Part.makeCylinder(p["ear_pilot_d"] / 2.0, p["ear_h"], App.Vector(ex, ey, L["shoulder_z"] - p["ear_h"] + 0.5)))
    for (mx, my) in p["ir_mounts"]:
        bx, by = p["ir_center"][0] + mx, p["ir_center"][1] + my
        # blind from below - never breaks through to the dry inside
        solid = solid.cut(Part.makeCylinder(p["ir_pilot_d"] / 2.0, p["ir_boss_drop"] + ft - 0.8, App.Vector(bx, by, -p["ir_boss_drop"] - 0.01)))
    solid = solid.cut(Part.makeCylinder(p["gland_d"] / 2.0, 40.0, App.Vector(0, gy - 1, p["gland_z"]), App.Vector(0, 1, 0)))

    # ---- internal furniture
    # camera baffle collar (ring around the lens, stops IR washing the image)
    collar = Part.makeCylinder(p["collar_od"] / 2.0, p["collar_h"], App.Vector(cx, cy, 0))
    collar = collar.cut(Part.makeCylinder(p["collar_id"] / 2.0, p["collar_h"] + 1, App.Vector(cx, cy, -0.5)))
    solid = solid.fuse(collar)
    # camera standoffs (V2/V3, 21 x 12.5)
    solid = solid.fuse(four_posts(cx, cy, p["cam_hole_dx"], p["cam_hole_dy"], ft, p["cam_post_h"], p["cam_post_d"], p["cam_pilot_d"]))
    # main board (Pi) standoffs
    for (x, y) in p["pcb_posts"]:
        solid = solid.fuse(post(x, y, ft, p["pcb_post_h"], p["cam_post_d"], p["pcb_pilot_d"], p["pcb_post_h"] - 1.0))

    return solid.removeSplitter()


# =====================================================================
# legs
# =====================================================================
def _peg(z0):
    p = P
    s, t = p["peg_sq"], p["peg_sq"] * 0.86
    bot = Part.makeBox(s, s, 0.01, App.Vector(-s / 2.0, -s / 2.0, z0 - 0.6))
    top = Part.makeBox(t, t, 0.01, App.Vector(-t / 2.0, -t / 2.0, z0 + p["peg_h"]))
    return Part.makeLoft([bot.Faces[0].OuterWire, top.Faces[0].OuterWire], True)


def build_leg_segment():
    p = P
    o, h = p["leg_out"], p["leg_seg_h"]
    body = Part.makeBox(o, o, h, App.Vector(-o / 2.0, -o / 2.0, 0)).fuse(_peg(h))
    s = p["peg_sq"] + p["fit"]
    sock = Part.makeBox(s, s, p["peg_h"] + 0.6, App.Vector(-s / 2.0, -s / 2.0, -0.01))
    return body.cut(sock).removeSplitter()


def build_foot():
    p = P
    f = Part.makeCone(p["foot_d"] / 2.0, p["leg_out"] / 2.0, p["foot_h"], App.Vector(0, 0, 0)).fuse(_peg(p["foot_h"]))
    return f.removeSplitter()


# =====================================================================
# run
# =====================================================================
def export(shape, name, outdir):
    path = os.path.join(outdir, name + ".stl")
    try:
        import MeshPart
        m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.08, AngularDeflection=0.35, Relative=False)
        m.write(path)
    except Exception:
        shape.exportStl(path)
    return path


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    outdir = os.path.join(here, "stl")
    if not os.path.isdir(outdir):
        os.makedirs(outdir)

    doc = App.newDocument("ladybug")
    parts = [("belly", build_belly()), ("leg_segment", build_leg_segment()), ("foot", build_foot())]
    for name, shape in parts:
        doc.addObject("Part::Feature", name).Shape = shape
        bb = shape.BoundBox
        single = shape.isValid() and len(shape.Solids) == 1
        print("%-12s  %6.1f x %6.1f x %6.1f mm   printable=%s  volume=%.1f cm3"
              % (name, bb.XLength, bb.YLength, bb.ZLength, single, shape.Volume / 1000.0))
        if not single:
            print("   !! not a single closed solid (%d solids) - fix before printing" % len(shape.Solids))
        print("              -> " + export(shape, name, outdir))
    doc.recompute()
    doc.saveAs(os.path.join(here, "ladybug.FCStd"))
    print("saved ladybug.FCStd")


main()
