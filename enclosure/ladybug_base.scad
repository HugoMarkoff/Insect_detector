// ================================================================
//  Insect Detector — ladybug enclosure   ·   PART 1: base + legs
//  Parametric. Units = millimetres. Open in OpenSCAD.
//  Pick what to export with `part` below, then Render (F6) → export STL.
//  github.com/HugoMarkoff/Insect_detector
// ================================================================
//
//  Concept: the ladybug's domed SHELL (printed later, part 2) hides the
//  Pi + trap board + battery. This BOTTOM TRAY is the belly: it carries the
//  three downward-looking windows (camera, IR, light sensor), mounts the
//  boards, and has six sockets for Lego-style stackable legs.
//
// ----------------------------------------------------------------

/* [What to render] */
part = "assembly";   // [assembly, base, leg_segment, foot]

/* [Body size] */
body_len   = 120;    // front→back length of the belly footprint
body_wid   = 96;     // left→right width
rim_h      = 16;     // height of the tray wall (the tall dome sits on top later)
floor_th   = 3.0;    // thickness of the belly floor
wall       = 2.6;    // side-wall thickness
head_bulge = 8;      // how far the little "head" pokes forward

/* [Downward optics — round windows in the floor, all looking straight down] */
// Measure these against your camera/IR/LDR and move them to suit.
cam_d  = 14;   cam_x  = 0;    cam_y  =  6;    // camera lens clearance
ir_d   = 9;    ir_x   = 0;    ir_y   = -20;   // IR illuminator window
ldr_d  = 4.5;  ldr_x  = 24;   ldr_y  =  6;    // photoresistor (light sensor) window

/* [Legs — Lego-style stack] */
socket_od    = 12;    // outer diameter of the socket boss under the belly
socket_sq    = 7.2;   // square hole across-flats (square = anti-rotation)
socket_depth = 11;    // how far the square hole reaches up into the boss
socket_drop  = 12;    // how far the boss hangs below the floor
leg_seg_h    = 12;    // HEIGHT ADDED BY ONE LEG SEGMENT  (stack more = taller)
leg_out      = 9;     // outer square size of a leg segment
peg_sq       = 6.9;   // square peg across-flats  (plugs into a socket)
peg_h        = 8;     // peg length
fit          = 0.20;  // clearance: smaller = tighter grip, bigger = looser

/* [Board standoffs — PLACEHOLDERS, set to your board's holes] */
post_xy   = [[34,28],[-34,28],[34,-30],[-34,-30]];
post_h    = 6;
post_d    = 6;
screw_d   = 2.2;      // M2.5 self-tap pilot

/* [Dome interface] */
ledge_w = 1.4;        // width of the shoulder the dome will rest on
ledge_h = 5;          // height of that shoulder

$fn = 96;

// --- six leg anchor points [x,y] (3 per side): front, mid, rear ---
lx_f = body_wid*0.32; ly_f =  body_len*0.27;
lx_m = body_wid*0.37; ly_m =  0;
lx_r = body_wid*0.28; ly_r = -body_len*0.31;
leg_pos = [[ lx_f, ly_f],[-lx_f, ly_f],
           [ lx_m, ly_m],[-lx_m, ly_m],
           [ lx_r, ly_r],[-lx_r, ly_r]];

// ---------------- 2D belly outline (ellipse + head bump) ----------------
module body_outline() {
  hull() {
    scale([body_wid/2, body_len/2]) circle(r=1);
    translate([0, body_len/2 - 2]) scale([body_wid*0.34, head_bulge]) circle(r=1);
  }
}

// ---------------- leg socket bosses (hang below the floor) ----------------
module leg_bosses(solid=true) {
  for (p = leg_pos) translate([p[0], p[1], 0])
    if (solid)
      translate([0,0,-socket_drop]) cylinder(d=socket_od, h=socket_drop + floor_th);
    else                                  // the square hole, opening downward
      translate([0,0,-socket_drop-0.01]) linear_extrude(socket_depth)
        square([socket_sq, socket_sq], center=true);
}

// ---------------- board standoffs ----------------
module pcb_posts() {
  for (p = post_xy) translate([p[0], p[1], floor_th])
    difference() {
      cylinder(d=post_d, h=post_h);
      translate([0,0,post_h-5]) cylinder(d=screw_d, h=6);
    }
}

// ---------------- the base tray ----------------
module base_tray() {
  difference() {
    union() {
      linear_extrude(floor_th + rim_h) body_outline();
      leg_bosses(solid=true);
    }
    // hollow the inside
    translate([0,0,floor_th]) linear_extrude(rim_h + 1) offset(delta=-wall) body_outline();
    // dome locating shoulder (thin the inner top edge so the shell drops in)
    translate([0,0, floor_th + rim_h - ledge_h]) linear_extrude(ledge_h + 1)
      difference() {
        offset(delta=-wall+0.2) body_outline();
        offset(delta=-wall-ledge_w) body_outline();
      }
    // the three downward windows
    for (o = [[cam_d,cam_x,cam_y],[ir_d,ir_x,ir_y],[ldr_d,ldr_x,ldr_y]])
      translate([o[1], o[2], -1]) cylinder(d=o[0], h=floor_th + 2);
    // square leg holes
    leg_bosses(solid=false);
  }
  pcb_posts();
}

// ---------------- Lego-style leg parts ----------------
module leg_peg()  { linear_extrude(peg_h, scale=0.82) square([peg_sq, peg_sq], center=true); }

module leg_segment() {                 // peg on top, socket in the bottom → stackable
  difference() {
    union() {
      linear_extrude(leg_seg_h) square([leg_out, leg_out], center=true);
      translate([0,0,leg_seg_h]) leg_peg();
    }
    translate([0,0,-0.01]) linear_extrude(peg_h + 0.6)
      square([peg_sq + fit, peg_sq + fit], center=true);   // bottom socket
  }
}

module foot() {                        // peg on top, flat grippy pad on the bottom
  foot_h = 6;
  union() {
    cylinder(d1=leg_out*1.35, d2=leg_out, h=foot_h);
    translate([0,0,foot_h]) leg_peg();
  }
}

// ---------------- one assembled leg hanging under a socket ----------------
//  segments_n = how many 12 mm segments between belly and foot.
module leg_stack(segments_n=2) {
  // peg tip of the topmost segment reaches up into the belly socket
  top = -socket_drop + socket_depth - peg_h;
  for (i=[0:segments_n-1])
    translate([0,0, top - leg_seg_h - i*leg_seg_h]) leg_segment();
  translate([0,0, top - leg_seg_h - segments_n*leg_seg_h - 6]) foot();
}

// ---------------- render selector ----------------
if (part == "base")        base_tray();
else if (part == "leg_segment") leg_segment();
else if (part == "foot")   foot();
else {                                  // "assembly" preview
  color("#c0392b") base_tray();
  color("#2c3e50") for (p = leg_pos) translate([p[0], p[1], 0]) leg_stack(2);
}
