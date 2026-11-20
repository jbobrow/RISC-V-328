"""The ADC's offset-cancelled comparator: residual offset over corners and mismatch, decision time from balance
and when it has to reverse the decision before, current."""
import sys, os, statistics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table

TB = """
vdd avdd 0 {vdd}
xb avdd 0 avdd vref vbp ok rv328_bgr
vn inn 0 {cm}
* inputs equal while az is high; 1 us after az falls the input difference steps to d
vp inp 0 pwl(0 {cm} 6u {cm} 6.01u '{cm}+({d})')
* the clamp control as the ADC front end makes it: a fast rise and a slow fall
vaz azn 0 pwl(0 0 5u 0 5.01u {vdd})
xzp az azn avddc avddc pfet_06v0 w=2u l=0.6u
xzn az azn 0 0 nfet_06v0 w=0.5u l=8u
xzc az 0 cap_mim_2f0fF c_width=10u c_length=10u
vdc avddc 0 {vdd}
x1 avddc 0 inp inn out vbp avddc az rv328_adccmp
.options reltol=1e-4 abstol=1e-13 vntol=1e-7
.control
tran 20n 30u
meas tran vo find v(out) at=29.9u
meas tran td when v(out)={half} cross=1 from=6.02u
meas tran idd avg i(vdc) from=1u to=4u
.endc
"""

# the same, but the comparator first decides one way on 5 mV and then has to reverse on a small difference
TBR = TB.replace("vp inp 0 pwl(0 {cm} 6u {cm} 6.01u '{cm}+({d})')",
                 "vp inp 0 pwl(0 {cm} 6u {cm} 6.01u '{cm}+({d1})' 12u '{cm}+({d1})' 12.01u '{cm}+({d})')")
TBR = TBR.replace("cross=1 from=6.02u", "cross=1 from=12.02u")

def reverse(d1, d, vdd=5.0, **kw):
    """Time (us) for the output to cross mid-supply after the input goes from d1 to d (both relative to balance)."""
    r = run(TBR.format(vdd=vdd, cm=0.4 * vdd, d="%.8g" % d, d1="%.8g" % d1, half=vdd / 2), vdd=vdd, **kw)
    return 1e6 * (r.get("td", float("nan")) - 12.01e-6)

def decide(d, vdd=5.0, cm=None, **kw):
    # inputs at 0.4 of the supply, where the ADC front end puts them
    return run(TB.format(vdd=vdd, cm=0.4 * vdd if cm is None else cm, d="%.8g" % d, half=vdd / 2), vdd=vdd, **kw)

def offset(vdd=5.0, **kw):
    """Input difference at which the decision changes, by bisection (mV)."""
    lo, hi = -2e-3, 2e-3
    for _ in range(11):
        mid = (lo + hi) / 2
        if decide(mid, vdd, **kw).get("vo", 0) > vdd / 2: hi = mid
        else: lo = mid
    return 1e3 * (lo + hi) / 2

if __name__ == "__main__":
    rows = []
    for vdd, corner, temp in ((5.0, "tt", 25), (2.7, "tt", 25), (2.7, "ss", -40), (2.7, "ss", 125), (4.5, "ss", 125), (5.5, "ff", -40), (5.5, "ff", 125)):
        o = offset(vdd, corner=corner, temp=temp)
        hi = decide(o * 1e-3 + 0.2e-3, vdd, corner=corner, temp=temp)
        rev = max(reverse(sg * 5e-3, o * 1e-3 - sg * 0.3e-3, vdd, corner=corner, temp=temp) for sg in (1, -1))
        rows.append(dict(vdd=vdd, corner=corner, temp=temp, o=1e3 * o, tr=max(0.0, 1e6 * (hi.get("td", 6.01e-6) - 6.01e-6)), rev=rev, i=-1e6 * hi.get("idd", float("nan"))))
        sys.stderr.write("%s\n" % rows[-1])
    print(table(rows, [("vdd", "AVDD (V)", "%.1f"), ("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"), ("o", "Offset left (uV)", "%+.0f"),
                       ("tr", "First decision after the clamps open, 0.2 mV beyond the threshold (us; 0 = output already there)", "%.2f"),
                       ("rev", "Time to reverse a 5 mV decision on 0.3 mV, slower direction (us)", "%.2f"), ("i", "Current (uA)", "%.0f")]))
    v = [1e3 * offset(mismatch=True, seed=s) for s in range(1, 31)]
    print("\nOffset left with mismatch, %d runs at 5 V: mean %+.0f uV, sigma %.0f uV, worst %.0f uV" % (len(v), statistics.mean(v), statistics.stdev(v), max(abs(x) for x in v)))
