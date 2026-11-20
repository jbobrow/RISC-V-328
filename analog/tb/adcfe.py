"""ADC front end: complete 10-bit conversions, one transient each, and the position of code transitions.

The successive-approximation logic is digital and lives in the core, so here the trial codes are applied
in the order that logic would apply them for the given input, and all ten comparator decisions are
checked. In the first table inputs sit in the middle of a code, so a conversion is "correct" when every
transition it crosses is within half an LSB of its ideal place. The second table measures where
individual transitions actually are.

  adcfe.py [quick] [--pex | --layout]
     quick      nominal conditions only
     --pex      with the capacitor array as extracted from its layout
     --layout   with the whole front end as extracted from its layout (array, switches, logic, comparator)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table, LAYOUT_ADC

TS, TH, TBIT = 1e-6, 11e-6, 5e-6        # sample from 1 to 11 us, then 5 us per bit (200 kHz ADC clock)

TB = """
vdd avdd 0 {vdd}
* comparator bias: the 4 uA unit current the reference block provides
ib vbp 0 4u
xmb vbp vbp avdd avdd pfet_06v0 w=16u l=8u
vr vrefp 0 {vref}
vin src 0 {vin}
rs src ain 10k
vs sample 0 pwl(0 0 {ts} 0 '{ts}+10n' {vdd} {th} {vdd} '{th}+10n' 0)
{codes}
x1 avdd 0 ain vrefp sample d9 d8 d7 d6 d5 d4 d3 d2 d1 d0 vbp avdd cmp rv328_adcfe
* Tight tolerances: with ngspice's defaults the charge on the array is not conserved well enough,
* and transitions move by up to 0.4 LSB at a 1.1 V reference (gear integration agrees with these).
.options reltol=1e-4 abstol=1e-13 vntol=1e-7
.control
tran 20n {tend}
{meas}
meas tran topmin min v(x1.top) from={th} to={tend}
meas tran topmax max v(x1.top) from={th} to={tend}
meas tran iref avg i(vr) from={ts} to={tend}
meas tran idd avg i(vdd) from={ts} to={tend}
.endc
"""

def convert(k, vref=5.0, vdd=5.0, frac=0.5, **kw):
    """Convert an input of (k + frac) LSB. Returns (result, list of decisions, expected decisions, sim dict)."""
    vin = (k + frac) * vref / 1024
    acc, trials, expect = 0, [], []
    for n in range(10):
        t = acc | (1 << (9 - n)); trials.append(t)
        keep = vin >= t * vref / 1024; expect.append(int(keep))
        if keep: acc = t
    codes = []
    for b in range(10):
        pts, last = [], None
        for n, t in enumerate(trials):
            v = vdd if (t >> b) & 1 else 0
            if last is None: pts.append("0 %g" % v)
            elif v != last: pts.append("%.4g %g %.4g %g" % (TH + n * TBIT, last, TH + n * TBIT + 10e-9, v))
            last = v
        codes.append("vd%d d%d 0 pwl(%s)" % (b, b, " ".join(pts)))
    meas = "\n".join("meas tran c%d find v(cmp) at=%.5g" % (n, TH + (n + 1) * TBIT - 50e-9) for n in range(10))
    r = run(TB.format(vdd=vdd, vref=vref, vin=vin, ts=TS, th=TH, tend=TH + 10 * TBIT, codes="\n".join(codes), meas=meas), vdd=vdd, **kw)
    got = [int(r.get("c%d" % n, -vdd) > vdd / 2) if ("c%d" % n) in r else -1 for n in range(10)]
    res = 0
    for n in range(10):
        if got[n] == 1: res |= 1 << (9 - n)
    # the result is only meaningful when the decisions agree with the sequence that was applied
    return (res if got == expect else None), got, expect, r


def threshold(code, vref=5.0, vdd=5.0, steps=7, **kw):
    """Where the transition into `code` actually is, as an error in LSB (negative: at a lower input than ideal).
    Trial code `code` is applied at the step of its lowest set bit, and the trials before it are the same
    for any input within one LSB of it, so a bisection on that one decision finds the transition."""
    n = 9 - ((code & -code).bit_length() - 1)
    lo, hi = -1.0, 1.0
    for _ in range(steps):
        f = (lo + hi) / 2
        _, got, _, _ = convert(code, vref, vdd, frac=f, **kw)
        if got[n] == 1: hi = f
        else: lo = f
    return (lo + hi) / 2


if __name__ == "__main__":
    quick = "quick" in sys.argv[1:]
    pex = ("adccap",) if "--pex" in sys.argv[1:] else LAYOUT_ADC if "--layout" in sys.argv[1:] else False
    if pex == ("adccap",): print("Capacitor array with the wiring capacitance extracted from its layout (analog/layout).\n")
    if pex == LAYOUT_ADC: print("The whole front end as extracted from its layout (analog/layout): devices as drawn, with the wiring capacitance.\n")
    plan = [(5.0, 5.0, "tt", 25, (0, 1, 2, 3, 127, 128, 255, 256, 341, 511, 512, 682, 767, 768, 1022, 1023)),
            (1.1, 5.0, "tt", 25, (1, 341, 512, 682, 1023)), (2.7, 2.7, "tt", 25, (0, 341, 512, 682, 1023)),
            (4.5, 4.5, "ss", 125, (0, 341, 682, 1023)), (5.5, 5.5, "ff", -40, (0, 341, 682, 1023)), (2.7, 2.7, "ss", -40, (0, 341, 682, 1023)),
            (1.1, 2.7, "ss", 125, (1, 341, 682, 1023)), (1.1, 5.5, "ff", 125, (1, 341, 682, 1023))]
    if quick: plan = plan[:1]
    rows, bad = [], 0
    for vref, vdd, corner, temp, ks in plan:
        for k in ks:
            res, got, expect, r = convert(k, vref, vdd, corner=corner, temp=temp, pex=pex)
            ok = res == k; bad += not ok
            rows.append(dict(vref=vref, vdd=vdd, corner=corner, temp=temp, k=k, vin=1e3 * (k + 0.5) * vref / 1024,
                             dec="".join("?" if g < 0 else str(g) for g in got), ok="yes" if ok else "NO (expected %s)" % "".join(map(str, expect)),
                             lo=r.get("topmin", float("nan")), hi=r.get("topmax", float("nan")),
                             iref=-1e6 * r.get("iref", float("nan")), idd=-1e6 * r.get("idd", float("nan"))))
            sys.stderr.write("%s\n" % rows[-1])
    print(table(rows, [("vref", "Reference (V)", "%.1f"), ("vdd", "AVDD (V)", "%.1f"), ("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"),
                       ("vin", "Input (mV)", "%.2f"), ("k", "Expected code", "%d"), ("dec", "Comparator decisions, MSB first", "%s"), ("ok", "Correct", "%s"),
                       ("lo", "Top plate, lowest (V)", "%.2f"), ("hi", "highest (V)", "%.2f"),
                       ("iref", "Reference current, average (uA)", "%.1f"), ("idd", "AVDD current, average (uA)", "%.0f")]))
    print("\n%d of %d conversions correct." % (len(rows) - bad, len(rows)))

    plan = [(5.0, 5.0, "tt", 25, (1, 2, 4, 64, 128, 256, 341, 512, 683, 768, 896, 1023)),
            (1.1, 5.0, "tt", 25, (1, 256, 512, 768, 1023)), (2.7, 2.7, "tt", 25, (1, 256, 512, 768, 1023)),
            (4.5, 4.5, "ss", 125, (1, 512, 1023)), (5.5, 5.5, "ff", -40, (1, 512, 1023)), (2.7, 2.7, "ss", -40, (1, 512, 1023)),
            (1.1, 2.7, "ss", 125, (1, 512, 1023)), (1.1, 5.5, "ff", 125, (1, 512, 1023))]
    if quick: plan = plan[:1]
    steps = 7
    if pex == LAYOUT_ADC:
        # a conversion from the layout takes four to five times as long: three transitions per condition, to 1/32 LSB
        plan, steps = [(vref, vdd, corner, temp, (1, 512, 1023)) for vref, vdd, corner, temp, _ in plan], 6
    rows = []
    for vref, vdd, corner, temp, codes in plan:
        for c in codes:
            e = threshold(c, vref, vdd, steps=steps, corner=corner, temp=temp, pex=pex)
            rows.append(dict(vref=vref, vdd=vdd, corner=corner, temp=temp, c="%d / %d" % (c - 1, c), e=e, mv=e * vref / 1024 * 1e3))
            sys.stderr.write("%s\n" % rows[-1])
    print("\nTransition positions (bisection to 1/%d LSB)\n" % 2 ** (steps - 1))
    print(table(rows, [("vref", "Reference (V)", "%.1f"), ("vdd", "AVDD (V)", "%.1f"), ("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"),
                       ("c", "Transition", "%s"), ("e", "Error (LSB)", "%+.2f"), ("mv", "Error (mV at the input)", "%+.2f")]))
    worst = max(rows, key=lambda r: abs(r["e"]))
    print("\nLargest transition error: %+.2f LSB (%s, %.1f V reference, %s %d C)." % (worst["e"], worst["c"], worst["vref"], worst["corner"], worst["temp"]))

    if not quick and pex != LAYOUT_ADC:
        import statistics
        v = [threshold(512, 1.1, 5.0, mismatch=True, seed=s, pex=pex) for s in range(1, 11)]
        print("\nTransistor mismatch, 10 runs, 511 / 512 transition at a 1.1 V reference: mean %+.2f LSB, sigma %.2f LSB, worst %+.2f LSB."
              % (statistics.mean(v), statistics.stdev(v), max(v, key=abs)))
        print("(The foundry capacitor model has no mismatch term, so capacitor matching is not part of this.)")
