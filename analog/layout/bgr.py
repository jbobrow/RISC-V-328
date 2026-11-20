#!/usr/bin/env python3
"""Layout of the reference, rv328_bgr (analog/blocks/bgr.spice).

  bgr.py <output directory>     writes rv328_bgr.gds and rv328_bgr_lvs.spice

The netlist for LVS is made from analog/blocks/bgr.spice itself (parameters filled in, the one
inverter written out as its two transistors), so the layout is checked against what was simulated.
"""
import os
import re
import sys

from block import Block, pnp_array

HERE = os.path.dirname(os.path.abspath(__file__))
PDK = os.environ.get("PDK_DIR") or os.path.join(os.environ.get("PDK_ROOT", ""), "gf180mcuD")
NETS = ["vss", "sx", "enb", "en", "stb", "st", "ok", "o1", "n1", "tail", "b", "a", "b2", "e3", "vbg", "vref", "vbp", "avdd"]
PORTS = ["avdd", "vss", "en", "vref", "vbp", "ok"]


def lvs_netlist(path):
    text = open(os.path.join(HERE, "..", "blocks", "bgr.spice")).read()
    body = text[text.index(".subckt rv328_bgr"):text.index(".ends")]
    par = dict(re.findall(r"(\w+)=([\d.]+u)", re.search(r"^\.param (.*)$", body, re.M).group(1)))
    out = [".subckt rv328_bgr avdd vss en vref vbp ok"]
    for line in body.splitlines()[1:]:
        if not line.startswith("x"):
            continue
        t = line.split()
        if t[-1] == "rv328_inv":                         # xien avdd vss en enb rv328_inv: wp=2u wn=1u, lengths from logic.spice
            out.append("%sp %s %s %s %s pfet_06v0 w=2u l=0.55u" % (t[0], t[4], t[3], t[1], t[1]))
            out.append("%sn %s %s %s %s nfet_06v0 w=1u l=0.7u" % (t[0], t[4], t[3], t[2], t[2]))
            continue
        m = re.search(r"r_length=(\w+)(?:\s+s=(\d+))?", line)
        if m:                                            # s strips in series: LVS sees their total length
            total = float(par.get(m.group(1), m.group(1)).rstrip("u")) * int(m.group(2) or 1)
            line = line[:m.start()] + "r_length=%gu" % total + line[m.end():]
        line = re.sub(r"\s+par=\d+", "", line)
        out.append(line)
    out.append(".ends")
    open(path, "w").write("\n".join(out) + "\n")


def build(outdir):
    b = Block("rv328_bgr", NETS, PORTS)
    lib = b.lib

    def mos(name, kind, w, l, nf, row, d, g, s, bulk, **kw):
        b.add(lib.mos(kind, w, l, nf, **kw), row, {"D@1": d, "G": g, "S@0": s, "B": bulk}, name=name, kind=kind + "mos")

    # top row: PMOS, then the two bandgap resistors, the short arm of the divider and the capacitors
    for i, d in enumerate(("a", "b", "vbg")):                     # xmp1 xmp2 xmp3: the three matched unit currents
        mos("xmp%d" % (i + 1), "p", 16, 8, 1, "top", d, "vbp", "avdd", "avdd")
    mos("xmpd", "p", 16, 8, 1, "top", "vbp", "vbp", "avdd", "avdd")        # xmpd
    mos("xmt", "p", 8, 8, 1, "top", "tail", "vbp", "avdd", "avdd")        # xmt
    mos("xmsp", "p", 8, 8, 1, "top", "st", "vbp", "avdd", "avdd")          # xmsp
    mos("xma", "p", 10, 4, 4, "top", "n1", "a", "tail", "avdd")           # xma  40u/4u as four fingers
    mos("xmb", "p", 10, 4, 4, "top", "o1", "b", "tail", "avdd")           # xmb
    mos("xmi1", "p", 1, 2, 1, "top", "stb", "st", "avdd", "avdd")          # xmi1
    mos("xmoff", "p", 2, 0.6, 1, "top", "vbp", "en", "avdd", "avdd")        # xmoff
    mos("xmo1", "p", 1, 1, 1, "top", "ok", "stb", "avdd", "avdd")          # xmo1
    mos("xien p", "p", 2, 0.55, 1, "top", "enb", "en", "avdd", "avdd")       # xien, PMOS
    b.add(lib.res(13.4, 1), "top", {"A": "b", "B": "b2", "SUB": "vss"}, name="xr1", kind="res")        # xr1: one unit
    b.add(lib.res(13.4, 10), "top", {"A": "vbg", "B": "e3", "SUB": "vss"}, name="xr2", kind="res")     # xr2: ten of the same unit
    b.add(lib.res(35, 2), "top", {"A": "vbg", "B": "vref", "SUB": "vss"}, name="xra", kind="res")      # xra: two strips of sixty-nine
    b.add(lib.cap(30, 30), "top", {"T": "vref", "Bot": "vss"}, name="xcr", kind="cap")                 # xcr
    b.add(lib.cap(36, 36), "top", {"T": "o1", "Bot": "vss"}, name="xcc", kind="cap")                   # xcc

    # bottom row: NMOS, the bipolars, the long arm of the divider and the start-up resistor
    mos("xmn1", "n", 8, 8, 1, "bot", "n1", "n1", "vss", "vss")             # xmn1
    mos("xmn2", "n", 8, 8, 1, "bot", "o1", "n1", "vss", "vss")             # xmn2
    mos("xm6", "n", 8, 8, 4, "bot", "vbp", "o1", "vss", "vss")            # xm6  32u/8u as four fingers
    mos("xmi2", "n", 1, 2, 1, "bot", "stb", "st", "vss", "vss")            # xmi2
    mos("xms", "n", 2, 1, 1, "bot", "vbp", "stb", "sx", "vss")            # xms
    mos("xmse", "n", 2, 1, 1, "bot", "sx", "en", "vss", "vss")             # xmse
    mos("xmoff2", "n", 1, 0.7, 1, "bot", "o1", "enb", "vss", "vss")          # xmoff2
    mos("xmo2", "n", 1, 1, 1, "bot", "ok", "stb", "vss", "vss")            # xmo2
    mos("xien n", "n", 1, 0.7, 1, "bot", "enb", "en", "vss", "vss")          # xien, NMOS
    # xq1 in the middle of the eight that make xq2; xq3 beside them
    arr = pnp_array(lib, os.path.join(PDK, "libs.ref", "gf180mcu_fd_pr", "gds", "pnp_10p00x10p00.gds"),
                    [["b2", "b2", "b2", None], ["b2", "a", "b2", "e3"], ["b2", "b2", "b2", None]])
    b.add(arr, "bot", {"a": "a", "b2": "b2", "e3": "e3", "C": "vss"}, gap=3.0, name="xq1 xq2 xq3", kind="pnp")
    b.add(lib.res(35, 67), "bot", {"A": "vref", "B": "vss", "SUB": "vss"}, name="xrb", kind="res")     # xrb: the other sixty-seven
    b.add(lib.res(35, 60), "bot", {"A": "st", "B": "vss", "SUB": "vss"}, name="xrs", kind="res")       # xrs
    bb = b.route()
    os.makedirs(outdir, exist_ok=True)
    b.write(os.path.join(outdir, "rv328_bgr.gds"))
    lvs_netlist(os.path.join(outdir, "rv328_bgr_lvs.spice"))
    import json
    json.dump({"placed": b.placed, "nets": NETS, "h": b.h, "bbox": [bb.left, bb.bottom, bb.right, bb.top],
               "tracks": {n: b.track_y(n) for n in NETS}}, open(os.path.join(outdir, "bgr_map.json"), "w"))
    print("rv328_bgr: %.1f x %.1f um = %.4f mm2, %d placed cells, %d leads" % (bb.width(), bb.height(), bb.width() * bb.height() * 1e-6, b.count, len(b.leads)))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out"))
