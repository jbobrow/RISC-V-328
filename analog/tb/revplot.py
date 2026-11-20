"""Figure: the ADC comparator reversing a decision, with its second-stage capacitor left connected (as it
was after the second design round) and with the capacitor switched off after the clamps open (now).
Writes results/comparator_reversal.png. Needs numpy and matplotlib in addition to ngspice."""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from sim import run
import adccmp

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "results")
W = os.path.abspath(os.path.join(OUT, "wave"))

def old_comparator():
    """The present netlist with the capacitor wired straight to o1 again."""
    text = open(os.path.join(HERE, "..", "blocks", "adccmp.spice")).read()
    body = text[text.index(".subckt rv328_adccmp"):]
    body = body[:body.index(".ends") + 5]
    body = body.replace(".subckt rv328_adccmp", ".subckt rv328_adccmp_old")
    body = re.sub(r"^xso .*\n", "", body, flags=re.M).replace("xco  oc vss", "xco  o1 vss")
    return body

def simulate(vdd=2.7, corner="ss", temp=125):
    os.makedirs(W, exist_ok=True)
    for name, cell in (("rev_new", "rv328_adccmp"), ("rev_old", "rv328_adccmp_old")):
        tb = adccmp.TBR.replace("rv328_adccmp", cell).replace("tran 20n 30u", "tran 5n 20u\nwrdata %s/%s.txt v(x1.o1) v(out) v(x1.vb)" % (W, name))
        deck = old_comparator() + "\n" + tb.format(vdd=vdd, cm=0.4 * vdd, d="-0.3e-3", d1="5e-3", half=vdd / 2)
        run(deck, vdd=vdd, corner=corner, temp=temp)

def draw(vdd=2.7):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    INK, INK2, GRID, SURF, BLUE, ORANGE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb", "#2a78d6", "#d9730d"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 5.8), sharex=True, facecolor=SURF)
    data = {}
    for name in ("rev_old", "rev_new"):
        a = np.loadtxt(os.path.join(W, name + ".txt"))
        data[name] = (a[:, 0] * 1e6 - 12.0, a[:, 1], a[:, 3], a[:, 5])
    for ax in axes:
        ax.set_facecolor(SURF); ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.axvline(0, color=INK2, linewidth=0.8, linestyle=(0, (4, 3)))
    for name, col, label in (("rev_old", ORANGE, "capacitor always connected (second round)"), ("rev_new", BLUE, "capacitor switched off after the clamps open (now)")):
        t, o1, out, vb = data[name]
        axes[0].plot(t, o1, color=col, linewidth=1.8, label=label)
        axes[1].plot(t, out, color=col, linewidth=1.8)
        k = np.where((t > 0.02) & (out < vdd / 2))[0]
        if len(k):
            axes[1].annotate("output reverses after %.1f us" % t[k[0]], (t[k[0]], vdd / 2), (t[k[0]] + 0.25, vdd / 2 + 0.35), fontsize=8.5, color=INK,
                             arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    axes[0].plot(data["rev_new"][0], data["rev_new"][3], color=INK2, linewidth=1.0, linestyle=(0, (1, 2)))
    axes[0].text(-0.9, data["rev_new"][3][0] - 0.03, "switching level\nof the next stage", ha="left", va="top", fontsize=8, color=INK2)
    axes[0].set_ylabel("Second-stage output (V)"); axes[1].set_ylabel("Comparator output (V)")
    axes[1].set_xlabel("Time after the input reverses (us)")
    axes[0].legend(loc="lower right", frameon=False, fontsize=8.5)
    axes[0].text(0.08, 0.24, "input goes from +5 mV to -0.3 mV", ha="left", va="center", fontsize=8, color=INK2)
    axes[1].axvspan(5, 8, color=GRID, alpha=0.5, linewidth=0)
    axes[1].text(5.1, 0.15, "next bit (5 us per bit at the fastest ADC clock)", ha="left", va="bottom", fontsize=8, color=INK2)
    axes[1].set_xlim(-1, 8)
    fig.suptitle("ADC comparator reversing a decision on 0.3 mV: slow corner, 125 C, 2.7 V", fontsize=11, fontweight="bold", color=INK, x=0.07, ha="left")
    fig.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.09, hspace=0.12)
    fig.savefig(os.path.join(OUT, "comparator_reversal.png"), dpi=170, facecolor=SURF)

if __name__ == "__main__":
    if "--draw-only" not in sys.argv:
        simulate()
    draw()
