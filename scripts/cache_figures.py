#!/usr/bin/python3
"""Figures of the cache study from the benchmark logs in build/bench/run (docs/cache_study.md).

  cache_figures.py      writes docs/cache_speed_vs_avr.png and docs/cache_organisation.png
"""
import os, re, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "build", "bench", "run")
INK, INK2, MUTED, GRID, AXIS, SURF = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"

def marks(path):
    t = open(path).read()
    return t, dict((int(a), (int(c), int(v))) for a, c, v in re.findall(r"MARK (\d+) cyc=(\d+).*?val=(\d+)", t))

def window(name):
    _, m = marks(os.path.join(RUN, name))
    return m[2][0] - m[1][0]

def style(ax):
    ax.set_facecolor(SURF)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=MUTED, length=0, labelsize=10)
    ax.xaxis.grid(True, color=GRID, linewidth=1)
    ax.set_axisbelow(True)

def speed_vs_avr():
    progs = [("blink", "Blink and button\n(1.0 KB)"), ("display", "Display UI\n(3.5 KB)"), ("comms", "Serial protocol\n(2.5 KB)"),
             ("logger", "Float sensor logger\n(15.2 KB)"), ("full", "All three in one\n(19.4 KB)")]
    cfgs = [("2_1_0_0", "2 KB cache (today)", MUTED), ("4_3_2_0", "12 KB three-way cache", BLUE), ("4_3_2_1", "12 KB cache and fast multiplier", ORANGE)]
    fig, ax = plt.subplots(figsize=(9.6, 6.2), dpi=160)
    fig.patch.set_facecolor(SURF)
    style(ax)
    h = 0.24
    for i, (p, label) in enumerate(progs):
        avr = window("avr_%s.log" % p)
        for k, (c, _, col) in enumerate(cfgs):
            v = avr / window("%s_null.%s.log" % (p, c))
            y = i + (k - 1) * (h + 0.03)
            ax.barh(y, v, height=h, color=col)
            ax.text(v * 1.06, y, ("%.2f" % v if v < 1 else "%.1f" % v) + "×", va="center", ha="left", fontsize=9.5, color=INK2)
    ax.axvline(1.0, color=INK, linewidth=1.2)
    ax.text(1.04, 4.56, "ATmega328P", ha="left", va="center", fontsize=10, color=INK)
    ax.set_xscale("log")
    ax.set_xlim(0.02, 8)
    ax.set_xticks([0.05, 0.1, 0.25, 0.5, 1, 2, 4])
    ax.set_xticklabels(["0.05×", "0.1×", "0.25×", "0.5×", "1×", "2×", "4×"])
    ax.minorticks_off()
    ax.set_yticks(range(len(progs)))
    ax.set_yticklabels([l for _, l in progs], fontsize=10.5, color=INK)
    ax.invert_yaxis()
    ax.set_xlabel("Speed at the same clock, relative to an ATmega328P (higher is faster)", color=INK2, fontsize=10.5)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in cfgs], labels=[n for _, n, _ in cfgs],
              loc="upper center", bbox_to_anchor=(0.45, 1.09), ncol=3, frameon=False, fontsize=10, labelcolor=INK2, handlelength=1, handleheight=1)
    fig.suptitle("The same C programs on the RV328 and on an ATmega328P: processor work only", x=0.02, ha="left", fontsize=13, color=INK, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(os.path.join(ROOT, "docs", "cache_speed_vs_avr.png"), facecolor=SURF)

def organisation():
    cfgs = [("2_1_0", "2 KB, simple (today)"), ("8_1_0", "8 KB, simple"), ("4_2_0", "8 KB, two-way"), ("4_3_2", "12 KB, three-way, handlers pinned"),
            ("16_1_0", "16 KB, simple"), ("8_2_0", "16 KB, two-way")]
    ref = window("full.16_2_0.log")
    fig, ax = plt.subplots(figsize=(9.6, 4.9), dpi=160)
    fig.patch.set_facecolor(SURF)
    style(ax)
    for i, (c, label) in enumerate(cfgs):
        t, m = marks(os.path.join(RUN, "full.%s.log" % c))
        v = (m[2][0] - m[1][0]) / ref
        lat = sorted(int(x) for x in re.findall(r"IRQLAT (\d+)", t))
        ax.barh(i, v, height=0.5, color=ORANGE if c == "4_3_2" else BLUE)
        ax.text(v + 0.08, i, "%.2f\u00d7" % v, va="center", ha="left", fontsize=9.5, color=INK2)
        ax.text(7.6, i, "%d of 40" % m[2][1], va="center", ha="center", fontsize=10, color=INK2)
        ax.text(10.2, i, "%d clocks" % lat[int(len(lat) * 0.95)], va="center", ha="center", fontsize=10, color=INK2)
    ax.text(7.6, -0.78, "Serial requests\nanswered", va="center", ha="center", fontsize=10, color=INK)
    ax.text(10.2, -0.78, "Interrupt answered\nwithin (95 %)", va="center", ha="center", fontsize=10, color=INK)
    ax.plot([1, 1], [-0.4, 5.4], color=INK, linewidth=1.2)
    ax.set_ylim(-1.15, 5.5)
    ax.set_xlim(0, 11.6)
    ax.set_xticks([1, 2, 3, 4, 5, 6])
    ax.set_xticklabels(["1×", "2×", "3×", "4×", "5×", "6×"])
    ax.set_yticks(range(len(cfgs)))
    ax.set_yticklabels([l for _, l in cfgs], fontsize=10.5, color=INK)
    ax.invert_yaxis()
    ax.xaxis.grid(False)
    for gx in (2, 3, 4, 5, 6):
        ax.plot([gx, gx], [-0.4, 5.4], color=GRID, linewidth=1, zorder=0)
    ax.set_xlabel("Time for the same work, relative to everything cached (lower is better)", color=INK2, fontsize=10.5, loc="left")
    fig.suptitle("The 19.4 KB firmware on six cache designs, on the simulated chip with interrupts and serial traffic", x=0.02, ha="left", fontsize=13, color=INK, y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(os.path.join(ROOT, "docs", "cache_organisation.png"), facecolor=SURF)

if __name__ == "__main__":
    speed_vs_avr()
    organisation()
