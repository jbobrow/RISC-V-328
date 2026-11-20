"""Off states: what each block draws with its enable low, after a 20 us supply ramp to 5 V.

The corner sweeps all run with the blocks enabled, so a block that leaks when it is *disabled* does not
show there (the reference did: 0.27 mA before it was fixed). The two blocks that are always on are
measured late, because the reset delay keeps its Schmitt trigger conducting for about a millisecond.
`python3 tb/off.py --whole` also runs the whole assembled block with every enable low for 4 ms
(about 15 minutes): that is the run that shows what the per-block numbers miss.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table

CASES = [
    ("Reference, disabled", "x1 avdd 0 0 vref vbp ok rv328_bgr", "400u", "320u"),
    ("Comparator, disabled, inputs at 2.5 V", "vp inp 0 pwl(0 0 20u 2.5)\nvn inn 0 pwl(0 0 20u 2.5)\nx1 avdd 0 inp inn out avdd 0 rv328_cmp mt=2", "4m", "3.4m"),
    ("Brown-out detector, disabled", "x1 avdd 0 0 0 0 0 avdd 0 bod_o rv328_bod", "4m", "3.4m"),
    ("RC oscillator, disabled", "x1 avdd 0 0 0 0 0 0 0 0 0 0 clk rv328_rcosc", "400u", "320u"),
    ("Crystal oscillator, disabled", "rx1 xi 0 100k\nrx2 xo 0 100k\nx1 avdd 0 0 0 0 xi xo avdd clk rv328_xosc", "400u", "320u"),
    ("Reference buffer, disabled", "x1 avdd 0 0 0 0 avdd aref rv328_refbuf\nc1 aref 0 100n", "400u", "320u"),
    ("Temperature sensor, disabled", "x1 avdd 0 0 avdd vtemp rv328_tsens", "400u", "320u"),
    ("ADC front end, disabled", "vm ain 0 pwl(0 0 20u 2.5)\nx1 avdd 0 ain aref 0 0 0 0 0 0 0 0 0 0 0 avdd 0 cmp rv328_adcfe\nc1 aref 0 100n", "4m", "3.4m"),
    ("Power-on reset, first 0.4 ms", "x1 avdd 0 por_n rv328_por", "400u", "320u"),
    ("Power-on reset, settled (always on)", "x1 avdd 0 por_n rv328_por", "4m", "3.4m"),
    ("128 kHz oscillator (always on)", "x1 avdd 0 clk rv328_lfosc", "4m", "3.4m"),
]

PINS = ("rc_en rc_trim7 rc_trim6 rc_trim5 rc_trim4 rc_trim3 rc_trim2 rc_trim1 rc_trim0 xo_en xo_mode1 xo_mode0 bod_en bod_level2 bod_level1 "
        "bod_level0 adc_en adc_mux3 adc_mux2 adc_mux1 adc_mux0 adc_refs1 adc_refs0 adc_sample adc_dac9 adc_dac8 adc_dac7 adc_dac6 adc_dac5 "
        "adc_dac4 adc_dac3 adc_dac2 adc_dac1 adc_dac0 ac_en ac_bg ac_mux_en").split()

WHOLE = """
vdd avdd 0 pwl(0 0 20u {vdd})
{low}
* the analog pins sit at mid-supply, the worst case for anything left floating behind them
vmid mid 0 pwl(0 0 20u {half})
{pins}
caref aref 0 100n
x1 avdd 0 xtal1 xtal2 aref adc7 adc6 adc5 adc4 adc3 adc2 adc1 adc0 ain0 ain1
+ clk_rc clk_xa clk_lf por_n bod_o
+ rc_en rc_trim7 rc_trim6 rc_trim5 rc_trim4 rc_trim3 rc_trim2 rc_trim1 rc_trim0
+ xo_en xo_mode1 xo_mode0 bod_en bod_level2 bod_level1 bod_level0
+ adc_en adc_mux3 adc_mux2 adc_mux1 adc_mux0 adc_refs1 adc_refs0 adc_sample
+ adc_dac9 adc_dac8 adc_dac7 adc_dac6 adc_dac5 adc_dac4 adc_dac3 adc_dac2 adc_dac1 adc_dac0 adc_cmp
+ ac_en ac_bg ac_mux_en ac_out rv328_analog
.control
* 20 ns steps: at 100 ns the 128 kHz oscillator's current is not integrated accurately, and the
* same run has read anything between 4 and 7 uA
tran 20n 4m
meas tran i_early avg i(vdd) from=320u to=400u
meas tran i_off avg i(vdd) from=3.4m to=4m
.endc
"""

def whole(vdd=5.0, **kw):
    low = "\n".join("v_%s %s 0 0" % (p, p) for p in PINS)
    pins = "\n".join("r_%s mid %s 100k" % (p, p) for p in "xtal1 xtal2 adc7 adc6 adc5 adc4 adc3 adc2 adc1 adc0 ain0 ain1".split())
    return run(WHOLE.format(vdd=vdd, half=vdd / 2, low=low, pins=pins), vdd=vdd, timeout=7200, **kw)

if __name__ == "__main__":
    rows = []
    for name, body, tend, start in CASES:
        r = run("vdd avdd 0 pwl(0 0 20u 5)\n" + body + "\n.control\ntran 100n %s\nmeas tran i1 avg i(vdd) from=%s to=%s\n.endc\n" % (tend, start, tend))
        rows.append(dict(name=name, win="%s to %s" % (start, tend), i=-1e6 * r.get("i1", float("nan"))))
    print(table(rows, [("name", "Block", "%s"), ("win", "Measured from", "%s"), ("i", "Supply current (uA)", "%.2f")]))
    print("\nSum of the two always-on blocks: %.1f uA." % (rows[-1]["i"] + rows[-2]["i"]))
    if "--whole" in sys.argv:
        r = whole()
        print("\nWhole block, every enable low, analog pins at half supply: %.0f uA at 0.3 to 0.4 ms, %.1f uA at 3.4 to 4 ms."
              % (-1e6 * r.get("i_early", float("nan")), -1e6 * r.get("i_off", float("nan"))))
