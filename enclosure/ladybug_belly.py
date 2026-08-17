"""
Insect Detector - ladybug enclosure, PART 1: the BELLY (bottom tray).

Parametric FreeCAD script. Edit PARAMS, run, get STLs.

    "C:\\Program Files\\FreeCAD 1.0\\bin\\FreeCADCmd.exe" ladybug_belly.py

Built around the real hardware. EVERYTHING mounts INSIDE the body:

  * IR board: EXACT geometry auto-extracted from IRarray-v6.1.pcbdoc -
    81.0 x 98.4 mm batwing, camera slot 37.2 wide from y=+10.1 flaring to the
    wing tips, two 3.0 mm centreline mount holes at (0,-6.5) and (0,-29.1),
    VT90N1 photoresistor at (0,+6.3), JST-XH pins poking through near the
    bottom wing tips. It rides a SMART ELEVATION 5 mm up: two M3 screw posts
    + centreline rest posts + a perimeter ledge under its outer 2.5 mm
    (gapped at the JST pin fields). The floor has WING-SHAPED WINDOWS the
    LED fields fill tightly; the centre strip stays over solid floor.
  * Camera (Pi V2 or V3, same 21 x 12.5 holes) sits INSIDE THE SLOT on its
    own standoffs; lens looks down a 12 mm hole (clears both barrels).
  * Pi Zero 2 W rides above on 13 mm posts (official 58 x 23 hole pattern);
    one post pair stands in the camera slot, one below the board's bottom
    plateau - neither touches the board. Full-size Pi pattern in a comment.

Sealing: ONE rectangular clear acrylic sheet (~105 x 91 x 2 mm) drops into a
rebate on the underside and is siliconed in - it closes every floor opening
(wing windows, sensor hole, camera hole) in one go. The lid is the usual
lift-off labyrinth (skirt over rebate + tongue, weep-drained).

Legs: FOUR, tilted 14 deg outward like a tripod - stacking 25 mm blocks, so
5 blocks + foot = ~12.5 cm legs, and the stance widens the taller it gets.
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
    # --- overall body (cavity swallows the 100 x 80 IR board with margin) ---
    "body_len":      172.0,   # front-back (Y)
    "body_wid":      130.0,   # left-right (X)
    "head_rx":        38.0,
    "head_ry":        16.0,
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

    # --- IR board: EXACT outline auto-extracted from IRarray-v6.1.pcbdoc ---
    #     81.0 x 98.4 mm; camera slot 37.2 wide from y=+10.1, flaring to the
    #     wing tips; bottom edge has an indented centre plateau at y=-39.1.
    "ir_outline": [
        (-40.50, -49.15), (-40.32, -49.21), (-28.86, -49.22), (-28.82, -49.21),
        (-11.41, -39.08), (11.41, -39.08), (28.83, -49.21), (28.87, -49.22),
        (40.33, -49.22), (40.48, -49.13), (40.48, 4.52), (40.45, 4.60),
        (36.80, 8.24), (36.80, 15.31), (40.47, 18.98), (40.50, 19.05),
        (40.50, 46.19), (40.36, 46.28), (33.32, 49.22), (33.24, 49.21),
        (18.61, 34.74), (18.59, 34.69), (18.59, 10.14), (-18.58, 10.14),
        (-18.58, 34.69), (-18.60, 34.74), (-33.23, 49.21), (-33.31, 49.22),
        (-40.36, 46.28), (-40.50, 46.19), (-40.50, 18.86), (-40.47, 18.78),
        (-36.00, 14.31), (-36.00, 9.07), (-40.47, 4.60), (-40.50, 4.52),
    ],
    "ir_center":    (0.0, 0.0),
    # windows: the LED wing zones. Window = board outline shrunk by
    # `win_inset`, kept outside the solid centre strip |x| < `win_xmin`.
    # (innermost LED edge is at |x|=14.9 - from the PcbDoc)
    "win_inset":     4.0,
    "win_xmin":     14.5,
    # centreline mounting holes + light sensor: EXACT from the PcbDoc.
    "ir_mounts":  [(0.0, -6.50), (0.0, -29.06)],   # 2x plated 3.0 mm holes
    "sensor_pos":   (0.0, 6.30),   # R30, VT90N1 photoresistor (through-hole)
    "sensor_hole_d": 8.0,
    "ir_post_h":     5.0,          # the "smart elevation": spikes hang free
    "ir_post_d":     7.0,
    "ir_pilot_d":    2.5,          # M3 self-tap (board holes are 3.0)
    # extra centreline rest posts (no screw), clear of pads and the sensor
    "ir_rests":   [(0.0, 1.0), (0.0, -35.0)],
    # perimeter support ledge under the board's outer 2.5 mm, interrupted
    # where the JST connector pins poke through near the bottom wing tips
    "ledge_out":     1.5,
    "ledge_in":      2.5,
    "ledge_gaps":  [(33.2, -46.3), (-33.2, -46.3)],  # JST pin fields
    "ledge_gap_w":  14.0,
    "ledge_gap_l":  10.0,

    # --- camera (V2 / V3): sits inside the board's camera slot ---
    "cam_pos":      (0.0, 30.0),   # lens centre (slot is 37.2 wide, y 10..35+)
    "cam_lens_d":   12.0,          # clears BOTH V2 and V3 lens barrels
    "cam_hole_dx":  21.0,          # V2/V3 mount holes: 21 x 12.5 mm
    "cam_hole_dy":  12.5,
    "cam_post_h":    3.0,          # lens reaches down into its hole
    "cam_post_d":    6.0,
    "cam_pilot_d":   2.2,          # M2
    "collar_od":    16.0,          # baffle ring around the lens (kills IR glare)
    "collar_id":    12.5,
    "collar_h":      2.5,

    # --- one rectangular clear sheet seals ALL openings (underside rebate) ---
    "sheet_w":     106.0,
    "sheet_l":      96.0,
    "sheet_r":       8.0,          # corner radius
    "sheet_cy":     -1.0,          # rebate centre offset (Y)
    "sheet_th":      2.0,          # rebate depth = sheet thickness

    # --- Raspberry Pi Zero 2 W, portrait, above the IR board's centre strip ---
    #     (upper post pair stands inside the camera slot; lower pair below the
    #      board's bottom plateau - neither touches the board)
    "pi_posts":   [(11.5, 15.0), (-11.5, 15.0), (11.5, -43.0), (-11.5, -43.0)],
    "pi_post_h":    13.0,          # clears the IR screw heads; JSTs are outboard
    "pi_post_d":     5.0,
    "pi_pilot_d":    2.2,          # M2.5

    # --- legs: FOUR, splayed outward like a tripod ---
    "leg_pos":     [(34, 58), (-34, 58), (38, -57), (-38, -57)],
    "leg_splay":    14.0,          # degrees outward
    "socket_od":    14.0,
    "socket_drop":  13.0,
    "socket_sq":     7.4,
    "socket_depth": 10.0,          # blind - never breaks into the dry side
    "leg_seg_h":    25.0,          # one block = +25 mm (5 blocks ~ 12.5 cm leg)
    "leg_out":       9.5,
    "peg_sq":        7.0,
    "peg_h":         8.0,
    "fit":           0.20,         # peg clearance - TUNE THIS on a test print
    "foot_h":        6.0,
    "foot_d":       14.0,

    # --- lid screw ears (outside the seal) ---
    "ear_angles":  [15, 165, 195, 345],
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


def simplify_poly(pts, tol=0.35):
    """Merge vertices closer than tol (the PCB outline has 0.04 mm arc stubs
    that make offsets explode) and drop collinear points."""
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    out = []
    for pt in pts:
        if not out or math.hypot(pt[0] - out[-1][0], pt[1] - out[-1][1]) > tol:
            out.append(pt)
    if len(out) > 2 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) <= tol:
        out.pop()
    clean = []
    m = len(out)
    for i in range(m):
        x0, y0 = out[i - 1]
        x1, y1 = out[i]
        x2, y2 = out[(i + 1) % m]
        cross = (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)
        if abs(cross) > 1e-3:
            clean.append(out[i])
    return clean


def offset_poly(pts, d):
    """Miter-offset a closed CCW polygon by d (+grow / -shrink). Pure python,
    so the concave notch offsets correctly and there's no CAD-kernel surprise."""
    pts = simplify_poly(pts)
    n = len(pts)
    out = []
    for i in range(n):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        l0 = math.hypot(x1 - x0, y1 - y0)
        l1 = math.hypot(x2 - x1, y2 - y1)
        d0 = ((x1 - x0) / l0, (y1 - y0) / l0)
        d1 = ((x2 - x1) / l1, (y2 - y1) / l1)
        n0 = (d0[1], -d0[0])                     # outward normal (CCW winding)
        n1 = (d1[1], -d1[0])
        ax, ay = x1 + d * n0[0], y1 + d * n0[1]
        bx, by = x1 + d * n1[0], y1 + d * n1[1]
        den = d0[0] * d1[1] - d0[1] * d1[0]
        if abs(den) < 1e-9:
            out.append(((ax + bx) / 2.0, (ay + by) / 2.0))
        else:
            t = ((bx - ax) * d1[1] - (by - ay) * d1[0]) / den
            out.append((ax + t * d0[0], ay + t * d0[1]))
    return out


def ir_prism(z0, h, grow=0.0):
    """The batwing footprint as a vertical prism, offset by `grow`."""
    p = P
    pts = offset_poly(p["ir_outline"], grow) if abs(grow) > 1e-6 else simplify_poly(p["ir_outline"])
    ox, oy = p["ir_center"]
    vs = [App.Vector(ox + x, oy + y, z0) for (x, y) in pts]
    if vs[0].distanceToPoint(vs[-1]) > 1e-6:
        vs.append(vs[0])
    return Part.Face(Part.makePolygon(vs)).extrude(App.Vector(0, 0, h))


def rrect(cx, cy, w, l, r, z0, h):
    """Rounded-rectangle solid."""
    a = Part.makeBox(w, l - 2 * r, h, App.Vector(cx - w / 2.0, cy - l / 2.0 + r, z0))
    b = Part.makeBox(w - 2 * r, l, h, App.Vector(cx - w / 2.0 + r, cy - l / 2.0, z0))
    s = a.fuse(b)
    for sx in (-1, 1):
        for sy in (-1, 1):
            s = s.fuse(Part.makeCylinder(r, h, App.Vector(cx + sx * (w / 2.0 - r), cy + sy * (l / 2.0 - r), z0)))
    return s.removeSplitter()


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


def leg_socket(x, y, splay, solid):
    """Leg boss (solid=True) or its blind square socket (solid=False), tilted
    `splay` degrees outward so the stance widens as blocks are added."""
    p, ft = P, P["floor_th"]
    drop = p["socket_drop"]
    if solid:
        shape = Part.makeCylinder(p["socket_od"] / 2.0, drop + 40.0, App.Vector(0, 0, -drop))
    else:
        sq = p["socket_sq"]
        shape = Part.makeBox(sq, sq, p["socket_depth"] + 0.01,
                             App.Vector(-sq / 2.0, -sq / 2.0, -drop - 0.01))
    r = math.hypot(x, y) or 1.0
    axis = App.Vector(-y / r, x / r, 0)          # tilt in the radial plane
    shape.rotate(App.Vector(0, 0, ft), axis, -splay)
    shape.translate(App.Vector(x, y, 0))
    if solid:                                    # embed into the floor, no poke-through
        keep = Part.makeBox(500, 500, 500, App.Vector(-250, -250, -500 + ft - 0.2))
        shape = shape.common(keep)
    return shape


# =====================================================================
# the belly
# =====================================================================
def build_belly():
    p, L = P, zlevels()
    ft = p["floor_th"]
    ox, oy = p["ir_center"]
    cx, cy = p["cam_pos"]

    # ---- shell: body + rebate step + tongue
    solid = outline_solid(0.0, 0.0, L["shoulder_z"])
    solid = solid.fuse(outline_solid(L["inset_rebate"], L["shoulder_z"], p["shoulder_drop"]))
    tongue = outline_solid(L["inset_tongue"], L["seat_z"], p["tongue_h"]).cut(
        outline_solid(L["inset_cavity"], L["seat_z"] - 1, p["tongue_h"] + 2))
    solid = solid.fuse(tongue)

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

    # ---- wing windows: LED zones only. Board outline shrunk by win_inset,
    #      minus the solid centre strip |x| < win_xmin.
    wings = ir_prism(-1.0, ft + 2.0, grow=-p["win_inset"])
    half = 400.0
    keep_r = Part.makeBox(half, 2 * half, ft + 4, App.Vector(ox + p["win_xmin"], -half, -1.5))
    keep_l = Part.makeBox(half, 2 * half, ft + 4, App.Vector(ox - p["win_xmin"] - half, -half, -1.5))
    solid = solid.cut(wings.common(keep_r)).cut(wings.common(keep_l))

    # ---- light-sensor window (sensor is an SMD on the board's bottom face)
    sx, sy = p["sensor_pos"]
    solid = solid.cut(Part.makeCylinder(p["sensor_hole_d"] / 2.0, ft + 2, App.Vector(ox + sx, oy + sy, -1)))

    # ---- camera lens hole (through the floor, inside the notch)
    solid = solid.cut(Part.makeCylinder(p["cam_lens_d"] / 2.0, ft + 2, App.Vector(cx, cy, -1)))

    # ---- underside rebate for the ONE clear acrylic sheet that seals it all
    solid = solid.cut(rrect(0.0, p["sheet_cy"], p["sheet_w"] + 1.0, p["sheet_l"] + 1.0,
                            p["sheet_r"], 0.0, p["sheet_th"]))

    # ---- weep notches drain the gutter outward
    ring = outline_solid(-1.0, L["seat_z"] - 1.5, 3.0).cut(outline_solid(L["inset_tongue"], L["seat_z"] - 2.0, 5.0))
    spokes = None
    for ang in p["weep_angles"]:
        bx = Part.makeBox(400, p["weep_w"], 5.0, App.Vector(-200, -p["weep_w"] / 2.0, L["seat_z"] - 2.0))
        bx.rotate(App.Vector(0, 0, 0), Z, ang)
        spokes = bx if spokes is None else spokes.fuse(bx)
    solid = solid.cut(ring.common(spokes))

    # ---- pilot holes: ears + gland bore
    for (ex, ey) in ears:
        solid = solid.cut(Part.makeCylinder(p["ear_pilot_d"] / 2.0, p["ear_h"], App.Vector(ex, ey, L["shoulder_z"] - p["ear_h"] + 0.5)))
    solid = solid.cut(Part.makeCylinder(p["gland_d"] / 2.0, 40.0, App.Vector(0, gy - 1, p["gland_z"]), App.Vector(0, 1, 0)))

    # ---- splayed leg bosses + their blind sockets (after the big cuts, so
    #      nothing slices them off into loose solids)
    for (x, y) in p["leg_pos"]:
        solid = solid.fuse(leg_socket(x, y, p["leg_splay"], solid=True))
    for (x, y) in p["leg_pos"]:
        solid = solid.cut(leg_socket(x, y, p["leg_splay"], solid=False))

    # ---- internal furniture (fused last: cuts can't orphan it) ----
    # IR board: two centreline screw standoffs ("smart elevation")
    for (mx, my) in p["ir_mounts"]:
        solid = solid.fuse(post(ox + mx, oy + my, ft, p["ir_post_h"], p["ir_post_d"],
                                p["ir_pilot_d"], p["ir_post_h"] - 1.0))
    # ... plus plain rest posts on the centreline (no screw)
    for (px, py) in p["ir_rests"]:
        solid = solid.fuse(Part.makeCylinder(p["ir_post_d"] / 2.0, p["ir_post_h"],
                                             App.Vector(ox + px, oy + py, ft)))
    # ... plus a perimeter ledge the board's outer edge lies on, gapped at the
    #     JST connectors whose pins poke through the bottom face
    ledge = ir_prism(ft, p["ir_post_h"], grow=p["ledge_out"]).cut(
        ir_prism(ft - 1, p["ir_post_h"] + 2, grow=-p["ledge_in"]))
    for (gx, gy2) in p["ledge_gaps"]:
        ledge = ledge.cut(Part.makeBox(p["ledge_gap_w"], p["ledge_gap_l"], p["ir_post_h"] + 4,
                                       App.Vector(ox + gx - p["ledge_gap_w"] / 2.0,
                                                  oy + gy2 - p["ledge_gap_l"] / 2.0, ft - 1)))
    ledge = ledge.common(outline_solid(L["inset_cavity"] + 0.3, ft - 0.5, p["ir_post_h"] + 1.5))
    solid = solid.fuse(ledge)
    # camera: baffle collar + V2/V3 standoffs
    collar = Part.makeCylinder(p["collar_od"] / 2.0, p["collar_h"], App.Vector(cx, cy, ft))
    collar = collar.cut(Part.makeCylinder(p["collar_id"] / 2.0, p["collar_h"] + 2, App.Vector(cx, cy, ft - 1)))
    solid = solid.fuse(collar)
    solid = solid.fuse(four_posts(cx, cy, p["cam_hole_dx"], p["cam_hole_dy"], ft,
                                  p["cam_post_h"], p["cam_post_d"], p["cam_pilot_d"]))
    # Pi Zero 2 W posts
    for (x, y) in p["pi_posts"]:
        solid = solid.fuse(post(x, y, ft, p["pi_post_h"], p["pi_post_d"],
                                p["pi_pilot_d"], min(8.0, p["pi_post_h"] - 1.0)))

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


def _block(h):
    p = P
    o = p["leg_out"]
    body = Part.makeBox(o, o, h, App.Vector(-o / 2.0, -o / 2.0, 0)).fuse(_peg(h))
    s = p["peg_sq"] + p["fit"]
    sock = Part.makeBox(s, s, p["peg_h"] + 0.6, App.Vector(-s / 2.0, -s / 2.0, -0.01))
    return body.cut(sock).removeSplitter()


def build_leg_segment():
    return _block(P["leg_seg_h"])


def build_leg_segment_half():
    return _block(P["leg_seg_h"] / 2.0)


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
    parts = [("belly", build_belly()),
             ("leg_segment", build_leg_segment()),
             ("leg_segment_half", build_leg_segment_half()),
             ("foot", build_foot())]
    for name, shape in parts:
        doc.addObject("Part::Feature", name).Shape = shape
        bb = shape.BoundBox
        single = shape.isValid() and len(shape.Solids) == 1
        print("CHECK %-16s %6.1f x %6.1f x %6.1f mm  printable=%s  volume=%.1f cm3"
              % (name, bb.XLength, bb.YLength, bb.ZLength, single, shape.Volume / 1000.0))
        if not single:
            print("CHECK    !! not a single closed solid (%d solids) - fix before printing" % len(shape.Solids))
        print("CHECK    -> " + export(shape, name, outdir))

    seg, foot_h = P["leg_seg_h"], P["foot_h"]
    splay = math.radians(P["leg_splay"])
    print("CHECK")
    print("CHECK leg stacks (4 legs, splayed %.0f deg):" % P["leg_splay"])
    for n in (2, 3, 4, 5, 6):
        along = n * seg + foot_h
        print("CHECK    %d blocks -> %5.1f mm leg = %5.1f mm clearance, feet %.0f mm wider per side"
              % (n, along, along * math.cos(splay), along * math.sin(splay)))

    doc.recompute()
    doc.saveAs(os.path.join(here, "ladybug.FCStd"))
    print("CHECK saved ladybug.FCStd")


main()
