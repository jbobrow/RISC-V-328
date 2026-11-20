"""ADC front end: the two transitions that depend most on the decision before them.

Code 342 (0101010110) and code 682 (1010101010) are decided on bit 1 after a run of alternating
decisions, so the comparator has to reverse its previous output on half an LSB of overdrive. Where it
is too slow for that within one ADC clock period (5 us), the transition appears displaced: towards
lower inputs after a 1, towards higher inputs after a 0. The main bench (adcfe.py) does not measure
these two.  Each is measured on the schematic and on the whole front end as extracted from its layout.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import table, LAYOUT_ADC
from adcfe import threshold

if __name__ == "__main__":
    rows = []
    for vref, vdd, corner, temp in ((5.0, 5.0, "tt", 25), (1.1, 5.0, "tt", 25), (2.7, 2.7, "ss", 125), (1.1, 2.7, "ss", 125), (1.1, 2.7, "ss", -40)):
        for code in (342, 682):
            e = [threshold(code, vref, vdd, steps=s, corner=corner, temp=temp, pex=p) for p, s in ((False, 7), (LAYOUT_ADC, 6))]
            rows.append(dict(vref=vref, vdd=vdd, corner=corner, temp=temp, c="%d / %d" % (code - 1, code), sch=e[0], pex=e[1]))
            sys.stderr.write("%s\n" % rows[-1])
    print(table(rows, [("vref", "Reference (V)", "%.1f"), ("vdd", "AVDD (V)", "%.1f"), ("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"),
                       ("c", "Transition", "%s"), ("sch", "Error, schematic (LSB)", "%+.2f"), ("pex", "Error, from layout (LSB)", "%+.2f")]))
    worst = max(rows, key=lambda r: abs(r["pex"]))
    print("\nLargest: %+.2f LSB (%s, %.1f V reference, %.1f V supply, %s %d C)." % (worst["pex"], worst["c"], worst["vref"], worst["vdd"], worst["corner"], worst["temp"]))
