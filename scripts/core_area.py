#!/usr/bin/env python3
"""What fills the core of a routed layout, from its DEF and the library LEF files.

  core_area.py <chip.def or chip.def.gz> <pdk>/gf180mcuD [more LEF files or directories]

The flow's own metric for standard-cell area (design__instance__area__stdcell) counts the four corner cells
of the pad ring as standard cells, half a square millimetre. This adds up the cells by what they are.
"""
import collections
import glob
import gzip
import json
import os
import re
import sys


def kind(c):
    if "_fd_io__" in c:
        return "pad ring"
    if "_ws_ip__" in c:
        return "identification cells (in the corners of the pad ring)"
    if "_fd_sc_" not in c:
        return "memories"
    name = c.split("__")[-1]
    if name == "filltie" or name == "endcap":
        return "taps and row ends"
    if name.startswith("fill"):
        return "fill and decoupling cells"
    return "logic cells"


def main(path, pdk, extra):
    text = (gzip.open(path, "rt") if path.endswith(".gz") else open(path)).read()
    core = [float(v) for v in re.search(r"CORE_AREA: \[([^\]]+)\]", open(os.path.join(os.path.dirname(__file__), "..", "flow", "librelane", "slot_1x0p5.yaml")).read()).group(1).split(",")]
    size = {}
    files = glob.glob(os.path.join(pdk, "libs.ref", "*", "lef", "*.lef"))
    for e in extra:
        files += glob.glob(os.path.join(e, "**", "*.lef"), recursive=True) if os.path.isdir(e) else [e]
    for f in files:
        for m in re.finditer(r"MACRO\s+(\S+).*?SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", open(f, errors="ignore").read(), re.S):
            size.setdefault(m.group(1), float(m.group(2)) * float(m.group(3)))
    comp = text[text.index("COMPONENTS"):text.index("END COMPONENTS")]
    count = collections.Counter(m.group(1) for m in re.finditer(r"^\s*-\s+\S+\s+(\S+)", comp, re.M))
    area, n = collections.Counter(), collections.Counter()
    for c, k in count.items():
        area[kind(c)] += k * size[c] * 1e-6
        n[kind(c)] += k
    core_mm2 = (core[2] - core[0]) * (core[3] - core[1]) * 1e-6
    print("| In the core (%.2f mm2) | Cells | Area (mm2) |\n|---|---|---|" % core_mm2)
    for k in ("memories", "logic cells", "taps and row ends", "fill and decoupling cells"):
        print("| %s | %d | %.3f |" % (k, n[k], area[k]))
    std = area["logic cells"] + area["taps and row ends"]
    rows = std + area["fill and decoupling cells"]
    print("\nStandard cells without fill: %.2f mm2, %.0f %% of the %.2f mm2 of cell rows (the rest of the core is memories and the margins around them)."
          % (std, 100 * std / rows, rows))
    macro = json.load(open(os.path.join(os.path.dirname(__file__), "..", "analog", "layout", "reports", "macro.json")))
    w, h = macro["width"], macro["height"]
    for label, a in (("the analog macro as drawn, %.0f x %.0f um plus 10 um all round" % (w, h), (w + 20) * (h + 20) * 1e-6), ("an analog macro of 1.0 mm2 plus margin", 1.03)):
        print("With %s in those rows: %.0f %% full." % (label, 100 * std / (rows - a)))
    corners = sum(k * size[c] for c, k in count.items() if c.endswith("__cor")) * 1e-6
    print("Pad ring: %.2f mm2, of which the corner cells %.2f mm2." % (area["pad ring"], corners))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
