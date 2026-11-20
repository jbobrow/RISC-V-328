#!/usr/bin/env python3
"""Layout of the ADC front end, rv328_adcfe.

  adcfe.py [output directory]         draw it: rv328_adcfe.gds, rv328_adcfe_lvs.spice, adcfe_map.json
  adcfe.py [output directory] --pex   also extract it: analog/layout/rv328_adcfe_pex.spice

Three kinds of cell are stacked, from the top: the capacitor array (caparray.py), the comparator
(the same cell autoblock.py draws by itself), and everything else in the netlist, cut into blocks
no wider than the array: first the capacitors, resistors and bias devices, then the sequencer, the
ten bit drivers and the bottom-plate switches.  Each block wires its own nets (block.py).  Nets
that leave a block run on vertical Metal4 lines in a column to the left of the stack, one line per
net, and every block's Metal3 track of that net is extended to its line.  The array's Metal2 buses
reach the same lines.  Only the top plate and the reference side, the two small-signal nodes, are
kept away from that column: they come down from the array on Metal5 at the right.
"""
import json
import os
import re
import sys

import klayout.db as kdb

import caparray
import pex_block
from autoblock import ORDER, block_map, flat_lines, flatten, generate, make, std_netlists, subckts
from block import DEV_GAP
from devices import SC, VIA, Lib

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCKS = os.path.join(HERE, "..", "blocks")
CELL = "rv328_adcfe"
WMAX = 344.0                   # widest block; the array's columns end at 350
GAP = 3.0                      # between stacked cells
SP_W, SP_PITCH, SP_X0 = 0.40, 0.90, -3.0     # Metal4 lines of the column
# Tracks next to ground inside a block. The first two are the small-signal nets; they lie between ground and
# the level they are sampled at, and those two tracks run the whole length of the block as screens.
QUIET = ["top", "dum", "vcm", "vbp", "en"]
RIGHT = {"top": (356.3, 358.3), "dum": (351.3, 353.3)}      # Metal5 lines, in the array's x coordinates
PASSIVE = ("cap_mim_2f0fF", "ppolyf_u_1k_6p0", "ppolyf_u")


BIAS = ("xcvc", "xrv1", "xrv2", "xmv", "xmv2", "xmt", "xmd")


def ordered(lines):
    """The netlist's devices in the order they are placed, as groups; each group starts a block of its own.
    First the top-plate switches with their bias divider: the only block besides the comparator that touches
    the top plate and the reference side, and nothing in it moves once the top plate has been released. (In
    one block with the sequencer, every lead that crossed those two tracks put 0.25 fF on each.)
    Then the rest, tall devices first so that they share rows, the bottom-plate switches last."""
    bias = [l for n in BIAS for l in lines if l[0] == n]
    lines = [l for l in lines if l not in bias]
    first = [l for l in lines if l[2] in PASSIVE]
    first.sort(key=lambda l: (l[2] != "cap_mim_2f0fF", -float(l[3].get("c_width", "0u")[:-1])))
    sw = [l for l in lines if re.match(r"x(tip|tin|trp|trn|tg)\d$|xtix_|xtgx$", l[0])]
    sw.sort(key=lambda l: (-int(re.search(r"\d", l[0]).group()) if re.search(r"\d", l[0]) else 1))
    rest = [l for l in lines if l not in first and l not in sw]
    # The plain gates are foundry standard cells and get blocks of their own: such a block is wired at minimum
    # pitch, which is right for logic and not for the switches, whose tracks carry the capacitors' charge.
    gates = [l for l in rest if l[2].startswith(SC)]
    rest = [l for l in rest if l not in gates]
    return [bias, first + rest, gates, sw]


def pack(lib, groups, W):
    """Cut the groups into blocks of two rows, each row at most W long: [[(line, row)]]."""
    blocks = []
    for lines in groups:
        cur, x = [], {"top": 0.0, "bot": 0.0}
        for line in lines:
            w = sum(d.bbox[2] - d.bbox[0] + DEV_GAP for d, _, _ in generate(lib, line[2], line[3]))
            # capacitors and resistors, the tall devices, in the upper row; transistors in whichever row is shorter,
            # so that both rows grow together (a lead finds room among those of the row opposite only near its end)
            row = "top" if line[2] in PASSIVE or x["top"] <= x["bot"] else "bot"
            if x[row] + w > W:
                row = "bot" if row == "top" else "top"
            if x[row] + w > W:
                blocks.append(cur)
                cur, x, row = [], {"top": 0.0, "bot": 0.0}, "top"
            cur.append((line, row))
            x[row] += w
        blocks.append(cur)
    return blocks


def build(outdir, pex=False):
    os.makedirs(outdir, exist_ok=True)
    files = [os.path.join(BLOCKS, f) for f in ("adcfe.spice", "logic.spice")]
    sub = subckts(files)
    pins = sub[CELL][0]
    lines = flatten(CELL, sub)
    cap_line = [l for l in lines if l[2] == "rv328_adc_caparray"][0]
    cmp_line = [l for l in lines if l[2] == "rv328_adccmp"][0]
    lines = ordered([l for l in lines if l not in (cap_line, cmp_line)])

    # ---- the blocks --------------------------------------------------------------------------------------------------
    # Rows are packed to a length; leads that have to step aside for one another then add to it, by an amount
    # only the drawing shows. So draw, measure, and pack shorter until every block is within WMAX.
    outside = set(pins) | set(cap_line[1]) | set(cmp_line[1])
    w = WMAX - 6.0
    while True:
        lib = Lib()
        packed = pack(lib, lines, w)
        used = [set(n for l, _ in blk for n in l[1]) for blk in packed]
        cells = []                                 # (name, Block, {block net: net of the front end})
        for i, blk in enumerate(packed):
            others = outside.union(*(u for j, u in enumerate(used) if j != i))
            ports = [n for n in sorted(used[i]) if n in others]
            b = make("%s_p%d" % (CELL, i), [l for l, _ in blk], ports, lib, low=QUIET, calm=QUIET[2:], victims=QUIET[:2], full=["vss", "vcm"], rows={l[0]: r for l, r in blk})
            cells.append((b.top.name, b, {n: n for n in ports}))
        if max(b.bb.width() for _, b, _ in cells) <= WMAX:
            break
        w -= 6.0
    csub = subckts([os.path.join(BLOCKS, "adccmp.spice"), files[1]])
    cmp_devs = flatten("rv328_adccmp", csub)
    bc = make("rv328_adccmp", cmp_devs, csub["rv328_adccmp"][0], lib, **ORDER["rv328_adccmp"])
    cells.append(("rv328_adccmp", bc, dict(zip(csub["rv328_adccmp"][0], cmp_line[1]))))

    # ---- the stack: switches at the bottom, comparator under the array -----------------------------------------------
    top = lib.ly.create_cell(CELL)
    order = cells[:-1][::-1] + cells[-1:]
    y, placed, tracks, parts = 0.0, [], {}, []     # tracks: net -> [(x from, x to, y)] in the top cell
    half = {}                                      # and half the width of each of those tracks
    for name, b, netmap in order:
        bb = b.bb
        ox, oy = -bb.left, y - bb.bottom
        top.insert(kdb.DCellInstArray(b.top.cell_index(), kdb.DTrans(kdb.DVector(round(ox, 3), round(oy, 3)))))
        for n, (xa, xb, ty) in b.span.items():
            if n in netmap:
                tracks.setdefault(netmap[n], []).append((xa + ox, xb + ox, ty + oy))
                half.setdefault(netmap[n], []).append(b.tw[n] / 2)
        prefix = "xcmp_" if name == "rv328_adccmp" else ""
        for d in b.placed:
            placed.append(dict(d, name=prefix + d["name"], block=name, box=[d["box"][0] + ox, d["box"][1] + oy, d["box"][2] + ox, d["box"][3] + oy]))
        parts.append(dict(name=name, box=[0.0, y, bb.width(), y + bb.height()], channel=[oy, oy + b.h],
                          inner=[(prefix + n, x + ox, ty + oy) for n, x, ty in b.inner]))
        y += bb.height() + GAP
    caparray.build(outdir)
    lib.ly.read(os.path.join(outdir, "rv328_adc_caparray.gds"))
    arr = lib.ly.cell("rv328_adc_caparray")
    ay = y + 1.0 - arr.dbbox().bottom
    arr_inst = top.insert(kdb.DCellInstArray(arr.cell_index(), kdb.DTrans(kdb.DVector(0, round(ay, 3)))))
    parts.append(dict(name="rv328_adc_caparray", box=[arr.dbbox().left, y + 1.0, arr.dbbox().right, y + 1.0 + arr.dbbox().height()], inner=[]))

    # ---- the column of Metal4 lines at the left ----------------------------------------------------------------------
    h = caparray.CW / 2
    bus = {}                                       # the array's Metal2 buses: net -> (left end, y of its middle)
    for i, net in enumerate(caparray.BUSES):
        y2 = -h - caparray.ENC_Y - caparray.BUS_TOP - i * caparray.BUS_PITCH
        bus[net] = (-h - caparray.ENC_X - 4.0, ay + y2 - caparray.BUS_W / 2)
    nets = [n for n in tracks if n not in RIGHT and (len(tracks[n]) > 1 or n in bus or n in pins)]
    # Nearest the stack: the logic. Then the supplies and the two static control lines, as a screen. Farthest:
    # the input, the reference and the bottom plates. A block's track reaches its line on Metal3 across all
    # the lines in between, 0.05 fF per crossing, so in this order only the analog nets' own tracks cross the
    # logic, and only where bottom-plate switches are. (With the analog lines nearest, the two tracks of the
    # slow clamp control azc crossed all of them: 0.4 fF, and its edge, which is the sampling instant, pulled
    # the input down by 0.1 mV at 5.5 V.)
    calm = ("vss", "avdd", "vbp", "en")
    nets.sort(key=lambda n: (3 if n in bus and n != "vss" else 2 if n in ("ain", "vrefp") else 1 if n in calm else 0, n))
    spine, labels = {}, []
    for i, n in enumerate(nets):
        xs = SP_X0 - i * SP_PITCH
        ys = []
        for (xa, xb, ty), hw in zip(tracks[n], half[n]):
            lib.box(top, "metal3", xs - SP_W / 2, ty - hw, xa + 0.2, ty + hw)
            lib.box(top, "via3", xs - VIA / 2, ty - VIA / 2, xs + VIA / 2, ty + VIA / 2)
            ys.append(ty)
        if n in bus:
            bx, by = bus[n]
            lib.box(top, "metal2", xs - SP_W / 2, by - 0.20, bx + 0.5, by + 0.20)
            lib.box(top, "metal3", xs - SP_W / 2, by - 0.20, xs + SP_W / 2, by + 0.20)
            for lay in ("via2", "via3"):
                lib.box(top, lay, xs - VIA / 2, by - VIA / 2, xs + VIA / 2, by + VIA / 2)
            ys.append(by)
        lib.box(top, "metal4", xs - SP_W / 2, min(ys) - 0.25, xs + SP_W / 2, max(ys) + 0.25)
        spine[n] = (xs, min(ys), max(ys))
        if n in pins:
            lib.text(top, "metal4_label", n, xs, min(ys))
        else:
            labels.append(("metal4", n, xs, min(ys)))
    assert set(pins) <= set(spine), set(pins) - set(spine)

    # ---- top plate and reference side: Metal5 at the right -----------------------------------------------------------
    xr = (caparray.NCOL - 1) * caparray.PX + h
    for n, (x1, x2) in RIGHT.items():
        ylow = min(ty for _, _, ty in tracks[n])
        if n == "top":
            yhigh = ay + caparray.ROW_LO * caparray.PY - h + 0.5          # into the array's collector bar
        else:
            for r in range(caparray.ROW_LO):                             # the four rows below the converter's
                lib.box(top, "metal5", xr - 1.0, ay + r * caparray.PY - 0.5, x2, ay + r * caparray.PY + 0.5)
            yhigh = ay + (caparray.ROW_LO - 1) * caparray.PY + 0.5
        lib.box(top, "metal5", x1, ylow - 0.6, x2, yhigh)
        for xa, xb, ty in tracks[n]:
            lib.box(top, "metal3", xb - 0.2, ty - 0.20, x2, ty + 0.20)
            lib.box(top, "metal4", x1, ty - 0.20, x2, ty + 0.20)
            for lay in ("via3", "via4"):
                lib.contacts(top, x1, ty - 0.20, x2, ty + 0.20, layer=lay, size=VIA, space=0.36, enc=0.07)
        labels.append(("metal5", n, (x1 + x2) / 2, ylow))

    bb = top.dbbox()
    lib.box(top, "pr_bndry", bb.left - 1.0, bb.bottom - 1.0, bb.right + 1.0, bb.top + 1.0)
    gds = os.path.join(outdir, CELL + ".gds")
    lib.ly.write(gds)

    # ---- the netlist LVS compares with: everything flat except the array ---------------------------------------------
    full = subckts(files + [os.path.join(BLOCKS, "adccmp.spice")])
    devices = flatten(CELL, full)
    arr_text = open(os.path.join(BLOCKS, "adccap.spice")).read()
    open(os.path.join(outdir, CELL + "_lvs.spice"), "w").write(
        std_netlists(devices) + arr_text + "\n.subckt %s %s\n%s\n.ends\n" % (CELL, " ".join(pins), "\n".join(flat_lines(devices))))

    # ---- a copy for extraction: every net named, and without the array (its own extraction is pex.py) ----------------
    arr_inst.delete()
    for lay, n, x, yy in labels:
        lib.text(top, lay + "_label", n, x, yy)
    for p in parts:
        for n, x, yy in p["inner"]:
            lib.box(top, "metal3", x - 0.2, yy - 0.2, x + 0.2, yy + 0.2)      # something of the top cell for the label to sit on
            lib.text(top, "metal3_label", n, x, yy)
    lib.ly.write(os.path.join(outdir, CELL + "_noarray_named.gds"))

    bbox = [bb.left - 1.0, bb.bottom - 1.0, bb.right + 1.0, bb.top + 1.0]
    json.dump({"bbox": bbox, "parts": [dict(p, inner=len(p["inner"])) for p in parts], "placed": placed,
               "spine": spine, "right": {n: list(v) for n, v in RIGHT.items()}, "array_y": ay,
               "tracks": {n: v for n, v in tracks.items()}}, open(os.path.join(outdir, "adcfe_map.json"), "w"))
    print("%s: %.1f x %.1f um = %.4f mm2; %d blocks from the netlist, %d devices placed, %d lines in the column" %
          (CELL, bbox[2] - bbox[0], bbox[3] - bbox[1], (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) * 1e-6, len(packed), len(placed), len(spine)))
    for p in parts:
        print("   %-22s %6.1f x %5.1f um" % (p["name"], p["box"][2] - p["box"][0], p["box"][3] - p["box"][1]))
    if pex:
        extract(outdir, cap_line)


def extract(outdir, cap_line):
    """Netlist of the layout with its wiring capacitance. The array is left out of the extraction and put
    back as a cell, so that the benches can use either its schematic or its own extracted netlist."""
    tmp = os.path.join(outdir, "pexfe")
    os.makedirs(tmp, exist_ok=True)
    gds = os.path.join(tmp, CELL + ".gds")
    ly = kdb.Layout()
    ly.read(os.path.join(outdir, CELL + "_noarray_named.gds"))
    ly.write(gds)
    out = os.path.join(HERE, CELL + "_pex.spice")
    pex_block.main(gds, CELL, os.path.join(BLOCKS, "adcfe.spice"), out)
    text = open(out).read().rstrip().splitlines()
    assert text[-1].strip() == ".ends", text[-1]
    text[-1:] = ["* the capacitor array, a cell of its own (blocks/adccap.spice or its extracted netlist)",
                 "%s %s %s" % (cap_line[0], " ".join(cap_line[1]), cap_line[2]), ".ends"]
    open(out, "w").write("\n".join(text) + "\n")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    build(args[0] if args else os.path.join(HERE, "out"), pex="--pex" in sys.argv)
