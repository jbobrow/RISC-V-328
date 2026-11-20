"""Power-on reset: thresholds (slow supply sweep up and down), release delay, current."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table

DC = """
vdd avdd 0 5
x1 avdd 0 por_n rv328_por
.control
dc vdd 0.5 5.5 0.01
let rel = v(por_n) - 0.5*v(avdd)
meas dc v_rise find v(avdd) when rel=0 rise=1
meas dc i_5v find i(vdd) at=5
dc vdd 5.5 0.5 -0.01
let rel = v(por_n) - 0.5*v(avdd)
meas dc v_fall find v(avdd) when rel=0 fall=1
.endc
"""
TR = """
vdd avdd 0 pwl(0 0 {tr} 5 3m 5 3.001m 1.2 3.2m 1.2 3.201m 5)
x1 avdd 0 por_n rv328_por
.control
tran 2u 5m
meas tran t_good when v(avdd)=2.0 rise=1
meas tran t_rel when v(por_n)=2.5 rise=1
meas tran t_dip when v(avdd)=1.5 fall=1
meas tran t_low when v(por_n)=0.5 fall=1
meas tran t_rel2 when v(por_n)=2.5 rise=2
.endc
"""
if __name__ == "__main__":
    rows = []
    for corner in ("tt", "ss", "ff", "sf", "fs"):
        for temp in (-40, 25, 125):
            r = run(DC, corner=corner, temp=temp)
            r.update(corner=corner, temp=temp, i=-1e6 * r.get("i_5v", float("nan")))
            rows.append(r)
    print(table(rows, [("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"), ("v_rise", "Release at (V, rising)", "%.2f"),
                       ("v_fall", "Reset at (V, falling)", "%.2f"), ("i", "Current at 5 V (uA)", "%.2f")]))
    print()
    for corner, temp, tr in (("tt", 25, "100u"), ("ss", 125, "100u"), ("ff", -40, "100u"), ("tt", 25, "1u")):
        r = run(TR.format(tr=tr), corner=corner, temp=temp, timeout=600)
        print("%s %d C, supply rise %s: released %.0f us after the supply passes 2 V; a dip to 1.2 V resets within %.2f us and releases again after %.0f us"
              % (corner, temp, tr, 1e6 * (r["t_rel"] - r["t_good"]), 1e6 * (r["t_low"] - r["t_dip"]), 1e6 * (r["t_rel2"] - 3.201e-3)))
