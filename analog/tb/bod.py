"""Brown-out detector with the reference: trip points for each level, hysteresis, current."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table

DC = """
vdd avdd 0 5
el1 l1 0 vol='{l1}*v(avdd)'
el0 l0 0 vol='{l0}*v(avdd)'
ee  enn 0 vol='v(avdd)'
xb avdd 0 enn vref vbp ok rv328_bgr
x1 avdd 0 enn l1 l0 vref vbp ok bod rv328_bod
.control
dc vdd 5.5 1.6 -0.005
let rel = v(bod) - 0.5*v(avdd)
meas dc v_fall find v(avdd) when rel=0 rise=1
meas dc i_5v find i(vdd) at=5
dc vdd 1.6 5.5 0.005
let rel = v(bod) - 0.5*v(avdd)
meas dc v_rise find v(avdd) when rel=0 fall=1
.endc
"""
# The same crossing in time: the supply ramps down through the level at 0.1 V/ms and back up, and the output
# must change once each way. The taps are megohm nodes beside a comparator whose output swings 5 V, and the
# hysteresis only acts after the divider has settled, so this is where wiring could make it chatter.
RAMP = """
vdd avdd 0 pwl(0 0 0.2m {hi} 1m {hi} 4m {lo} 4.5m {lo} 7.5m {hi} 8m {hi})
el1 l1 0 vol='{l1}*v(avdd)'
el0 l0 0 vol='{l0}*v(avdd)'
ee  enn 0 vol='v(avdd)'
xb avdd 0 enn vref vbp ok rv328_bgr
x1 avdd 0 enn l1 l0 vref vbp ok bod rv328_bod
brel rel 0 v = v(bod) - 0.5*v(avdd)
.control
tran 50n 8m 0.9m
meas tran t1 when v(rel)=0 cross=1
meas tran t2 when v(rel)=0 cross=2
meas tran t3 when v(rel)=0 cross=3
meas tran v1 find v(avdd) when v(rel)=0 cross=1
meas tran v2 find v(avdd) when v(rel)=0 cross=2
.endc
"""

if __name__ == "__main__":
    rows = []
    for name, l1, l0 in (("2.3 V", 0, 0), ("2.7 V", 0, 1), ("4.3 V", 1, 0)):
        for corner, temp in (("tt", 25), ("tt", -40), ("tt", 125), ("ss", 125), ("ff", -40), ("tt_rcmax", 25), ("tt_rcmin", 25)):
            r = run(DC.format(l1=l1, l0=l0), corner=corner, temp=temp)
            r.update(level=name, corner=corner, temp=temp, i=-1e6 * r.get("i_5v", float("nan")),
                     hyst=100 * (r.get("v_rise", 0) / r.get("v_fall", 1) - 1))
            rows.append(r)
    print(table(rows, [("level", "Level", "%s"), ("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"), ("v_fall", "Trips at (V, falling)", "%.3f"),
                       ("v_rise", "Clears at (V, rising)", "%.3f"), ("hyst", "Hysteresis (%)", "%.1f"), ("i", "Reference + detector at 5 V (uA)", "%.1f")]))
    rows = []
    for name, level, l1, l0 in (("2.3 V", 2.3, 0, 0), ("2.7 V", 2.7, 0, 1), ("4.3 V", 4.3, 1, 0)):
        for corner, temp in (("tt", 25), ("ss", 125), ("ff", -40)):
            r = run(RAMP.format(l1=l1, l0=l0, hi=level + 0.3, lo=level - 0.15), corner=corner, temp=temp)
            n = sum(1 for k in ("t1", "t2", "t3") if k in r)
            rows.append(dict(level=name, corner=corner, temp=temp, v1=r.get("v1", float("nan")), v2=r.get("v2", float("nan")),
                             edges="one rise, one fall" if n == 2 else "%d edges" % n if n < 2 else "MORE THAN TWO"))
    print("\nSupply ramped through the level at 0.1 V/ms, down and back up\n")
    print(table(rows, [("level", "Level", "%s"), ("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"), ("v1", "Output rises at (V)", "%.3f"),
                       ("v2", "Output falls at (V)", "%.3f"), ("edges", "Edges on bod_o", "%s")]))
