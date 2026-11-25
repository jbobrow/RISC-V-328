# Supply straps and analog lines of the analog macro, drawn into the layout after the power grid and before
# placement.
#
#   openroad -python -exit scripts/analog_straps.py <in.odb> <out.odb>      (with the PDK's tech in the odb)
#
# AVCC: the macro's avdd pin (Metal4, 8 um wide, on its bottom edge) is joined to the AVCC pad
#   (apad_avcc, gf180mcu_fd_io__asig_5p0, pin ASIG5V: eight Metal2 fingers on the pad's core side) by a
#   strap of its own: AVCC is a supply separate from the core's VDD, and a router's 0.5 um wire over about
#   1.6 mm would drop half a volt at the macro's 2 mA. Each finger is carried out of the pad on Metal2
#   (inside the pad Metal3 is obstructed) to a Metal3 bar with a Via2 on each; a short Metal3 piece runs
#   west under the core ring, then WIDE um on the layers signal routing uses least, each in a gap between
#   the power grid's stripes: Metal4 north in the east column, Metal5 west under the macro, Metal4 north to
#   the pin. (A first version on Metal3 throughout congested the corner under the macro: run ana4.) The
#   net (A_AVCC) is made special so that the routers leave it alone.
# VSS: the macro's vss pin (Metal4, 8 um) is carried down on Metal4 and joined with Via4 to every VSS
#   stripe of the core grid (Metal5, horizontal) that it crosses within VSS_DROP um.
# Analog lines: ADC0..ADC7, AIN0, AIN1, AREF, XTAL1, XTAL2, from the macro's pins to the analog pads, on
#   Metal4 and Metal5 in planned corridors (see the section below). The routers will not route them.
#   Lengths go to <out.odb>.analog.json.
# Every shape is checked against the existing special wiring on its layer before it is drawn; the script
# stops rather than draw a short.
import json
import sys

import odb
from openroad import Design, Tech

WIDE = 10.0          # um, AVCC strap
VSS_DROP = 170.0     # um, how far the VSS strap runs down from the macro

src, dst = sys.argv[-2], sys.argv[-1]
tech = Tech()
design = Design(tech)
design.readDb(src)
block = design.getBlock()
dbu = block.getDbUnitsPerMicron()
U = lambda v: int(round(v * dbu))
T = lambda v: v / dbu
db_tech = block.getTech()
L = {n: db_tech.findLayer(n) for n in ("Metal2", "Via2", "Metal3", "Via3", "Metal4", "Via4", "Metal5")}


def pin_boxes(inst, pin, layer=None):
    """Absolute boxes of a pin of an instance."""
    out = []
    t = inst.getTransform()
    for mp in inst.getMaster().findMTerm(pin).getMPins():
        for g in mp.getGeometry():
            if layer and g.getTechLayer().getName() != layer:
                continue
            a, b = odb.Point(g.xMin(), g.yMin()), odb.Point(g.xMax(), g.yMax())
            t.apply(a); t.apply(b)
            r = odb.Rect(min(a.x(), b.x()), min(a.y(), b.y()), max(a.x(), b.x()), max(a.y(), b.y()))
            out.append((g.getTechLayer().getName(), r))
    return out


def special_boxes(layer):
    """Shapes of special wiring on a layer, vias included: a via counts on its bottom and top layer, as its
    outline grown by 0.3 um. (The power grid's via stacks from the Metal1 rails up to the Metal4 stripes
    have Metal2 and Metal3 pieces that odb does not list as shapes; a first version of this script missed
    them, and the AVCC strap's Metal3 run shorted VDD to VSS through two stacks: found by LVS, run tgm6lvs.)"""
    out = []
    g = U(0.3)
    for net in block.getNets():
        for sw in net.getSWires():
            for b in sw.getWires():
                if b.isVia():
                    v = b.getTechVia() or b.getBlockVia()
                    if v is None:
                        continue
                    names = {v.getBottomLayer().getName(), v.getTopLayer().getName()}
                    if layer in names:
                        e = 0 if v.getName().startswith("rv328_") else g   # this script's own vias are exact
                        out.append((net.getName(), odb.Rect(b.xMin() - e, b.yMin() - e, b.xMax() + e, b.yMax() + e)))
                elif b.getTechLayer() and b.getTechLayer().getName() == layer:
                    out.append((net.getName(), odb.Rect(b.xMin(), b.yMin(), b.xMax(), b.yMax())))
    return out


def overlaps(a, b):
    return a.xMin() < b.xMax() and b.xMin() < a.xMax() and a.yMin() < b.yMax() and b.yMin() < a.yMax()


def check_free(layer, r, own):
    for n, b in special_boxes(layer):
        if n != own and overlaps(r, b):
            raise SystemExit("%s box %s would touch %s on %s" % (own, [T(v) for v in (r.xMin(), r.yMin(), r.xMax(), r.yMax())], n, layer))


def via(name, lower, cut, upper, w, h, cut_size, cut_space, enc):
    """A block via of the given outline: an array of cuts with the given enclosure."""
    v = block.findVia(name)
    if v:
        return v
    v = odb.dbVia.create(block, name)
    p = odb.dbViaParams()
    p.setBottomLayer(L[lower]); p.setCutLayer(L[cut]); p.setTopLayer(L[upper])
    p.setXCutSize(U(cut_size)); p.setYCutSize(U(cut_size))
    p.setXCutSpacing(U(cut_space)); p.setYCutSpacing(U(cut_space))
    nx = max(1, int((w - 2 * enc + cut_space) // (cut_size + cut_space)))
    ny = max(1, int((h - 2 * enc + cut_space) // (cut_size + cut_space)))
    p.setNumCutCols(nx); p.setNumCutRows(ny)
    ex = (w - nx * cut_size - (nx - 1) * cut_space) / 2
    ey = (h - ny * cut_size - (ny - 1) * cut_space) / 2
    for f in (p.setXBottomEnclosure, p.setXTopEnclosure):
        f(U(ex))
    for f in (p.setYBottomEnclosure, p.setYTopEnclosure):
        f(U(ey))
    v.setViaParams(p)
    # Name the generate rule too, so the DEF carries the via as "+ VIARULE ... + ROWCOL" like the power grid's
    # own vias. Written out as a list of "+ RECT"s instead, Magic's DEF reader adds a stray Metal4-Via4-Metal5
    # stack at the via's centre, and one such stack under a Metal5 stripe shorted XTAL2 to VSS (run sgn).
    v.setViaGenerateRule(db_tech.findViaGenerateRule(cut + "_GEN_HH"))
    return v


def wire(sw, layer, x1, y1, x2, y2, own):
    r = odb.Rect(U(min(x1, x2)), U(min(y1, y2)), U(max(x1, x2)), U(max(y1, y2)))
    check_free(layer, r, own)
    odb.dbSBox_create(sw, L[layer], r.xMin(), r.yMin(), r.xMax(), r.yMax(), "STRIPE")


def put_via(sw, v, x, y):
    odb.dbSBox_create(sw, v, U(x), U(y), "STRIPE")


ana = block.findInst("u_analog")
pad = block.findInst("apad_avcc")
assert ana and pad, "u_analog or apad_avcc missing"
mb = ana.getBBox()
mx0, my0, mx1, my1 = T(mb.xMin()), T(mb.yMin()), T(mb.xMax()), T(mb.yMax())

# ---------------- AVCC ----------------
net = ana.findITerm("avdd").getNet()
assert net and net.getName() == "A_AVCC", net and net.getName()
(_, pr), = pin_boxes(ana, "avdd", "Metal4")
px = T(pr.xMin() + pr.xMax()) / 2
pw = T(pr.xMax() - pr.xMin())
fingers = [r for _, r in pin_boxes(pad, "ASIG5V", "Metal2")]
fx0 = T(min(r.xMin() for r in fingers)); fx1 = T(max(r.xMax() for r in fingers))
fy0 = T(min(r.yMin() for r in fingers)); fy1 = T(max(r.yMax() for r in fingers))
# the pad is on the east side: its fingers are horizontal and end at the pad's core side (smallest x);
# inside the pad Metal3 is obstructed, so the strap starts just outside it
assert fx1 - fx0 > fy1 - fy0, "expected the AVCC pad on the east side"
edge = fx0
net.setSpecial()
if net.getWire():
    odb.dbWire.destroy(net.getWire())
sw = odb.dbSWire.create(net, "ROUTED")
fh = min(T(r.yMax() - r.yMin()) for r in fingers)
v2 = via("rv328_avcc_via2", "Metal2", "Via2", "Metal3", WIDE - 0.4, fh - 0.4, 0.26, 0.36, 0.2)
# landing: each finger carried 16 um out of the pad on Metal2, a vertical Metal3 bar across them
lx0, lx1 = edge - 16.0, edge - 16.0 + WIDE
for r in fingers:
    wire(sw, "Metal2", lx0, T(r.yMin()), edge + 1.0, T(r.yMax()), net.getName())
    put_via(sw, v2, (lx0 + lx1) / 2, T(r.yMin() + r.yMax()) / 2)
wire(sw, "Metal3", lx0, fy0, lx1, fy1, net.getName())
# run: a short Metal3 piece west under the core ring, then the upper layers, which signal routing uses
# least (Metal4 vertical and Metal5 horizontal, each in a gap between the power grid's stripes): Metal4
# north in the east column, Metal5 west under the macro, Metal4 north to the pin
yc = (fy0 + fy1) / 2
def free_x(x_hi, x_lo, y0, y1, w):
    x = x_hi
    while x > x_lo:
        r = odb.Rect(U(x - w / 2), U(y0), U(x + w / 2), U(y1))
        if not any(n != net.getName() and overlaps(r, b) for n, b in special_boxes("Metal4")):
            return x
        x -= 1.0
    raise SystemExit("no free Metal4 column for AVCC")
def free_y(y_hi, y_lo, x0, x1, w):
    y = y_hi
    while y > y_lo:
        r = odb.Rect(U(x0), U(y - w / 2), U(x1), U(y + w / 2))
        if not any(n != net.getName() and overlaps(r, b) for n, b in special_boxes("Metal5")):
            return y
        y -= 1.0
    raise SystemExit("no free Metal5 row for AVCC")
yh = free_y(my0 - 120.0, my0 - 200.0, px - pw / 2 - 1, mx1, WIDE + 2)
xv = free_x(mx1 - 10.0, mx1 - 120.0, fy0 - 2.0, yh + WIDE / 2, WIDE + 2)
v34 = via("rv328_avcc_via3w", "Metal3", "Via3", "Metal4", WIDE - 0.4, WIDE - 0.4, 0.26, 0.36, 0.2)
v45 = via("rv328_avcc_via4w", "Metal4", "Via4", "Metal5", WIDE - 0.4, WIDE - 0.4, 0.26, 0.36, 0.2)
v45p = via("rv328_avcc_via4p", "Metal4", "Via4", "Metal5", pw - 0.4, WIDE - 0.4, 0.26, 0.36, 0.2)
# The Metal3 run crosses the core's Metal4 stripes near the east edge, where via stacks come up from every
# Metal1 rail (5.04 um apart): a 10 um line cannot pass them. It goes as up to three 3 um lines in the gaps.
RUN_W = 3.0
m3 = special_boxes("Metal3")
def run_free(y):
    q = odb.Rect(U(xv - WIDE / 2 - 0.3), U(y - RUN_W / 2 - 0.3), U(lx1 + 0.3), U(y + RUN_W / 2 + 0.3))
    return not any(n != net.getName() and overlaps(q, b) for n, b in m3)
runs = []
y = fy0 + RUN_W / 2
while y <= fy1 - RUN_W / 2 and len(runs) < 3:
    if run_free(y) and all(abs(y - r) >= RUN_W + 0.6 for r in runs):
        runs.append(y)
        y += RUN_W + 0.6
    else:
        y += 0.1
if not runs:
    raise SystemExit("no free Metal3 track for the AVCC run")
v34r = via("rv328_avcc_via3r", "Metal3", "Via3", "Metal4", min(RUN_W, WIDE) - 0.2, RUN_W - 0.2, 0.26, 0.36, 0.2)
for y in runs:
    wire(sw, "Metal3", xv - WIDE / 2, y - RUN_W / 2, lx1, y + RUN_W / 2, net.getName())
    put_via(sw, v34r, xv, y)
yc = min(runs)
wire(sw, "Metal4", xv - WIDE / 2, yc - RUN_W / 2, xv + WIDE / 2, yh + WIDE / 2, net.getName())
put_via(sw, v45, xv, yh)
wire(sw, "Metal5", px - pw / 2, yh - WIDE / 2, xv + WIDE / 2, yh + WIDE / 2, net.getName())
put_via(sw, v45p, px, yh)
wire(sw, "Metal4", px - pw / 2, yh - WIDE / 2, px + pw / 2, my0 + T(pr.yMax() - pr.yMin()), net.getName())
length = (lx1 - xv) + (yh - yc) + (xv - px) + (my0 - yh)
print("AVCC Metal3 run: %d lines of %.1f um at y %s" % (len(runs), RUN_W, ", ".join("%.2f" % r for r in runs)))
print("AVCC strap: %.0f um (Metal3 %.0f, Metal4 %.0f, Metal5 %.0f), about %.1f ohm at 90 mohm/sq" % (
    length, lx1 - xv, (yh - yc) + (my0 - yh), xv - px, 0.09 * ((lx1 - xv + yh - yc + xv - px) / WIDE + (my0 - yh) / pw)))

# ---------------- VSS ----------------
vnet = block.findNet("VSS")
ana.findITerm("vss").connect(vnet)
(_, gr), = pin_boxes(ana, "vss", "Metal4")
gx0, gx1 = T(gr.xMin()), T(gr.xMax())
ybot = my0 - VSS_DROP
stripes = [r for n, r in special_boxes("Metal5") if n == "VSS"
           and T(r.xMin()) <= gx0 and T(r.xMax()) >= gx1 and ybot <= T(r.yMin()) and T(r.yMax()) <= my0]
assert stripes, "no VSS stripe on Metal5 within %g um under the macro's vss pin" % VSS_DROP
vsw = odb.dbSWire.create(vnet, "ROUTED")
low = min(T(r.yMin()) for r in stripes)
wire(vsw, "Metal4", gx0, low, gx1, my0 + T(gr.yMax() - gr.yMin()), "VSS")
# Where the strap lies over a VSS stripe of the power grid's own Metal4, the grid already has a Via4 array at
# the crossing; a second array there puts cuts 0.05 um apart (foundry rule V4.2a, 784 errors on run sgnv).
grid_v4 = []
for sw in vnet.getSWires():
    for b in sw.getWires():
        v = b.getTechVia() or b.getBlockVia() if b.isVia() else None
        if v and {v.getBottomLayer().getName(), v.getTopLayer().getName()} == {"Metal4", "Metal5"}:
            grid_v4.append(odb.Rect(b.xMin(), b.yMin(), b.xMax(), b.yMax()))
for r in stripes:
    h = T(r.yMax() - r.yMin())
    cx, cy = (gx0 + gx1) / 2, T(r.yMin() + r.yMax()) / 2
    if any(g.xMin() < U(gx1) and U(gx0) < g.xMax() and g.yMin() < r.yMax() and r.yMin() < g.yMax() for g in grid_v4):
        continue
    v4 = via("rv328_vss_via4_%d" % U(h), "Metal4", "Via4", "Metal5", gx1 - gx0 - 0.4, h - 0.4, 0.26, 0.36, 0.2)
    put_via(vsw, v4, cx, cy)
print("VSS strap: %.0f um of Metal4 from the macro's vss pin, joined to %d VSS stripes" % (my0 - low, len(stripes)))

# ---------------- analog signal nets ----------------
# The pad ring step leaves every net of an analog pad (gf180mcu_fd_io__asig_5p0) as a special net without
# wires, and the routers do not route them: made ordinary nets they are skipped by global routing without a
# message (runs anb3, anc2) and crash the detailed router's pin access on the pad pin (anb3). So they are
# drawn here, like AVCC: each pad's fingers carried out of the pad to a Metal3 landing bar, and a path of
# Metal4 (vertical) and Metal5 (horizontal) lines in planned corridors, every line in a track of its own
# (TRACK um apart), each segment checked against all special wiring on its layer before it is drawn:
#   ADC0..ADC5 (north pads)  down from the macro, east under it, north in the strip east of it, along the
#                            north strip to the pad, up to the landing
#   ADC6, ADC7, AREF (east)  down, east under the macro, north or south in the strip to the pad's height,
#                            Metal3 under the core ring to the landing
#   AIN0, AIN1 (south pads)  down, east under the macro, south in the east column, west along the south
#                            strip, down to the landing
#   XTAL1, XTAL2 (west)      up from the macro's top, west above it, along the west strip to the pad's
#                            height, Metal3 to the landing
# The nets stay special (the routers leave them alone) and keep their pad and macro connections.
core = block.getCoreArea()
cx0, cy0, cx1, cy1 = T(core.xMin()), T(core.yMin()), T(core.xMax()), T(core.yMax())
ccx, ccy = (cx0 + cx1) / 2, (cy0 + cy1) / 2
LAND_W, TRACK, AW = 8.0, 4.0, 1.0
mac = odb.Rect(mb.xMin(), mb.yMin(), mb.xMax(), mb.yMax())

SB = {}
def is_free(layer, x0, y0, x1, y1, own, clear=1.5, macro_ok=False):
    q = odb.Rect(U(min(x0, x1) - clear), U(min(y0, y1) - clear), U(max(x0, x1) + clear), U(max(y0, y1) + clear))
    if layer in ("Metal4", "Metal5") and not macro_ok and overlaps(q, mac):
        return False
    if layer not in SB:
        SB[layer] = special_boxes(layer)
    return not any(n_ != own and overlaps(q, b_) for n_, b_ in SB[layer])

def find_row(layer, xa, xb, y_from, y_to, w, own):
    """First y from y_from towards y_to (step 0.5) where a horizontal line xa..xb is free."""
    step = 0.5 if y_to > y_from else -0.5
    y = y_from
    while (y - y_to) * step < 0:
        if is_free(layer, xa, y - w / 2, xb, y + w / 2, own):
            return y
        y += step
    raise SystemExit("no free %s row for %s between %g and %g" % (layer, own, y_from, y_to))

def find_drop_row(px, wd, y_edge, xa, xb, w, own, down=True):
    """The row nearest the macro edge where both the Metal4 drop from the pin and the Metal5 row are free."""
    step = -0.5 if down else 0.5
    y = y_edge + 4 * step
    for _ in range(600):
        if is_free("Metal4", px - wd / 2, min(y, y_edge), px + wd / 2, max(y, y_edge), own, clear=0.3, macro_ok=True) \
                and is_free("Metal5", xa, y - w / 2, xb, y + w / 2, own):
            return y
        y += step
    raise SystemExit("no free row for the drop of %s" % own)

def find_tail_y(bar, xa, xb, w, own):
    """A y along the landing bar where a Metal3 line from xa to xb passes the power grid's via stacks
    (rails every 5.04 um under the core's Metal4 stripes): nearest the bar's middle."""
    lo, hi = bar[1] + w / 2 + 0.3, bar[3] - w / 2 - 0.3
    mid = (bar[1] + bar[3]) / 2
    cands = sorted((lo + k * 0.1 for k in range(int((hi - lo) / 0.1) + 1)), key=lambda y: abs(y - mid))
    for y in cands:
        if is_free("Metal3", min(xa, xb), y - w / 2, max(xa, xb), y + w / 2, own, clear=0.3):
            return y
    raise SystemExit("no free Metal3 track to the landing of %s" % own)

def find_col(layer, ya, yb, x_from, x_to, w, own):
    step = 0.5 if x_to > x_from else -0.5
    x = x_from
    while (x - x_to) * step < 0:
        if is_free(layer, x - w / 2, ya, x + w / 2, yb, own):
            return x
        x += step
    raise SystemExit("no free %s column for %s between %g and %g" % (layer, own, x_from, x_to))

V45 = {}
def v45(w):
    k = round(w, 2)
    if k not in V45:
        V45[k] = via("rv328_ana_via4_%d" % U(k), "Metal4", "Via4", "Metal5", max(w, 0.64), max(w, 0.64), 0.26, 0.36, 0.05)
    return V45[k]
V34 = {}
def v34(w):
    k = round(w, 2)
    if k not in V34:
        V34[k] = via("rv328_ana_via3_%d" % U(k), "Metal3", "Via3", "Metal4", max(w, 0.64), max(w, 0.64), 0.26, 0.36, 0.05)
    return V34[k]

def seg(sw, layer, xa, ya, xb, yb, w, own):
    SB.pop(layer, None)
    if xa == xb:
        wire(sw, layer, xa - w / 2, min(ya, yb) - w / 2, xa + w / 2, max(ya, yb) + w / 2, own)
    else:
        wire(sw, layer, min(xa, xb) - w / 2, ya - w / 2, max(xa, xb) + w / 2, ya + w / 2, own)

def landing(n, sw, pinst):
    """Fingers carried out of the pad to a Metal3 bar; returns the bar (x0, y0, x1, y1) and the pad's side."""
    fing = [r for _, r in pin_boxes(pinst, "ASIG5V", "Metal2")]
    x0 = T(min(r.xMin() for r in fing)); x1 = T(max(r.xMax() for r in fing))
    y0 = T(min(r.yMin() for r in fing)); y1 = T(max(r.yMax() for r in fing))
    name = n.getName()
    def free_offset(make):
        o = LAND_W + 1.0
        while o < 40.0:
            r = make(o)
            if is_free("Metal3", *r, name, clear=0.5) and is_free("Metal2", *r, name, clear=0.5):
                return r
            o += 0.5
        raise SystemExit("no room for the landing of %s" % name)
    if (x1 - x0) > (y1 - y0):
        side = "east" if (x0 + x1) / 2 > ccx else "west"
        edge = x0 if side == "east" else x1
        bar = free_offset(lambda o: (edge - o, y0, edge - o + LAND_W, y1) if side == "east" else (edge + o - LAND_W, y0, edge + o, y1))
        fh = min(T(r.yMax() - r.yMin()) for r in fing)
        v = via("rv328_apad_via2h", "Metal2", "Via2", "Metal3", LAND_W - 0.4, fh - 0.4, 0.26, 0.36, 0.2)
        for r in fing:
            wire(sw, "Metal2", min(bar[0], edge), T(r.yMin()), max(bar[2], edge) + (1.0 if side == "east" else 0), T(r.yMax()), name)
            put_via(sw, v, (bar[0] + bar[2]) / 2, T(r.yMin() + r.yMax()) / 2)
    else:
        side = "north" if (y0 + y1) / 2 > ccy else "south"
        edge = y0 if side == "north" else y1
        bar = free_offset(lambda o: (x0, edge - o, x1, edge - o + LAND_W) if side == "north" else (x0, edge + o - LAND_W, x1, edge + o))
        fw = min(T(r.xMax() - r.xMin()) for r in fing)
        v = via("rv328_apad_via2v", "Metal2", "Via2", "Metal3", fw - 0.4, LAND_W - 0.4, 0.26, 0.36, 0.2)
        for r in fing:
            wire(sw, "Metal2", T(r.xMin()), min(bar[1], edge), T(r.xMax()), max(bar[3], edge), name)
            put_via(sw, v, T(r.xMin() + r.xMax()) / 2, (bar[1] + bar[3]) / 2)
    wire(sw, "Metal3", *bar, name)
    SB.clear()
    return bar, side

# AREF first: its pin sits over a VDD stripe that stops 11 um short of the macro, so only the band between
# the last power rows and the macro is open to it
ANALOG = [("A_AREF", "aref", "apad_aref")] + [("A_ADC%d" % k, "adc%d" % k, "apad_adc%d" % k) for k in range(8)] + [
    ("A_AIN0", "ain0", "apad_ain0"), ("A_AIN1", "ain1", "apad_ain1"),
    ("A_XTAL1", "xtal1", "apad_xtal1"), ("A_XTAL2", "xtal2", "apad_xtal2")]
report = []
under_y = my0 - 6.0                      # rows under the macro are searched downwards from here
strip_x = mx1 + 4.0                      # columns east of the macro, searched eastwards from here
north_y = cy1 - 6.0                      # rows of the north strip, searched downwards
south_y = cy0 + 6.0
west_x = cx0 + 6.0
above_y = my1 + 6.0
col_below = mx1 - 6.0                    # columns of the south-going lines, searched westwards under the macro
for name, pin, padname in ANALOG:
    n = block.findNet(name)
    for sw_ in list(n.getSWires()):
        odb.dbSWire.destroy(sw_)
    n.setSpecial()
    ana.findITerm(pin).connect(n)
    pinst = block.findInst(padname)
    pinst.findITerm("ASIG5V").connect(n)
    sw = odb.dbSWire.create(n, "ROUTED")
    bar, side = landing(n, sw, pinst)
    (_, pr), = pin_boxes(ana, pin, "Metal4")
    px = T(pr.xMin() + pr.xMax()) / 2
    pwid = T(pr.xMax() - pr.xMin())
    w = 2.0 if name in ("A_AREF", "A_XTAL1", "A_XTAL2") else AW   # the crystal loop gets half the resistance
    wd = max(min(pwid, w), 0.8)          # the drop from the pin keeps to the pin's own pitch
    bx, by = (bar[0] + bar[2]) / 2, (bar[1] + bar[3]) / 2
    pts = []
    if side == "east":
        by = find_tail_y(bar, strip_x, bx, w, name)
    if side == "west":                   # XTAL: up from the top edge
        ya = find_drop_row(px, wd, my1, min(px, west_x) - 2, px + 2, w, name, down=False)
        reach = west_x + 2
        for _ in range(4):               # the tail's height and the column depend on each other
            by = find_tail_y(bar, bx, reach, w, name)
            xc = find_col("Metal4", min(by, ya) - 2, max(by, ya) + 2, west_x, west_x + 60, w, name)
            if xc <= reach:
                break
            reach = xc + 0.5
        else:
            raise SystemExit("no tail and column that fit for %s" % name)
        west_x = xc + TRACK
        path = [("Metal4", px, my1, px, ya, wd), ("Metal5", px, ya, xc, ya, w), ("Metal4", xc, ya, xc, by, w)]
        tail = ("Metal3", xc, by, bx, by, w)
    else:
        ya = find_drop_row(px, wd, my0, px - 2, cx1 - 2, w, name)
        if side == "south":
            xc = find_col("Metal4", south_y - 2, ya + 2, col_below, col_below - 250, w, name); col_below = xc - TRACK
        else:
            xc = find_col("Metal4", ya - 2, (north_y if side == "north" else max(by, ya)) + 2, strip_x, cx1 - 2, w, name); strip_x = xc + TRACK
        path = [("Metal4", px, my0, px, ya, wd), ("Metal5", px, ya, xc, ya, w)]
        if side == "east":
            path.append(("Metal4", xc, ya, xc, by, w))
            tail = ("Metal3", xc, by, bx, by, w)
        else:
            if side == "north":
                yr = find_row("Metal5", min(bx, xc) - 2, max(bx, xc) + 2, north_y, north_y - 80, w, name); north_y = yr - TRACK
            else:
                yr = find_row("Metal5", min(bx, xc) - 2, max(bx, xc) + 2, south_y, south_y + 80, w, name); south_y = yr + TRACK
            # the last column, at the landing: anywhere along the bar
            xl = find_col("Metal4", min(yr, by) - 2, max(yr, by) + 2, bx, bar[0] + 1, w, name)
            path += [("Metal4", xc, ya, xc, yr, w), ("Metal5", xc, yr, xl, yr, w), ("Metal4", xl, yr, xl, by, w)]
            tail = None
    length = 0.0
    for k, (layer, xa, ya_, xb, yb, ww) in enumerate(path):
        seg(sw, layer, xa, ya_, xb, yb, ww, name)
        length += abs(xb - xa) + abs(yb - ya_)
        if k > 0:
            put_via(sw, v45(min(ww, path[k - 1][5])), xa, ya_)
    end_layer, ex, ey = path[-1][0], path[-1][3], path[-1][4]
    if tail:
        seg(sw, "Metal3", *tail[1:5], w, name)
        put_via(sw, v34(w), tail[1], tail[2])
        length += abs(tail[3] - tail[1])
    else:
        put_via(sw, v34(w), ex, ey)
    report.append((name, side, round(length)))
print("analog lines drawn: " + ", ".join("%s %s %d um" % r for r in report))
json.dump({r[0]: dict(side=r[1], length_um=r[2]) for r in report}, open(dst + ".analog.json", "w"), indent=1)

# ---------------- antenna diodes for the macro's inputs ----------------
# Every digital input of the macro drives gates inside it over a Metal4 line of up to 0.6 mm (the trunk). The
# LEF says nothing about those gates, so the flow's antenna check and repair cannot see them, and the foundry's
# antenna deck on run sgnv found nine inputs (rc_trim1..7, bod_level1..2, adc_sample) where the Metal4 of the
# trunk and of the route to it is up to 1.45 times the allowed ratio to those gates while Metal4 is etched (the
# driver joins the net on Metal5). One diode cell per input, fixed in the rows under the macro next to its pin,
# puts a diffusion on every such net from Metal1 up; the router connects it like any other sink.
DIODE = "gf180mcu_fd_sc_mcu9t5v0__antenna"
dm = design.getDb().findMaster(DIODE)
assert dm, DIODE
taken = []                                      # (x0, y0, x1, y1) of everything fixed in those rows
mb = ana.getBBox()
rows = sorted([r for r in block.getRows() if r.getBBox().yMax() <= mb.yMin() and r.getBBox().yMax() > mb.yMin() - U(40)
               and r.getBBox().xMin() < mb.xMin() and r.getBBox().xMax() > mb.xMax() - U(800)],
              key=lambda r: -r.getBBox().yMax())[:6]
for inst in block.getInsts():
    b = inst.getBBox()
    if inst.isFixed() or inst.getPlacementStatus() in ("LOCKED", "FIRM", "COVER"):
        taken.append((b.xMin(), b.yMin(), b.xMax(), b.yMax()))
for blk in block.getBlockages():
    b = blk.getBBox()
    taken.append((b.xMin(), b.yMin(), b.xMax(), b.yMax()))


def fits(x0, y0, x1, y1):
    return not any(x0 < t[2] and t[0] < x1 and y0 < t[3] and t[1] < y1 for t in taken)


vdd, vss = block.findNet("VDD"), block.findNet("VSS")
diodes = 0
inputs = sorted((it for it in ana.getITerms() if it.getMTerm().getIoType() == "INPUT" and it.getNet()),
                key=lambda it: it.getBBox().xMin())
for it in inputs:
    px = (it.getBBox().xMin() + it.getBBox().xMax()) // 2
    best = None
    for r in rows:
        rb, sw_ = r.getBBox(), r.getSite().getWidth()
        for k in range(0, 400):
            for sgn in (1, -1):
                x0 = rb.xMin() + ((px - rb.xMin()) // sw_ + sgn * k) * sw_
                if x0 < rb.xMin() or x0 + dm.getWidth() > rb.xMax():
                    continue
                if fits(x0, rb.yMin(), x0 + dm.getWidth(), rb.yMax()):
                    cost = abs(x0 - px) + (mb.yMin() - rb.yMax())
                    if best is None or cost < best[0]:
                        best = (cost, x0, r)
                    break
            if best and k * sw_ > best[0]:
                break
    assert best, "no room for a diode on " + it.getNet().getName()
    _, x0, r = best
    d = odb.dbInst.create(block, dm, "rv328_ana_diode_" + it.getMTerm().getName())
    d.setOrient(r.getOrient())
    d.setLocation(x0, r.getBBox().yMin())
    d.setPlacementStatus("FIRM")
    d.findITerm("I").connect(it.getNet())
    for p, n in (("VDD", vdd), ("VNW", vdd), ("VSS", vss), ("VPW", vss)):
        d.findITerm(p).connect(n)
    b = d.getBBox()
    taken.append((b.xMin(), b.yMin(), b.xMax(), b.yMax()))
    diodes += 1
print("antenna diodes on the macro's inputs: %d, in the %d rows under it" % (diodes, len(rows)))

design.writeDb(dst)
