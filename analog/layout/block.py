#!/usr/bin/env python3
"""Assemble an analog block from generated devices: two rows of devices facing a wiring channel.

Every terminal gets a vertical Metal2 lead from the device into the channel, at an x of its own,
and every net one horizontal Metal3 track across the channel; a Via2 joins a lead to its track.
Nothing else is routed, so the wiring cannot short as long as leads keep their distance, which
add() checks.  It is not a dense layout, but it is correct by construction and easy to inspect.
"""
import klayout.db as kdb

from devices import SC_END, SC_H, SC_RAIL, SC_SITE, VIA, Lib

LEAD_W, LEAD_SP = 0.40, 0.40        # Metal2 leads
GUARD = 3.0                         # between the lead of a small-signal net and a lead that switches, centre to centre
TRK_W, TRK_PITCH = 0.40, 0.90       # Metal3 tracks
HEAVY_W = 1.60                      # tracks of nets that carry milliamperes; their leads end on two Via2
ROW_GAP = 1.5                       # between the channel and a row
DEV_GAP = 1.2                       # between neighbouring devices
# A block that holds standard cells is wired at the metal's minimum width and spacing: the cells' pins stand
# 0.56 um apart, and so must their leads.
FINE = dict(lead_w=0.28, lead_sp=0.28, trk_w=0.28, trk_pitch=0.56)
VIA_END = 0.19                      # from the middle of a via to the end of a narrow line over it (0.13 + 0.06)
STD_GAP = 2.0                       # between a strip of standard cells and a device beside it
TAP_EVERY = 12.0                    # a well tap at least every so many um of standard cells


class Block:
    def __init__(self, name, nets, ports, lib=None, victims=(), calm=(), full=(), heavy=(), fine=False):
        """heavy: nets that carry milliamperes; they get tracks HEAVY_W wide. victims: small-signal nets. calm: nets that do not move while the block works (supplies and bias
        lines are calm anyway). A lead of a victim keeps GUARD away from the leads of other devices that are
        neither: two leads side by side couple about 0.05 fF per um, which is a millivolt on a picofarad node."""
        self.lib = lib or Lib()                       # pass a Lib to draw several blocks into one layout
        self.top = self.lib.ly.create_cell(name)
        self.nets = list(nets)                        # order = track order, bottom to top
        self.ports = list(ports)
        self.lead_w, self.lead_sp, self.trk_w, self.trk_pitch = LEAD_W, LEAD_SP, TRK_W, TRK_PITCH
        if fine:
            self.lead_w, self.lead_sp, self.trk_w, self.trk_pitch = (FINE[k] for k in ("lead_w", "lead_sp", "trk_w", "trk_pitch"))
        self.tw = {n: HEAVY_W if n in heavy else self.trk_w for n in self.nets}
        self.ty, edge = {}, 0.8                        # the middle of every track; tracks are trk_pitch - trk_w apart
        for n in self.nets:
            self.ty[n] = round(edge + self.tw[n] / 2, 3)
            edge += self.tw[n] + self.trk_pitch - self.trk_w
        self.strip = {}                               # row -> the strip of standard cells being built in it
        self.h = edge + 0.8
        self.x = {"top": 0.0, "bot": 0.0}
        self.leads = []                               # (x, net, pin layer, pin y, y from, y to)
        self.count = 0
        self.placed = []                              # for the pictures: name, kind, box, nets of every device
        self.inner = []                               # (net, x, y) of the tracks that are not ports
        self.victims, self.calm = set(victims), set(calm) | {"vss", "avdd"}
        self.full = set(full)                         # nets whose track runs the whole length of the block, as a screen

    def track_y(self, net):
        return self.ty[net]

    def add(self, dev, row, pinmap, gap=DEV_GAP, name="", kind=""):
        """Place dev next in its row. pinmap: {pin name: net}; a pin may be listed as 'S@0' or 'D@1' to ask
        for a lead at that fraction of the pin's width. The device is moved right in 0.1 um steps until none
        of its leads comes too close to a lead that is already there."""
        self.close_std(row)
        w, hgt = dev.bbox[2] - dev.bbox[0], dev.bbox[3] - dev.bbox[1]
        y = self.h + ROW_GAP if row == "top" else -ROW_GAP - hgt
        for step in range(600):
            x = self.x[row] + 0.1 * step
            dx, dy = x - dev.bbox[0], y - dev.bbox[1]
            leads = []
            for key, net in pinmap.items():
                pin, frac = (key.split("@") + ["0.5"])[:2]
                p = dev.pins[pin]
                lay, r = (p[0], p[1:]) if isinstance(p[0], str) else ("metal1", p)
                x1, y1, x2, y2 = r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy
                assert net in self.nets, net
                lx = x1 + 0.25 + (x2 - x1 - 0.5) * float(frac) if x2 - x1 > 0.6 else (x1 + x2) / 2
                lx = round(lx / 0.005) * 0.005
                ty = self.track_y(net)
                # the lead reaches from the middle of the pin (or, on a tall pin, its channel end) to the track
                py = (y1 + 0.3 if row == "top" else y2 - 0.3) if y2 - y1 > 1.0 else (y1 + y2) / 2
                over = max(self.tw[net] / 2, VIA_END if self.lead_w < 0.34 else 0.0)     # a lead crosses the whole of its track
                leads.append((lx, net, lay, py, min(py, ty) - over, max(py, ty) + over))
            if not any(self.clash(l, u) for l in leads for u in leads if u is not l) and \
               not any(self.clash(l, u) or self.disturbs(l, u) for l in leads for u in self.leads):
                break
        else:
            raise ValueError("no room for the leads of %s" % dev.cell.name)
        self.lib.place(self.top, dev, x, y)
        self.placed.append(dict(name=name, kind=kind, box=[x, y, x + w, y + hgt], nets=sorted(set(pinmap.values()))))
        self.x[row] = x + w + gap
        self.count += 1
        self.leads += leads

    def disturbs(self, l, u):
        """A victim's lead next to the lead of a net that switches (leads of two different devices)."""
        a, b = l[1] in self.victims, u[1] in self.victims
        if a == b or (u[1] if a else l[1]) in self.calm:
            return False
        return abs(l[0] - u[0]) < GUARD - 1e-6 and not (l[5] <= u[4] or u[5] <= l[4])

    def clash(self, l, u):
        if l[1] == u[1] and abs(l[0] - u[0]) < 1e-6:
            return False                              # same net on the same line: they simply merge
        return abs(l[0] - u[0]) < self.lead_w + self.lead_sp - 1e-6 and not (l[5] + self.lead_sp <= u[4] or u[5] + self.lead_sp <= l[4])

    # ---- standard cells: abutted in a strip with an end cell either side and well taps along it ------------------
    def _std_place(self, row, cell, x, mirror_x=False):
        """Instance of a standard cell with its box's lower left corner at x (its right one if mirror_x); the lower
        row is drawn upside down, so that in both rows the ground rail is the one next to the channel."""
        y = self.h + ROW_GAP + SC_RAIL if row == "top" else -ROW_GAP - SC_RAIL
        rot = {(False, False): kdb.DTrans.R0, (False, True): kdb.DTrans.M90, (True, False): kdb.DTrans.M0, (True, True): kdb.DTrans.R180}[(row == "bot", mirror_x)]
        self.top.insert(kdb.DCellInstArray(cell.cell_index(), kdb.DTrans(rot, kdb.DVector(round(x, 3), round(y, 3)))))
        return y

    def _std_leads(self, row, x, spots, nets, chosen=()):
        """One lead per pin, at one of the places where a via may stand on it, such that no two leads come too
        close: the first combination that works, or None. spots: [(pin, [(x, y)])]."""
        if not spots:
            return list(chosen)
        y0 = self.h + ROW_GAP + SC_RAIL if row == "top" else -ROW_GAP - SC_RAIL
        (pin, places), rest = spots[0], spots[1:]
        net = nets[pin]
        assert net in self.nets, net
        ty, over = self.track_y(net), max(self.tw[net] / 2, VIA_END)
        for px, py in places:
            lx, vy = round(x + px, 3), round(y0 + py if row == "top" else y0 - py, 3)
            lead = (lx, net, "std", vy, min(vy - VIA_END, ty - over), max(vy + VIA_END, ty + over))
            if any(self.clash(lead, u) for u in chosen) or any(self.clash(lead, u) or self.disturbs(lead, u) for u in self.leads):
                continue
            found = self._std_leads(row, x, rest, nets, tuple(chosen) + (lead,))
            if found is not None:
                return found
        return None

    def _std_tap(self, row):
        """A well tap: the foundry's tap cell and one empty site beside it. The supply is taken from the tap's
        own metal, ground from the rail over the empty site, since the two leads cannot stand at one x."""
        st, lib = self.strip[row], self.lib
        tie, fill = lib.std("filltie"), lib.std("fill_1")
        for k in range(40):
            x = st["x"] + k * SC_SITE
            leads = self._std_leads(row, x, [("VDD", [(0.52, 2.53)]), ("VSS", [(tie.width + 0.28, 0.0)])], {"VDD": st["vdd"], "VSS": st["vss"]})
            if leads is not None:
                break
        else:
            raise ValueError("no room for the leads of a well tap")
        for j in range(k):
            self._std_place(row, fill.cell, st["x"] + j * SC_SITE)
        self._std_place(row, tie.cell, x)
        self._std_place(row, fill.cell, x + tie.width)
        self.leads += leads
        st["x"], st["since"] = x + tie.width + fill.width, 0.0
        self.x[row] = st["x"]

    def add_std(self, sd, row, nets, name=""):
        """Place the standard cell sd (devices.Std) next in its row's strip. nets: {pin: net}. The cell moves right
        one site at a time, with empty cells in between, until each of its pins has a lead that fits."""
        lib = self.lib
        vdd, vss = nets["VDD"], nets["VSS"]
        assert nets.get("VNW", vdd) == vdd and nets.get("VPW", vss) == vss, (name, nets)
        if row not in self.strip:
            x0 = round(self.x[row] + (STD_GAP if self.x[row] > 0 else 0.0) + SC_END, 2)
            end = lib.std("endcap")
            self._std_place(row, end.cell, x0)
            self.strip[row] = dict(x=x0 + end.width, since=0.0, vdd=vdd, vss=vss, x0=x0 - SC_END)
            self._std_tap(row)
        st = self.strip[row]
        assert (st["vdd"], st["vss"]) == (vdd, vss), name
        fill = lib.std("fill_1")
        spots = [(p, sd.spots[p]) for p in sd.pins if p in sd.spots]
        assert all(v for _, v in spots), (sd.name, spots)
        for k in range(60):
            x = st["x"] + k * SC_SITE
            leads = self._std_leads(row, x, spots, nets)
            if leads is not None:
                break
        else:
            raise ValueError("no room for the leads of %s (%s)" % (name, sd.name))
        for j in range(k):
            self._std_place(row, fill.cell, st["x"] + j * SC_SITE)
        y = self._std_place(row, sd.cell, x)
        box = [x, y - SC_RAIL, x + sd.width, y + SC_H + SC_RAIL] if row == "top" else [x, y - SC_H - SC_RAIL, x + sd.width, y + SC_RAIL]
        self.placed.append(dict(name=name, kind="std", cell=sd.name.split("__")[-1], box=box, nets=sorted(set(nets.values()))))
        self.leads += leads
        self.count += 1
        st["x"], st["since"] = x + sd.width, st["since"] + k * SC_SITE + sd.width
        self.x[row] = st["x"]
        if st["since"] >= TAP_EVERY:
            self._std_tap(row)

    def close_std(self, row):
        """End the row's strip of standard cells, if one is open: a last tap if cells follow the previous one, and
        the end cell, mirrored."""
        if row not in self.strip:
            return
        st = self.strip[row]
        if st["since"] > 0:
            self._std_tap(row)
        end = self.lib.std("endcap")
        self._std_place(row, end.cell, st["x"] + end.width, mirror_x=True)
        self.x[row] = st["x"] + end.width + SC_END + STD_GAP
        del self.strip[row]

    def route(self):
        lib, top = self.lib, self.top
        for row in list(self.strip):
            self.close_std(row)
        span = {}
        for lx, net, lay, py, ya, yb in sorted(self.leads):
            ty = self.track_y(net)
            lib.box(top, "metal2", lx - self.lead_w / 2, ya, lx + self.lead_w / 2, yb)
            for vy in ((ty,) if self.tw[net] != HEAVY_W else (ty - 0.45, ty + 0.45)):
                lib.box(top, "via2", lx - VIA / 2, vy - VIA / 2, lx + VIA / 2, vy + VIA / 2)
            if lay == "std":                           # a standard cell's pin: the via stands on the cell's own metal
                lib.box(top, "via1", lx - VIA / 2, py - VIA / 2, lx + VIA / 2, py + VIA / 2)
            if lay == "metal1":
                lib.box(top, "metal1", lx - 0.20, py - 0.20, lx + 0.20, py + 0.20)      # landing, in case the pin is narrow
                lib.box(top, "via1", lx - VIA / 2, py - VIA / 2, lx + VIA / 2, py + VIA / 2)
            a, b = span.get(net, (lx, lx))
            span[net] = (min(a, lx), max(b, lx))
        right = max(b for _, b in span.values())
        for net in self.full:
            if net in span:
                span[net] = (min(a for a, _ in span.values()), right)
        for net, (a, b) in span.items():
            ty = self.track_y(net)
            lib.box(top, "metal3", a - 0.30, ty - self.tw[net] / 2, max(b, a + 0.4) + 0.30, ty + self.tw[net] / 2)
            if net in self.ports:
                lib.text(top, "metal3_label", net, a, ty)
            else:
                self.inner.append((net, a, ty))
        missing = [n for n in self.nets if n not in span]
        assert not missing, missing
        # where each net's track runs, for whoever wires blocks together: net -> (x from, x to, y)
        self.span = {n: (a - 0.30, max(b, a + 0.4) + 0.30, self.track_y(n)) for n, (a, b) in span.items()}
        bb = top.dbbox()
        lib.box(top, "pr_bndry", bb.left - 0.5, bb.bottom - 0.5, bb.right + 0.5, bb.top + 0.5)
        return bb

    def write(self, path, named=None):
        """Write the layout. named: also write a copy in which the inner nets carry labels too, so that an
        extracted netlist keeps their names (as ports they would confuse LVS, hence the separate file)."""
        self.lib.ly.write(path)
        if named:
            ly = self.lib.ly.dup()
            top = ly.cell(self.top.name)
            for net, x, y in self.inner:
                top.shapes(ly.layer(42, 10)).insert(kdb.DText(net, kdb.DTrans(kdb.DVector(x, y))))
            ly.write(named)


def pnp_array(lib, gds, layout, pitch=14.0):
    """Array of foundry pnp_10p00x10p00 cells. layout: rows (bottom first) of emitter net names or None.
    Bases and collectors are all tied together on Metal1 (pin C). Emitters of one net are joined on
    Metal2 / Metal3 and brought to a Metal2 pad above the array (pins named after the nets)."""
    ly = lib.ly
    ly.read(gds)
    cellidx = ly.cell("pnp_10p00x10p00").cell_index()
    c = ly.create_cell("pnp_array")
    nrow, ncol = len(layout), len(layout[0])
    top_y = (nrow - 1) * pitch + 13.44
    # the net with the widest spread of cells gets the lowest bar above the array, so that the lead from
    # any bar up to the channel never crosses another bar
    nets = sorted(set(n for row in layout for n in row if n),
                  key=lambda n: -(max(c for r in layout for c, m in enumerate(r) if m == n) - min(c for r in layout for c, m in enumerate(r) if m == n)))
    # Metal2 for horizontal joins at a height of its own per net, Metal3 for vertical ones at an x of its own per net
    off = {n: -3.5 + 2.2 * i for i, n in enumerate(nets)}
    pins = {}
    for r, row in enumerate(layout):
        for col, net in enumerate(row):
            if not net:
                continue
            x0, y0 = col * pitch, r * pitch
            c.insert(kdb.DCellInstArray(cellidx, kdb.DTrans(kdb.DVector(x0, y0))))
            cx, cy = x0 + 6.8, y0 + 6.8
            # base ring to collector ring, and collector ring to the neighbours
            right = col + 1 < ncol and layout[r][col + 1]
            up = r + 1 < nrow and layout[r + 1][col]
            lib.box(c, "metal1", x0 + 12.30, cy - 0.5, x0 + (pitch + 0.5 if right else 13.10), cy + 0.5)
            lib.box(c, "metal1", cx - 0.5, y0 + 12.30, cx + 0.5, y0 + (pitch + 0.5 if up else 13.10))
            # emitter up to Metal3 on a pad placed at this net's own offsets
            px, py = cx + off[net], cy + off[net]
            lib.box(c, "metal2", px - 0.8, py - 0.8, px + 0.8, py + 0.8)
            lib.contacts(c, px - 0.8, py - 0.8, px + 0.8, py + 0.8, layer="via1", size=VIA, space=0.36, enc=0.10)
            lib.box(c, "metal3", px - 0.8, py - 0.8, px + 0.8, py + 0.8)
            lib.contacts(c, px - 0.8, py - 0.8, px + 0.8, py + 0.8, layer="via2", size=VIA, space=0.36, enc=0.10)
    for net in nets:
        cells = [(r, col) for r, row in enumerate(layout) for col, n in enumerate(row) if n == net]
        cols = sorted(set(col for _, col in cells))
        for col in cols:                                       # Metal3 column through this net's pads, up past the array
            px = col * pitch + 6.8 + off[net]
            rows = [r for r, cc in cells if cc == col]
            lib.box(c, "metal3", px - 0.5, min(rows) * pitch + 6.8 + off[net] - 0.5, px + 0.5, top_y + 1.0 + 2.2 * nets.index(net) + 1.0)
        # Metal2 bar above the array joins this net's columns; its left end is the pin
        by = top_y + 1.0 + 2.2 * nets.index(net)
        xa, xb = cols[0] * pitch + 6.8 + off[net], cols[-1] * pitch + 6.8 + off[net]
        lib.box(c, "metal2", xa - 0.8, by, xb + 0.8, by + 1.0)
        for col in cols:
            px = col * pitch + 6.8 + off[net]
            lib.contacts(c, px - 0.5, by, px + 0.5, by + 1.0, layer="via2", size=VIA, space=0.36, enc=0.10)
        pins[net] = ("metal2", xa - 0.8, by, xa + 0.8, by + 1.0)
    # collector / base pin: the tie on top of the upper right cell
    r, col = max((r, col) for r, row in enumerate(layout) for col, n in enumerate(row) if n)
    pins["C"] = (col * pitch + 6.3, r * pitch + 12.30, col * pitch + 7.3, r * pitch + 13.10)
    from devices import Dev
    return Dev(c, pins, (0.0, 0.0, (ncol - 1) * pitch + 13.6, top_y + 1.0 + 2.2 * len(nets) + 1.2))
