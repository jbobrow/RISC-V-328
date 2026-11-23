#!/usr/bin/env python3
"""Picture of a placed (or routed) trial layout: where the cells are and how full each part of the core is.

  trial_figure.py <chip.def> <pdk>/gf180mcuD <out.png> [title]

Cell area per 25 um square as a share of the square, one hue from light to dark; macros as outlines.
"""
import glob
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

SURF, INK, INK2 = "#fcfcfb", "#1a1a19", "#6b6a66"
BIN = 25.0


def main(path, pdk, out, title):
    area, size = {}, {}
    for f in glob.glob(pdk + "/libs.ref/gf180mcu_fd_sc_mcu9t5v0/lef/*.lef") + glob.glob(pdk + "/libs.ref/gf180mcu_fd_ip_sram/lef/*.lef"):
        for m in re.finditer(r"MACRO (\S+).*?SIZE ([\d.]+) BY ([\d.]+)", open(f).read(), re.S):
            size[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    t = open(path).read()
    dbu = float(re.search(r"UNITS DISTANCE MICRONS (\d+)", t).group(1))
    die = [float(v) / dbu for v in re.search(r"DIEAREA \( (\S+) (\S+) \) \( (\S+) (\S+) \)", t).groups()]
    rows = [(int(x) / dbu, int(y) / dbu, int(n) * int(s) / dbu) for x, y, n, s in re.findall(r"^ROW \S+ \S+ (\d+) (\d+) \S+ DO (\d+) BY 1 STEP (\d+)", t, re.M)]
    core = (min(r[0] for r in rows), min(r[1] for r in rows), max(r[0] + r[2] for r in rows), max(r[1] for r in rows) + 5.04)
    nx, ny = int(die[2] // BIN) + 1, int(die[3] // BIN) + 1
    grid, room = np.zeros((ny, nx)), np.zeros((ny, nx))
    for x, y, w in rows:                                   # row area per square
        for k in range(int(x // BIN), int((x + w) // BIN) + 1):
            a, b = max(x, k * BIN), min(x + w, (k + 1) * BIN)
            if b > a:
                room[int(y // BIN), k] += (b - a) * 5.04
    macros, total = [], 0.0
    comp = t[t.index("COMPONENTS"):t.index("END COMPONENTS")]
    for m in re.finditer(r"- (\S+) (\S+) .*?\+ (?:PLACED|FIXED) \( (-?\d+) (-?\d+) \) (\S+)", comp):
        name, cell, x, y, o = m.group(1), m.group(2), int(m.group(3)) / dbu, int(m.group(4)) / dbu, m.group(5)
        if "sram" in cell or cell in ("rv328_analog_blank", "rv328_analog"):
            macros.append((name, cell, x, y))
            continue
        if cell not in size or "__fill_" in cell or "__fillcap" in cell:
            continue
        w, h = size[cell]
        grid[int(y // BIN), int(x // BIN)] += w * h
        total += w * h
    dens = np.where(room > 0, np.minimum(grid / np.maximum(room, 1e-9), 1.0), np.nan)
    fig, ax = plt.subplots(figsize=(13, 13 * die[3] / die[2] + 0.9), facecolor=SURF)
    ax.set_facecolor(SURF)
    im = ax.imshow(dens, origin="lower", extent=(0, nx * BIN, 0, ny * BIN), cmap="Blues", vmin=0, vmax=1, interpolation="nearest", zorder=1)
    ax.add_patch(Rectangle((die[0], die[1]), die[2], die[3], facecolor="none", edgecolor=INK, linewidth=1.0, zorder=3))
    ax.add_patch(Rectangle((core[0], core[1]), core[2] - core[0], core[3] - core[1], facecolor="none", edgecolor=INK2, linewidth=0.8, linestyle=(0, (4, 3)), zorder=3))
    ax.text((die[0] + die[2]) / 2, (core[1]) / 2, "pad ring", ha="center", va="center", fontsize=9, color=INK2)
    lef_blank = re.search(r"SIZE ([\d.]+) BY ([\d.]+)", open(sys.argv[5]).read()) if len(sys.argv) > 5 else None
    for name, cell, x, y in macros:
        if cell == "rv328_analog_blank":
            w, h = (float(lef_blank.group(1)), float(lef_blank.group(2))) if lef_blank else (927.0, 1381.0)
            ax.add_patch(Rectangle((x, y), w, h, facecolor="#e9e7e1", edgecolor=INK, linewidth=1.0, hatch="///", zorder=2))
            ax.text(x + w / 2, y + h / 2, "blank block\n(room for the analog macro)\n%.0f x %.0f um" % (w, h), ha="center", va="center", fontsize=10.5, color=INK, zorder=4,
                    bbox=dict(facecolor=SURF, edgecolor="none", pad=3))
        elif cell == "rv328_analog":
            w, h = (float(lef_blank.group(1)), float(lef_blank.group(2)))
            ax.add_patch(Rectangle((x, y), w, h, facecolor="#d9e4d2", edgecolor=INK, linewidth=1.0, zorder=2))
            ax.text(x + w / 2, y + h / 2, "analog macro\n%.0f x %.0f um" % (w, h), ha="center", va="center", fontsize=10.5, color=INK, zorder=4,
                    bbox=dict(facecolor=SURF, edgecolor="none", pad=3))
        else:
            w, h = size[cell]
            ax.add_patch(Rectangle((x, y), w, h, facecolor="#efeeea", edgecolor=INK2, linewidth=0.7, zorder=2))
            ax.text(x + w / 2, y + h / 2, "SRAM\n" + ("cache" if "cache" in name else "RAM"), ha="center", va="center", fontsize=8, color=INK2, zorder=4)
    ax.set_xlim(die[0] - 20, die[2] + 20); ax.set_ylim(die[1] - 20, die[3] + 20); ax.set_aspect("equal"); ax.axis("off")
    cb = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.035, pad=0.02, aspect=50)
    cb.set_label("share of the cell rows taken by cells, per %.0f um square (fill cells not counted)" % BIN, fontsize=9, color=INK)
    cb.outline.set_visible(False)
    ax.set_title(title + "   (%.2f mm2 of cells in %.2f mm2 of rows: %.0f %%)" % (total * 1e-6, room.sum() * 1e-6, 100 * total / room.sum()),
                 fontsize=11.5, fontweight="bold", color=INK, loc="left", pad=10)
    fig.savefig(out, dpi=150, facecolor=SURF, bbox_inches="tight")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "Trial layout")
