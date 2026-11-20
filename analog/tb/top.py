"""The assembled analog block: one power-up with every function used once."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table
import adcfe

K = 682                      # ADC input: the middle of this code
TS, TH, TBIT = 100e-6, 110e-6, 5e-6

def stim(vdd):
    vin = (K + 0.5) * vdd / 1024
    acc, trials, expect = 0, [], []
    for n in range(10):
        t = acc | (1 << (9 - n)); trials.append(t)
        keep = vin >= t * vdd / 1024; expect.append(int(keep))
        if keep: acc = t
    lines = []
    def hi(name, t_on=30e-6):
        lines.append("v%s %s 0 pwl(0 0 %g 0 %g %g)" % (name, name, t_on, t_on + 20e-9, vdd))
    def lo(name):
        lines.append("v%s %s 0 0" % (name, name))
    for b in range(10):
        pts, last = [], None
        for n, t in enumerate(trials):
            v = vdd if (t >> b) & 1 else 0
            if last is None: pts.append("0 0 30u 0 30.02u %g" % v)
            elif v != last: pts.append("%.5g %g %.5g %g" % (TH + n * TBIT, last, TH + n * TBIT + 10e-9, v))
            last = v
        lines.append("vd%d adc_dac%d 0 pwl(%s)" % (b, b, " ".join(pts)))
    lines.append("vsm adc_sample 0 pwl(0 0 %g 0 %g %g %g %g %g 0)" % (TS, TS + 10e-9, vdd, TH, vdd, TH + 10e-9))
    hi("adc_en"); lo("adc_mux3"); lo("adc_mux2"); hi("adc_mux1"); lo("adc_mux0"); lo("adc_refs1"); hi("adc_refs0")
    hi("bod_en"); lo("bod_level2"); hi("bod_level1"); lo("bod_level0")
    hi("ac_en"); hi("ac_bg"); lo("ac_mux_en")
    hi("rc_en", 310e-6)
    for i in range(8): (hi if i == 7 else lo)("rc_trim%d" % i)
    lo("xo_en"); lo("xo_mode1"); lo("xo_mode0")
    return "\n".join(lines), vin, expect

TB = """
vdd avdd 0 pwl(0 0 20u {vdd})
{stim}
* board: 100 nF on AREF, the signal sources
caref aref 0 100n
vin2 s2 0 {vin}
rin2 s2 adc2 10k
vain1 ain1 0 pwl(0 0.9 200u 0.9 200.1u 1.3)
x1 avdd 0 xtal1 xtal2 aref adc7 adc6 adc5 adc4 adc3 adc2 adc1 adc0 ain0 ain1
+ clk_rc clk_xa clk_lf por_n bod_o
+ rc_en rc_trim7 rc_trim6 rc_trim5 rc_trim4 rc_trim3 rc_trim2 rc_trim1 rc_trim0
+ xo_en xo_mode1 xo_mode0 bod_en bod_level2 bod_level1 bod_level0
+ adc_en adc_mux3 adc_mux2 adc_mux1 adc_mux0 adc_refs1 adc_refs0 adc_sample
+ adc_dac9 adc_dac8 adc_dac7 adc_dac6 adc_dac5 adc_dac4 adc_dac3 adc_dac2 adc_dac1 adc_dac0 adc_cmp
+ ac_en ac_bg ac_mux_en ac_out rv328_analog
rpull1 xtal1 0 1meg
rpull2 xtal2 0 1meg
.control
tran 20n 315u
{meas}
meas tran por_early find v(por_n) at=100u
meas tran por_late find v(por_n) at=305u
meas tran t_por when v(por_n)={half} rise=1
meas tran bod_at find v(bod_o) at=150u
meas tran ac_before find v(ac_out) at=195u
meas tran ac_after find v(ac_out) at=230u
meas tran aref_v find v(aref) at=99u
meas tran lf1 when v(clk_lf)={half} rise=3
meas tran lf2 when v(clk_lf)={half} rise=13
meas tran rc_quiet max v(clk_rc) from=30u to=309u
meas tran rc1 when v(clk_rc)={half} rise=3
meas tran rc2 when v(clk_rc)={half} rise=19
meas tran i_all avg i(vdd) from=240u to=300u
.endc
"""

if __name__ == "__main__":
    vdd = 5.0
    st, vin, expect = stim(vdd)
    meas = "\n".join("meas tran c%d find v(adc_cmp) at=%.6g" % (n, TH + (n + 1) * TBIT - 50e-9) for n in range(10))
    r = run(TB.format(vdd=vdd, half=vdd / 2, stim=st, vin=vin, meas=meas), vdd=vdd, timeout=7200, keep="/tmp/top_tb.spice")
    got = "".join(str(int(r.get("c%d" % n, 0) > vdd / 2)) if ("c%d" % n) in r else "?" for n in range(10))
    exp = "".join(map(str, expect))
    g = lambda k: r.get(k, float("nan"))
    rows = [
        ("Reset held while the supply settles (por_n at 100 us)", "%.2f V" % g("por_early"), g("por_early") < 0.5),
        ("Reset released", "%.0f us after power-on" % (1e6 * g("t_por")), g("por_late") > vdd - 0.5),
        ("128 kHz oscillator", "%.1f kHz" % (10 / (g("lf2") - g("lf1")) / 1e3), 100e3 < 10 / (g("lf2") - g("lf1")) < 160e3),
        ("Brown-out detector at the 4.3 V level, supply 5 V", "bod_o = %d" % (g("bod_at") > vdd / 2), g("bod_at") < 0.5),
        ("Comparator, 1.1 V reference against AIN1 = 0.9 V then 1.3 V", "ac_out = %d then %d" % (g("ac_before") > vdd / 2, g("ac_after") > vdd / 2),
         g("ac_before") > vdd - 0.5 and g("ac_after") < 0.5),
        ("AREF pin with AVCC selected", "%.3f V" % g("aref_v"), abs(g("aref_v") - vdd) < 0.01),
        ("ADC conversion of %.4f V on ADC2 (expected code %d)" % (vin, K), "decisions %s" % got, got == exp),
        ("RC oscillator silent until enabled", "peak %.2f V" % g("rc_quiet"), g("rc_quiet") < 0.5),
        # This run uses 20 ns steps, too coarse for the oscillator's period (see tb/rcosc.py for the frequency): only check that it runs.
        ("RC oscillator after rc_en", "running, 16 periods in %.2f us" % (1e6 * (g("rc2") - g("rc1"))), 1.5e-6 < g("rc2") - g("rc1") < 3.5e-6),
        ("Supply current: reset, 128 kHz, reference, brown-out, ADC and comparator on", "%.0f uA" % (-1e6 * g("i_all")), -g("i_all") < 200e-6),
    ]
    print("| Check | Result | Pass |\n|---|---|---|")
    for a, b, ok in rows:
        print("| %s | %s | %s |" % (a, b, "yes" if ok else "NO"))
    if "c9" not in r:
        print("\n```\n" + r["_log"][-1500:] + "\n```")
