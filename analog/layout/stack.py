#!/usr/bin/env python3
"""Draw a cell from its netlist as a stack of blocks, for cells too long for one block.

  stack.py <cell> <netlist file> <output directory> [more netlist files for sub-cells]

autoblock.py puts every device of a cell into two rows facing one wiring channel. With a hundred
transistors that is a strip half a millimetre long. Here the netlist is cut into groups (STACK
below says which devices belong together), every group becomes a block of its own, no wider than
the cell's `wmax`, and the blocks are stacked. A net that is used in more than one block, or is a
pin, gets a vertical Metal4 line in a column at the left of the stack, and every block's Metal3
track of that net is extended to its line. The ADC front end (adcfe.py) is built the same way, with
its capacitor array on top.

Writes <cell>.gds, <cell>_named.gds (every net labelled, for extraction), <cell>_lvs.spice and
<cell>_map.json.
"""
import json
import os
import re
import sys

import klayout.db as kdb

from autoblock import block_map, flatten, generate, make, subckts, write_flat
from block import DEV_GAP
from devices import VIA, Lib

HERE = os.path.dirname(os.path.abspath(__file__))
GAP = 3.0                                  # between stacked blocks
SP_W, SP_SPACE, SP_X0 = 0.40, 0.80, -2.8   # Metal4 lines of the column: width, spacing, right edge of the first
SUPPLY_W = 1.6                             # the two supply lines
PASSIVE = ("cap_mim_2f0fF", "ppolyf_u_1k_6p0", "ppolyf_u")
WMAX_AMUX = 330.0

# How a cell is cut up. groups: from the bottom of the stack to the top; a device belongs to the first group
# whose `match` (a regular expression on its flat name) fits, and to the last group if none does.
#   top, bot    expressions for the devices that must stand in the upper / lower row of their block; the others
#               go where adcfe.py would put them (capacitors and resistors above, transistors in the shorter row)
#   last        expression for the devices that are placed after the group's others
#   bytype      PMOS in the upper row, NMOS in the lower one, as autoblock does: matched pairs then stand side
#               by side, and no transistor's supply lead has to cross the whole channel
#   low, high, victims, calm, full    as in autoblock.ORDER, for this group's blocks
# far: nets whose column lines stand farthest from the stack, beyond the supplies (small-signal nets, so that
# the logic lines' tracks do not cross them).
# heavy, strong: the nets that carry milliamperes and the transistors on them (autoblock.ORDER): wide tracks and
# column lines, several leads per source and drain.
STACK = {
    # 8 MHz oscillator. Bottom: the capacitor banks with their switches and the trim inverters right under them.
    # Middle: thresholds, bias, the two comparators, latch, driver and the timing resistor. Top: run control,
    # the two flip-flops and the output gate. The timing node vc joins the two lower blocks.
    "rv328_rcosc": dict(
        wmax=215.0, far=["vc"],
        groups=[
            dict(name="capacitors", match=r"xc[ft]\d?$|xst\d$|xit\d_", bot=r"xst|xit", low=["vc"] + ["cb%d" % i for i in range(8)],
                 calm=["cb%d" % i for i in range(8)] + ["tb%d" % i for i in range(8)] + ["t%d" % i for i in range(8)]),
            dict(name="core", match=r"xmth$|xrd\d$|xmbe$|xrb$|xmb\d$|xl|xh|xsb_|xq\d_|xd\d_|xrt$",
                 bytype=True,
                 low="vh vbn vl vbpl th tl vc".split(), victims=["vh", "vl"], calm="vbn vbpl tl th dtop bt run runb".split()),
            dict(name="logic", match=r"."),
        ]),
    # Crystal oscillator. Bottom: the amplifier and the feedback resistors (10 Mohm in 66 strips). Middle: the
    # current sources of the three settings with their switches. Top: the setting decoder, and the replica of the
    # amplifier with the Schmitt trigger and the output buffer it drives. The replica's output r1 runs on a third
    # of a microampere at 32 kHz: with the replica beside the amplifier it crossed all three blocks, 133 fF of
    # wire, and its slow edges cost 3.5 uA in the Schmitt trigger.
    # The two crystal pins have the outermost lines of the column.
    "rv328_xosc": dict(
        wmax=230.0, far=["vbp", "xo", "xi"],
        # setting 2 draws 1.2 mA from the supply through xmp2, xms2, the pin xo, the amplifier and its foot switch
        heavy=["avdd", "vss", "xo", "ft", "s1", "s2"], strong=r"xmn$|xmft$|xmp[12]$|xms[12]$",
        groups=[
            dict(name="amplifier", match=r"xmn$|xmft$|xrf$|xrg$|xtf_|xtg_|xie_",
                 low="xi rf rg ft xo".split(), victims=["xi", "rf", "rg"], calm=["ft", "on", "off", "ehf", "ehfb"]),
            dict(name="current sources", match=r"xmu|xmnb$|xmn5$|xmp|xms|xrl$|xml",
                 top=r"xmpb$|xmp1$|xmp2$|xmpr$|xmpq$|xmlb$|xml1$|xmlr$", bot=r".",      # the two mirrors, each in one row
                 last=r"xrl$|xmle$|xmlb$|xmlo$|xml1$|xms3$|xmlr$",                       # the replica's three switches together
                 low="lb lbs nb nbs pb vbp".split(), victims=["lb", "lbs"],
                 calm="nb nbs pb vbp e1n e2n e3n e3 ehf s1 s2 s3 sr sq s3r".split()),
            dict(name="logic", match=r".", low=["xi", "ftr", "r1", "on", "off"], victims=["r1"],
                 calm="xi ftr on off en m0 m1 m0b m1b e1 e2 e3 e1n e2n e3n ehf".split()),
        ]),
    # Brown-out detector. Bottom: the supply divider (5 Mohm in 90 strips), its tap switches, the hysteresis
    # switch and the comparator. Top: level decoding and output logic. The taps are megohm nodes with 2 %
    # (22 mV) of hysteresis between them and a wrong answer; the comparator's output stages stand in the same
    # block, so their leads keep their distance from the taps' and their tracks lie at the far side.
    "rv328_bod": dict(
        wmax=256.0, far=["vref"],
        groups=[
            dict(name="divider", match=r"xr\d$|xrh$|xc[tf]$|xmen$|xmh$|xt\d_|xc_xm(t|1|2|n1|n2|3|p3)$|xc_xtb_|xc_xpb$", bytype=True,
                 low="vref tap t43 t27 t23 nh top xc_tail xc_n1 xc_o1 xc_vbi vbp".split(), high="xc_o2 xc_o3 cmp low".split(),
                 victims="tap t43 t27 t23 nh xc_n1 xc_o1".split(),
                 calm="vref top xc_tail xc_vbi vbp s23 s23b s27 s27b s43 l1b en enb xc_enb".split()),
            dict(name="logic", match=r"."),
        ]),
    # Input multiplexer, one block: the eleven switches, and after them in the same two rows the decoder and each
    # switch's gate and inverter as standard cells. The selects do not move during a conversion, so nothing here
    # is small-signal in the sense of the other cells; the inputs and the output only keep to the far side of
    # the column and to the tracks next to ground.
    "rv328_amux": dict(
        wmax=WMAX_AMUX, far=["vbg", "vtemp"] + ["a%d" % i for i in range(8)] + ["out"],
        groups=[
            dict(name="rows", match=r".", bytype=True, last=r".*_x1$", low=["out"] + ["a%d" % i for i in range(8)] + ["vtemp", "vbg"]),
        ]),
}


def pack(lib, lines, W, top=None, bot=None, bytype=False):
    """Cut device lines into blocks of two rows, each row at most W long: [[(line, row)]]."""
    blocks, cur, x = [], [], {"top": 0.0, "bot": 0.0}
    for line in lines:
        w = sum(d.bbox[2] - d.bbox[0] + DEV_GAP for d, _, _ in generate(lib, line[2], line[3]))
        if top and re.match(top, line[0]):
            row = "top"
        elif bot and re.match(bot, line[0]):
            row = "bot"
        elif bytype and line[2] in ("pfet_06v0", "nfet_06v0"):
            row = "top" if line[2][0] == "p" else "bot"
        else:
            row = "top" if (line[2] in PASSIVE and not bytype) or x["top"] <= x["bot"] else "bot"
            if x[row] + w > W:
                row = "bot" if row == "top" else "top"
        if x[row] + w > W and cur:
            blocks.append(cur)
            cur, x = [], {"top": 0.0, "bot": 0.0}
        cur.append((line, row))
        x[row] += w
    blocks.append(cur)
    return blocks


def build(cell, files, outdir):
    os.makedirs(outdir, exist_ok=True)
    spec = STACK[cell]
    sub = subckts(files)
    pins = sub[cell][0]
    devices = flatten(cell, sub)
    groups = [[] for _ in spec["groups"]]
    for d in devices:
        for i, g in enumerate(spec["groups"]):
            if re.match(g["match"], d[0]) or i == len(groups) - 1:
                groups[i].append(d)
                break
    for i, g in enumerate(spec["groups"]):
        if "last" in g:                            # these devices after the others, both in the netlist's order
            groups[i].sort(key=lambda d: bool(re.match(g["last"], d[0])))

    # ---- the blocks: draw, measure, and pack shorter until every block is within wmax --------------------------------
    w = [spec["wmax"]] * len(groups)               # every group is packed shorter by itself
    while True:
        lib = Lib()
        packed = []                                # (index of the group, [(line, row)])
        for i, (g, lines) in enumerate(zip(spec["groups"], groups)):
            packed += [(i, blk) for blk in pack(lib, lines, w[i], g.get("top"), g.get("bot"), g.get("bytype"))]
        used = [set(n for l, _ in blk for n in l[1]) for _, blk in packed]
        cells, over = [], set()
        for i, (gi, blk) in enumerate(packed):
            g = spec["groups"][gi]
            others = set(pins).union(*(u for j, u in enumerate(used) if j != i))
            ports = [n for n in sorted(used[i]) if n in others]
            opts = {k: g[k] for k in ("low", "high", "victims", "calm", "full") if k in g}
            opts.update(heavy=spec.get("heavy", ()), strong=spec.get("strong"))
            b = make("%s_p%d" % (cell, i), [l for l, _ in blk], ports, lib, rows={l[0]: r for l, r in blk}, **opts)
            cells.append((g.get("name", "block %d" % i), b, ports))
            if b.bb.width() > spec["wmax"] and w[gi] > 40:
                over.add(gi)
        if not over:
            break
        for gi in over:
            w[gi] -= 5.0

    # ---- the stack ---------------------------------------------------------------------------------------------------
    top = lib.ly.create_cell(cell)
    y, placed, tracks, parts = 0.0, [], {}, []     # tracks: net -> [(x from, x to, y)] in the top cell
    half = {}                                      # and half the width of each of those tracks
    for name, b, ports in cells:
        bb = b.bb
        ox, oy = -bb.left, y - bb.bottom
        top.insert(kdb.DCellInstArray(b.top.cell_index(), kdb.DTrans(kdb.DVector(round(ox, 3), round(oy, 3)))))
        for n in ports:
            xa, xb, ty = b.span[n]
            tracks.setdefault(n, []).append((xa + ox, xb + ox, ty + oy))
            half.setdefault(n, []).append(b.tw[n] / 2)
        for d in b.placed:
            placed.append(dict(d, block=name, box=[d["box"][0] + ox, d["box"][1] + oy, d["box"][2] + ox, d["box"][3] + oy]))
        parts.append(dict(name=name, cell=b.top.name, box=[0.0, y, bb.width(), y + bb.height()], channel=[oy, oy + b.h],
                          inner=[(n, x + ox, ty + oy) for n, x, ty in b.inner]))
        y += bb.height() + GAP

    # ---- the column of Metal4 lines at the left: logic nearest the stack, then the supplies, then the `far` nets -----
    far, heavy = spec.get("far", []), spec.get("heavy", ())
    supplies = ("vss", "avdd")
    nets = sorted(tracks, key=lambda n: (2 + far.index(n) if n in far else 1 if n in supplies else 0, n))
    spine, labels, edge = {}, [], SP_X0
    for n in nets:
        wl = SUPPLY_W if n in supplies or n in heavy else SP_W
        x1, x2 = edge - wl, edge
        edge = x1 - SP_SPACE
        xs, ys = (x1 + x2) / 2, []
        for (xa, xb, ty), hw in zip(tracks[n], half[n]):
            lib.box(top, "metal3", x1, ty - hw, xa + 0.2, ty + hw)
            lib.contacts(top, x1, ty - hw, x2, ty + hw, layer="via3", size=VIA, space=0.36, enc=0.07)
            ys.append(ty)
        hw = max(half[n])
        lib.box(top, "metal4", x1, min(ys) - hw - 0.05, x2, max(ys) + hw + 0.05)
        spine[n] = (xs, min(ys), max(ys))
        if n in pins:
            lib.text(top, "metal4_label", n, xs, min(ys))
        else:
            labels.append((n, xs, min(ys)))
    assert set(pins) <= set(spine), set(pins) - set(spine)

    bb = top.dbbox()
    bbox = [bb.left - 1.0, bb.bottom - 1.0, bb.right + 1.0, bb.top + 1.0]
    lib.box(top, "pr_bndry", *bbox)
    lib.ly.write(os.path.join(outdir, cell + ".gds"))
    write_flat(os.path.join(outdir, cell + "_lvs.spice"), cell, pins, devices)

    # ---- a copy for extraction, in which every net carries its name ---------------------------------------------------
    for n, x, yy in labels:
        lib.text(top, "metal4_label", n, x, yy)
    for p in parts:
        for n, x, yy in p["inner"]:
            lib.box(top, "metal3", x - 0.2, yy - 0.2, x + 0.2, yy + 0.2)      # something of the top cell for the label to sit on
            lib.text(top, "metal3_label", n, x, yy)
    lib.ly.write(os.path.join(outdir, cell + "_named.gds"))

    json.dump({"bbox": bbox, "parts": [dict(p, inner=len(p["inner"])) for p in parts], "placed": placed,
               "spine": spine, "tracks": tracks, "blocks": {b.top.name: block_map(b) for _, b, _ in cells}},
              open(os.path.join(outdir, cell + "_map.json"), "w"))
    print("%s: %.1f x %.1f um = %.4f mm2; %d devices in the netlist, %d blocks, %d lines in the column" %
          (cell, bbox[2] - bbox[0], bbox[3] - bbox[1], (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) * 1e-6, len(devices), len(parts), len(spine)))
    for p in parts:
        print("   %-12s %6.1f x %5.1f um" % (p["name"], p["box"][2] - p["box"][0], p["box"][3] - p["box"][1]))


if __name__ == "__main__":
    cell, netlist, outdir = sys.argv[1:4]
    extra = sys.argv[4:] or [os.path.join(HERE, "..", "blocks", "logic.spice")]
    build(cell, [netlist] + extra, outdir)
