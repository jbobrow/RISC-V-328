"""Comparator: delay at 10 mV overdrive, input offset from mismatch, current."""
import sys, os, statistics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table, ENV_PEX

TR = """
vdd avdd 0 {vdd}
xb avdd 0 avdd vref vbp ok rv328_bgr
vn inn 0 {cm}
vp inp 0 pwl(0 '{cm}-0.05' 20u '{cm}-0.05' 20.001u '{cm}+0.01' 30u '{cm}+0.01' 30.001u '{cm}-0.01')
vdc avddc 0 {vdd}
x1 avddc 0 inp inn out vbp avddc rv328_cmp mt={mt}
.control
tran 5n 40u
meas tran t_r when v(out)={half} rise=1
meas tran t_f when v(out)={half} fall=1
meas tran i_c avg i(vdc) from=10u to=19u
.endc
"""
OFS = """
vdd avdd 0 5
xb avdd 0 avdd vref vbp ok rv328_bgr
vn inn 0 1.1
vp inp 0 1.1
x1 avdd 0 inp inn out vbp avdd rv328_cmp mt={mt}
.control
dc vp 1.07 1.13 0.0002
meas dc trip find v(inp) when v(out)=2.5 rise=1
.endc
"""
if __name__ == "__main__":
    # the layout is of the mt=2 setting only (the other one is drawn inside the brown-out detector)
    for mt in ((2,) if "cmp" in ENV_PEX else (2, 0.5)):
        rows = []
        for vdd, cm in ((5.0, 0.1), (5.0, 1.1), (5.0, 3.3), (2.7, 0.1), (2.7, 1.1)):
            for corner, temp in (("tt", 25), ("ss", 125), ("ff", -40)):
                r = run(TR.format(vdd=vdd, cm=cm, mt=mt, half=vdd / 2), corner=corner, temp=temp, vdd=vdd)
                r.update(vdd=vdd, cm=cm, corner=corner, temp=temp, tr=1e9 * (r.get("t_r", float("nan")) - 20e-6), tf=1e9 * (r.get("t_f", float("nan")) - 30e-6), i=-1e6 * r.get("i_c", float("nan")))
                rows.append(r)
        print("\nBias setting mt=%s\n" % mt)
        print(table(rows, [("vdd", "AVDD (V)", "%.1f"), ("cm", "Input level (V)", "%.1f"), ("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"),
                           ("tr", "Delay, rising (ns)", "%.0f"), ("tf", "Delay, falling (ns)", "%.0f"), ("i", "Current (uA)", "%.1f")]))
        v = [run(OFS.format(mt=mt), mismatch=True, seed=s).get("trip") for s in range(1, 41)]
        v = [1e3 * (x - 1.1) for x in v if x]
        print("\nOffset from mismatch, %d runs: mean %.2f mV, sigma %.2f mV, worst %.1f mV" % (len(v), statistics.mean(v), statistics.stdev(v), max(abs(x) for x in v)))
