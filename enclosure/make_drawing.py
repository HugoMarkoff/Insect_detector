"""Dimensioned TOP + BOTTOM views of the belly.

Reads the PARAMS block straight out of ladybug_belly.py (via ast, one source
of truth) and draws a technical view with matplotlib. Plain Python - no
FreeCAD needed.

    python make_drawing.py     ->  drawing.png
"""
import ast
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Circle, Rectangle, FancyBboxPatch, Polygon as MplPoly

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- read PARAMS out of the CAD script ------------------------------------
src = open(os.path.join(HERE, "ladybug_belly.py"), encoding="utf-8").read()
P = None
for node in ast.walk(ast.parse(src)):
    if isinstance(node, ast.Assign):
        t = node.targets[0]
        if isinstance(t, ast.Name) and t.id == "P":
            P = ast.literal_eval(node.value)
if P is None:
    raise SystemExit("PARAMS block not found")


def offset_poly(pts, d):
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    clean = [pts[0]]
    for pt in pts[1:]:
        if math.hypot(pt[0] - clean[-1][0], pt[1] - clean[-1][1]) > 0.35:
            clean.append(pt)
    if math.hypot(clean[0][0] - clean[-1][0], clean[0][1] - clean[-1][1]) <= 0.35:
        clean.pop()
    pts = clean
    n = len(pts)
    out = []
    for i in range(n):
        x0, y0 = pts[i - 1]; x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        l0 = math.hypot(x1 - x0, y1 - y0); l1 = math.hypot(x2 - x1, y2 - y1)
        d0 = ((x1 - x0) / l0, (y1 - y0) / l0); d1 = ((x2 - x1) / l1, (y2 - y1) / l1)
        n0 = (d0[1], -d0[0]); n1 = (d1[1], -d1[0])
        axp, ayp = x1 + d * n0[0], y1 + d * n0[1]
        bxp, byp = x1 + d * n1[0], y1 + d * n1[1]
        den = d0[0] * d1[1] - d0[1] * d1[0]
        if abs(den) < 1e-9:
            out.append(((axp + bxp) / 2, (ayp + byp) / 2))
        else:
            t = ((bxp - axp) * d1[1] - (byp - ayp) * d1[0]) / den
            out.append((axp + t * d0[0], ayp + t * d0[1]))
    return out


def clip_halfplane(pts, sgn, xmin):
    """Sutherland-Hodgman: keep the part of polygon with sgn*x >= xmin."""
    def inside(p):
        return sgn * p[0] >= xmin
    def isect(a, b):
        t = (xmin - sgn * a[0]) / (sgn * b[0] - sgn * a[0])
        return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if inside(b):
            if not inside(a):
                out.append(isect(a, b))
            out.append(b)
        elif inside(a):
            out.append(isect(a, b))
    return out


INK = "#22232b"; DIM = "#c0392b"; HW = "#2471a3"; SOFT = "#8a8d98"
A, B = P["body_wid"] / 2.0, P["body_len"] / 2.0
HEADY = B - 6.0
ins_reb = P["skirt_th"] + P["skirt_gap"]
ins_ton = ins_reb + P["gutter_w"]
ins_cav = ins_ton + P["tongue_w"]
ox, oy = P["ir_center"]
board = [(ox + x, oy + y) for x, y in P["ir_outline"]]
win_r = clip_halfplane(offset_poly(board, -P["win_inset"]), 1, ox + P["win_xmin"])
win_l = clip_halfplane(offset_poly(board, -P["win_inset"]), -1, -(ox - P["win_xmin"]))


def dim_h(ax, x1, x2, y, label, color=DIM):
    ax.annotate("", xy=(x1, y), xytext=(x2, y),
                arrowprops=dict(arrowstyle="<->", color=color, lw=1.0))
    ax.text((x1 + x2) / 2, y + 1.5, label, ha="center", va="bottom", color=color, fontsize=8.5)


def dim_v(ax, y1, y2, x, label, color=DIM, rot=90):
    ax.annotate("", xy=(x, y1), xytext=(x, y2),
                arrowprops=dict(arrowstyle="<->", color=color, lw=1.0))
    ax.text(x + 1.5, (y1 + y2) / 2, label, ha="left", va="center", color=color,
            fontsize=8.5, rotation=rot)


def body_patches(ax, fill="#f0efe9"):
    ax.add_patch(Ellipse((0, 0), 2 * A, 2 * B, fc=fill, ec=INK, lw=1.4, zorder=1))
    ax.add_patch(Ellipse((0, HEADY), 2 * P["head_rx"], 2 * P["head_ry"], fc=fill, ec=INK, lw=1.4, zorder=1))


def common_marks(ax):
    for ang in P["ear_angles"]:
        t = math.radians(ang)
        ax.add_patch(Circle((A * math.cos(t), B * math.sin(t)), P["ear_d"] / 2, fc="#fff", ec=INK, lw=0.9, zorder=6))
        ax.add_patch(Circle((A * math.cos(t), B * math.sin(t)), P["ear_pilot_d"] / 2, fc=INK, ec="none", zorder=7))
    for ang in P["weep_angles"]:
        t = math.radians(ang)
        r0, r1 = 0.995, 1.06
        ax.plot([A * r0 * math.cos(t) * (1 - ins_ton / A), A * r1 * math.cos(t)],
                [B * r0 * math.sin(t) * (1 - ins_ton / B), B * r1 * math.sin(t)],
                color=SOFT, lw=2.4, alpha=0.8, zorder=5)
    ax.add_patch(Rectangle((-P["gland_boss_d"] / 2, -B - 12), P["gland_boss_d"], 12, fc="#fff", ec=INK, lw=0.9, zorder=6))
    ax.add_patch(Circle((0, -B - 6), P["gland_d"] / 2, fc="#fff", ec=SOFT, lw=0.8, zorder=7))
    ax.text(0, -B - 17, "cable gland", ha="center", fontsize=7.5, color=SOFT)


# ===========================================================================
fig, axes = plt.subplots(1, 2, figsize=(17.5, 10.5), facecolor="white")
for ax in axes:
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_xlim(-95, 95); ax.set_ylim(-118, 112)

# ------------------------------------------------ TOP (inside) -------------
ax = axes[0]
ax.set_title("TOP VIEW - inside the tray  (head up, +Y)", fontsize=12, color=INK, pad=8)
body_patches(ax)
# cavity + tongue rings
for inset, ls, lw in [(ins_reb, ":", 0.8), (ins_ton, "-", 0.8), (ins_cav, "-", 1.1)]:
    ax.add_patch(Ellipse((0, 0), 2 * (A - inset), 2 * (B - inset), fc="#faf9f5" if inset == ins_cav else "none",
                         ec=SOFT, ls=ls, lw=lw, zorder=2))
# windows (through-cuts)
for w in (win_r, win_l):
    ax.add_patch(MplPoly(w, closed=True, fc="#fbe3e0", ec=DIM, lw=1.2, zorder=3))
# IR board outline
ax.add_patch(MplPoly(board, closed=True, fc="none", ec=HW, lw=1.5, ls="--", zorder=4))
# sensor + camera
sx, sy = P["sensor_pos"]
ax.add_patch(Rectangle((ox + sx - P["sensor_w"] / 2, oy + sy - P["sensor_l"] / 2), P["sensor_w"], P["sensor_l"],
                       fc="#fbe3e0", ec=DIM, lw=1.1, zorder=5))
ax.text(ox + sx + 6, oy + sy - 1, "VT90N1 window\n%.1f x %.1f" % (P["sensor_w"], P["sensor_l"]),
        fontsize=7.5, color=DIM)
cx, cy = P["cam_pos"]
pw, pl = P["cam_board_w"] + P["cam_fit"], P["cam_board_l"] + P["cam_fit"]
pcy = cy + P["cam_board_off"]
ax.add_patch(Rectangle((cx - pw / 2, pcy - pl / 2), pw, pl, fc="#eef4ea", ec=HW, lw=1.0, zorder=4))
ax.add_patch(Rectangle((cx - P["cam_cut_sq"] / 2, cy - P["cam_cut_sq"] / 2), P["cam_cut_sq"], P["cam_cut_sq"],
                       fc="#fbe3e0", ec=DIM, lw=1.2, zorder=5))
ax.add_patch(Rectangle((cx - P["ribbon_w"] / 2, cy - P["cam_cut_sq"] / 2 - P["ribbon_len"]),
                       P["ribbon_w"], P["ribbon_len"], fc="#fbe3e0", ec=DIM, lw=1.0, zorder=5))
ax.add_patch(Rectangle((cx - P["ffc_w"] / 2, pcy - pl / 2 - P["ffc_len"]), P["ffc_w"], P["ffc_len"],
                       fc="#f4ede2", ec="#e67e22", lw=1.0, zorder=4))
for sxs in (-1, 1):
    for sys_ in (-1, 1):
        ax.add_patch(Circle((cx + sxs * P["cam_hole_dx"] / 2, cy + sys_ * P["cam_hole_dy"] / 2),
                            P["cam_pilot_d"] / 2 + 0.6, fc="#fff", ec=HW, lw=1.0, zorder=5))
ax.text(cx + 15, cy + 6, "cam V2/V3 FLUSH in %.1f pocket\nhousing out through %.1f sq\nFFC trench below" % (
        P["cam_pocket_d"], P["cam_cut_sq"]), fontsize=7.5, color=HW)
# IR standoffs + rest pads
for (mx, my) in P["ir_mounts"]:
    ax.add_patch(Circle((ox + mx, oy + my), 3.0, fc="#fff", ec=HW, lw=1.2, zorder=5))
    ax.add_patch(Circle((ox + mx, oy + my), P["ir_pilot_d"] / 2, fc=HW, ec="none", zorder=6))
for (gx, gy2) in P["pin_pockets"]:
    ax.add_patch(Rectangle((ox + gx - P["pocket_w"] / 2, oy + gy2 - P["pocket_l"] / 2),
                           P["pocket_w"], P["pocket_l"], fc="#fbe3e0", ec="#e67e22", lw=1.2, zorder=5))
ax.annotate("M3 screws through the board's real holes\ninto floor pilots (0,-6.5) (0,-29.1)", xy=(ox, oy - 29.1), xytext=(-60, -38),
            fontsize=7.5, color=HW, arrowprops=dict(arrowstyle="-", color=HW, lw=0.7))
ax.annotate("board lies FLUSH on the floor\n(orange = JST pin through-pockets)", xy=(ox - 30, oy - 44), xytext=(-88, 44),
            fontsize=7.5, color="#e67e22", arrowprops=dict(arrowstyle="-", color="#e67e22", lw=0.7))
# Pi Zero
pxs = [q[0] for q in P["main_posts"]]; pys = [q[1] for q in P["main_posts"]]
pcx = sum(pxs) / 4.0
rows = sorted(set(pys))
byc = (rows[0] + rows[-1]) / 2.0 + 8.37        # the 58 x 23 pattern sits off-centre
ax.add_patch(Rectangle((pcx - 20, byc - 41), 40, 82, fc="none", ec="#1e8449", lw=1.0, ls="--", zorder=5))
for (x, y) in P["main_posts"]:
    ax.add_patch(Circle((x, y), P["main_post_d"] / 2, fc="#fff", ec="#1e8449", lw=1.0, zorder=5))
ax.text(pcx - 62, -74, "MAIN trap PCB 82 x 40 (exact from PcbDoc)\non %.0f mm posts, holes 58 x 23\nPi Zero stacks on top" % P["main_post_h"],
        fontsize=7.5, color="#1e8449")
# legs
for (x, y) in P["leg_pos"]:
    ax.add_patch(Circle((x, y), P["socket_od"] / 2, fc="#e8e6dc", ec=INK, lw=1.1, zorder=5))
    ax.add_patch(Rectangle((x - P["socket_sq"] / 2, y - P["socket_sq"] / 2), P["socket_sq"], P["socket_sq"],
                           fc="#fff", ec=INK, lw=0.9, zorder=6))
    r = math.hypot(x, y); ux, uy = x / r, y / r
    ax.annotate("", xy=(x + 14 * ux, y + 14 * uy), xytext=(x, y),
                arrowprops=dict(arrowstyle="->", color=INK, lw=0.9))
common_marks(ax)
# dimensions
dim_h(ax, -A, A, -B - 24, "%.0f" % P["body_wid"])
dim_v(ax, -B, HEADY + P["head_ry"], -A - 12, "%.0f  (body %.0f)" % (B + HEADY + P["head_ry"], P["body_len"]))
bxs = [q2[0] for q2 in board]; bys = [q2[1] for q2 in board]
dim_h(ax, min(bxs), max(bxs), max(bys) + 4, "IR board %.1f" % (max(bxs) - min(bxs)), HW)
dim_v(ax, min(bys), max(bys), min(bxs) - 8, "%.1f" % (max(bys) - min(bys)), HW)
dim_h(ax, ox - 18.6, ox + 18.6, oy + 12.5, "slot 37.2", HW)
ax.text(0, 104, "camera lens at Y=+%.0f inside the board slot - geometry extracted from IRarray-v6.1.pcbdoc" % cy, fontsize=8, color=INK, ha="center")

# ------------------------------------------------ BOTTOM (underside) -------
ax = axes[1]
ax.set_title("BOTTOM VIEW - underside  (projected through, same orientation)", fontsize=12, color=INK, pad=8)
body_patches(ax)
# sheet rebate
for w in (win_r, win_l):
    ax.add_patch(MplPoly(w, closed=True, fc="#fbe3e0", ec=DIM, lw=1.2, zorder=3))
ax.add_patch(MplPoly(board, closed=True, fc="none", ec=HW, lw=1.0, ls="--", zorder=4))
ax.add_patch(Rectangle((ox + sx - P["sensor_w"] / 2, oy + sy - P["sensor_l"] / 2), P["sensor_w"], P["sensor_l"],
                       fc="#fbe3e0", ec=DIM, lw=1.1, zorder=5))
ax.add_patch(Rectangle((cx - P["cam_cut_sq"] / 2, cy - P["cam_cut_sq"] / 2), P["cam_cut_sq"], P["cam_cut_sq"],
                       fc="#fbe3e0", ec=DIM, lw=1.2, zorder=5))
ax.add_patch(Rectangle((cx - P["ribbon_w"] / 2, cy - P["cam_cut_sq"] / 2 - P["ribbon_len"]),
                       P["ribbon_w"], P["ribbon_len"], fc="#fbe3e0", ec=DIM, lw=1.0, zorder=5))
ax.text(cx + 8, cy - 2, "housing cutout %.1f sq\n+ ribbon slot" % P["cam_cut_sq"], fontsize=7.5, color=DIM)
# legs w/ splay arrows
for (x, y) in P["leg_pos"]:
    ax.add_patch(Circle((x, y), P["socket_od"] / 2, fc="#e8e6dc", ec=INK, lw=1.1, zorder=5))
    ax.add_patch(Rectangle((x - P["socket_sq"] / 2, y - P["socket_sq"] / 2), P["socket_sq"], P["socket_sq"],
                           fc="#fff", ec=INK, lw=0.9, zorder=6))
    r = math.hypot(x, y); ux, uy = x / r, y / r
    ax.annotate("", xy=(x + 16 * ux, y + 16 * uy), xytext=(x, y),
                arrowprops=dict(arrowstyle="->", color=DIM, lw=1.2))
ax.text(0, -108, "arrows = leg splay direction, %.0f° outward" % P["leg_splay"], fontsize=8, color=DIM, ha="center")
common_marks(ax)
# dimensions
dim_h(ax, -P["win_xmin"], P["win_xmin"], oy - 52, "solid strip %.0f" % (2 * P["win_xmin"]), DIM)
dim_h(ax, P["leg_pos"][1][0], P["leg_pos"][0][0], P["leg_pos"][0][1] + 12, "front %.0f" % (2 * abs(P["leg_pos"][0][0])))
dim_h(ax, P["leg_pos"][3][0], P["leg_pos"][2][0], P["leg_pos"][2][1] + 14, "mid %.0f" % (2 * abs(P["leg_pos"][2][0])))
dim_h(ax, P["leg_pos"][5][0], P["leg_pos"][4][0], P["leg_pos"][4][1] - 12, "rear %.0f" % (2 * abs(P["leg_pos"][4][0])))
dim_v(ax, P["leg_pos"][4][1], P["leg_pos"][0][1], A + 10, "leg rows Y %+.0f / 0 / %+.0f" % (P["leg_pos"][0][1], P["leg_pos"][4][1]))

# ------------------------------------------------ footer spec text ---------
seg, fh, sp = P["leg_seg_h"], P["foot_h"], math.radians(P["leg_splay"])
rows = ["%d blocks + foot = %3.0f mm leg  (%3.0f mm clearance, feet +%2.0f mm/side)"
        % (n, n * seg + fh, (n * seg + fh) * math.cos(sp), (n * seg + fh) * math.sin(sp)) for n in (2, 3, 4, 5)]
fig.text(0.5, 0.055,
         "ELEVATIONS (Z from floor top):  every opening OPEN below, filled by its part - IR board flush (LEDs/pins in windows + pockets), camera flush in its pocket, housing out the bottom   -   main trap PCB on 10 mm posts, Pi Zero stacked on it\n"
         "LEG STACKS (25 mm Lego blocks, 6 legs @ 14 deg):   " + "   |   ".join(rows[:2]) + "\n"
         + " " * 56 + rows[2] + "   |   " + rows[3] + "      target: 5 blocks = 12.5 cm legs\n"
         "GEOMETRY SOURCE:  outline, mount holes, sensor + connector positions auto-extracted from IRarray-v6.1.pcbdoc",
         ha="center", va="bottom", fontsize=9, color=INK, family="monospace")

plt.tight_layout(rect=[0, 0.10, 1, 0.97])
out = os.path.join(HERE, "drawing.png")
plt.savefig(out, dpi=115, facecolor="white")
print("saved", out)
