"""Temperature sensor, reference buffer and input multiplexer."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table

BG = """
vdd avdd 0 {vdd}
xb avdd 0 avdd vref vbp ok rv328_bgr
"""

def tsens(**kw):
    r = run(BG.format(vdd=kw.get("vdd", 5.0)) + """
xt avdd 0 avdd vbp vtemp rv328_tsens
.control
op
let vt = v(vtemp)
print vt
.endc
""", **kw)
    return r.get("vt", float("nan"))

def refbuf_dc(iload=0.0, **kw):
    r = run(BG.format(vdd=kw.get("vdd", 5.0)) + """
xr avdd 0 avdd 0 vref vbp aref rv328_refbuf
il aref 0 %g
cst aref 0 100n
.control
op
let va = v(aref)
let vr = v(vref)
let idd = -i(vdd)
print va vr idd
.endc
""" % iload, **kw)
    return r

def refbuf_tran(cext, **kw):
    """Enable at 20 us, then a 20 uA load step. Returns settling time to 1 % and the excursion at the step."""
    slow = cext > 1e-9
    t1, tend, step = (5e-3, 7e-3, 1e-6) if slow else (150e-6, 300e-6, 10e-9)
    r = run(BG.format(vdd=kw.get("vdd", 5.0)) + """
ven enb 0 pwl(0 0 20u 0 20.1u {vdd})
xr avdd 0 enb 0 vref vbp aref rv328_refbuf
cext aref 0 {cext}
* pin leakage, which also defines the level while the buffer is off
rleak aref 0 10meg
brel rel 0 v = v(aref) - 0.99 * v(vref)
il aref 0 pwl(0 0 {t1} 0 '{t1}+100n' 20u)
.control
tran {step} {tend}
meas tran vfin find v(aref) at={tpre}
meas tran tset when v(rel)=0 rise=1
meas tran vmin min v(aref) from={t1} to={tend}
meas tran vmax max v(aref) from={t1} to={tend}
meas tran vend find v(aref) at={tend}
.endc
""".format(vdd=kw.get("vdd", 5.0), cext=cext if cext else 1e-15, t1=t1, tend=tend, step=step, tpre=t1 - 2 * step), **kw)
    return r

def ron(vin, vdd=5.0, **kw):
    r = run("""
vdd avdd 0 {vdd}
vin a3 0 {vin}
vs1 s1 0 {vdd}
vs0 s0 0 {vdd}
ven en 0 {vdd}
xm avdd 0 0 0 0 0 a3 0 0 0 0 0 0 0 s1 s0 en out rv328_amux
il out 0 10u
.control
op
let dv = v(a3) - v(out)
print dv
.endc
""".format(vdd=vdd, vin=vin), vdd=vdd, **kw)
    return r.get("dv", float("nan")) / 10e-6

if __name__ == "__main__":
    print("Temperature sensor output (mV)\n")
    rows = []
    for corner in ("tt", "ss", "ff"):
        for vdd in (2.7, 5.0):
            v = [1e3 * tsens(corner=corner, vdd=vdd, temp=t) for t in (-40, 25, 85, 125)]
            rows.append(dict(corner=corner, vdd=vdd, a=v[0], b=v[1], c=v[2], d=v[3], slope=(v[3] - v[0]) / 165))
    print(table(rows, [("corner", "Corner", "%s"), ("vdd", "AVDD (V)", "%.1f"), ("a", "-40 C", "%.1f"), ("b", "25 C", "%.1f"), ("c", "85 C", "%.1f"),
                       ("d", "125 C", "%.1f"), ("slope", "Slope (mV/K)", "%.3f")]))

    print("\nReference buffer, static\n")
    rows = []
    for corner, temp, vdd in (("tt", 25, 5.0), ("tt", 25, 2.7), ("ss", 125, 2.7), ("ff", -40, 5.5)):
        r0, r1, r2 = (refbuf_dc(i, corner=corner, temp=temp, vdd=vdd) for i in (0, 20e-6, -20e-6))
        rows.append(dict(corner=corner, temp=temp, vdd=vdd, err=1e3 * (r0.get("va", 0) - r0.get("vr", 0)), src=1e3 * (r1.get("va", 0) - r0.get("va", 0)),
                         snk=1e3 * (r2.get("va", 0) - r0.get("va", 0)), i=1e6 * r0.get("idd", 0)))
    print(table(rows, [("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"), ("vdd", "AVDD (V)", "%.1f"), ("err", "Output - reference (mV)", "%+.2f"),
                       ("src", "Change with 20 uA drawn (mV)", "%+.2f"), ("snk", "Change with 20 uA fed in (mV)", "%+.2f"), ("i", "Reference + buffer (uA)", "%.0f")]))

    print("\nReference buffer, switching on and a 20 uA load step\n")
    rows = []
    for cext, corner, temp, vdd in ((100e-9, "tt", 25, 5.0), (100e-9, "ss", 125, 2.7), (0, "tt", 25, 5.0), (0, "ff", -40, 5.5), (0, "ss", 125, 2.7), (1e-9, "tt", 25, 5.0)):
        r = refbuf_tran(cext, corner=corner, temp=temp, vdd=vdd)
        g = lambda k: r.get(k, float("nan"))
        rows.append(dict(c="100 nF" if cext > 5e-8 else "1 nF" if cext else "none", corner=corner, temp=temp, vdd=vdd, ts=1e3 * (g("tset") - 20e-6), vfin=g("vfin"),
                         drop=1e3 * (g("vend") - g("vfin")), under=1e3 * (g("vmin") - g("vend"))))
    print(table(rows, [("c", "Capacitor on AREF", "%s"), ("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"), ("vdd", "AVDD (V)", "%.1f"),
                       ("ts", "Within 1 % after (ms)", "%.3f"), ("vfin", "Settles at (V)", "%.4f"), ("drop", "Change with the load (mV)", "%+.1f"),
                       ("under", "Undershoot beyond that (mV)", "%+.1f")]))

    print("\nInput multiplexer, resistance of a selected channel (ohm)\n")
    rows = []
    for corner, temp, vdd in (("tt", 25, 5.0), ("ss", 125, 4.5), ("tt", 25, 2.7), ("ss", -40, 2.7), ("ss", 125, 2.7)):
        rows.append(dict(corner=corner, temp=temp, vdd=vdd, a=ron(0.05, vdd, corner=corner, temp=temp), b=ron(vdd / 2, vdd, corner=corner, temp=temp),
                         c=ron(vdd - 0.05, vdd, corner=corner, temp=temp)))
    print(table(rows, [("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"), ("vdd", "AVDD (V)", "%.1f"), ("a", "Input near ground", "%.0f"),
                       ("b", "Input at half supply", "%.0f"), ("c", "Input near the supply", "%.0f")]))
