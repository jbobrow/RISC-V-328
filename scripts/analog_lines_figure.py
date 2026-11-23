#!/usr/bin/env python3
"""Picture of the drawn analog lines (scripts/analog_straps.py) over the chip outline.

Two stages, because OpenROAD's Python has no matplotlib:
  openroad -python -exit scripts/analog_lines_figure.py dump <chip_top.odb> <boxes.json>
  /usr/bin/python3 scripts/analog_lines_figure.py draw <boxes.json> <out.png>
"""
import json
import sys

NETS = ["A_ADC%d" % k for k in range(8)] + ["A_AIN0", "A_AIN1", "A_AREF", "A_XTAL1", "A_XTAL2", "A_AVCC"]


def dump(src, dst):
    import odb
    from openroad import Tech, Design
    tech = Tech()
    design = Design(tech)
    design.readDb(src)
    block = design.getBlock()
    u = block.getDbUnitsPerMicron()
    T = lambda v: v / u
    box = lambda r: [T(r.xMin()), T(r.yMin()), T(r.xMax()), T(r.yMax())]
    out = dict(die=box(block.getDieArea()), core=box(block.getCoreArea()), macros=[], pads={}, nets={})
    for inst in block.getInsts():
        m = inst.getMaster()
        if m.isBlock():
            out["macros"].append(dict(name=inst.getName(), master=m.getName(), box=box(inst.getBBox())))
        if m.isPad() and inst.getName().startswith("apad_"):
            out["pads"][inst.getName()] = box(inst.getBBox())
    for name in NETS:
        n = block.findNet(name)
        if not n:
            continue
        segs = []
        for sw in n.getSWires():
            for b in sw.getWires():
                if not b.isVia() and b.getTechLayer():
                    segs.append([b.getTechLayer().getName()] + box(b))
        out["nets"][name] = segs
    json.dump(out, open(dst, "w"))


def draw(src, dst):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    d = json.load(open(src))
    # one hue per destination (reference palette slots 1 to 4, and the AVCC strap in slot 6)
    group = {"north": "#2a78d6", "east": "#eb6834", "south": "#1baf7a", "west": "#6250d6", "avcc": "#008300"}
    side = {}
    for k in range(6):
        side["A_ADC%d" % k] = "north"
    side.update(A_ADC6="east", A_ADC7="east", A_AREF="east", A_AIN0="south", A_AIN1="south",
                A_XTAL1="west", A_XTAL2="west", A_AVCC="avcc")
    x0, y0, x1, y1 = d["die"]
    fig, ax = plt.subplots(figsize=(8, 8 * (y1 - y0) / (x1 - x0)), dpi=160)
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#f4f3f0", ec="#52514e", lw=0.8))
    c = d["core"]
    ax.add_patch(Rectangle((c[0], c[1]), c[2] - c[0], c[3] - c[1], fc="#fcfcfb", ec="#b5b3ad", lw=0.6))
    for m in d["macros"]:
        b = m["box"]
        ana = m["master"] == "rv328_analog"
        ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1], fc="#e4efe4" if ana else "#e9e8e4",
                               ec="#52514e" if ana else "#b5b3ad", lw=0.8 if ana else 0.4))
        if ana:
            ax.text((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, "analog macro", ha="center", va="center",
                    fontsize=9, color="#0b0b0b")
    for name, segs in d["nets"].items():
        col = group[side[name]]
        for layer, a, b_, c_, e in segs:
            w, h = c_ - a, e - b_
            # thin lines would vanish at this scale: draw each segment as a line of fixed visual width
            if w >= h:
                ax.plot([a, c_], [(b_ + e) / 2] * 2, color=col, lw=1.1 if name != "A_AVCC" else 2.2,
                        solid_capstyle="butt")
            else:
                ax.plot([(a + c_) / 2] * 2, [b_, e], color=col, lw=1.1 if name != "A_AVCC" else 2.2,
                        solid_capstyle="butt")
    for p, b in d["pads"].items():
        ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1], fc="#ffffff", ec="#52514e", lw=0.5))
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        lab = p.replace("apad_", "").upper()
        if b[3] - b[1] > b[2] - b[0]:     # a pad on the north or south edge
            ax.text(cx, cy, lab, ha="center", va="center", fontsize=5.5, rotation=90, color="#0b0b0b")
        else:
            ax.text(cx, cy, lab, ha="center", va="center", fontsize=5.5, color="#0b0b0b")
    handles = [plt.Line2D([], [], color=group[g], lw=2, label=l) for g, l in
               [("north", "ADC0 to ADC5 (north pads)"), ("east", "ADC6, ADC7, AREF (east pads)"),
                ("south", "AIN0, AIN1 (south pads)"), ("west", "XTAL1, XTAL2 (west pads)"),
                ("avcc", "AVCC supply strap")]]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, -0.01), ncol=2, fontsize=7, frameon=False)
    ax.set_xlim(x0 - 20, x1 + 20)
    ax.set_ylim(y0 - 20, y1 + 20)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Analog lines drawn on Metal4 and Metal5, from the analog macro to the pads", fontsize=9,
                 color="#0b0b0b", loc="left")
    fig.savefig(dst, bbox_inches="tight", facecolor="white")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("-")]
    i = a.index("dump") if "dump" in a else a.index("draw")
    (dump if a[i] == "dump" else draw)(a[i + 1], a[i + 2])
