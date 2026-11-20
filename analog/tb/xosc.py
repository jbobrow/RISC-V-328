"""Crystal oscillator: gain margin (negative resistance against the crystal's loss) and start-up."""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table

COMMON = """
vdd avdd 0 {vdd}
xb avdd 0 bgen vref vbp ok rv328_bgr
vbg bgen 0 {bgen}
vm1 m1 0 {m1}
vm0 m0 0 {m0}
x1 avdd 0 en m1 m0 xi xo vbp clk rv328_xosc
c1 xi 0 {c1}
c2 xo 0 {c2}
"""
AC = COMMON + """
ven en 0 {vdd}
c0 xi xo {c0}
iac xo xi dc 0 ac 1
.control
op
let idd = -i(vdd)
let vxi = v(xi)
print idd vxi
ac lin 1 {f} {f}
let rn = real(v(xi)-v(xo))
print rn
.endc
"""
TR = COMMON + """
ven en 0 {vdd}
* crystal: motional arm and shunt capacitance
lm xi xa {lm}
cm xa xb {cm}
rm xb xc {esr}
vx xc xo 0
c0 xi xo {c0}
cl clk 0 50f
* the run starts from the bias point; this pulse (1 uA for a twentieth of a period) is the disturbance
ik 0 xi pulse(0 1u {t0} 1n 1n {tk} 1)
.control
tran {step} {tend}
meas tran vmax max v(xi) from={ta} to={tend}
meas tran vmin min v(xi) from={ta} to={tend}
meas tran t1 when v(clk)={half} rise=1 from={ta}
meas tran t2 when v(clk)={half} rise=11 from={ta}
meas tran tf when v(clk)={half} fall=1 from={t1x}
meas tran tfirst when v(clk)={half} rise=3
meas tran idd avg i(vdd) from={ta} to={tend}
meas tran irm rms i(vx) from={ta} to={tend}
.endc
"""
# setting, frequency, crystal loss (ohm), load capacitance, shunt capacitance
CASES = [(1, 4e6, 150, 18e-12, 5e-12), (1, 8e6, 80, 18e-12, 5e-12), (1, 16e6, 40, 18e-12, 5e-12), (2, 16e6, 40, 18e-12, 5e-12),
         (2, 20e6, 30, 18e-12, 5e-12), (3, 32768, 70e3, 12.5e-12, 1.5e-12)]
STRAY = 3e-12      # pad, bond wire and board at each pin

def bits(mode, vdd):
    # the reference is left off in the watch-crystal setting, which must not need it
    return dict(m1=vdd if mode & 2 else 0, m0=vdd if mode & 1 else 0, bgen=0 if mode == 3 else vdd)

def margin(mode, f, esr, cl, c0, vdd=5.0, **kw):
    r = run(AC.format(vdd=vdd, f=f, c1=2 * cl, c2=2 * cl, c0=c0, **bits(mode, vdd)), vdd=vdd, **kw)
    if "rn" in r:
        r["margin"] = -r["rn"] / esr
    return r

def startup(mode, f, esr, cl, c0, vdd=5.0, qdiv=20, **kw):
    """Start-up with the crystal's motional capacitance multiplied by qdiv (and the inductance divided),
    which leaves the loss and so the gain condition as they are but shortens the build-up by about qdiv."""
    cm = (3e-15 if f < 1e5 else 20e-15) * qdiv
    lm = 1 / ((2 * math.pi * f) ** 2 * cm)
    per = 1 / f
    t0, tend = 2 * per, 1000 * per
    ta = tend - 40 * per
    r = run(TR.format(vdd=vdd, half=vdd / 2, c1=2 * cl, c2=2 * cl, c0=c0, lm=lm, cm=cm, esr=esr, t0=t0, tk=per / 20, step=per / 60, tend=tend,
                      ta=ta, t1x=ta + 1.5 * per, **bits(mode, vdd)), vdd=vdd, **kw)
    if "t1" in r and "t2" in r:
        r["f"] = 10 / (r["t2"] - r["t1"])
        r["pp"] = r["vmax"] - r["vmin"]
        r["cycles"] = (r["tfirst"] - t0) * f
        r["i"] = -1e6 * r["idd"]
        r["drive"] = 1e6 * esr * r["irm"] ** 2
        t = (r["tf"] - r["t1"]) * r["f"]
        r["duty"] = 100 * (t % 1)
    return r

if __name__ == "__main__":
    rows = []
    for mode, f, esr, cl, c0 in CASES:
        for corner, temp, vdd in (("tt", 25, 5.0), ("tt", 25, 2.7), ("ss", 125, 4.5), ("ss", 125, 2.7), ("ff", -40, 5.5)):
            r = margin(mode, f, esr, cl, c0, vdd=vdd, corner=corner, temp=temp)
            r.update(mode=mode, fs="%g MHz" % (f / 1e6) if f > 1e5 else "32.768 kHz", esr=esr, clp=cl * 1e12, corner=corner, temp=temp, vdd=vdd,
                     ia=1e6 * r.get("idd", float("nan"))); rows.append(r)
    print(table(rows, [("mode", "Setting", "%d"), ("fs", "Crystal", "%s"), ("esr", "Loss (ohm)", "%g"), ("clp", "Load (pF)", "%g"), ("corner", "Corner", "%s"),
                       ("temp", "Temp (C)", "%d"), ("vdd", "AVDD (V)", "%.1f"), ("rn", "Negative resistance (ohm)", "%.0f"), ("margin", "Gain margin (x)", "%.1f"),
                       ("ia", "Current at the bias point, before the swing builds (uA)", "%.1f")]))
    rows = []
    for mode, f, esr, cl, c0 in (CASES[1], CASES[4], CASES[5]):
        for corner, temp, vdd in (("tt", 25, 5.0), ("ss", 125, 2.7)):
            r = startup(mode, f, esr, cl, c0, vdd=vdd, corner=corner, temp=temp)
            r.update(mode=mode, fs="%g MHz" % (f / 1e6) if f > 1e5 else "32.768 kHz", corner=corner, temp=temp, vdd=vdd, dev=1e6 * (r.get("f", float("nan")) / f - 1)); rows.append(r)
    print()
    print(table(rows, [("mode", "Setting", "%d"), ("fs", "Crystal", "%s"), ("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"), ("vdd", "AVDD (V)", "%.1f"),
                       ("cycles", "Clock running after (cycles, with the shortened build-up)", "%.0f"), ("pp", "Swing at XTAL1 (V p-p)", "%.2f"), ("duty", "Clock duty (%)", "%.1f"),
                       ("i", "Current (uA)", "%.1f"), ("drive", "Crystal drive (uW)", "%.2f")]))
