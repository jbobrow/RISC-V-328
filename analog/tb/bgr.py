"""Bandgap / bias: reference voltage over temperature, supply and corner; start-up; current."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table

DC = """
vdd avdd 0 {vdd}
ven en 0 {vdd}
x1 avdd 0 en vref vbp ok rv328_bgr {params}
.control
dc temp -40 125 5
meas dc vref_m40 find v(vref) at=-40
meas dc vref_25 find v(vref) at=25
meas dc vref_125 find v(vref) at=125
meas dc vref_max max v(vref)
meas dc vref_min min v(vref)
meas dc idd_25 find i(vdd) at=25
.endc
"""
LINE = """
vdd avdd 0 5
ven en 0 5
x1 avdd 0 en vref vbp ok rv328_bgr {params}
.control
dc vdd 1.5 5.5 0.05
meas dc v_2v2 find v(vref) at=2.2
meas dc v_2v7 find v(vref) at=2.7
meas dc v_5v5 find v(vref) at=5.45
.endc
"""
START = """
vdd avdd 0 pwl(0 0 100u {vdd})
ven en 0 pwl(0 0 100u {vdd})
x1 avdd 0 en vref vbp ok rv328_bgr {params}
.control
tran 0.5u 600u
meas tran t_start when v(vref)=1.0 rise=1
meas tran v_end find v(vref) at=590u
.endc
"""

def dc(params="", **kw):
    return run(DC.format(vdd=kw.get("vdd", 5.0), params=params), **kw)

if __name__ == "__main__":
    params = sys.argv[1] if len(sys.argv) > 1 else ""
    rows = []
    for corner in ("tt", "ss", "ff", "sf", "fs"):
        for vdd in (2.7, 5.0, 5.5):
            r = dc(params, corner=corner, vdd=vdd)
            r.update(corner=corner, vdd=vdd, tc=1e6 * (r["vref_max"] - r["vref_min"]) / r["vref_25"] / 165, idd=-1e6 * r["idd_25"])
            rows.append(r)
    print(table(rows, [("corner", "Corner", "%s"), ("vdd", "AVDD (V)", "%.1f"), ("vref_m40", "-40 C", "%.4f"), ("vref_25", "25 C", "%.4f"),
                       ("vref_125", "125 C", "%.4f"), ("tc", "TC (ppm/K, box)", "%.0f"), ("idd", "Current (uA)", "%.1f")]))
    r = run(LINE.format(params=params))
    print("\nLine: %.4f V at 2.2 V, %.4f V at 2.7 V, %.4f V at 5.5 V" % (r["v_2v2"], r["v_2v7"], r["v_5v5"]))
    import statistics
    mc = [run("vdd avdd 0 5\nven en 0 5\nx1 avdd 0 en vref vbp ok rv328_bgr %s\n.control\nop\nmeas op vr find v(vref) at=0\nprint v(vref)\n.endc" % params,
              mismatch=True, seed=s)["_log"] for s in range(1, 41)]
    import re
    v = [float(re.search(r"v\(vref\) = ([-0-9.e+]+)", l).group(1)) for l in mc]
    print("Mismatch, 40 runs at 25 C: mean %.4f V, sigma %.1f mV (%.2f %%)" % (statistics.mean(v), 1e3 * statistics.stdev(v), 100 * statistics.stdev(v) / statistics.mean(v)))
    for corner, temp in (("tt", 25), ("ss", -40), ("ff", 125)):
        r = run(START.format(vdd=5.0, params=params), corner=corner, temp=temp)
        print("Start-up %s %d C: reference reaches 1.0 V %.0f us after the supply starts to rise, settles at %.4f V" % (corner, temp, 1e6 * r.get("t_start", float("nan")), r.get("v_end", float("nan"))))
    off = []
    for corner, temp, vdd in (("tt", 25, 5.0), ("ff", -40, 5.5), ("ff", 125, 5.5), ("ss", 125, 2.7)):
        r = run("vdd avdd 0 %g\nven en 0 0\nx1 avdd 0 en vref vbp ok rv328_bgr %s\n.control\nop\nlet ioff = -i(vdd)\nprint ioff\n.endc" % (vdd, params),
                corner=corner, temp=temp, vdd=vdd)
        off.append("%s %d C %.1f V: %.2f nA" % (corner, temp, vdd, 1e9 * r.get("ioff", float("nan"))))
    print("Disabled (en = 0): " + "; ".join(off))
