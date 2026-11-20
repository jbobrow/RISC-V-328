#!/usr/bin/env python3
"""Explanatory figures for the ADC capacitor array, drawn from the generator's and the extraction's data.

  figures.py [work directory]     reads caparray_map.json and caparray_pex.json there, writes analog/layout/renders/

  caparray_map.png        which unit belongs to which capacitor
  caparray_section.png    the metal stack through two units (heights from the magic technology file)
  caparray_linearity.png  transition errors that the extracted wiring causes
  adcfe_transitions.png   simulated transitions, schematic against the extracted front end (if the result files exist)
  bgr_map.png             the reference as placed, every device named
  adccmp_map.png          the ADC comparator as placed
  adcfe_map.png           the ADC front end: what each part of the stack holds
  por_map.png, lfosc_map.png   the reset circuit and the 128 kHz oscillator as placed
  rcosc_map.png, xosc_map.png  the 8 MHz and the crystal oscillator: the blocks of their stacks
  bod_map.png, amux_map.png, refbuf_map.png, cmp_map.png, tsens_map.png   the last five blocks
  analog_cells.png        every drawn block side by side, to scale
  analog_macro_map.png    the assembled macro: cells, channels, trunk, pins
"""
import json
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders")
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#d9730d"
# one hue, light to dark, for b0 .. b9: the weight of the capacitor
RAMP = ["#dbe9fb", "#c3daf7", "#a9c9f2", "#8db6ec", "#70a1e4", "#548cda", "#3b76cc", "#2861b6", "#1b4c98", "#103672"]
SIDE, REF, BX = "#e9e8e4", "#cfcdc7", "#ffffff"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False})


def colour(top, bottom):
    if top == "dum":
        return REF
    if bottom == "vss":
        return SIDE
    if bottom == "bx":
        return BX
    return RAMP[int(bottom[1:])]


def fig_map(m):
    nc, nr, px, py = m["ncol"], m["nrow"], m["px"], m["py"]
    fig = plt.figure(figsize=(13.2, 8.6), facecolor=SURF)
    ax = fig.add_axes([0.03, 0.05, 0.60, 0.86], facecolor=SURF)
    for c in range(nc):
        for r in range(nr):
            ax.add_patch(Rectangle((c * px - 3.1, r * py - 3.5), 6.2, 7.0, facecolor=colour(m["topnet"][r], m["bottom"][c][r]),
                                   edgecolor=INK2 if m["bottom"][c][r] == "bx" else "none", linewidth=0.5))
    # collectors and buses, to scale
    x0, x1, y0, y1 = -2.5, (nc - 1) * px + 2.5, -2.5, (nr - 1) * py + 2.5
    ax.add_patch(Rectangle((x0 - 8, y0), 2, y1 - y0, facecolor=INK2))
    ax.add_patch(Rectangle((x1 + 6, 4 * py - 2.5), 2, 31 * py + 5, facecolor=BLUE))
    ax.add_patch(Rectangle((x0 - 4.6, -24.1), x1 - x0 + 5.2, 18.6, facecolor="none", edgecolor=INK2, linewidth=0.8, hatch="-----"))
    ax.text(x0 - 12, (y0 + y1) / 2, "reference side  (dum)", rotation=90, ha="right", va="center", color=INK2, fontsize=8.5)
    ax.text(x1 + 12, (y0 + y1) / 2, "top plate  (top), to the comparator", rotation=270, ha="left", va="center", color=BLUE, fontsize=8.5)
    ax.text((x0 + x1) / 2, -29, "twelve Metal2 buses: vss, b9 ... b0, bx", ha="center", va="top", color=INK2, fontsize=8.5)
    for c in range(8, 40):                      # which bit each array column carries
        b = m["bottom"][c][10]
        if c == 24:
            continue
        ax.text(c * px + (px / 2 if c == 23 else 0), y1 + 5, "5-0" if c == 23 else b[1:], ha="center", va="bottom", fontsize=6.5, color=INK)
    ax.text(8 * px - 6, y1 + 5, "bit of each column:", ha="right", va="bottom", fontsize=7.5, color=INK2)
    ax.text(3.5 * px, 20 * py, "256 units\ntop plate\nto ground", ha="center", va="center", fontsize=8.5, color=INK)
    ax.text(43.5 * px, 20 * py, "256 units\ntop plate\nto ground", ha="center", va="center", fontsize=8.5, color=INK)
    ax.text(23.5 * px, 1.5 * py, "192 units, reference side", ha="center", va="center", fontsize=8.5, color=INK)
    ax.text(23.5 * px, 37.5 * py, "192 units, reference side", ha="center", va="center", fontsize=8.5, color=INK)
    ax.plot([x1 - 50, x1], [-40, -40], color=INK, linewidth=2)
    ax.text(x1 - 25, -43, "50 um", ha="center", va="top", fontsize=8, color=INK)
    ax.set_xlim(x0 - 22, x1 + 22); ax.set_ylim(-52, y1 + 16); ax.set_aspect("equal"); ax.axis("off")

    # the two shared columns, enlarged, with the bit number written in every unit
    az = fig.add_axes([0.655, 0.05, 0.10, 0.86], facecolor=SURF)
    for i, c in enumerate((23, 24)):
        for r in range(4, 36):
            b = m["bottom"][c][r]
            az.add_patch(Rectangle((i * 1.1, r), 1.0, 0.9, facecolor=colour("top", b), edgecolor=INK2 if b == "bx" else "none", linewidth=0.6))
            az.text(i * 1.1 + 0.5, r + 0.45, "x" if b == "bx" else b[1:], ha="center", va="center", fontsize=7,
                    color="#ffffff" if b not in ("bx",) and int(b[1:]) >= 5 else INK)
    az.set_xlim(-0.1, 2.2); az.set_ylim(3.6, 36.4); az.axis("off")
    az.set_title("the two centre columns", fontsize=8.5, color=INK, pad=4)

    al = fig.add_axes([0.78, 0.05, 0.21, 0.86], facecolor=SURF); al.axis("off")
    al.set_xlim(0, 1); al.set_ylim(0, 1)
    y = 0.965
    al.text(0, y, "Capacitor, units", fontsize=9, fontweight="bold", color=INK, va="center")
    rows = [("b%d" % i, RAMP[i], "%d" % 2 ** i) for i in range(9, -1, -1)] + [("bx", BX, "1, completes 1024"),
            ("top plate to ground", SIDE, "512"), ("reference side", REF, "384")]
    for name, col, n in rows:
        y -= 0.043
        al.add_patch(Rectangle((0, y - 0.013), 0.07, 0.026, facecolor=col, edgecolor=INK2, linewidth=0.5))
        al.text(0.10, y, name, fontsize=8.5, color=INK, va="center")
        al.text(0.98, y, n, fontsize=8.5, color=INK2, va="center", ha="right")
    notes = ["A column of the array belongs to one bit.",
             "Columns alternate in a ruler pattern,",
             "mirrored about the centre line, and every",
             "bit runs the full height: a gradient across",
             "the die in either direction changes all bits",
             "in proportion.",
             "",
             "b5 ... b0 and bx share the two centre",
             "columns, the second being the first",
             "turned by 180 degrees.",
             "",
             "Units around the array are capacitors the",
             "circuit needs anyway, so every array unit",
             "has identical neighbours."]
    y -= 0.07
    for line in notes:
        al.text(0, y, line, fontsize=8.2, color=INK2, va="center"); y -= 0.027
    bb = m["bbox"]
    fig.text(0.03, 0.955, "ADC capacitor array: 1920 units of 5 um x 5 um, %.0f um x %.0f um" % (bb[2] - bb[0], bb[3] - bb[1]),
             fontsize=12, fontweight="bold", color=INK)
    fig.savefig(os.path.join(OUT, "caparray_map.png"), dpi=170, facecolor=SURF)
    plt.close(fig)


def fig_section():
    """Section along a column through one Metal3 track: two neighbouring units and the gap between them."""
    fig, ax = plt.subplots(figsize=(11.5, 4.6), facecolor=SURF)
    ax.set_facecolor(SURF)
    M2c, M3c, M4c, M5c, MIM, VIA = "#ff6b6b", "#2ec4b6", "#e0a800", "#9b5de5", "#ff7b00", "#8a8985"
    z = {"m2": (2.38, 0.55), "v2": (2.93, 0.60), "m3": (3.53, 0.55), "v3": (4.08, 0.60), "m4": (4.68, 0.55), "v4": (5.23, 0.60), "m5": (5.83, 1.0)}

    def r(x, w, key, col, **kw):
        ax.add_patch(Rectangle((x, z[key][0]), w, z[key][1], facecolor=col, edgecolor="none", **kw))

    pitch = 8.2
    ax.add_patch(Rectangle((-11.5, 2.2), 21.5, 4.9, facecolor="#f1f0ec", edgecolor="none"))       # oxide
    r(-11.5, 21.5, "m3", M3c)                                           # the track runs under both units
    for y0 in (-pitch, 0.0):
        r(y0 - 3.5, 7.0, "m4", M4c)
        ax.add_patch(Rectangle((y0 - 2.5, 5.23 + 0.04), 5.0, 0.16, facecolor=MIM, edgecolor="none"))   # top plate on the dielectric
        r(y0 - 2.5, 5.0, "m5", M5c)
        for k in range(6):
            x = y0 - 1.9 + 0.76 * k
            ax.add_patch(Rectangle((x - 0.13, 5.23 + 0.20), 0.26, 0.40, facecolor=VIA, edgecolor="none"))
        for s in (-1, 1):
            r(y0 + s * 3.28 - 0.13, 0.26, "v3", VIA)
    ax.annotate("Metal5 cover, joined to its neighbours\nby straps across the column gaps", (-8.2, 6.83), (-8.2, 7.75), ha="center", fontsize=8.5, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.annotate("top plate (FuseTop) on the capacitor dielectric,\n36 Via4 up to the cover", (1.2, 5.37), (4.4, 7.75), ha="center", fontsize=8.5, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.annotate("Metal4 bottom plate,\none per unit", (-11.2, 4.95), (-14.6, 4.95), ha="center", va="center", fontsize=8.5, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.annotate("Via3 on the margin of the plate,\n0.65 um clear of the top plate", (3.28, 4.38), (5.2, 2.75), ha="left", va="center", fontsize=8.5, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.annotate("Metal3 track of this bit, under the plates", (-4.1, 3.6), (-4.1, 2.55), ha="center", va="top", fontsize=8.5, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.annotate("", (-4.7, 6.0), (-3.5, 6.0), arrowprops=dict(arrowstyle="<->", color=INK2, lw=0.8))
    ax.text(-4.1, 6.12, "1.2 um", ha="center", va="bottom", fontsize=8, color=INK2)
    ax.plot([-11.5, -6.5], [1.95, 1.95], color=INK, linewidth=2)
    ax.text(-9.0, 1.85, "5 um along the column", ha="center", va="top", fontsize=8, color=INK)
    ax.plot([10.6, 10.6], [3.53, 4.53], color=INK, linewidth=2)
    ax.text(10.8, 4.03, "1 um of height", ha="left", va="center", fontsize=8, color=INK)
    ax.set_xlim(-18, 14.5); ax.set_ylim(1.4, 8.5); ax.set_aspect(1.6); ax.axis("off")
    ax.set_title("Section through two units along a column (height drawn 1.6 times larger; dielectric thickness not to scale)",
                 fontsize=10.5, fontweight="bold", color=INK, loc="left")
    fig.savefig(os.path.join(OUT, "caparray_section.png"), dpi=170, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)


def fig_linearity(p):
    d = p["corners"]["nominal"]
    codes = list(range(1, 1024))
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 5.6), sharex=True, facecolor=SURF)
    for ax, key, name in ((axes[0], "inl", "Transition position error (INL), LSB"), (axes[1], "dnl", "Step width error (DNL), LSB")):
        ax.set_facecolor(SURF)
        ax.axhline(0, color=INK2, linewidth=0.8)
        ax.plot(codes, d[key], color=BLUE, linewidth=1.0)
        ax.set_ylabel(name, fontsize=8.5)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_ylim(-0.05, 0.05)
        worst = max(range(1023), key=lambda i: abs(d[key][i]))
        up = d[key][worst] > 0
        ax.annotate("largest: %+.3f LSB at code %d" % (d[key][worst], worst + 1), (worst + 1, d[key][worst]),
                    (worst + 1, 0.040 if up else -0.040), ha="center", va="center", fontsize=8.5, color=INK,
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    axes[1].set_xlabel("Transition into code")
    axes[1].set_xlim(0, 1024); axes[1].set_xticks(range(0, 1025, 128))
    fig.suptitle("What the wiring of the capacitor array does to the converter (extracted, nominal)", fontsize=11, fontweight="bold", color=INK, x=0.06, ha="left")
    fig.text(0.06, 0.915, "Bit weights from the layout: capacitor plus wiring between the top plate and each bit. "
             "The vertical range shown is a tenth of the +-0.5 LSB budget.", fontsize=8.5, color=INK2)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.88, bottom=0.09, hspace=0.12)
    fig.savefig(os.path.join(OUT, "caparray_linearity.png"), dpi=170, facecolor=SURF)
    plt.close(fig)


def transitions(path):
    rows = []
    text = open(path).read()
    part = text[text.index("Transition positions"):]
    for line in part.splitlines():
        m = re.match(r"\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*(\w+)\s*\|\s*(-?\d+)\s*\|\s*(\d+ / \d+)\s*\|\s*([-+][\d.]+)\s*\|", line)
        if m:
            rows.append((float(m.group(1)), float(m.group(2)), m.group(3), int(m.group(4)), m.group(5), float(m.group(6))))
    return rows


def pattern(path):
    """Rows of tb/adcpat.py: both arrays in one table."""
    a, b = [], []
    for line in open(path):
        m = re.match(r"\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*(\w+)\s*\|\s*(-?\d+)\s*\|\s*(\d+ / \d+)\s*\|\s*([-+][\d.]+)\s*\|\s*([-+][\d.]+)\s*\|", line)
        if m:
            key = (float(m.group(1)), float(m.group(2)), m.group(3), int(m.group(4)), m.group(5))
            a.append(key + (float(m.group(6)),)); b.append(key + (float(m.group(7)),))
    return a, b


def fig_transitions(a_path, b_path, pat_path=None):
    """Transitions of the schematic against those of the layout, for the ones measured both ways."""
    b = transitions(b_path)
    keys = [r[:5] for r in b]
    a = [r for r in transitions(a_path) if r[:5] in keys]
    assert [r[:5] for r in a] == keys
    n_main = len(a)
    if pat_path and os.path.exists(pat_path):
        pa, pb = pattern(pat_path)
        a, b = a + pa, b + pb
    fig, ax = plt.subplots(figsize=(15.5, 5.8), facecolor=SURF)
    ax.set_facecolor(SURF)
    ax.axhline(0, color=INK2, linewidth=0.8)
    for lim in (-0.5, 0.5):
        ax.axhline(lim, color=INK2, linewidth=0.8, linestyle=(0, (4, 3)))
    ax.text(len(a) - 0.4, 0.5, "+0.5 LSB", ha="right", va="bottom", fontsize=8, color=INK2)
    ax.text(len(a) - 0.4, -0.5, "-0.5 LSB", ha="right", va="top", fontsize=8, color=INK2)
    xs = list(range(len(a)))
    for x, ra, rb in zip(xs, a, b):
        ax.plot([x, x], [ra[5], rb[5]], color=GRID, linewidth=2, zorder=1)
    ax.scatter(xs, [r[5] for r in a], s=42, color=BLUE, zorder=3, label="schematic", edgecolors=SURF, linewidths=1.2)
    ax.scatter(xs, [r[5] for r in b], s=42, color=ORANGE, zorder=3, marker="D", label="extracted from the layout", edgecolors=SURF, linewidths=1.2)
    ax.set_xticks(xs); ax.set_xticklabels([r[4].split(" / ")[1] for r in a], fontsize=7.5, rotation=90)
    groups, start = [], 0
    for i in range(1, len(a) + 1):
        if i == len(a) or a[i][:4] != a[start][:4]:
            groups.append((start, i - 1, a[start])); start = i
    top = max(0.5, max(r[5] for r in a + b))
    if n_main < len(a):
        ax.axvline(n_main - 0.5, color=INK2, linewidth=1.2)
        ax.text((n_main - 1) / 2, top + 0.52, "main bench: %d transitions" % n_main, ha="center", va="bottom", fontsize=8.5, color=INK2)
        ax.text((n_main + len(a) - 1) / 2, top + 0.52, "decided right after the opposite decision", ha="center", va="bottom", fontsize=8.5, color=INK2)
    for s, e, r in groups:
        if s and s != n_main:
            ax.axvline(s - 0.5, color=GRID, linewidth=1)
        ax.text((s + e) / 2, top + 0.14, "%.1f V ref\n%.1f V, %s\n%d C" % (r[0], r[1], r[2], r[3]), ha="center", va="bottom", fontsize=7.8, color=INK)
    ax.set_ylim(-0.66, top + 0.62); ax.set_xlim(-0.6, len(a) - 0.4)
    ax.set_yticks([-0.5, -0.25, 0, 0.25, 0.5])
    ax.set_ylabel("Transition error, LSB"); ax.set_xlabel("Transition into code")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.legend(loc="lower left", frameon=False, fontsize=8.5, ncol=2)
    worst = max(abs(rb[5] - ra[5]) for ra, rb in zip(a, b))
    ax.set_title("Code transitions of the ADC front end in simulation: schematic and layout (largest difference %.2f LSB)" % worst,
                 fontsize=10.5, fontweight="bold", color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "adcfe_transitions.png"), dpi=170, facecolor=SURF)
    plt.close(fig)
    return a, b


def fig_bgr_map(m):
    """The reference as placed: every device named, the wiring channel between the two rows."""
    KIND = {"pmos": ("#dbe9fb", "PMOS"), "nmos": ("#d7efe2", "NMOS"), "res": ("#f6dfc4", "resistor strips"),
            "cap": ("#e9e8e4", "MIM capacitor"), "pnp": ("#eadcf5", "bipolars")}
    bb = m["bbox"]
    fig, ax = plt.subplots(figsize=(14.5, 8.3), facecolor=SURF)
    ax.set_facecolor(SURF)
    ax.add_patch(Rectangle((bb[0], 0), bb[2] - bb[0], m["h"], facecolor="#f1f0ec", edgecolor="none"))
    for net, y in m["tracks"].items():
        ax.plot([bb[0], bb[2]], [y, y], color=GRID, linewidth=0.8)
    ax.text(bb[2] + 3, m["h"] / 2, "wiring channel:\n%d nets, one Metal3\ntrack each" % len(m["nets"]), ha="left", va="center", fontsize=8.5, color=INK2)
    note = {"xmp1": "xmp1\n16/8", "xmp2": "xmp2", "xmp3": "xmp3", "xmpd": "xmpd", "xmt": "xmt\n8/8", "xmsp": "xmsp", "xma": "xma\n4 x 10/4", "xmb": "xmb\n4 x 10/4",
            "xmn1": "xmn1\n8/8", "xmn2": "xmn2", "xm6": "xm6  4 x 8/8", "xr1": "xr1", "xr2": "xr2\n10 x\n13.4 um", "xra": "xra  2 x 35 um",
            "xrb": "xrb\n67 strips\nof 35 um", "xrs": "xrs\n60 strips\nof 35 um", "xcr": "xcr\n30 x 30 um", "xcc": "xcc\n36 x 36 um",
            "xq1 xq2 xq3": "xq2 (8) around xq1,\nxq3 beside"}
    small = []
    for d in m["placed"]:
        x1, y1, x2, y2 = d["box"]
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, facecolor=KIND[d["kind"]][0], edgecolor=INK2, linewidth=0.7))
        if x2 - x1 > 9:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, note.get(d["name"], d["name"]), ha="center", va="center", fontsize=7.5, color=INK)
        else:
            small.append(d)
    for row, sign in (("top", 1), ("bot", -1)):                   # small devices: names on leader lines, fanned out
        ds = [d for d in small if (d["box"][1] > 0) == (sign > 0)]
        for i, d in enumerate(ds):
            x = (d["box"][0] + d["box"][2]) / 2
            yd = d["box"][3] if sign > 0 else d["box"][1]
            yt = yd + sign * (6 + 4.5 * (i % 4))
            ax.plot([x, x], [yd, yt], color=INK2, linewidth=0.6)
            ax.text(x, yt + sign * 0.8, d["name"], ha="center", va="bottom" if sign > 0 else "top", fontsize=7.5, color=INK)
    hx = bb[0]
    for kind, (col, label) in KIND.items():
        ax.add_patch(Rectangle((hx, bb[3] + 8), 5, 5, facecolor=col, edgecolor=INK2, linewidth=0.7))
        ax.text(hx + 7, bb[3] + 10.5, label, ha="left", va="center", fontsize=8.5, color=INK)
        hx += 14 + 5.2 * len(label)
    ax.plot([bb[0], bb[0] + 50], [bb[1] + 4, bb[1] + 4], color=INK, linewidth=2)
    ax.text(bb[0] + 25, bb[1] + 1, "50 um", ha="center", va="top", fontsize=8, color=INK)
    ax.set_xlim(bb[0] - 4, bb[2] + 38); ax.set_ylim(bb[1] - 6, bb[3] + 18); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("Reference (rv328_bgr) as laid out: %.0f um x %.0f um, sizes in um as width / length" % (bb[2] - bb[0], bb[3] - bb[1]),
                 fontsize=11, fontweight="bold", color=INK, loc="left")
    fig.savefig(os.path.join(OUT, "bgr_map.png"), dpi=170, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)

KIND = {"pmos": ("#dbe9fb", "PMOS"), "nmos": ("#d7efe2", "NMOS"), "res": ("#f6dfc4", "resistor strips"),
        "cap": ("#e9e8e4", "MIM capacitor"), "pnp": ("#eadcf5", "bipolars"), "std": ("#f3e7a6", "standard cell")}


def kinds_of(placed):
    """The kinds of device to name in a legend: the usual four, and standard cells where there are any."""
    return ("pmos", "nmos", "res", "cap") + (("std",) if any(d["kind"] == "std" for d in placed) else ())


def legend(ax, x, y, kinds, size=5.0, step=5.2):
    for kind in kinds:
        col, label = KIND[kind]
        ax.add_patch(Rectangle((x, y), size, size, facecolor=col, edgecolor=INK2, linewidth=0.7))
        ax.text(x + size * 1.4, y + size / 2, label, ha="left", va="center", fontsize=8.5, color=INK)
        x += size * 3.0 + step * len(label)


def fig_cmp_map(m):
    """The ADC comparator as placed, with the three groups of nets that decide its arrangement."""
    bb = m["bbox"]
    fig, ax = plt.subplots(figsize=(15, 6.6), facecolor=SURF)
    ax.set_facecolor(SURF)
    ax.add_patch(Rectangle((bb[0], 0), bb[2] - bb[0], m["h"], facecolor="#f1f0ec", edgecolor="none"))
    group = {"az": "sw", "azn": "sw", "enb": "sw", "o2": "sw", "o3": "sw", "out": "sw", "d1": "sw", "azd": "sw",
             "x": "v", "y": "v", "xm": "v", "ym": "v", "inp": "v", "inn": "v"}
    for net, y in m["tracks"].items():
        g = group.get(net)
        ax.plot([bb[0], bb[2]], [y, y], color=ORANGE if g == "sw" else BLUE if g == "v" else GRID, linewidth=1.3 if g else 0.8)
    note = {"xca": "xca\n1 pF", "xcb": "xcb\n1 pF", "xm3a": "xm3a", "xm3b": "xm3b", "xmt2": "xmt2", "xm1": "xm1\n8 x 10/2", "xm2": "xm2\n8 x 10/2",
            "xmt": "xmt  4 x 16/8", "xmbp": "xmbp", "xmp4": "xmp4", "xr1": "xr1  60 kohm", "xr2": "xr2  60 kohm", "xcv": "xcv\n1 pF", "xco": "xco\n1 pF",
            "xd2c": "xd2c", "xd1c": "xd1c"}
    small = []
    for d in m["placed"]:
        x1, y1, x2, y2 = d["box"]
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, facecolor=KIND[d["kind"]][0], edgecolor=INK2, linewidth=0.7))
        if x2 - x1 > 9:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, note.get(d["name"], d["name"]), ha="center", va="center", fontsize=7.5, color=INK)
        else:
            small.append(d)
    for sign in (1, -1):
        ds = sorted((d for d in small if (d["box"][1] > 0) == (sign > 0)), key=lambda d: d["box"][0])
        for i, d in enumerate(ds):
            x = (d["box"][0] + d["box"][2]) / 2
            yd = d["box"][3] if sign > 0 else d["box"][1]
            yt = yd + sign * (4 + 4.6 * (i % 5))
            ax.plot([x, x], [yd, yt], color=INK2, linewidth=0.6)
            ax.text(x, yt + sign * 0.8, d["name"].replace("_xm", " "), ha="center", va="bottom" if sign > 0 else "top", fontsize=7, color=INK)
    top = bb[3] + 8
    for x1, x2, text in ((bb[2] - 62, bb[2], "everything on the two capacitor nodes:\\ncoupling capacitors, second pair, clamps"),
                         (bb[2] - 205, bb[2] - 62, "input pair, current sources, loads"), (bb[0], bb[2] - 205, "output inverters, delay chain, enable")):
        ax.plot([x1 + 1, x2 - 1], [top, top], color=INK2, linewidth=1.0)
        ax.text((x1 + x2) / 2, top + 1.5, text, ha="center", va="bottom", fontsize=8.5, color=INK)
    ly = bb[1] - 30
    legend(ax, bb[0], ly, ("pmos", "nmos", "res", "cap"), size=4.0, step=1.9)
    ax.plot([bb[0], bb[0] + 10], [ly - 6, ly - 6], color=BLUE, linewidth=1.6)
    ax.text(bb[0] + 12, ly - 6, "tracks of small-signal nets (capacitor nodes, inputs)", ha="left", va="center", fontsize=8.5, color=INK)
    ax.plot([bb[0] + 120, bb[0] + 130], [ly - 6, ly - 6], color=ORANGE, linewidth=1.6)
    ax.text(bb[0] + 132, ly - 6, "tracks of nets that switch (clamp controls at the bottom, logic at the top)", ha="left", va="center", fontsize=8.5, color=INK)
    ax.plot([bb[2] - 50, bb[2]], [ly + 2, ly + 2], color=INK, linewidth=2)
    ax.text(bb[2] - 25, ly, "50 um", ha="center", va="top", fontsize=8, color=INK)
    ax.set_xlim(bb[0] - 4, bb[2] + 4); ax.set_ylim(ly - 10, bb[3] + 22); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("ADC comparator (rv328_adccmp) as laid out: %.0f um x %.0f um" % (bb[2] - bb[0], bb[3] - bb[1]),
                 fontsize=11, fontweight="bold", color=INK, loc="left")
    fig.savefig(os.path.join(OUT, "adccmp_map.png"), dpi=170, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)


def describe(part, placed):
    """What a block of the front end holds, from the names of its devices."""
    names = [d["name"] for d in placed if d["block"] == part["name"]]
    drv = sorted(set(int(mm.group(2)) for mm in (re.match(r"x(db|a|i|rb|o|g|gb)(\d)_", n) for n in names) if mm))
    sw = sorted(set(int(mm.group(2)) for mm in (re.match(r"x(tip|tin|trp|trn|tg)(\d)$", n) for n in names) if mm))
    out = []
    if "xmt" in names:
        out.append("top-plate switches and their bias divider")
    if "xdc" in names:
        out.append("capacitors and resistor")
    std = any(d["kind"] == "std" for d in placed if d["block"] == part["name"])
    if any(n.startswith(("xq1", "xds")) for n in names):
        out.append("delays and slow edges of the sequencer")
    rng = lambda v: "bit %d" % v[0] if len(v) == 1 else "bits %d to %d" % (v[0], v[-1])
    if drv:
        out.append(("gates of the sequencer and drivers of %s,\nas standard cells" if std else "drivers of %s") % rng(drv))
    if sw:
        out.append("bottom-plate switches of " + rng(sw))
    return ", ".join(out) if len(out) < 3 else ",\n".join(out)


def fig_fe_map(m):
    """The ADC front end: the stack of cells, the column of lines that joins them, and what each holds."""
    bb = m["bbox"]
    fig, ax = plt.subplots(figsize=(11.5, 15.5), facecolor=SURF)
    ax.set_facecolor(SURF)
    for d in m["placed"]:
        x1, y1, x2, y2 = d["box"]
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, facecolor=KIND[d["kind"]][0], edgecolor=INK2, linewidth=0.35))
    for p in m["parts"]:
        x1, y1, x2, y2 = p["box"]
        if p["name"].endswith("caparray"):
            ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, facecolor=RAMP[2], edgecolor=INK2, linewidth=0.8))
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, "capacitor array\n1920 units of 54.5 fF\n(1024 of the converter, 512 from the\ntop plate to ground, 384 reference side)", ha="center", va="center", fontsize=10, color=INK)
            text = "rv328_adc_caparray"
        else:
            ch = p["channel"]
            ax.add_patch(Rectangle((x1, ch[0]), x2 - x1, ch[1] - ch[0], facecolor="#f1f0ec", edgecolor="none", zorder=0))
            ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, facecolor="none", edgecolor=INK2, linewidth=0.6, linestyle=(0, (3, 2))))
            text = "comparator (rv328_adccmp)" if p["name"] == "rv328_adccmp" else describe(p, m["placed"])
        ax.text(bb[2] + 8, (y1 + y2) / 2, text, ha="left", va="center", fontsize=8.8, color=INK)
    for n, (x, y1, y2) in m["spine"].items():
        ax.plot([x, x], [y1, y2], color="#b58a1f", linewidth=0.45)
    for n, (x1, x2) in m["right"].items():
        ys = [t[2] for t in m["tracks"][n]]
        ax.add_patch(Rectangle((x1, min(ys)), x2 - x1, m["array_y"] + 25 - min(ys), facecolor="#8a5fc7", edgecolor="none"))
    xs = [v[0] for v in m["spine"].values()]
    ax.annotate("%d Metal4 lines, one per net\nthat leaves a block" % len(m["spine"]), xy=(min(xs) + 8, 150), xytext=(min(xs) - 6, 150), ha="right", va="center", fontsize=8.8, color=INK,
                arrowprops=dict(arrowstyle="-", color=INK2, linewidth=0.7))
    ax.annotate("top plate and reference side\ncome down on Metal5,\naway from the logic", xy=(m["right"]["top"][1], m["array_y"] - 60), xytext=(bb[2] + 8, m["array_y"] - 12), ha="left", va="center",
                fontsize=8.8, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, linewidth=0.7))
    ax.annotate("the array's twelve Metal2 buses\nreach the column here", xy=(-20, m["array_y"] - 14), xytext=(min(xs) - 6, m["array_y"] + 30), ha="right", va="center",
                fontsize=8.8, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, linewidth=0.7))
    legend(ax, bb[0], bb[1] - 28, kinds_of(m["placed"]), size=9.0, step=5.6)
    ax.plot([bb[2] - 100, bb[2]], [bb[1] - 52, bb[1] - 52], color=INK, linewidth=2)
    ax.text(bb[2] - 50, bb[1] - 57, "100 um", ha="center", va="top", fontsize=8.5, color=INK)
    ax.set_xlim(bb[0] - 150, bb[2] + 215); ax.set_ylim(bb[1] - 75, bb[3] + 8); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("ADC front end (rv328_adcfe) as laid out: %.0f um x %.0f um" % (bb[2] - bb[0], bb[3] - bb[1]), fontsize=11, fontweight="bold", color=INK, loc="left")
    fig.savefig(os.path.join(OUT, "adcfe_map.png"), dpi=170, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)

def fig_block_map(m, cell, title, groups, wide=25.0):
    """A block drawn by autoblock.py: its devices, the passives named. groups: [(x from, x to, text)] above.
    Devices wider than `wide` um, and all those with a note, carry their name."""
    bb = m["bbox"]
    wid = 15.0 if bb[2] - bb[0] > 200 else 9.0 if bb[2] - bb[0] > 60 else 4.5
    fig, ax = plt.subplots(figsize=(wid, wid * (bb[3] - bb[1] + 60) / (bb[2] - bb[0] + 10) if bb[2] - bb[0] > 250 else wid * 1.15 * (bb[3] - bb[1]) / (bb[2] - bb[0]) + 0.6), facecolor=SURF)
    ax.set_facecolor(SURF)
    ax.add_patch(Rectangle((bb[0], 0), bb[2] - bb[0], m["h"], facecolor="#f1f0ec", edgecolor="none"))
    for d in m["placed"]:
        x1, y1, x2, y2 = d["box"]
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, facecolor=KIND[d["kind"]][0], edgecolor=INK2, linewidth=0.6))
        if x2 - x1 > wide or d.get("note"):
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, (d["name"] + "\n" + d.get("note", "")).strip(), ha="center", va="center", fontsize=8 if x2 - x1 > 25 else 6.5, color=INK)
    top = bb[3] + 6
    for x1, x2, text in groups:
        ax.plot([x1 + 2, x2 - 2], [top, top], color=INK2, linewidth=1.0)
        ax.text((x1 + x2) / 2, top + 3, text, ha="center", va="bottom", fontsize=8.5, color=INK)
    if bb[2] - bb[0] > 250:
        ly = bb[1] - 22
        legend(ax, bb[0], ly, kinds_of(m["placed"]), size=7.0, step=3.4)
        ax.plot([bb[2] - 100, bb[2]], [ly + 3.5, ly + 3.5], color=INK, linewidth=2)
        ax.text(bb[2] - 50, ly, "100 um", ha="center", va="top", fontsize=8, color=INK)
        ax.set_xlim(bb[0] - 5, bb[2] + 5); ax.set_ylim(ly - 12, bb[3] + 28); ax.set_aspect("equal"); ax.axis("off")
    else:                                                    # a small cell: only a scale bar, in proportion
        k = (bb[2] - bb[0]) / 300.0
        bar = 20 if bb[2] - bb[0] > 60 else 5
        ly = bb[1] - 14 * k
        ax.plot([bb[2] - bar, bb[2]], [ly, ly], color=INK, linewidth=2)
        ax.text(bb[2] - bar / 2, ly - 4 * k, "%d um" % bar, ha="center", va="top", fontsize=8, color=INK)
        ax.set_xlim(bb[0] - 5 * k, bb[2] + 5 * k); ax.set_ylim(ly - 22 * k, bb[3] + 8 * k); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("%s as laid out: %.0f um x %.0f um" % (title, bb[2] - bb[0], bb[3] - bb[1]), fontsize=11, fontweight="bold", color=INK, loc="left")
    fig.savefig(os.path.join(OUT, cell + "_map.png"), dpi=170, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)


def fig_stack_map(m, cell, title, notes, parts, marked=()):
    """A cell drawn by stack.py: its blocks with their devices, the column of lines at the left.
    notes: {device: text} for the large devices; parts: {block name: what it holds}; marked: nets whose
    column line is drawn in blue (the small-signal ones)."""
    bb = m["bbox"]
    wid = 13.0
    fig, ax = plt.subplots(figsize=(wid, wid * (bb[3] - bb[1] + 55) / (bb[2] - bb[0] + 215)), facecolor=SURF)
    ax.set_facecolor(SURF)
    for p in m["parts"]:
        x1, y1, x2, y2 = p["box"]
        ch = p["channel"]
        ax.add_patch(Rectangle((x1, ch[0]), x2 - x1, ch[1] - ch[0], facecolor="#f1f0ec", edgecolor="none", zorder=0))
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, facecolor="none", edgecolor=INK2, linewidth=0.6, linestyle=(0, (3, 2))))
    for name in sorted(set(p["name"] for p in m["parts"])):      # one caption per group, also when it was cut in two
        ys = [y for p in m["parts"] if p["name"] == name for y in (p["box"][1], p["box"][3])]
        ax.text(bb[2] + 6, (min(ys) + max(ys)) / 2, parts.get(name, name), ha="left", va="center", fontsize=8.8, color=INK)
    for d in m["placed"]:
        x1, y1, x2, y2 = d["box"]
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, facecolor=KIND[d["kind"]][0], edgecolor=INK2, linewidth=0.5))
        if d["name"] in notes and notes[d["name"]]:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, notes[d["name"]], ha="center", va="center", fontsize=7.6, color=INK,
                    rotation=90 if (y2 - y1) > 2.2 * (x2 - x1) else 0)
    for n, (x, y1, y2) in m["spine"].items():
        ax.plot([x, x], [y1, y2], color=BLUE if n in marked else "#b58a1f", linewidth=1.3 if n in marked else 0.6)
    for n in marked:                                        # and the marked nets' tracks inside the blocks
        for xa, xb, ty in m["tracks"].get(n, []):
            ax.plot([m["spine"][n][0], xb], [ty, ty], color=BLUE, linewidth=1.0)
    xs = [v[0] for v in m["spine"].values()]
    ax.text(min(xs) - 3, bb[3] - 4, "%d Metal4 lines:\none per net that joins\ntwo blocks or is a pin" % len(m["spine"]), ha="right", va="top", fontsize=8.5, color=INK)
    if marked:
        ax.plot([min(xs) - 62, min(xs) - 52], [bb[3] - 44, bb[3] - 44], color=BLUE, linewidth=1.6)
        ax.text(min(xs) - 49, bb[3] - 44, marked[0] if len(marked) == 1 else ", ".join(marked), ha="left", va="center", fontsize=8.5, color=INK)
    ly = bb[1] - 20
    legend(ax, bb[0], ly, kinds_of(m["placed"]), size=6.0, step=3.6)
    ax.plot([bb[2] + 30, bb[2] + 80], [ly + 3, ly + 3], color=INK, linewidth=2)
    ax.text(bb[2] + 55, ly, "50 um", ha="center", va="top", fontsize=8, color=INK)
    ax.set_xlim(bb[0] - 75, bb[2] + 140); ax.set_ylim(ly - 12, bb[3] + 6); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("%s as laid out: %.0f um x %.0f um" % (title, bb[2] - bb[0], bb[3] - bb[1]), fontsize=11, fontweight="bold", color=INK, loc="left")
    fig.savefig(os.path.join(OUT, cell + "_map.png"), dpi=170, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)


STACKS = {
    "rv328_rcosc": ("8 MHz RC oscillator (rv328_rcosc)",
                    {"xcf": "73 units\nalways in", "xct7": "trim bit 7\n128 units of 50 fF", "xct6": "bit 6\n64 units", "xct5": "bit 5", "xct4": "bit 4",
                     "xst7": "switch 7", "xrd1": "400 k", "xrd2": "400 k", "xrd3": "400 k", "xrb": "60 k", "xrt": "timing\nresistor", "xd2_xmp": "driver", "xd2_xmn": "driver"},
                    {"capacitors": "timing capacitor: 328 units in banks,\none switch and one inverter per trim bit",
                     "core": "threshold divider, bias, the two\ncomparators, latch, driver,\ntiming resistor",
                     "logic": "run control, two flip-flops,\noutput gate"}, ("vc",)),
    "rv328_xosc": ("Crystal oscillator (rv328_xosc)",
                   {"xrf": "10 Mohm feedback resistor, 66 strips", "xrg": "500 k", "xmn": "amplifier\n400 / 0.7", "xmft": "foot switch\n400 / 0.7",
                    "xrl": "4 Mohm\n62 strips", "xmp2": "1 mA source: 50 x 10 / 1", "xmp1": "0.3 mA", "xms2": "switch"},
                   {"amplifier": "amplifier and foot switch,\nfeedback resistors with their switches",
                    "current sources": "current sources of the three settings\n(0.3 mA, 1 mA, 3 uA) and their switches,\n32 kHz bias resistor",
                    "logic": "setting decoder; replica of the amplifier,\nSchmitt trigger and output buffer"}, ("xi", "xo")),
    "rv328_bod": ("Brown-out detector (rv328_bod)",
                  {"xr1": "2.6 Mohm\n45 strips", "xr2": "0.35 Mohm", "xr3": "0.76 Mohm\n14 strips", "xr4": "1.2 Mohm\n24 strips", "xct": "1 pF",
                   "xc_xm1": "pair", "xc_xm2": "pair"},
                  {"divider": "supply divider with its three taps,\ntap and hysteresis switches,\ncomparator",
                   "logic": "level decoder, output logic,\ncomparator's output stages"}, ("vref",)),
    "rv328_amux": ("Input multiplexer (rv328_amux)", {},
                   {"rows": "the eleven switches; at the right\nthe decoder and each switch's gate\nand inverter, as standard cells"}, ("out",)),
}

def fig_family(work):
    """Every drawn block side by side, to scale: analog_cells.png."""
    def load(name):
        path = os.path.join(work, name)
        return json.load(open(path)) if os.path.exists(path) else None
    cells = {"ADC front end": load("adcfe_map.json"), "reference": load("bgr_map.json")}
    for key, f in (("power-on reset", "por"), ("128 kHz oscillator", "lfosc"), ("8 MHz oscillator", "rcosc"), ("crystal oscillator", "xosc"),
                   ("brown-out detector", "bod"), ("reference buffer", "refbuf"), ("multiplexer", "amux"), ("comparator", "cmp"), ("temperature sensor", "tsens")):
        cells[key] = load("rv328_%s_map.json" % f)
    if any(v is None for v in cells.values()):
        return
    size = {k: (m["bbox"][2] - m["bbox"][0], m["bbox"][3] - m["bbox"][1]) for k, m in cells.items()}
    g = 50.0                                                 # room between cells, for the captions
    x0 = size["ADC front end"][0] + 2 * g
    H = size["ADC front end"][1]
    pos = {"ADC front end": (0.0, 0.0)}
    y = H - size["128 kHz oscillator"][1]                    # three shelves beside the front end, from the top
    pos["128 kHz oscillator"] = (x0, y)
    pos["reference buffer"] = (x0 + size["128 kHz oscillator"][0] + g, y + size["128 kHz oscillator"][1] - size["reference buffer"][1])
    pos["comparator"] = (pos["reference buffer"][0], pos["reference buffer"][1] - g - size["comparator"][1])
    pos["temperature sensor"] = (pos["comparator"][0] + size["comparator"][0] + 3 * g, pos["comparator"][1])
    y -= g + size["power-on reset"][1]
    pos["power-on reset"] = (x0, y)
    pos["reference"] = (x0 + size["power-on reset"][0] + g, y)
    y -= g + size["crystal oscillator"][1]
    pos["8 MHz oscillator"] = (x0, y)
    pos["crystal oscillator"] = (x0 + size["8 MHz oscillator"][0] + g, y)
    xb = pos["crystal oscillator"][0] + size["crystal oscillator"][0] + g
    pos["brown-out detector"] = (xb, y + size["crystal oscillator"][1] - size["brown-out detector"][1])
    pos["multiplexer"] = (xb, pos["brown-out detector"][1] - g - size["multiplexer"][1])
    W = max(pos[k][0] + size[k][0] for k in cells)
    fig, ax = plt.subplots(figsize=(15, 15 * (H + 113) / (W + 20)), facecolor=SURF)
    ax.set_facecolor(SURF)
    total = 0.0
    for k, m in cells.items():
        bb = m["bbox"]
        dx, dy = pos[k][0] - bb[0], pos[k][1] - bb[1]
        ax.add_patch(Rectangle(pos[k], size[k][0], size[k][1], facecolor="#f6f5f1", edgecolor=INK2, linewidth=0.7))
        for p in m.get("parts", []):
            if p["name"].endswith("caparray"):
                x1, y1, x2, y2 = p["box"]
                ax.add_patch(Rectangle((x1 + dx, y1 + dy), x2 - x1, y2 - y1, facecolor=RAMP[2], edgecolor=INK2, linewidth=0.4))
        for d in m["placed"]:
            x1, y1, x2, y2 = d["box"]
            ax.add_patch(Rectangle((x1 + dx, y1 + dy), x2 - x1, y2 - y1, facecolor=KIND[d["kind"]][0], edgecolor=INK2, linewidth=0.25))
        area = size[k][0] * size[k][1] * 1e-6
        total += area
        ax.text(pos[k][0], pos[k][1] - 5, "%s\n%.0f x %.0f um, %.3f mm2" % (k, size[k][0], size[k][1], area), ha="left", va="top", fontsize=8.5, color=INK)
    legend(ax, x0, -82, ("pmos", "nmos", "res", "cap", "pnp"), size=14.0, step=7.5)
    ax.plot([W - 200, W], [-75, -75], color=INK, linewidth=2)
    ax.text(W - 100, -82, "200 um", ha="center", va="top", fontsize=8.5, color=INK)
    ax.set_xlim(-10, W + 10); ax.set_ylim(-105, H + 8); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("The eleven blocks of the analog macro as laid out, to scale: %.2f mm2 in all" % total, fontsize=12, fontweight="bold", color=INK, loc="left")
    fig.savefig(os.path.join(OUT, "analog_cells.png"), dpi=170, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)


SMALL = {
    "rv328_refbuf": ("Reference buffer (rv328_refbuf)", {"xmt": "tail source, 25 x 16 / 8", "xm1": "input pair", "xm2": "input pair", "xcc": "5 pF", "xmn1": "mirror", "xmn2": "mirror", "xma": "AVCC\nswitch"}),
    "rv328_cmp": ("Analog comparator (rv328_cmp)", {"xmt": "tail", "xm1": "pair", "xm2": "pair", "xmp3": "load"}),
    "rv328_tsens": ("Temperature sensor (rv328_tsens)", {"xr": "6 strips\nof 13.4 um", "xm1": "source"}),
}

NOTES = {"rv328_por": ("Power-on reset (rv328_por)", {"xrl": "10 Mohm load\n66 strips", "xrd": "10 Mohm delay\n66 strips", "xcd": "15 pF", "xrt": "3.3 Mohm", "xrb": "4.2 Mohm", "xrh": "0.5 Mohm"}),
         "rv328_lfosc": ("128 kHz oscillator (rv328_lfosc)", {"xrd1": "8 Mohm\n64 strips", "xrd2": "8 Mohm\n64 strips", "xrd3": "8 Mohm\n64 strips", "xrb": "16 Mohm bias resistor, 64 strips",
                                                              "xrt": "timing resistor\n1.7 Mohm, 37 strips", "xct": "2 pF"})}


MACRO_NAMES = {"xfe": "ADC front end", "xrb": "reference buffer", "xts": "temp.\nsensor", "xbgr": "1.1 V reference\nand bias", "xmux": "input multiplexer",
               "acsw": "input\nswitches", "xac": "comparator\nrv328_cmp", "xpor": "power-on reset", "glue": "enable and\ngating logic", "xlf": "128 kHz oscillator",
               "xrc": "8 MHz\noscillator", "xxo": "crystal\noscillator", "xbod": "brown-out detector"}
# the four groups of nets in the order they lie in a channel: small-signal, the two supplies, set once, switching
GROUP = {0: (BLUE, "small-signal: references, bias, analog inputs"), 1: (INK, "ground and supply (6 um tracks, 8 um lines; the oscillators' own branches half that)"), 3: (INK, ""),
         2: ("#8f8d86", "set once: enables, trim, selects"), 4: (ORANGE, "switching: clocks, ADC bits, outputs")}


def fig_macro(m):
    """The assembled macro: the thirteen cells, the channels of tracks under the rows, the trunk, the pins."""
    bb = m["bbox"]
    fig, ax = plt.subplots(figsize=(15.5, 15.5 * (bb[3] - bb[1] + 180) / (bb[2] - bb[0] + 40)), facecolor=SURF)
    ax.set_facecolor(SURF)
    ax.add_patch(Rectangle((bb[0], bb[1]), bb[2] - bb[0], bb[3] - bb[1], facecolor="none", edgecolor=INK, linewidth=1.0))
    for i, (x1, y1, x2, y2) in m["boxes"].items():
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, facecolor="#eeede8", edgecolor=INK2, linewidth=0.7, zorder=1))
        small = (x2 - x1) < 110
        text = MACRO_NAMES[i] if small else "%s\n%s\n%.0f x %.0f um" % (MACRO_NAMES[i], m["cells"][i], x2 - x1, y2 - y1)
        if i == "xts":
            ax.text(x2 + 5, (y1 + y2) / 2, MACRO_NAMES[i].replace("\n", " "), ha="left", va="center", fontsize=7.2, color=INK, zorder=6,
                    bbox=dict(facecolor=SURF, edgecolor="none", pad=1.2))
        else:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, text, ha="center", va="center", fontsize=7.2 if small else 9.5, color=INK, zorder=3, linespacing=1.35)
    g = m["group"]
    for d in m["drops"]:
        ax.plot([d["x"], d["x"]], [d["y1"], d["y2"]], color=GROUP[g[d["net"]]][0], linewidth=0.45, alpha=0.75, zorder=2)
    for t in m["tracks"]:
        ax.add_patch(Rectangle((t["x1"], t["y"] - max(t["w"], 0.9) / 2), t["x2"] - t["x1"], max(t["w"], 0.9), facecolor=GROUP[g[t["net"]]][0], edgecolor="none", zorder=4))
    for t in m["trunk"]:
        ax.add_patch(Rectangle((t["x"] - max(t["w"], 0.9) / 2, t["y1"]), max(t["w"], 0.9), t["y2"] - t["y1"], facecolor=GROUP[g[t["net"]]][0], edgecolor="none", zorder=4))
    # captions for the channels and the trunk
    xs = [t["x"] for t in m["trunk"]]
    ax.annotate("trunk: %d Metal4 lines,\none per net that is in more\nthan one channel or is a pin" % len(m["trunk"]), ((min(xs) + max(xs)) / 2, bb[3] - 2),
                ((min(xs) + max(xs)) / 2, bb[3] + 30), ha="center", va="bottom", fontsize=8.8, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, linewidth=0.6))
    for ch, (a, b) in m["band"].items():
        n = sum(1 for t in m["tracks"] if t["channel"] == ch)
        x = max(t["x2"] for t in m["tracks"] if t["channel"] == ch)
        ax.text(min(x + 8, bb[2] + 8) if x < bb[2] - 150 else bb[2] + 8, (a + b) / 2, "%d tracks" % n, ha="left", va="center", fontsize=8.5, color=INK)
    # pins
    south = [p for n, p in m["pins"].items() if n not in m["direct"]]
    ax.annotate("44 pins at the foot of the trunk:\nsupply, ground, AREF, and every\ndigital control and output", ((min(xs) + max(xs)) / 2, bb[1]), ((min(xs) + max(xs)) / 2, bb[1] - 26),
                ha="center", va="top", fontsize=8.8, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, linewidth=0.6))
    for names, text, up, ha in ((["adc%d" % k for k in range(8)], "ADC0 ... ADC7", False, "right"), (["ain0", "ain1"], "AIN0, AIN1", False, "left"),
                                (["xtal1", "xtal2"], "XTAL1, XTAL2", True, "center")):
        px = [m["pins"][n][0] for n in names]
        y = bb[3] if up else bb[1]
        for x in px:
            ax.plot([x, x], [y - 6, y + 6], color=BLUE, linewidth=1.2, zorder=5)
        ax.text({"center": (min(px) + max(px)) / 2, "right": max(px) + 4, "left": min(px) - 4}[ha], y + (12 if up else -12), text, ha=ha, va="bottom" if up else "top", fontsize=8.8, color=INK)
    # legend and scale
    ly = bb[1] - 125
    for k, key in enumerate((0, 1, 2, 4)):
        col, label = GROUP[key]
        ax.add_patch(Rectangle((bb[0] + 520 * (k % 2), ly + 22 - 22 * (k // 2) - 4), 28, 8, facecolor=col, edgecolor="none"))
        ax.text(bb[0] + 520 * (k % 2) + 36, ly + 22 - 22 * (k // 2), label, ha="left", va="center", fontsize=8.8, color=INK)
    ax.plot([bb[2] - 200, bb[2]], [ly + 10, ly + 10], color=INK, linewidth=2)
    ax.text(bb[2] - 100, ly + 4, "200 um", ha="center", va="top", fontsize=8.5, color=INK)
    ax.set_xlim(bb[0] - 12, bb[2] + 75); ax.set_ylim(ly - 22, bb[3] + 75); ax.set_aspect("equal"); ax.axis("off")
    area = (bb[2] - bb[0]) * (bb[3] - bb[1]) * 1e-6
    ax.set_title("The analog macro assembled: %.0f um x %.0f um = %.2f mm2 (its thirteen cells alone: %.2f mm2)" % (bb[2] - bb[0], bb[3] - bb[1], area, m["cell_area"]),
                 fontsize=11.5, fontweight="bold", color=INK, loc="left", pad=14)
    fig.savefig(os.path.join(OUT, "analog_macro_map.png"), dpi=170, facecolor=SURF, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    work = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")
    os.makedirs(OUT, exist_ok=True)
    fig_map(json.load(open(os.path.join(work, "caparray_map.json"))))
    fig_section()
    fig_linearity(json.load(open(os.path.join(work, "caparray_pex.json"))))
    if os.path.exists(os.path.join(work, "bgr_map.json")):
        fig_bgr_map(json.load(open(os.path.join(work, "bgr_map.json"))))
    if os.path.exists(os.path.join(work, "rv328_adccmp_map.json")):
        fig_cmp_map(json.load(open(os.path.join(work, "rv328_adccmp_map.json"))))
    if os.path.exists(os.path.join(work, "adcfe_map.json")):
        fig_fe_map(json.load(open(os.path.join(work, "adcfe_map.json"))))
    for cell, (title, notes) in NOTES.items():
        path = os.path.join(work, cell + "_map.json")
        if os.path.exists(path):
            m = json.load(open(path))
            for d in m["placed"]:
                d["note"] = notes.get(d["name"], "")
            passive = [d for d in m["placed"] if d["kind"] in ("res", "cap")]
            x_p = max(d["box"][2] for d in passive if d["name"] != "xct")
            fig_block_map(m, cell.replace("rv328_", ""), title, [(m["bbox"][0], x_p, "resistors and capacitors"), (x_p, m["bbox"][2], "transistors")])
    for cell, (title, notes) in SMALL.items():
        path = os.path.join(work, cell + "_map.json")
        if os.path.exists(path):
            m = json.load(open(path))
            for d in m["placed"]:
                d["note"] = notes.get(d["name"], "")
            fig_block_map(m, cell.replace("rv328_", ""), title, [], wide=20.0)
    for cell, (title, notes, parts, marked) in STACKS.items():
        path = os.path.join(work, cell + "_map.json")
        if os.path.exists(path):
            fig_stack_map(json.load(open(path)), cell.replace("rv328_", ""), title, notes, parts, marked)
    fig_family(work)
    if os.path.exists(os.path.join(work, "rv328_analog_map.json")):
        fig_macro(json.load(open(os.path.join(work, "rv328_analog_map.json"))))
    res = os.path.join(HERE, "..", "results")
    if os.path.exists(os.path.join(res, "adcfe_layout.md")) and "Transition positions" in open(os.path.join(res, "adcfe_layout.md")).read():
        fig_transitions(os.path.join(res, "adcfe.md"), os.path.join(res, "adcfe_layout.md"), os.path.join(res, "adcpat.md"))
