#!/usr/bin/env python3
"""Assemble the analog macro rv328_analog from its blocks.

  macro.py <output directory> [--pex]

The netlist analog/blocks/rv328_analog.spice names eleven blocks, each of which has a layout of
its own (check.sh builds them into the output directory first), and 28 gates and switches of its
own. This script

  1. cuts those gates and switches into two cells and draws them with stack.py: rv328_acsw, the
     four switches at the comparator's inputs with their two inverters, and rv328_glue, the rest;
  2. places the thirteen cells in rows, in two bays with a trunk of vertical lines between them;
  3. wires them. Under every row lies a channel of horizontal Metal3 tracks, one per net; every
     pin of a cell is brought down to its track on Metal4; a net that is used in more than one
     channel, or is a pin of the macro, has a vertical Metal4 line in the trunk, and its tracks
     run to that line. Nothing is routed over a block.

Cells built by stack.py and the ADC front end have their pins as vertical Metal4 lines at their
left edge, which are simply made longer. Cells built by autoblock.py and the reference have theirs
as Metal3 tracks in their own channel; each of those is taken out of the nearer end of the cell to
a new Metal4 line beside it.

Order in the channels and in the trunk (see RANK): the small-signal nets, then ground, the nets
that are set once and stay, the supply, and last the nets that switch while a block is measuring.
The two supply tracks are 6 um wide and screen the groups from each other.

Twelve pins go straight from their block to the edge of the macro, without a track: the crystal
pins upwards from the crystal oscillator, the ten analog inputs downwards from the multiplexer and
the comparator's switches. The other 44 end at the bottom of the trunk.

Writes rv328_analog.gds (pins labelled), wires/rv328_analog.gds (the macro's own wiring and the
two glue cells only, every net labelled: what the wiring extraction reads), rv328_analog_lvs.spice
and rv328_analog_map.json; with --pex also ../rv328_analog_pex.spice.
"""
import json
import os
import re
import sys

import klayout.db as kdb

import pex_block
import stack
from autoblock import flat_lines, flatten, std_netlists, subckts
from devices import LAYER, VIA, Lib

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCKDIR = os.path.join(HERE, "..", "blocks")
TOP = "rv328_analog"
BLOCKS = ("rv328_por rv328_lfosc rv328_bgr rv328_bod rv328_rcosc rv328_xosc rv328_tsens rv328_amux "
          "rv328_refbuf rv328_adcfe rv328_cmp").split()
ACSW = "xg22 xg23 xtp0 xtp1 xtn0 xtn1".split()      # the lines of the top netlist that make up rv328_acsw

# The two cells drawn here. The switches: the two comparator inputs and what can be switched onto them keep to
# the far side of the column and to the tracks next to ground; their controls are set once.
stack.STACK.update({
    "rv328_acsw": dict(
        wmax=80.0, far="vref amx ain1 ain0 acm acp".split(),
        groups=[dict(name="switches", match=r".", bytype=True, low="acp acm ain0 ain1 amx vref".split(),
                     victims="acp acm ain0 ain1 amx vref".split(), calm="ac_bg bgn ac_mux_en amn".split())]),
    "rv328_glue": dict(wmax=126.0, groups=[dict(name="gates", match=r".", bytype=True)]),
})

# Where the cells stand: two bays, rows from the bottom up, cells from the left. The names are the instance
# names of the top netlist. The bottom rows of both bays share one channel. A place in a row can hold several
# cells one above the other, written as a tuple from the top down; the pin lines of an upper cell then pass
# beside the cells under it, which stand to the right of them.
#   A: the ADC front end
#   B: the 128 kHz oscillator, and beside it the multiplexer over the comparator's switches, the comparator and
#      the temperature sensor, next to the ADC's channel; reset and brown-out detector; and farthest from the
#      ADC the two fast oscillators, with the reference buffer, the reference and the logic beside them
FLOOR = {"A": [["xfe"]],
         "B": [["xlf", ("xmux", "acsw", "xac", "xts")], ["xpor", "xbod"], ["xrc", "xxo", ("xrb", "xbgr", "glue")]]}
DIRECT = dict([("xtal1", "north"), ("xtal2", "north"), ("ain0", "south"), ("ain1", "south")] +
              [("adc%d" % i, "south") for i in range(8)])

QUIET = "amx aref vtemp acp acm vref vbp".split()
SWITCHING = re.compile(r"adc_dac\d$|adc_sample$|smp$|cmpa$|adc_cmp$|aco$|ac_out$|clk_|por_n$|bod_o$")
SUPPLY = ("vss", "avdd")
# The two fast oscillators draw 0.7 and up to 1.2 mA. Their supply and ground have tracks and trunk lines of
# their own, which meet the others' only at the foot of the trunk, where the pins are: on one shared ground
# line that current would lift the ground of every cell beside them by millivolts, and the temperature
# sensor's output is 1 mV per kelvin.
BRANCH = {"xrc": "_osc", "xxo": "_osc"}     # instance -> what is added to "avdd" and "vss" for its lines
BRANCHES = tuple(n + b for b in sorted(set(BRANCH.values())) for n in SUPPLY)
HEAVY = ("aref",)                           # 1.6 um instead of 0.4: the ADC charges its capacitors through it

CELL_GAP = 6.0                              # between the cells of a row
NEST_GAP = 3.0                              # between cells that stand one above the other in one place of a row
ROW_GAP = 3.0                               # between a row and the channel under or over it
COL_GAP, COL_SPACE = 2.0, 0.8               # new Metal4 lines beside a cell: distance to the cell, to each other
COL_SCREEN = 4.0                            # between two such lines of which one is small-signal and the other switches
TRACK_SUPPLY, TRUNK_SUPPLY = 6.0, 8.0
EDGE = 5.0                                  # from the last track or cell to the edge of the macro
FOOT = 8.0                                  # under the bottom channel: room for the straps that join the supply's branches


def natural(n):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", n)]


def rank(n):
    """Order of the nets in a channel (from the row downwards) and in the trunk (from the ADC's bay)."""
    if n in QUIET:
        return (0, [QUIET.index(n)])
    if n in SUPPLY:
        return (1 if n == "vss" else 3, [])
    if n in BRANCHES:                               # beyond the switching nets, ground first
        return (5 if n.startswith("vss") else 6, [n])
    return (4 if SWITCHING.match(n) else 2, natural(n))


def cells_of(row):
    """The instances of a row, whether they stand alone or one above the other."""
    return [i for place in row for i in (place if isinstance(place, tuple) else (place,))]


def width(n, supply):
    """Of a net's track or trunk line. A branch gets half the width of the main supply lines: what drops in
    it is only its own cells' business."""
    return supply if n in SUPPLY else supply / 2 if n in BRANCHES else 1.6 if n in HEAVY else 0.4


def space(a, b):
    if a in SUPPLY + BRANCHES or b in SUPPLY + BRANCHES:
        return 1.0
    return 1.2 if a in QUIET or b in QUIET else 0.6


# ---- the netlist --------------------------------------------------------------------------------------------------
def parse(path):
    """(pins, [(instance, nets, cell)] of the blocks, the other lines) of the top netlist."""
    pins, _, body = subckts([path])[TOP]
    inst, rest = [], []
    for line in body:
        words = [a for a in line.split()[1:] if "=" not in a]
        if words[-1] in BLOCKS:
            inst.append((line.split()[0], words[:-1], words[-1]))
        else:
            rest.append(line)
    return pins, inst, rest


def glue_cells(pins, inst, rest, outdir):
    """Write the two glue cells as netlists of their own and draw them. Returns {cell: ports}."""
    sets = {"rv328_acsw": [l for l in rest if l.split()[0] in ACSW], "rv328_glue": [l for l in rest if l.split()[0] not in ACSW]}
    used = {c: [n for l in ls for n in [a for a in l.split()[1:] if "=" not in a][:-1]] for c, ls in sets.items()}
    out = {}
    for c, lines in sets.items():
        outside = set(pins) | set(n for _, ns, _ in inst for n in ns) | set(n for o, u in used.items() if o != c for n in u)
        ports = ["avdd", "vss"] + [n for n in dict.fromkeys(used[c]) if n in outside and n not in SUPPLY]
        path = os.path.join(outdir, c + ".spice")
        open(path, "w").write("* %s: lines %s of analog/blocks/rv328_analog.spice as a cell (written by macro.py)\n.subckt %s %s\n%s\n.ends\n" %
                              (c, " ".join(l.split()[0] for l in lines), c, " ".join(ports), "\n".join(lines)))
        stack.build(c, [path, os.path.join(BLOCKDIR, "logic.spice")], outdir)
        out[c] = ports
    return out


# ---- the cells as they are on file --------------------------------------------------------------------------------
class Cell:
    """A block's layout: its box, and where its pins are. pins[port] = (kind, x1, y1, x2, y2): 'v' a vertical
    Metal4 line, 'h' a horizontal Metal3 track."""

    def __init__(self, name, outdir):
        self.name = name
        ly = kdb.Layout()
        ly.read(os.path.join(outdir, name + ".gds"))
        c = ly.cell(name)
        bb = c.dbbox()
        self.box = (bb.left, bb.bottom, bb.right, bb.top)
        self.metal = {m: kdb.Region(c.begin_shapes_rec(ly.layer(*LAYER[m]))).merged() for m in ("metal3", "metal4")}
        self.pins, self.poly = {}, {}
        for m, kind in (("metal4", "v"), ("metal3", "h")):
            for s in c.shapes(ly.layer(*LAYER[m + "_label"])).each():
                if not s.is_text():
                    continue
                p = s.text.trans.disp
                hit = [q for q in self.metal[m].interacting(kdb.Region(kdb.Box(p.x - 1, p.y - 1, p.x + 1, p.y + 1))).each()]
                assert len(hit) == 1, (name, s.text.string)
                b = hit[0].bbox()
                r = (b.left * ly.dbu, b.bottom * ly.dbu, b.right * ly.dbu, b.top * ly.dbu)
                assert (r[2] - r[0] if kind == "v" else r[3] - r[1]) <= 2.0, (name, s.text.string, r)
                self.pins[s.text.string] = (kind,) + r
                self.poly[s.text.string] = (m, hit[0])
        self.ports = subckts([os.path.join(outdir, name + "_lvs.spice")])[name][0]
        assert set(self.ports) == set(self.pins), (name, set(self.ports) ^ set(self.pins))

    def clear(self, layer, port, x1, y1, x2, y2):
        """True if a new shape of `port` at this place (cell coordinates) keeps 0.3 um from the cell's other metal."""
        own = kdb.Region(self.poly[port][1]) if self.poly[port][0] == layer else kdb.Region()
        box = kdb.Region(kdb.Box(*[int(round(v * 1000)) for v in (x1 - 0.3, y1 - 0.3, x2 + 0.3, y2 + 0.3)]))
        return ((self.metal[layer] - own) & box).is_empty()


def same_cells(outdir, names):
    """The device cells of the blocks have their dimensions in their names; two files may bring the same one.
    Make sure cells of one name are the same cell, since the macro keeps only the first."""
    seen, n = {}, 0
    for name in names:
        ly = kdb.Layout()
        ly.read(os.path.join(outdir, name + ".gds"))
        for c in ly.each_cell():
            sig = tuple(sorted((ly.get_info(li).layer, ly.get_info(li).datatype, kdb.Region(c.begin_shapes_rec(li)).merged().area(),
                                str(c.bbox_per_layer(li))) for li in ly.layer_indexes() if not c.bbox_per_layer(li).empty()))
            if c.name in seen:
                assert seen[c.name] == sig, "cell %s differs between two files (second: %s)" % (c.name, name)
                n += 1
            seen[c.name] = sig
    return len(seen), n


# ---- the macro ----------------------------------------------------------------------------------------------------
def build(outdir, pex=False):
    topfile = os.path.join(BLOCKDIR, TOP + ".spice")
    pins, inst, rest = parse(topfile)
    glue = glue_cells(pins, inst, rest, outdir)
    insts = {name: (cell, nets) for name, nets, cell in inst}             # instance -> cell, nets in the order of its ports
    insts["acsw"], insts["glue"] = ("rv328_acsw", glue["rv328_acsw"]), ("rv328_glue", glue["rv328_glue"])
    assert sorted(insts) == sorted(i for bay in FLOOR.values() for row in bay for i in cells_of(row))
    cells = {c: Cell(c, outdir) for c in sorted(set(c for c, _ in insts.values()))}
    ncell, ndup = same_cells(outdir, sorted(cells))

    # ---- every instance by itself: the lines its pins come down on, in the cell's coordinates -----------------------
    # down[i] = [dict(net, x, w, y1, y2, ext)]: a Metal4 line at x that exists (or, with ext, is to be drawn)
    # between y1 and y2; ext = the Metal3 piece (x1, x2, y, half width) that joins a track of the cell to it.
    down, foot = {}, {}                                                    # foot[i] = x from, x to of all that belongs to i
    for i, (cname, nets) in insts.items():
        c = cells[cname]
        net = dict(zip(c.ports, nets))
        assert len(net) == len(nets), i
        net = {p: n + BRANCH[i] if i in BRANCH and n in SUPPLY else n for p, n in net.items()}
        x1, _, x2, _ = c.box
        left = sorted([p for p, g in c.pins.items() if g[0] == "h" and g[1] - x1 <= x2 - g[3]], key=lambda p: rank(net[p]))
        right = sorted([p for p, g in c.pins.items() if g[0] == "h" and g[1] - x1 > x2 - g[3]], key=lambda p: rank(net[p]))
        lines = []
        for p, g in c.pins.items():
            if g[0] == "v":
                lines.append(dict(net=net[p], port=p, x=(g[1] + g[3]) / 2, w=g[3] - g[1], y1=g[2], y2=g[4], ext=None))
        def apart(p, q):
            """Between two new lines side by side: more where a small-signal net would stand beside one that
            switches (the comparator's input beside its output, 0.8 um apart for 70 um, was 3.9 fF)."""
            if q is None:
                return 0.0
            return COL_SCREEN if {rank(net[p])[0], rank(net[q])[0]} == {0, 4} else COL_SPACE
        edge, last = x1 - COL_GAP, None
        for p in left:
            _, a, ya, b, yb = c.pins[p]
            w = min(1.6, max(0.4, round(yb - ya, 3)))
            edge -= apart(p, last)
            lines.append(dict(net=net[p], port=p, x=edge - w / 2, w=w, y1=None, y2=yb + 0.05, ext=(edge - w, a + 0.2, (ya + yb) / 2, (yb - ya) / 2)))
            edge, last = edge - w, p
        lo = edge - 1.0 if left else x1
        edge, last = x2 + COL_GAP, None
        for p in right:
            _, a, ya, b, yb = c.pins[p]
            w = min(1.6, max(0.4, round(yb - ya, 3)))
            edge += apart(p, last)
            lines.append(dict(net=net[p], port=p, x=edge + w / 2, w=w, y1=None, y2=yb + 0.05, ext=(b - 0.2, edge + w, (ya + yb) / 2, (yb - ya) / 2)))
            edge, last = edge + w, p
        hi = edge + 1.0 if right else x2
        down[i], foot[i] = lines, (lo, hi)

    # ---- across: the cells of every row side by side, the two bays, the trunk between them ---------------------------
    channels = [("bottom", cells_of(FLOOR["A"][0]) + cells_of(FLOOR["B"][0]))] + [("A%d" % k, cells_of(r)) for k, r in enumerate(FLOOR["A"]) if k] + \
               [("B%d" % k, cells_of(r)) for k, r in enumerate(FLOOR["B"]) if k]
    chan_nets = {}
    for ch, members in channels:
        chan_nets[ch] = sorted(set(l["net"] for i in members for l in down[i] if l["net"] not in DIRECT), key=rank)
    count = {}
    for ns in chan_nets.values():
        for n in ns:
            count[n] = count.get(n, 0) + 1
    trunk_nets = sorted([n for n in count if count[n] > 1 or n in pins or n in BRANCHES], key=rank)
    assert all(n in count or n in DIRECT for n in pins)

    # One place of a row: a cell, or several one above the other. A cell under another must clear the upper
    # one's pin lines: it starts to the right of those at the upper cell's left, and ends before those at its right.
    def column(place):
        """({instance: what to add to its cell's x, counted from the left of the place}, width of the place,
        {instance: height above the row's foot}, height of the place)."""
        col = place if isinstance(place, tuple) else (place,)
        off, zones, right = {}, [], 0.0
        for i in col:                                                      # from the top down
            c = cells[insts[i][0]]
            mid = (c.box[0] + c.box[2]) / 2
            x0 = max([z[0] for z in zones] + [0.0])
            off[i] = x0 - foot[i][0]
            assert all(foot[i][1] + off[i] <= z[1] for z in zones), (i, place)
            lo = [l["x"] + l["w"] / 2 for l in down[i] if l["x"] < mid]
            hi = [l["x"] - l["w"] / 2 for l in down[i] if l["x"] >= mid]
            zones.append(((max(lo) + 1.0 if lo else foot[i][0]) + off[i], (min(hi) - 1.0 if hi else float("inf")) + off[i]))
            right = max(right, foot[i][1] + off[i])
        up, y = {}, 0.0
        for i in reversed(col):
            c = cells[insts[i][0]]
            up[i] = y
            y += c.box[3] - c.box[1] + NEST_GAP
        return off, right, up, y - NEST_GAP
    placed = {(bay, k): [column(p) for p in row] for bay in FLOOR for k, row in enumerate(FLOOR[bay])}

    def row_width(key):
        return sum(c[1] for c in placed[key]) + CELL_GAP * (len(placed[key]) - 1)
    wa = max(row_width(k) for k in placed if k[0] == "A")
    trunk, x = {}, wa + CELL_GAP
    for a, n in zip([None] + trunk_nets, trunk_nets):
        if a:
            x += max(space(a, n), COL_SPACE)
        w = width(n, TRUNK_SUPPLY)
        trunk[n] = [x, x + w]
        x += w
    xb = x + CELL_GAP
    dx, lift = {}, {}                                                      # instance -> what to add to its cell's x; its height above its row's foot
    for (bay, k), cols in placed.items():
        x = 0.0 if bay == "A" else xb
        for off, w, up, _ in cols:
            for i in off:
                dx[i], lift[i] = round(x + off[i], 2), up[i]
            x += w + CELL_GAP
    right_edge = xb + max(row_width(k) for k in placed if k[0] == "B")

    # ---- up: rows and the channels under them -------------------------------------------------------------------------
    def tracks_of(nets):
        """[(net, width, distance of its middle below the top of the band)], height of the band."""
        out, off = [], 0.0
        for a, n in zip([None] + nets, nets):
            if a:
                off += space(a, n)
            w = width(n, TRACK_SUPPLY)
            out.append((n, w, off + w / 2))
            off += w
        return out, off

    def height(key):
        return max(c[3] for c in placed[key])
    band, row_y = {}, {}                                                   # band[ch] = (bottom, top)
    h0 = tracks_of(chan_nets["bottom"])[1]
    band["bottom"] = (-ROW_GAP - h0, -ROW_GAP)
    y = 0.0
    for k, row in enumerate(FLOOR["B"]):
        if k:
            h = tracks_of(chan_nets["B%d" % k])[1]
            band["B%d" % k] = (y + ROW_GAP, y + ROW_GAP + h)
            y += h + 2 * ROW_GAP
        row_y[("B", k)] = y
        y += height(("B", k))
    top_edge = y
    y = 0.0
    for k, row in enumerate(FLOOR["A"]):
        if k:
            h = tracks_of(chan_nets["A%d" % k])[1]
            lo = y + ROW_GAP
            while any(lo < b[1] + 2.0 and b[0] - 2.0 < lo + h for c, b in band.items() if c[0] == "B"):
                lo += 1.0                                                  # the tracks of the two bays meet in the trunk: never at one height
            band["A%d" % k] = (lo, lo + h)
            y = lo + h + ROW_GAP
        row_y[("A", k)] = y
        y += height(("A", k))
    top_edge = max(top_edge, y) + EDGE
    bottom_edge = band["bottom"][0] - FOOT
    dy = {i: round(row_y[(bay, k)] + lift[i] - cells[insts[i][0]].box[1], 2) for bay in FLOOR for k, row in enumerate(FLOOR[bay]) for i in cells_of(row)}
    under = {}                                                             # instance -> the instances under it in the same place
    for bay in FLOOR:
        for row in FLOOR[bay]:
            for place in row:
                if isinstance(place, tuple):
                    for k, i in enumerate(place):
                        under[i] = place[k + 1:]
    chan_of = {i: ch for ch, members in channels for i in members}
    ty = {ch: {n: (band[ch][1] - off, w) for n, w, off in tracks_of(chan_nets[ch])[0]} for ch in band}

    # ---- draw ---------------------------------------------------------------------------------------------------------
    lib = Lib()
    ly = lib.ly
    opt = kdb.LoadLayoutOptions()
    opt.cell_conflict_resolution = kdb.LoadLayoutOptions.CellConflictResolution.SkipNewCell
    for c in ["rv328_bgr"] + sorted(set(cells) - {"rv328_bgr"}):          # the reference first: it brings the foundry's bipolar cell
        ly.read(os.path.join(outdir, c + ".gds"), opt)
    top = ly.create_cell(TOP)
    boxes = {}
    for i, (cname, _) in insts.items():
        top.insert(kdb.DCellInstArray(ly.cell(cname).cell_index(), kdb.DTrans(kdb.DVector(dx[i], dy[i]))))
        b = cells[cname].box
        boxes[i] = [b[0] + dx[i], b[1] + dy[i], b[2] + dx[i], b[3] + dy[i]]

    def via(x1, y1, x2, y2):
        lib.contacts(top, x1, y1, x2, y2, layer="via3", size=VIA, space=0.36, enc=0.07)

    ends, drops, pin_at, wires = {}, [], {}, []                           # ends[(ch, net)] = [x1, x2] of what its track must reach
    for i, lines in down.items():
        c, ch = cells[insts[i][0]], chan_of[i]
        for l in lines:
            n, w, x = l["net"], l["w"], l["x"]
            if l["ext"]:                                                   # out of the cell's own channel on Metal3 to a new line
                ea, eb, ey, eh = l["ext"]
                assert c.clear("metal3", l["port"], ea, ey - eh, eb, ey + eh), (i, l["port"])
                lib.box(top, "metal3", ea + dx[i], ey - eh + dy[i], eb + dx[i], ey + eh + dy[i])
                via(x - w / 2 + dx[i], ey - eh + dy[i], x + w / 2 + dx[i], ey + eh + dy[i])
            if DIRECT.get(n) == "north":
                ya, yb = l["y2"] - 0.3, top_edge - dy[i]
            elif DIRECT.get(n) == "south":
                ya, yb = bottom_edge - dy[i], (l["y1"] + 0.3 if l["y1"] is not None else l["y2"])
            else:
                yt, tw = ty[ch][n]
                ya, yb = yt - tw / 2 - 0.05 - dy[i], (l["y1"] + 0.3 if l["y1"] is not None else l["y2"])
                via(x - w / 2 + dx[i], yt - tw / 2, x + w / 2 + dx[i], yt + tw / 2)
                e = ends.setdefault((ch, n), [x - w / 2 + dx[i], x + w / 2 + dx[i]])
                e[0], e[1] = min(e[0], x - w / 2 + dx[i]), max(e[1], x + w / 2 + dx[i])
            assert c.clear("metal4", l["port"], x - w / 2, ya, x + w / 2, yb), (i, l["port"])
            for j in under.get(i, ()):                                     # the line passes beside every cell under this one
                assert not (foot[j][0] + dx[j] - 0.5 < x + dx[i] < foot[j][1] + dx[j] + 0.5), (i, l["port"], j)
            lib.box(top, "metal4", x - w / 2 + dx[i], ya + dy[i], x + w / 2 + dx[i], yb + dy[i])
            drops.append(dict(net=n, inst=i, x=x + dx[i], w=w, y1=ya + dy[i], y2=yb + dy[i]))
            if n in DIRECT:
                pin_at[n] = (x + dx[i], top_edge - 1.0 if DIRECT[n] == "north" else bottom_edge + 1.0, w)
    lines_out = []
    for n, (xa, xc) in trunk.items():
        ys = [(ty[ch][n][0], ty[ch][n][1]) for ch in band if n in ty[ch]]
        for yt, tw in ys:
            via(xa, yt - tw / 2, xc, yt + tw / 2)
        for ch in band:
            if n in ty[ch]:
                e = ends.setdefault((ch, n), [xa, xc])
                e[0], e[1] = min(e[0], xa), max(e[1], xc)
        ya = bottom_edge if n in pins or n in BRANCHES else min(yt - tw / 2 for yt, tw in ys) - 0.05
        yb = max(yt + tw / 2 for yt, tw in ys) + 0.05
        lib.box(top, "metal4", xa, ya, xc, yb)
        lines_out.append(dict(net=n, x=(xa + xc) / 2, w=xc - xa, y1=ya, y2=yb))
        if n in pins:
            pin_at[n] = ((xa + xc) / 2, bottom_edge + 1.0, xc - xa)
    # a branch of the supply joins its net at the foot of the trunk: a Metal3 strap under the last channel
    for k, n in enumerate(b for b in BRANCHES if b in trunk):
        main = trunk[next(m for m in SUPPLY if n.startswith(m))]
        y1 = bottom_edge + 1.0 + 3.0 * k
        lib.box(top, "metal3", min(main[0], trunk[n][0]), y1, max(main[1], trunk[n][1]), y1 + 2.0)
        for xa, xc in (main, trunk[n]):
            via(xa, y1, xc, y1 + 2.0)
        wires.append(dict(net=n, channel="foot", y=y1 + 1.0, w=2.0, x1=min(main[0], trunk[n][0]), x2=max(main[1], trunk[n][1])))
    labels = {}
    for (ch, n), (xa, xc) in ends.items():
        yt, tw = ty[ch][n]
        assert xc - xa > 1.0, (ch, n)                                      # a track with one thing on it joins nothing
        lib.box(top, "metal3", xa, yt - tw / 2, xc, yt + tw / 2)
        wires.append(dict(net=n, channel=ch, y=yt, w=tw, x1=xa, x2=xc))
        if n not in BRANCHES:                                              # a branch is its net: one name is enough
            labels.setdefault(n, (xa + 0.2, yt))
    assert set(pin_at) == set(pins), set(pins) ^ set(pin_at)
    for n, (x, yy, w) in pin_at.items():
        lib.text(top, "metal4_label", n, x, yy)
    bbox = [-EDGE, bottom_edge, right_edge + EDGE, top_edge]
    lib.box(top, "pr_bndry", *bbox)
    keep = kdb.SaveLayoutOptions()
    keep.select_cell(top.cell_index())
    ly.write(os.path.join(outdir, TOP + ".gds"), keep)

    # ---- what LVS compares with: the blocks' own netlists, and the top netlist with its gates written out ------------
    text = "".join(open(os.path.join(outdir, c + "_lvs.spice")).read() + "\n" for c in BLOCKS)
    lib_sp = subckts([topfile, os.path.join(BLOCKDIR, "logic.spice")])
    devs = [(nm, ns, model, {} if model in BLOCKS else a) for nm, ns, model, a in flatten(TOP, lib_sp)]
    text = std_netlists(devs) + text + ".subckt %s %s\n%s\n.ends\n" % (TOP, " ".join(pins), "\n".join(flat_lines(devs)))
    seen, out = set(), []                          # several blocks bring the same standard cell's netlist: keep the first
    for part in re.split(r"(?m)^(?=\.(?:SUBCKT|subckt) )", text):
        name = part.split()[1] if part.lower().startswith(".subckt") else None
        if name is None or name not in seen:
            out.append(part)
        seen.add(name)
    open(os.path.join(outdir, TOP + "_lvs.spice"), "w").write("".join(out))

    # ---- the wiring by itself, every net with its name, for extraction -------------------------------------------------
    for inst_ in list(top.each_inst()):
        if inst_.cell.name not in glue:
            inst_.delete()
    for n, (x, yy) in labels.items():
        if n not in pins:
            lib.text(top, "metal3_label", n, x, yy)
    os.makedirs(os.path.join(outdir, "wires"), exist_ok=True)
    ly.write(os.path.join(outdir, "wires", TOP + ".gds"), keep)

    area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) * 1e-6
    json.dump(dict(bbox=bbox, boxes=boxes, cells={i: c for i, (c, _) in insts.items()}, band=band, tracks=wires, trunk=lines_out,
                   drops=drops, pins={n: list(p) for n, p in pin_at.items()}, direct=DIRECT, floor=FLOOR,
                   group={n: (1 if n.startswith("vss") else 3) if n in BRANCHES else rank(n)[0] for n in set(count) | set(DIRECT)}, branches=list(BRANCHES),
                   cell_area=sum((c.box[2] - c.box[0]) * (c.box[3] - c.box[1]) for c in cells.values()) * 1e-6),
              open(os.path.join(outdir, TOP + "_map.json"), "w"))
    json.dump(dict(width=bbox[2] - bbox[0], height=bbox[3] - bbox[1], area_mm2=area, cells_mm2=sum((c.box[2] - c.box[0]) * (c.box[3] - c.box[1]) for c in cells.values()) * 1e-6,
                   tracks=sum(1 for w in wires if w["channel"] in band), channels=len(band), trunk_lines=len(trunk), pin_lines=len(drops)),
              open(os.path.join(HERE, "reports", "macro.json"), "w"), indent=1)
    print("%s: %.1f x %.1f um = %.3f mm2; %d cells (%d device cells, %d of them in more than one file), %d tracks in %d channels, "
          "%d lines in the trunk, %d pin lines brought to a track" %
          (TOP, bbox[2] - bbox[0], bbox[3] - bbox[1], area, len(insts), ncell, ndup, sum(1 for w in wires if w["channel"] in band), len(band), len(trunk), len(drops)))
    for ch, (a, b) in sorted(band.items(), key=lambda kv: kv[1]):
        print("   channel %-6s y %7.1f to %7.1f, %2d tracks" % (ch, a, b, len(chan_nets[ch])))
    if pex:
        extract(outdir, pins, inst)


def extract(outdir, pins, inst):
    """The macro's wiring and its glue cells as a netlist with capacitances; the blocks stay the cells they are."""
    work = os.path.join(outdir, "wires")
    head = os.path.join(work, "ports.spice")
    open(head, "w").write(".subckt %s %s\n.ends\n" % (TOP, " ".join(pins)))
    tmp = os.path.join(work, TOP + "_wires.spice")
    pex_block.main(os.path.join(work, TOP + ".gds"), TOP, head, tmp)
    lines = open(tmp).read().splitlines()
    end = max(k for k, l in enumerate(lines) if l.startswith(".ends"))
    body = subckts([os.path.join(BLOCKDIR, TOP + ".spice")])[TOP][2]
    blocks = [l for l in body if [a for a in l.split()[1:] if "=" not in a][-1] in BLOCKS]
    assert len(blocks) == len(inst)
    note = ["* The blocks are the cells of analog/blocks (or their own extracted netlists, see sim.py); the gates and",
            "* switches of the macro itself and the capacitance of the wiring between the blocks are from the layout.",
            "* Not in here: capacitance between this wiring and the nodes inside a block."]
    out = [l for l in lines[:3]] + note + lines[3:end] + ["* --- the blocks"] + blocks + lines[end:]
    open(os.path.join(HERE, TOP + "_pex.spice"), "w").write("\n".join(out) + "\n")
    print("%s_pex.spice: %d lines, %d of them wiring capacitors" % (TOP, len(out), sum(1 for l in out if l.startswith("C"))))


if __name__ == "__main__":
    build(sys.argv[1], "--pex" in sys.argv)
