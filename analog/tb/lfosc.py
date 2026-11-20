"""128 kHz oscillator: frequency and current over supply, temperature and corner."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table

TB = """
vdd avdd 0 pwl(0 0 2u {vdd})
x1 avdd 0 clk rv328_lfosc {params}
cl clk 0 50f
.control
tran 20n 160u
meas tran t1 when v(clk)={half} rise=4
meas tran t2 when v(clk)={half} rise=10
meas tran tf1 when v(clk)={half} fall=4
meas tran idd avg i(vdd) from=40u to=100u
.endc
"""
def osc(vdd=5.0, params="", **kw):
    r = run(TB.format(vdd=vdd, half=vdd / 2, params=params), vdd=vdd, **kw)
    if "t1" in r and "t2" in r:
        r["f"] = 6 / (r["t2"] - r["t1"]) / 1e3
        r["duty"] = 100 * (r["tf1"] - r["t1"]) * r["f"] * 1e3
        r["i"] = -1e6 * r["idd"]
    return r

if __name__ == "__main__":
    params = sys.argv[1] if len(sys.argv) > 1 else ""
    rows = []
    for corner in ("tt", "ss", "ff", "sf", "fs", "tt_rcmax", "tt_rcmin"):
        for vdd, temp in (((5.0, 25), (5.0, -40), (5.0, 125), (2.7, 25), (3.3, 25), (5.5, 25)) if corner == "tt" else ((5.0, 25), (4.5, 125), (5.5, -40)) if corner in ("ss", "ff") else ((5.0, 25),)):
            r = osc(vdd=vdd, corner=corner, temp=temp, params=params)
            r.update(corner=corner, vdd=vdd, temp=temp); rows.append(r)
    f0 = rows[0]["f"]
    for r in rows: r["dev"] = 100 * (r.get("f", float("nan")) / f0 - 1)
    print(table(rows, [("corner", "Corner", "%s"), ("vdd", "AVDD (V)", "%.1f"), ("temp", "Temp (C)", "%d"), ("f", "Frequency (kHz)", "%.1f"),
                       ("dev", "vs typical (%)", "%+.1f"), ("duty", "Duty (%)", "%.1f"), ("i", "Current (uA)", "%.2f")]))
