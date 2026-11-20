#!/usr/bin/env python3
"""Layout generators for the devices the analog blocks are built from (GF180MCU, 6 V devices).

The foundry's own generators need gdsfactory, which does not install on the Python used here, so
these draw the same devices directly with KLayout's Python module. Every dimension that comes
from a design rule is named after the rule. Each generator returns a Dev: a KLayout cell plus the
rectangles (um, in the cell's coordinates) where its terminals can be contacted on Metal1.

  mos("n", w, l, nf)      nfet_06v0 / pfet_06v0 with its own tap ring
  res(length, n)          ppolyf_u_1k_6p0, n strips of that length in series (see below)
  res(length, n, w, "pp") ppolyf_u, the plain p+ poly resistor (350 ohm per square)
  cap(w, l)               cap_mim_2f0fF between Metal4 and Metal5
  cap(w, l, n)            n of them on one bottom plate, top plates joined (a bank of unit capacitors)

Run as a script it writes a test layout with one of each, for DRC and LVS.
"""
import os
import sys

import klayout.db as kdb

LAYER = {"comp": (22, 0), "nwell": (21, 0), "dualgate": (55, 0), "poly2": (30, 0), "nplus": (32, 0), "pplus": (31, 0),
         "sab": (49, 0), "resistor": (62, 0), "res_mk": (110, 5), "contact": (33, 0),
         "metal1": (34, 0), "via1": (35, 0), "metal2": (36, 0), "via2": (38, 0), "metal3": (42, 0), "via3": (40, 0),
         "metal4": (46, 0), "via4": (41, 0), "metal5": (81, 0), "fusetop": (75, 0), "cap_mk": (117, 5), "mim_l_mk": (117, 10),
         "metal1_label": (34, 10), "metal2_label": (36, 10), "metal3_label": (42, 10), "metal4_label": (46, 10),
         "metal5_label": (81, 10), "pr_bndry": (0, 0)}

# ---- design rules used (um) ----------------------------------------------------------------------------------------
CO = 0.22            # CO.1  contact size
CO_SP = 0.28         # CO.2b contact spacing in arrays (0.25 otherwise)
CO_ENC = 0.07        # CO.3 / CO.4 poly and COMP overlap of contact
CO_PL = 0.15         # CO.7  COMP contact to gate
M1_ENC = 0.06        # CO.6a Metal1 overlap of contact at a line end
M1_W, M1_SP = 0.23, 0.23
END_CAP = 0.25       # PL.4  poly beyond COMP (0.22)
PL_COMP = 0.30       # PL.5b field poly to COMP
GATE_IMP = 0.24      # NP.5a / PP.5a implant overlap of the gate (0.23)
TAP_IMP = 0.16       # NP.5d / PP.5d implant beyond COMP for a tap
NW_NCOMP = 0.16      # DF.4d nwell overlap of its n+ tap
DG_ENC = 0.24        # DV.6  dualgate beyond COMP; also clears DV.8 (0.4 beyond poly) with the ring in between
SD_END = 0.50        # DF.6  COMP beyond the gate (0.4) and room for a contact
SD_IN = 0.56         # contact between two gates: 2 x CO.7 + contact, rounded up
RING_W = 0.36        # tap ring: one contact and CO.4 either side
RING_GAP = 0.60      # device COMP to ring COMP: the two implants must not meet
VIA, VIA_ENC = 0.26, 0.06


SC = "gf180mcu_fd_sc_mcu9t5v0"      # the foundry's 9-track 5 V standard cells, used for plain logic on the analog supply
SC_H, SC_SITE = 5.04, 0.56          # row height and placement step
SC_RAIL = 0.45                      # the supply rails reach this far beyond the cell's box, above and below
SC_END = 2.93                       # the end cell's wells and implants reach this far beyond its box


class Std:
    """A standard cell as the generators see it: its name, its width, its pins in the order of the foundry
    netlist, and for every signal pin the places (x, y) in the cell where a Via1 may stand, lowest first."""

    def __init__(self, name, width, pins, spots):
        self.name, self.width, self.pins, self.spots = name, width, pins, spots
        self.bbox = (0.0, 0.0, width, SC_H)


def via_spots(rects, rail=False):
    """Where a 0.26 um via may stand on a pin drawn as these Metal1 rectangles: the via inside the metal, and
    0.06 um of metal beyond it on two opposite sides (rule V1.3: where the metal is flush with the via on one
    side, the adjacent sides need that much). Returned as (x, y) on the 5 nm grid, lowest first."""
    reg = kdb.Region()
    for r in rects:
        reg.insert(kdb.Box(*[int(round(v * 1000)) for v in r]))
    reg.merge()
    out = set()
    for dx, dy in ((189, 129), (129, 189)):                  # 1 nm of tolerance, so that an exact fit is not lost
        for p in reg.sized(-dx, -dy, 2).decompose_trapezoids_to_region().each():
            b = p.bbox()
            xs = sorted(set([5 * round((b.left + b.right) / 10)] + list(range(10 * (-(-b.left // 10)), b.right + 1, 10))))
            ys = [5 * (-(-b.bottom // 5))] if not rail else [5 * round((b.bottom + b.top) / 10)]
            for x in xs:
                for y in ys:
                    if b.left - 1 <= x <= b.right + 1 and b.bottom - 1 <= y <= b.top + 1:
                        out.add((x / 1000.0, y / 1000.0))
    return sorted(out, key=lambda p: (p[1], p[0]))


class Dev:
    """A device cell and where to reach its terminals: pins[name] = (x1, y1, x2, y2) on Metal1."""

    def __init__(self, cell, pins, bbox):
        self.cell, self.pins, self.bbox = cell, pins, bbox


class Lib:
    def __init__(self):
        self.ly = kdb.Layout()
        self.ly.dbu = 0.001
        self.L = {k: self.ly.layer(*v) for k, v in LAYER.items()}
        self.cache = {}

    def box(self, cell, layer, x1, y1, x2, y2):
        cell.shapes(self.L[layer]).insert(kdb.DBox(round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3)))

    def ring(self, cell, layer, x1, y1, x2, y2, w):
        """Frame of width w whose inner edge is the given rectangle."""
        self.box(cell, layer, x1 - w, y1 - w, x2 + w, y1)
        self.box(cell, layer, x1 - w, y2, x2 + w, y2 + w)
        self.box(cell, layer, x1 - w, y1, x1, y2)
        self.box(cell, layer, x2, y1, x2 + w, y2)

    def contacts(self, cell, x1, y1, x2, y2, layer="contact", size=CO, space=CO_SP, enc=CO_ENC):
        """Fill a rectangle with as many cuts as fit, centred, keeping enc to its edges."""
        pitch = size + space
        nx = max(1, int((x2 - x1 - 2 * enc + space) / pitch + 1e-6))
        ny = max(1, int((y2 - y1 - 2 * enc + space) / pitch + 1e-6))
        ox = (x1 + x2) / 2 - ((nx - 1) * pitch + size) / 2
        oy = (y1 + y2) / 2 - ((ny - 1) * pitch + size) / 2
        g = 0.005
        ox, oy = round(ox / g) * g, round(oy / g) * g
        for i in range(nx):
            for j in range(ny):
                self.box(cell, layer, ox + i * pitch, oy + j * pitch, ox + i * pitch + size, oy + j * pitch + size)

    def text(self, cell, layer, name, x, y):
        cell.shapes(self.L[layer]).insert(kdb.DText(name, kdb.DTrans(kdb.DVector(x, y))))

    # ---- transistor ---------------------------------------------------------------------------------------------
    def mos(self, kind, w, l, nf=1, tie=False):
        """6 V transistor, nf gates of width w and length l side by side, inside a tap ring.

        Sources are the odd diffusions counted from the left, drains the even ones.  Pins: S (bar across
        the bottom), D (bar across the top), G (pad at the upper left), B (the ring's left and right legs).
        tie=True contacts the source bar to the ring under it, for a source that is also the bulk.
        """
        key = ("mos", kind, w, l, nf, tie)
        if key in self.cache:
            return self.cache[key]
        c = self.ly.create_cell("%sfet_w%s_l%s_nf%d%s" % (kind, ("%g" % w).replace(".", "p"), ("%g" % l).replace(".", "p"), nf, "_t" if tie else ""))
        imp, tap = ("nplus", "pplus") if kind == "n" else ("pplus", "nplus")
        xc = 2 * SD_END + nf * l + (nf - 1) * SD_IN
        self.box(c, "comp", 0, 0, xc, w)
        self.box(c, imp, -GATE_IMP, -GATE_IMP, xc + GATE_IMP, w + GATE_IMP)
        # gates, joined by a strap above the device that ends in a contact pad on the left
        strap_y1, strap_y2 = w + PL_COMP, w + PL_COMP + 0.40
        pad_x1, pad_x2 = -1.05, -0.22
        for i in range(nf):
            gx = SD_END + i * (l + SD_IN)
            self.box(c, "poly2", gx, -END_CAP, gx + l, strap_y2)
        self.box(c, "poly2", pad_x1, strap_y1, SD_END + (nf - 1) * (l + SD_IN) + l, strap_y2)
        self.contacts(c, pad_x1, strap_y1, pad_x2, strap_y2, space=0.25)
        self.box(c, "metal1", pad_x1, strap_y1, pad_x2, strap_y2)
        # tap ring
        rx1, rx2 = pad_x1 - 0.40, xc + RING_GAP
        ry1, ry2 = -END_CAP - 0.40, strap_y2 + 0.40
        self.ring(c, "comp", rx1, ry1, rx2, ry2, RING_W)
        self.ring(c, tap, rx1 + TAP_IMP, ry1 + TAP_IMP, rx2 - TAP_IMP, ry2 - TAP_IMP, RING_W + 2 * TAP_IMP)
        for x1, x2 in ((rx1 - RING_W, rx1), (rx2, rx2 + RING_W)):          # contacts and Metal1 on the two legs
            self.contacts(c, x1, ry1 - RING_W, x2, ry2 + RING_W)
            self.box(c, "metal1", x1, ry1 - RING_W, x2, ry2 + RING_W)
        # source and drain: contact columns, Metal1 strips, a bar below for sources and one above for drains
        s_bar = (0, ry1 - RING_W - 0.07, xc, ry1 + 0.07)
        d_bar = (0, ry2 - 0.07, xc, ry2 + RING_W + 0.07)
        for i in range(nf + 1):
            cx = SD_END / 2 if i == 0 else (xc - SD_END / 2 if i == nf else SD_END + i * l + (i - 1) * SD_IN + SD_IN / 2)
            if i == 0:
                cx = SD_END - CO_PL - CO / 2 - 0.02
            if i == nf:
                cx = xc - (SD_END - CO_PL - CO / 2 - 0.02)
            self.contacts(c, cx - CO / 2 - CO_ENC, 0, cx + CO / 2 + CO_ENC, w)
            if i % 2 == 0:
                self.box(c, "metal1", cx - 0.17, s_bar[1], cx + 0.17, w)
            else:
                self.box(c, "metal1", cx - 0.17, 0, cx + 0.17, d_bar[3])
        self.box(c, "metal1", *s_bar)
        self.box(c, "metal1", *d_bar)
        if tie:
            self.contacts(c, 0, ry1 - RING_W, xc, ry1)
        if kind == "p":
            self.box(c, "nwell", rx1 - RING_W - NW_NCOMP, ry1 - RING_W - NW_NCOMP, rx2 + RING_W + NW_NCOMP, ry2 + RING_W + NW_NCOMP)
        bb = (rx1 - RING_W - DG_ENC, ry1 - RING_W - DG_ENC, rx2 + RING_W + DG_ENC, ry2 + RING_W + DG_ENC)
        self.box(c, "dualgate", *bb)
        pins = {"S": s_bar, "D": d_bar, "G": (pad_x1, strap_y1, pad_x2, strap_y2),
                "B": (rx1 - RING_W, ry1 - RING_W, rx1, ry2 + RING_W), "B2": (rx2, ry1 - RING_W, rx2 + RING_W, ry2 + RING_W)}
        d = Dev(c, pins, bb)
        self.cache[key] = d
        return d

    # ---- high-resistance poly resistor ------------------------------------------------------------------------------
    def res(self, ls, n=1, w=1.0, kind="1k"):
        """ppolyf_u_1k_6p0 (kind "1k") or ppolyf_u (kind "pp"): n strips of body length ls and width w, in
        series, inside a substrate tap ring. The two differ in the high-resistance implant and thick-oxide
        layers, which only the first has, and in how far the p+ implant must reach beyond the poly.

        Strips run along x and are stacked in y; neighbours are joined on Metal1 at alternate ends.
        Pins: A (left end of the first strip), B (free end of the last strip; brought out to the left
        beyond A when it is on the same side), SUB (the ring).
        """
        key = ("res", ls, n, w, kind)
        if key in self.cache:
            return self.cache[key]
        c = self.ly.create_cell("res%s_l%s_n%d_w%s" % (kind, ("%g" % ls).replace(".", "p"), n, ("%g" % w).replace(".", "p")))
        HEAD, HCON, SAB_X, SAB_Y, PP_PL, RL_X, RL_Y, GAP = 0.64, 0.36, 0.10, 0.28, 0.18, 1.04, 0.40, 0.50
        if kind == "pp":
            # PRES.5; strips far enough apart for their implants; PRES.9a: the salicide block ends with the body
            PP_PL, GAP, SAB_X = 0.30, 0.70, 0.0
        pitch = w + GAP
        top = (n - 1) * pitch + w
        pads = {}
        for i in range(n):
            y = i * pitch
            self.box(c, "poly2", -HEAD, y, ls + HEAD, y + w)
            self.box(c, "res_mk", 0, y, ls, y + w)
            # the contact sits exactly 0.22 from the salicide block: KLayout's HRES.8 asks for at least that,
            # magic checks it as a minimum and a maximum
            for side, x1 in (("L", -SAB_X - 0.22 - CO - CO_ENC), ("R", ls + SAB_X + 0.22 - CO_ENC)):
                self.contacts(c, x1, y, x1 + HCON, y + w, space=0.25)
                self.box(c, "metal1", x1, y, x1 + HCON, y + w)
                pads[(i, side)] = (x1, y, x1 + HCON, y + w)
        for i in range(n - 1):                                   # series links
            a, b = pads[(i, "R" if i % 2 == 0 else "L")], pads[(i + 1, "R" if i % 2 == 0 else "L")]
            self.box(c, "metal1", a[0], a[1], b[2], b[3])
        self.box(c, "sab", -SAB_X, -SAB_Y, ls + SAB_X, top + SAB_Y)
        rl = (-RL_X, -RL_Y, ls + RL_X, top + RL_Y)
        if kind == "pp":
            self.box(c, "pplus", -HEAD - PP_PL, -PP_PL, ls + HEAD + PP_PL, top + PP_PL)     # the body is p+ poly as well
        else:
            self.box(c, "pplus", -HEAD - PP_PL, -PP_PL, 0, top + PP_PL)
            self.box(c, "pplus", ls, -PP_PL, ls + HEAD + PP_PL, top + PP_PL)
            self.box(c, "resistor", *rl)
            self.box(c, "dualgate", *rl)
        pin_a = pads[(0, "L")]
        last = pads[(n - 1, "L" if n % 2 == 0 else "R")]
        left = rl[0]
        if n % 2 == 0:                                           # B on the same side as A: lead it out further left
            self.box(c, "metal1", last[0] - 1.0, last[1], last[2], last[1] + 0.40)
            pin_b = (last[0] - 1.0, last[1], last[0] - 0.5, last[1] + 0.40)
            left = last[0] - 1.0 - 0.3
        else:
            pin_b = last
        # substrate tap ring around everything
        rx1, ry1, rx2, ry2 = min(left, rl[0]) - 0.60, rl[1] - 0.60, rl[2] + 0.60, rl[3] + 0.60
        self.ring(c, "comp", rx1, ry1, rx2, ry2, RING_W)
        self.ring(c, "pplus", rx1 + TAP_IMP, ry1 + TAP_IMP, rx2 - TAP_IMP, ry2 - TAP_IMP, RING_W + 2 * TAP_IMP)
        for x1, y1, x2, y2 in ((rx1 - RING_W, ry1 - RING_W, rx1, ry2 + RING_W), (rx2, ry1 - RING_W, rx2 + RING_W, ry2 + RING_W),
                               (rx1, ry1 - RING_W, rx2, ry1), (rx1, ry2, rx2, ry2 + RING_W)):
            horiz = (x2 - x1) > (y2 - y1) and y2 - y1 < 0.5
            self.contacts(c, x1 + (0.25 if horiz else 0), y1, x2 - (0.25 if horiz else 0), y2)
            self.box(c, "metal1", x1, y1, x2, y2)
        bb = (rx1 - RING_W - 0.1, ry1 - RING_W - 0.1, rx2 + RING_W + 0.1, ry2 + RING_W + 0.1)
        d = Dev(c, {"A": pin_a, "B": pin_b, "SUB": (rx1, ry1 - RING_W, rx2, ry1)}, bb)
        self.cache[key] = d
        return d

    # ---- MIM capacitor ---------------------------------------------------------------------------------------------------
    def cap(self, w, l, n=1, rows=16):
        """cap_mim_2f0fF, w x l. Pins on Metal2 below the plate: T (top plate) and Bot (bottom plate).

        n > 1 draws a bank: n capacitors of that size on one bottom plate, in columns of up to `rows`,
        their top plates joined on Metal5. Every unit keeps its own top plate, so a bank of n is n times
        one unit, whatever the edges of the top plate come out as."""
        key = ("cap", w, l, n, rows)
        if key in self.cache:
            return self.cache[key]
        name = "mim_w%s_l%s" % (("%g" % w).replace(".", "p"), ("%g" % l).replace(".", "p"))
        c = self.ly.create_cell(name if n == 1 else "%s_x%d" % (name, n))
        SP = 0.8                                                 # between top plates (MIMTM.6 asks for 0.6)
        px, py = w + SP, l + SP
        cols = -(-n // rows)
        W, H = cols * px - SP, min(n, rows) * py - SP
        for i in range(n):
            x, y = (i // rows) * px, (i % rows) * py
            self.box(c, "fusetop", x, y, x + w, y + l)
            self.box(c, "mim_l_mk", x, y, x + w, y + 0.1)
            self.contacts(c, x, y, x + w, y + l, layer="via4", size=VIA, space=0.50, enc=0.45)
        if n == 1:
            self.box(c, "metal5", 0, 0, w, l)
            self.box(c, "metal5", w - 2.5, -4.0, w - 0.5, 0)     # lead off the plate
        else:
            for k in range(cols):                                # Metal5 over each column, down to a bar below the plate
                self.box(c, "metal5", k * px, -2.6, k * px + w, min(rows, n - k * rows) * py - SP)
            self.box(c, "metal5", 0, -4.0, W, -2.6)
        # bottom plate with a tab on its lower edge for Via3, 0.65 clear of the top plate (see caparray.py)
        self.box(c, "metal4", -0.6, -1.6, W + 0.6, H + 0.6)
        self.box(c, "cap_mk", -0.6, -1.6, W + 0.6, H + 0.6)
        bx = (0.5, -1.5, 2.5, -0.7)                              # stack Metal4 - Metal3 - Metal2 under the tab
        for lay in ("metal3", "metal2"):
            self.box(c, lay, *bx)
        self.contacts(c, *bx, layer="via3", size=VIA, space=0.36, enc=0.10)
        self.contacts(c, *bx, layer="via2", size=VIA, space=0.36, enc=0.10)
        # top plate: the Metal5 lead ends on a stack on its own Metal4 island, 1.2 from the bottom plate
        tx = (W - 2.5, -4.0, W - 0.5, -3.0)
        for lay in ("metal4", "metal3", "metal2"):
            self.box(c, lay, *tx)
        for lay in ("via4", "via3", "via2"):
            self.contacts(c, *tx, layer=lay, size=VIA, space=0.36, enc=0.10)
        d = Dev(c, {"T": ("metal2",) + tx, "Bot": ("metal2",) + bx}, (-0.6, -4.2, W + 0.6, H + 0.6))
        self.cache[key] = d
        return d

    # ---- standard cells ------------------------------------------------------------------------------------------
    def std(self, name):
        """The foundry standard cell `name` (with or without the library prefix), copied into this layout."""
        full = name if name.startswith(SC) else SC + "__" + name
        key = ("std", full)
        if key in self.cache:
            return self.cache[key]
        if not hasattr(Lib, "_sc"):
            ref = os.path.join(os.environ.get("PDK_DIR") or os.path.join(os.environ.get("PDK_ROOT", ""), "gf180mcuD"), "libs.ref", SC)
            src = kdb.Layout()
            src.read(os.path.join(ref, "gds", SC + ".gds"))
            lef, sizes, pins = open(os.path.join(ref, "lef", SC + ".lef")).read(), {}, {}
            import re
            for m in re.finditer(r"^MACRO (\S+)\n(.*?)^END \1", lef, re.M | re.S):
                sizes[m.group(1)] = float(re.search(r"SIZE ([\d.]+) BY", m.group(2)).group(1))
                pins[m.group(1)] = {}
                for p in re.finditer(r"PIN (\S+)\n(.*?)END \1", m.group(2), re.S):
                    lay, rects = None, []
                    for l, r in re.findall(r"LAYER (\S+) ;|RECT ([-\d. ]+) ;", p.group(2)):
                        if l:
                            lay = l
                        elif lay == "Metal1":
                            rects.append(tuple(float(v) for v in r.split()))
                    pins[m.group(1)][p.group(1)] = rects
            order = {m.group(1): m.group(2).split() for m in re.finditer(r"^\.SUBCKT (\S+) (.*)$", open(os.path.join(ref, "spice", SC + ".spice")).read(), re.M)}
            Lib._sc = (src, sizes, pins, order)
        src, sizes, pins, order = Lib._sc
        c = self.ly.create_cell(full)
        c.copy_tree(src.cell(full))
        rails = ("VDD", "VSS", "VNW", "VPW")
        d = Std(full, sizes[full], order.get(full, []), {p: via_spots(r) for p, r in pins[full].items() if p not in rails})
        d.cell = c
        self.cache[key] = d
        return d

    def place(self, top, dev, x, y):
        """Instance of dev with its lower left corner at (x, y); returns its pins in top coordinates."""
        dx, dy = x - dev.bbox[0], y - dev.bbox[1]
        top.insert(kdb.DCellInstArray(dev.cell.cell_index(), kdb.DTrans(kdb.DVector(round(dx, 3), round(dy, 3)))))
        out = {}
        for k, p in dev.pins.items():
            lay, r = (p[0], p[1:]) if isinstance(p[0], str) else ("metal1", p)
            out[k] = (lay, r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy)
        return out


def test(outdir):
    lib = Lib()
    top = lib.ly.create_cell("devtest")
    x = 0.0
    nets = []
    for i, (kind, w, l, nf) in enumerate((("n", 2.0, 1.0, 2), ("n", 0.5, 0.7, 1), ("n", 8.0, 8.0, 1), ("p", 2.0, 0.6, 1), ("p", 16.0, 8.0, 4), ("p", 1.0, 2.0, 3))):
        d = lib.mos(kind, w, l, nf)
        y = 0.0 if kind == "n" else 30.0
        pins = lib.place(top, d, x, y)
        for name in ("S", "D", "G", "B"):
            p = pins[name][1:]
            net = "%s%d" % (name.lower(), i) if name != "B" else ("vss" if kind == "n" else "nw%d" % i)
            lib.text(top, "metal1_label", net, (p[0] + p[2]) / 2, (p[1] + p[3]) / 2)
        if kind == "p":
            p = pins["B2"][1:]
            lib.text(top, "metal1_label", "nw%d" % i, (p[0] + p[2]) / 2, (p[1] + p[3]) / 2)
        nets.append("x%d d%d g%d s%d %s %sfet_06v0 w=%gu l=%gu m=%d" % (i, i, i, i, "vss" if kind == "n" else "nw%d" % i, kind, w, l, nf))
        x += d.bbox[2] - d.bbox[0] + 3.0
    for i, (ls, n) in enumerate(((13.4, 1), (13.75, 10), (21.75, 4))):
        d = lib.res(ls, n)
        pins = lib.place(top, d, x, 0.0)
        for name, net in (("A", "ra%d" % i), ("B", "rb%d" % i), ("SUB", "vss")):
            p = pins[name][1:]
            lib.text(top, "metal1_label", net, (p[0] + p[2]) / 2, (p[1] + p[3]) / 2)
        nets.append("xr%d ra%d rb%d vss ppolyf_u_1k_6p0 r_width=1u r_length=%gu" % (i, i, i, ls * n))
        x += d.bbox[2] - d.bbox[0] + 3.0
    for i, (ls, n, w) in enumerate(((34.3, 1, 2.0), (11.4, 2, 2.0))):
        d = lib.res(ls, n, w, "pp")
        pins = lib.place(top, d, x, 0.0)
        for name, net in (("A", "pa%d" % i), ("B", "pb%d" % i), ("SUB", "vss")):
            p = pins[name][1:]
            lib.text(top, "metal1_label", net, (p[0] + p[2]) / 2, (p[1] + p[3]) / 2)
        nets.append("xp%d pa%d pb%d vss ppolyf_u r_width=%gu r_length=%gu" % (i, i, i, w, ls * n))
        x += d.bbox[2] - d.bbox[0] + 3.0
    d = lib.cap(30.0, 30.0)
    pins = lib.place(top, d, x, 0.0)
    for name, net in (("T", "ct"), ("Bot", "cb")):
        p = pins[name][1:]
        lib.text(top, "metal2_label", net, (p[0] + p[2]) / 2, (p[1] + p[3]) / 2)
    nets.append("xc0 ct cb cap_mim_2f0fF c_width=30u c_length=30u")
    x += d.bbox[2] - d.bbox[0] + 3.0
    d = lib.cap(5.0, 5.0, 20, 8)
    pins = lib.place(top, d, x, 0.0)
    for name, net in (("T", "bt"), ("Bot", "bb")):
        p = pins[name][1:]
        lib.text(top, "metal2_label", net, (p[0] + p[2]) / 2, (p[1] + p[3]) / 2)
    nets.append("xc1 bt bb cap_mim_2f0fF c_width=5u c_length=5u m=20")
    os.makedirs(outdir, exist_ok=True)
    lib.ly.write(os.path.join(outdir, "devtest.gds"))
    ports = sorted(set(t for n in nets for t in n.split()[1:] if "=" not in t and "_" not in t))
    open(os.path.join(outdir, "devtest.spice"), "w").write(".subckt devtest %s\n%s\n.ends\n" % (" ".join(ports), "\n".join(nets)))
    print("devtest: %d devices" % len(nets))


if __name__ == "__main__":
    test(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
