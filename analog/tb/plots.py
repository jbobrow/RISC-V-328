"""Waveform figure for the README: runs four short simulations and draws analog/results/waveforms.png.
Needs numpy and matplotlib in addition to ngspice."""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from sim import run
import adcfe, xosc, rcosc

OUT = os.path.join(os.path.dirname(__file__), "..", "results")
W = os.path.abspath(os.path.join(OUT, "wave"))

def wr(deck, name, vectors):
    """Insert a wrdata line after the transient analysis."""
    lines = deck.split("\n")
    i = max(k for k, l in enumerate(lines) if l.startswith("tran "))
    lines.insert(i + 1, "wrdata %s/%s.txt %s" % (W, name, " ".join(vectors)))
    return "\n".join(lines)

def load(name, n):
    a = np.loadtxt(os.path.join(W, name + ".txt"))
    return a[:, 0], [a[:, 2 * k + 1] for k in range(n)]

def simulate():
    os.makedirs(W, exist_ok=True)
    # 1. one ADC conversion, input in the middle of code 682, 5 V reference
    k, vref, vdd = 682, 5.0, 5.0
    vin = (k + 0.5) * vref / 1024
    acc, trials = 0, []
    for n in range(10):
        t = acc | (1 << (9 - n)); trials.append(t)
        if vin >= t * vref / 1024: acc = t
    codes = []
    for b in range(10):
        pts, last = [], None
        for n, t in enumerate(trials):
            v = vdd if (t >> b) & 1 else 0
            if last is None: pts.append("0 %g" % v)
            elif v != last: pts.append("%.4g %g %.4g %g" % (adcfe.TH + n * adcfe.TBIT, last, adcfe.TH + n * adcfe.TBIT + 10e-9, v))
            last = v
        codes.append("vd%d d%d 0 pwl(%s)" % (b, b, " ".join(pts)))
    deck = adcfe.TB.format(vdd=vdd, vref=vref, vin=vin, ts=adcfe.TS, th=adcfe.TH, tend=adcfe.TH + 10 * adcfe.TBIT, codes="\n".join(codes), meas="")
    run(wr(deck, "adc", ["v(x1.top)", "v(x1.dum)", "v(cmp)"]), vdd=vdd)
    # 2. 8 MHz crystal building up
    mode, f, esr, cl, c0 = xosc.CASES[1]
    cm = 20e-15 * 20; lm = 1 / ((2 * math.pi * f) ** 2 * cm); per = 1 / f
    deck = xosc.TR.format(vdd=5.0, half=2.5, c1=2 * cl, c2=2 * cl, c0=c0, lm=lm, cm=cm, esr=esr, t0=2 * per, tk=per / 20, step=per / 60,
                          tend=450 * per, ta=400 * per, t1x=401.5 * per, **xosc.bits(mode, 5.0))
    run(wr(deck, "xosc", ["v(xi)", "v(clk)"]), vdd=5.0)
    # 3. RC oscillator switched on and off
    deck = rcosc.TB.format(vdd=5.0, half=2.5, trim=rcosc.trimsrc(128, 5.0), params="", toff="1.0u", tend="1.5u", t3=1.2e-6, t4=1.4e-6)
    run(wr(deck, "rc", ["v(en)", "v(clk)"]), vdd=5.0)
    # 4. reference against temperature
    rows = []
    for corner in ("tt", "ss", "ff"):
        for temp in range(-40, 126, 15):
            r = run("vdd avdd 0 5\nxb avdd 0 avdd vref vbp ok rv328_bgr\n.control\nop\nlet vr = v(vref)\nprint vr\n.endc\n", corner=corner, temp=temp)
            rows.append((corner, temp, r.get("vr", float("nan"))))
    with open(os.path.join(W, "bgr.txt"), "w") as fh:
        for c, t, v in rows: fh.write("%s %d %.6f\n" % (c, t, v))

def draw():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"            # categorical slots 1-3, fixed order
    INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlecolor": INK, "figure.facecolor": SURF,
                         "axes.facecolor": SURF, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                         "grid.linewidth": 0.6, "lines.linewidth": 1.6, "legend.frameon": False})
    fig, ax = plt.subplots(2, 2, figsize=(13, 8.2), dpi=200)
    fig.subplots_adjust(left=0.06, right=0.975, top=0.90, bottom=0.07, hspace=0.42, wspace=0.17)
    fig.suptitle("RV328 analog blocks, transistor-level simulation (typical corner, 25 C, 5 V)", x=0.06, ha="left", fontsize=12.5, fontweight="bold", color=INK)

    a = ax[0][0]
    t, (top, dum, cmp_) = load("adc", 3)
    m = t > 9e-6
    a.plot(t[m] * 1e6, top[m], color=S1, label="capacitor array, top plate")
    a.plot(t[m] * 1e6, dum[m], color=S2, label="held comparison level")
    a.set_title("ADC: one conversion of 3.3325 V (code 682 = 1010101010)", loc="left")
    a.set_xlabel("time (us); sampled until 11 us, then one bit every 5 us"); a.set_ylabel("V")
    for n in range(10):
        tt = adcfe.TH + (n + 1) * adcfe.TBIT - 50e-9
        bit = int(np.interp(tt, t, cmp_) > 2.5)
        a.text((adcfe.TH + (n + 0.5) * adcfe.TBIT) * 1e6, 0.35, str(bit), ha="center", va="center", color=INK, fontsize=10, fontweight="bold")
    a.text(61.3, 0.35, "comparator\ndecisions", ha="left", va="center", color=INK2, fontsize=8)
    a.set_xlim(9, 68); a.set_ylim(0, 4.6)
    a.legend(loc="upper right", ncol=1)

    a = ax[0][1]
    t, (xi, clk) = load("xosc", 2)
    a.plot(t * 1e6, xi, color=S1, linewidth=0.5)
    a.set_title("Crystal oscillator, 8 MHz: swing at XTAL1 building up", loc="left")
    a.set_xlabel("time (us); crystal model with the build-up shortened 20 times"); a.set_ylabel("V")
    high0 = clk[0] > 2.5
    change = np.nonzero((clk > 2.5) != high0)[0]
    if len(change):
        k = change[0]
        a.axvline(t[k] * 1e6, color=INK2, linewidth=0.8, linestyle=(0, (3, 3)))
        a.text(t[k] * 1e6 - 0.6, 0.06, "clock output\nstarts", color=INK2, fontsize=8, va="bottom", ha="right")
    a.set_xlim(0, t[-1] * 1e6)

    a = ax[1][0]
    t, (en, clk) = load("rc", 2)
    a.plot(t * 1e6, clk / 5.0, color=S1)
    a.plot(t * 1e6, en / 5.0 + 1.5, color=S2)
    a.set_yticks([0.5, 2.0]); a.set_yticklabels(["clk_rc", "rc_en"], color=INK)
    a.grid(axis="y", visible=False)
    a.set_title("8 MHz RC oscillator: enabled, then disabled (no partial pulses)", loc="left")
    a.set_xlabel("time (us)"); a.set_ylim(-0.2, 2.8); a.set_xlim(0, 1.5)

    a = ax[1][1]
    rows = [l.split() for l in open(os.path.join(W, "bgr.txt"))]
    for corner, col, name in (("tt", S1, "typical"), ("ss", S2, "slow"), ("ff", S3, "fast")):
        x = [int(r[1]) for r in rows if r[0] == corner]; y = [float(r[2]) for r in rows if r[0] == corner]
        a.plot(x, y, color=col, marker="o", markersize=3.5, label=name)
        a.text(x[-1] + 3, y[-1], name, color=INK, fontsize=8.5, va="center")
    a.set_title("1.1 V reference against temperature, three process corners", loc="left")
    a.set_xlabel("temperature (C)"); a.set_ylabel("V"); a.set_ylim(1.085, 1.112); a.set_xlim(-45, 148)
    a.legend(loc="lower left", ncol=3)
    fig.savefig(os.path.join(OUT, "waveforms.png"))

if __name__ == "__main__":
    if "--draw-only" not in sys.argv:
        simulate()
    draw()
