#!/usr/bin/env python3
"""Wiring capacitance of the ADC capacitor array, and what it does to the converter.

  pex.py [work directory]        needs klayout.db, magic, and PDK_DIR (gf180mcuD) or PDK_ROOT (its parent)

magic extracts a MIM capacitor correctly as a device, but for wiring capacitance it treats the
top plate as if it were Metal4, so the Metal3 tracks under a capacitor appear coupled to the top
plate when in the silicon the bottom plate lies in between.  The wiring is therefore extracted
from a copy of the layout without the capacitor layers (FuseTop, its markers and the Via4 on it):
plain Metal4 plates under plain Metal5 covers.  From that result the parallel-plate capacitance
between a cover and the plate under it is taken off again, because the capacitor itself is there
instead.  The fringe from the edge of a cover to its own plate is left in; the foundry model has a
perimeter term that probably contains it already, and it is the same for every unit anyway.

Writes rv328_adc_caparray_pex.spice next to this script (the cell of blocks/adccap.spice plus the
wiring) and reports/caparray_pex.md, and caparray_pex.json in the work directory for the figures.
"""
import json
import os
import re
import subprocess
import sys

import klayout.db as kdb

HERE = os.path.dirname(os.path.abspath(__file__))
PDK = os.environ.get("PDK_DIR") or os.path.join(os.environ.get("PDK_ROOT", ""), "gf180mcuD")
CELL = "rv328_adc_caparray"
DROP = [(75, 0), (117, 5), (117, 10), (41, 0)]           # FuseTop, CAP_MK, MIM_L_MK, Via4
COVER_AREA = 25.0                                        # um2 of Metal5 over Metal4 that is really the capacitor
M5_M4 = {"nominal": 39.351, "high": 46.417, "low": 34.152}   # aF/um2, from the magic technology file
STYLE = {"nominal": "ngspice()", "high": "ngspice(hrhc)", "low": "ngspice(lrlc)"}
CU = 54.52e-15                                           # one unit in the foundry model: 1.99 fF/um2 and 0.2383 fF/um
UNIT = {"f": 1e-15, "p": 1e-12, "a": 1e-18, "n": 1e-9}


def metal_view(src, dst):
    ly = kdb.Layout()
    ly.read(src)
    for lay, dt in DROP:
        idx = ly.find_layer(lay, dt)
        if idx is not None:
            ly.clear_layer(idx)
    top = ly.cell(CELL)
    top.flatten(True)
    ly.write(dst)


def extract(gds, work, corner):
    out = os.path.join(work, "metal_%s.spice" % corner)
    tcl = os.path.join(work, "pex_%s.tcl" % corner)
    open(tcl, "w").write("\n".join([
        "gds read %s" % gds, "load %s" % CELL, "select top cell",
        "extract style %s" % STYLE[corner], "extract all",
        "ext2spice cthresh 0", "ext2spice rthresh infinite", "ext2spice format ngspice",
        "ext2spice -o %s" % out, "quit -noprompt", ""]))
    rc = os.path.join(PDK, "libs.tech", "magic", "gf180mcuD.magicrc")
    p = subprocess.run(["magic", "-dnull", "-noconsole", "-rcfile", rc, tcl], cwd=work, capture_output=True, text=True,
                       env=dict(os.environ, PDK="gf180mcuD", PDK_ROOT=os.path.dirname(os.path.abspath(PDK))))
    open(os.path.join(work, "pex_%s.log" % corner), "w").write(p.stdout + p.stderr)
    caps = {}
    for m in re.finditer(r"^C\d+\s+(\S+)\s+(\S+)\s+([0-9.eE+-]+)([fpan]?)", open(out).read(), re.M):
        a, b = (n.lower() for n in m.group(1, 2))
        a, b = ("vss" if a == "vsubs" else a), ("vss" if b == "vsubs" else b)     # the substrate is analog ground
        if a == b:
            continue
        key = tuple(sorted((a, b)))
        caps[key] = caps.get(key, 0.0) + float(m.group(3)) * UNIT.get(m.group(4), 1.0)
    return caps


def units_of(netlist):
    """{(top net, bottom net): number of units} from the schematic cell."""
    n = {}
    for m in re.finditer(r"^x\S+\s+(\S+)\s+(\S+)\s+cap_mim_2f0fF.*?m=(\d+)", netlist, re.M):
        n[(m.group(1), m.group(2))] = int(m.group(3))
    return n


def linearity(weight, wx):
    """Transition positions of an ideal converter built on these bit weights, as errors in LSB."""
    total = sum(weight) + wx
    inl, dnl, prev = [], [], 0.0
    for k in range(1, 1024):
        pos = sum(w for i, w in enumerate(weight) if (k >> i) & 1) / total * 1024
        inl.append(pos - k)
        dnl.append(pos - prev - 1)
        prev = pos
    return inl, dnl


def main(work):
    work = os.path.abspath(work)
    os.makedirs(work, exist_ok=True)
    gds = os.path.join(work, "rv328_adc_caparray.gds")
    mgds = os.path.join(work, "caparray_metal.gds")
    metal_view(gds, mgds)
    schem = open(os.path.join(HERE, "..", "blocks", "adccap.spice")).read()
    units = units_of(schem)
    result = {}
    for corner in ("nominal", "high", "low"):
        caps = extract(mgds, work, corner)
        for (tp, bt), n in units.items():                 # the cover over its plate is the capacitor, not wiring
            key = tuple(sorted((tp, bt)))
            caps[key] = caps[key] - n * COVER_AREA * M5_M4[corner] * 1e-18
        result[corner] = caps
    nom = result["nominal"]
    bits = ["b%d" % i for i in range(10)]

    # extracted netlist: the schematic cell plus the wiring, substrate folded into vss
    body = schem[schem.index(".subckt"):schem.index(".ends")].rstrip()
    lines = ["* ADC capacitor array with the wiring capacitance of its layout (nominal). Written by analog/layout/pex.py",
             "* from rv328_adc_caparray.gds; same cell and pins as blocks/adccap.spice. Substrate counted as vss.",
             body, "* wiring"]
    for (a, b), c in sorted(nom.items()):
        if c > 0.5e-18:
            lines.append("cw_%s_%s %s %s %.4ff" % (a, b, a, b, c * 1e15))
    lines.append(".ends")
    open(os.path.join(HERE, "rv328_adc_caparray_pex.spice"), "w").write("\n".join(lines) + "\n")

    # report
    def c(caps, a, b):
        return caps.get(tuple(sorted((a, b))), 0.0)

    rep = ["# ADC capacitor array: wiring capacitance extracted from the layout", "",
           "Extracted with magic from a metal-only copy of `rv328_adc_caparray.gds` (see `analog/layout/pex.py` for why),",
           "nominal wiring corner. One unit is %.2f fF in the foundry model." % (CU * 1e15), "",
           "| Capacitor | Units | Design value (fF) | Top plate to its bottom plate, wiring (fF) | per unit (fF) | Bottom plate to ground (fF) | to other bottom plates (fF) |",
           "|---|---|---|---|---|---|---|"]
    per_unit = {}
    for net in bits[::-1] + ["bx"]:
        n = units[("top", net)]
        par = c(nom, "top", net)
        per_unit[net] = par / n
        others = sum(v for (a, b), v in nom.items() if net in (a, b) and "top" not in (a, b) and "vss" not in (a, b) and "dum" not in (a, b))
        rep.append("| %s | %d | %.1f | %.2f | %.3f | %.0f | %.0f |" % (net, n, n * CU * 1e15, par * 1e15, per_unit[net] * 1e15,
                                                                 c(nom, net, "vss") * 1e15, others * 1e15))
    top_gnd = {k: c(result[k], "top", "vss") for k in result}
    dum_gnd = {k: c(result[k], "dum", "vss") for k in result}
    rep += ["",
            "Other wiring on the two comparator inputs (nominal): top plate to ground %.2f pF on top of the %.1f pF of the 512 units"
            % (top_gnd["nominal"] * 1e12, 512 * CU * 1e12),
            "(the top plate then moves by %.3f of an array step instead of %.3f); reference side to ground %.2f pF on top of %.1f pF;"
            % (1024 * CU / (1536 * CU + top_gnd["nominal"] + sum(c(nom, "top", b) for b in bits + ["bx"])), 1024 / 1536,
               dum_gnd["nominal"] * 1e12, 384 * CU * 1e12),
            "top plate to reference side %.1f fF; reference side to all bottom plates %.1f fF."
            % (c(nom, "top", "dum") * 1e15, sum(c(nom, "dum", b) for b in bits + ["bx"]) * 1e15), "",
            "## Effect on linearity", "",
            "Bit weights are the design capacitance plus the wiring between the top plate and that bit's bottom plates.",
            "Only the part of the wiring that is not in proportion to the number of units moves a transition.", "",
            "| Wiring corner | Largest INL (LSB) | Largest DNL (LSB) | at code | Gain error (LSB at full scale) |", "|---|---|---|---|---|"]
    data = {"per_unit_fF": {k: v * 1e15 for k, v in per_unit.items()}, "corners": {}}
    for corner in ("low", "nominal", "high"):
        caps = result[corner]
        w = [units[("top", b)] * CU + c(caps, "top", b) for b in bits]
        wx = CU + c(caps, "top", "bx")
        inl, dnl = linearity(w, wx)
        ideal_ratio = [wi / w[9] * 512 for wi in w]
        worst_dnl = max(range(1023), key=lambda i: abs(dnl[i]))
        rep.append("| %s | %+.4f | %+.4f | %d | %+.3f |" % (corner, max(inl, key=abs), dnl[worst_dnl], worst_dnl + 1, inl[-1]))
        data["corners"][corner] = {"inl": inl, "dnl": dnl, "weights_units": ideal_ratio,
                                   "top_gnd_pF": top_gnd[corner] * 1e12, "dum_gnd_pF": dum_gnd[corner] * 1e12}
    data["caps_fF"] = {"%s %s" % k: v * 1e15 for k, v in sorted(nom.items())}
    os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
    open(os.path.join(HERE, "reports", "caparray_pex.md"), "w").write("\n".join(rep) + "\n")
    json.dump(data, open(os.path.join(work, "caparray_pex.json"), "w"))
    print("\n".join(rep))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out"))
