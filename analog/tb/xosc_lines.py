"""Crystal oscillator gain margin with the chip's XTAL lines in place.

The full-height layout runs XTAL1 and XTAL2 from the analog macro to their pads over 3.7 and 4.4 mm of
2 um Metal4/Metal5 (scripts/analog_straps.py, docs/layout_results.md): about 131 and 162 ohm in series and
about 1.4 and 1.8 pF to ground (half put at each end of the line here). This bench repeats tb/xosc.py's
negative-resistance measurement with those lines between the amplifier and the crystal's pins, against the
same measurement without them.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table
from xosc import CASES, bits

R1, R2 = 131.0, 162.0          # ohm, XTAL1 and XTAL2 lines
C1, C2 = 1.4e-12, 1.8e-12      # F

AC = """
vdd avdd 0 {vdd}
xb avdd 0 bgen vref vbp ok rv328_bgr
vbg bgen 0 {bgen}
vm1 m1 0 {m1}
vm0 m0 0 {m0}
x1 avdd 0 en m1 m0 xi xo vbp clk rv328_xosc
ven en 0 {vdd}
* the lines: amplifier side xi/xo, pin side pi/po
rl1 xi pi {r1}
rl2 xo po {r2}
cl1a xi 0 {c1h}
cl1b pi 0 {c1h}
cl2a xo 0 {c2h}
cl2b po 0 {c2h}
* load capacitors and the crystal's shunt capacitance at the pins
c1 pi 0 {cl1}
c2 po 0 {cl2}
c0 pi po {c0}
iac po pi dc 0 ac 1
.control
op
ac lin 1 {f} {f}
let rn = real(v(pi)-v(po))
print rn
.endc
"""

def margin(mode, f, esr, cl, c0, lines, vdd=5.0, **kw):
    r1, r2, c1, c2 = (R1, R2, C1, C2) if lines else (1e-3, 1e-3, 0.0, 0.0)
    r = run(AC.format(vdd=vdd, f=f, cl1=2 * cl, cl2=2 * cl, c0=c0, r1=r1, r2=r2, c1h=max(c1 / 2, 1e-18),
                      c2h=max(c2 / 2, 1e-18), **bits(mode, vdd)), vdd=vdd, **kw)
    if "rn" in r:
        r["margin"] = -r["rn"] / esr
    return r

if __name__ == "__main__":
    rows = []
    for mode, f, esr, cl, c0 in CASES:
        for corner, temp, vdd in (("tt", 25, 5.0), ("ss", 125, 2.7)):
            r0 = margin(mode, f, esr, cl, c0, False, vdd=vdd, corner=corner, temp=temp, pex=True)
            r1 = margin(mode, f, esr, cl, c0, True, vdd=vdd, corner=corner, temp=temp, pex=True)
            rows.append(dict(mode=mode, fs="%g MHz" % (f / 1e6) if f > 1e5 else "32.768 kHz", esr=esr, corner=corner, temp=temp,
                             vdd=vdd, m0=r0.get("margin", float("nan")), m1=r1.get("margin", float("nan"))))
            print(rows[-1], flush=True)
    print(table(rows, [("mode", "Setting", "%d"), ("fs", "Crystal", "%s"), ("esr", "Loss (ohm)", "%g"), ("corner", "Corner", "%s"),
                       ("temp", "Temp (C)", "%d"), ("vdd", "AVDD (V)", "%.1f"), ("m0", "Gain margin, no lines (x)", "%.1f"),
                       ("m1", "Gain margin, with the lines (x)", "%.1f")]))
