"""RC oscillator: frequency against trim, supply, temperature and corner; start, stop, current.
  rcosc.py          the tables of results/rcosc.md
  rcosc.py steps    the trim steps where a larger bit takes over (results/rcosc_steps*.md)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table

TB = """
vdd avdd 0 {vdd}
ven en 0 pwl(0 0 0.2u 0 0.201u {vdd} {toff} {vdd} '{toff}+1n' 0)
{trim}
x1 avdd 0 en t7 t6 t5 t4 t3 t2 t1 t0 clk rv328_rcosc {params}
cl clk 0 50f
.control
tran 0.2n {tend}
meas tran t1 when v(clk)={half} rise=3
meas tran t2 when v(clk)={half} rise=9
meas tran tf1 when v(clk)={half} fall=3
meas tran t_first when v(clk)={half} rise=1
meas tran idd avg i(vdd) from=0.8u to=1.5u
meas tran ioff avg i(vdd) from={t3} to={t4}
meas tran nrise_dummy when v(clk)={half} rise=last
.endc
"""

def trimsrc(code, vdd):
    return "\n".join("vt%d t%d 0 %g" % (i, i, vdd if (code >> i) & 1 else 0) for i in range(8))

def osc(code=128, vdd=5.0, params="", toff="1.8u", tend="3.2u", **kw):
    r = run(TB.format(vdd=vdd, half=vdd / 2, trim=trimsrc(code, vdd), params=params, toff=toff, tend=tend,
                      t3=float(toff.rstrip('u')) * 1e-6 + 0.9e-6, t4=float(toff.rstrip('u')) * 1e-6 + 1.3e-6), vdd=vdd, **kw)
    if "t1" in r and "t2" in r:
        r["f"] = 6 / (r["t2"] - r["t1"]) / 1e6
        r["duty"] = 100 * (r["tf1"] - r["t1"]) * r["f"] * 1e6
        r["i"] = -1e6 * r.get("idd", float("nan"))
        r["ioff_n"] = -1e9 * r.get("ioff", float("nan"))
        r["start"] = 1e6 * (r["t_first"] - 0.2e-6)
        r["stop"] = 1e6 * (r["nrise_dummy"] - float(toff.rstrip("u")) * 1e-6)
    return r

STEPS = (0x07, 0x08, 0x0F, 0x10, 0x1F, 0x20, 0x3F, 0x40, 0x41, 0x7F, 0x80, 0x81, 0xBF, 0xC0, 0xDF, 0xE0, 0xFE, 0xFF)


def steps(freq=None):
    """Frequency on either side of every place where a larger trim bit takes over from the smaller ones:
    there the step depends on how well the banks match, wiring included. freq: {code: MHz} already known."""
    freq = dict(freq or {})
    for code in STEPS:
        if code not in freq:
            freq[code] = osc(code, **(dict(toff="2.8u", tend="4.2u") if code < 100 else {})).get("f", float("nan"))
    rows = []
    for a, b in zip(STEPS, STEPS[1:]):
        if b == a + 1:
            rows.append(dict(a="0x%02X" % a, b="0x%02X" % b, fa=freq[a], fb=freq[b], step=100 * (freq[b] / freq[a] - 1)))
    print(table(rows, [("a", "From", "%s"), ("b", "To", "%s"), ("fa", "Frequency (MHz)", "%.4f"), ("fb", "Frequency (MHz)", "%.4f"),
                       ("step", "Step (%)", "%+.2f")]))
    print("\nSmallest step %+.2f %%, largest %+.2f %%. 0x40 to 0x41 and 0x80 to 0x81 are ordinary steps of one unit, for comparison." % (min(r["step"] for r in rows), max(r["step"] for r in rows)))


if __name__ == "__main__":
    if sys.argv[1:2] == ["steps"]:               # rcosc.py steps [code=MHz ...]
        steps({int(a.split("=")[0], 16): float(a.split("=")[1]) for a in sys.argv[2:]})
        sys.exit()
    params = sys.argv[1] if len(sys.argv) > 1 else ""
    rows = []
    for code in (0, 64, 127, 128, 129, 192, 255):
        # the lowest settings need a longer window for nine periods
        r = osc(code, params=params, **(dict(toff="2.8u", tend="4.2u") if code < 100 else {})); r["code"] = "0x%02X" % code; rows.append(r)
    print(table(rows, [("code", "Trim", "%s"), ("f", "Frequency (MHz)", "%.3f"), ("duty", "Duty (%)", "%.1f")]))
    f0 = rows[3]["f"]
    print("\nStep at centre: %.2f %% per code. Range %.2f to %.2f MHz." % (50 * (rows[4]["f"] - rows[2]["f"]) / f0, rows[0].get("f", float("nan")), rows[-1].get("f", float("nan"))))
    rows = []
    for corner in ("tt", "ss", "ff", "sf", "fs", "tt_rcmax", "tt_rcmin"):
        for vdd, temp in (((5.0, 25), (5.0, -40), (5.0, 125), (2.7, 25), (3.3, 25), (5.5, 25), (4.5, 125), (5.5, -40)) if corner == "tt"
                          else ((5.0, 25), (4.5, 125), (5.5, -40)) if corner in ("ss", "ff") else ((5.0, 25),)):
            r = osc(128, vdd=vdd, corner=corner, temp=temp, params=params)
            r.update(corner=corner, vdd=vdd, temp=temp, dev=100 * (r.get("f", float("nan")) / f0 - 1)); rows.append(r)
    print()
    print(table(rows, [("corner", "Corner", "%s"), ("vdd", "AVDD (V)", "%.1f"), ("temp", "Temp (C)", "%d"), ("f", "Frequency (MHz)", "%.3f"),
                       ("dev", "vs typical (%)", "%+.1f"), ("i", "Current (uA)", "%.0f"), ("ioff_n", "Off current (nA)", "%.1f"),
                       ("start", "First clock after enable (us)", "%.2f"), ("stop", "Last rising edge after disable (us)", "%.2f")]))
