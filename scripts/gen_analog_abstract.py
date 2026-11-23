#!/usr/bin/env python3
"""Hand-off files of the analog macro for the digital flow, made from its layout.

    scripts/gen_analog_abstract.py        (run with the Python that has the klayout module)

Reads analog/layout/rv328_analog.gds.gz (made by analog/layout/macro.py) and writes
flow/librelane/ip/rv328_analog/:
  gds/rv328_analog.gds   the layout moved so that its outline starts at (0, 0); the drawn cell is renamed
                         rv328_analog_body and placed in a new top cell rv328_analog
  lef/rv328_analog.lef   outline, pins and obstructions
  lib/rv328_analog.lib   pin directions and input capacitances, no timing arcs (the clocks the macro
                         makes are declared in chip_top.sdc)
  vh/rv328_analog.v      black box with the macro's own pin names

Pins: every Metal4 label at the macro's top level marks a line that ends at the outline (57 at the
bottom, xtal1 and xtal2 at the top). The pin shape is that line within PIN_BAND of the outline.
Obstructions: Metal1 to Metal5 over the whole outline, except Metal4 within PIN_BAND of the bottom and
top edges, where only pin lines run, so that the router can reach the pins from outside.
Supply: both supply pins are written as signal pins. vss is joined to VSS by a strap down to the core
grid's VSS stripes, and avdd to the AVCC pad by a strap of its own (AVCC is a supply separate from the
core's VDD); both are drawn before placement by scripts/analog_straps.py. The power-grid tool cannot do
the first: the pin lies under the macro's Metal5 (the capacitors' top plates), which the LEF obstructs.
"""
import gzip
import os
import re
import tempfile

import klayout.db as kdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "analog", "layout", "rv328_analog.gds.gz")
OUT = os.path.join(ROOT, "flow", "librelane", "ip", "rv328_analog")
STUB = os.path.join(ROOT, "rtl", "analog", "rv328_analog_stub.v")
NAME = "rv328_analog"
PIN_BAND = 2.0
M4, M4_LABEL = (46, 0), (46, 10)
METALS = {"Metal1": (34, 0), "Metal2": (36, 0), "Metal3": (42, 0), "Metal4": (46, 0), "Metal5": (81, 0)}

# direction of each pin, from the stub's ports (buses split into bits, names in lower case)
OUTPUTS = {"clk_rc", "clk_xa", "clk_lf", "por_n", "bod_o", "adc_cmp", "ac_out"}
ANALOG = {"xtal1", "xtal2", "aref", "avdd", "vss", "ain0", "ain1"} | {"adc%d" % k for k in range(8)}


def main():
    raw = tempfile.NamedTemporaryFile(suffix=".gds", delete=False).name
    open(raw, "wb").write(gzip.open(SRC).read())
    ly = kdb.Layout()
    ly.read(raw)
    os.unlink(raw)
    body = ly.top_cell()
    assert body.name == NAME, body.name
    bb = body.dbbox()
    dx, dy = -bb.left, -bb.bottom
    W, H = bb.width(), bb.height()

    # pins: label -> Metal4 shape under it, cut to the band at the nearest edge
    m4 = kdb.Region(body.begin_shapes_rec(ly.layer(*M4)))
    m4.merge()
    pins = {}
    for s in body.shapes(ly.layer(*M4_LABEL)).each():
        if not s.is_text():
            continue
        n = s.text.string
        p = kdb.Point(s.text.x, s.text.y)
        hit = [poly for poly in m4.each() if poly.inside(p) or poly.bbox().contains(p)]
        assert len(hit) >= 1, n
        b = hit[0].bbox().to_dtype(ly.dbu)
        if abs(b.bottom - bb.bottom) < 0.01:
            r = (b.left + dx, 0.0, b.right + dx, PIN_BAND)
        elif abs(b.top - bb.top) < 0.01:
            r = (b.left + dx, H - PIN_BAND, b.right + dx, H)
        else:
            raise SystemExit("pin %s does not reach the outline" % n)
        pins[n] = r
    expected = set(port_names())
    assert set(pins) == expected | {"vss"}, (set(pins) ^ (expected | {"vss"}))

    # layout moved to (0, 0), drawn cell renamed
    body.name = NAME + "_body"
    top = ly.create_cell(NAME)
    top.insert(kdb.DCellInstArray(body.cell_index(), kdb.DTrans(dx, dy)))
    for d in ("gds", "lef", "lib", "vh"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    opt = kdb.SaveLayoutOptions()
    opt.select_cell(top.cell_index())
    ly.write(os.path.join(OUT, "gds", NAME + ".gds"), opt)

    # LEF
    L = ['VERSION 5.7 ;', '  NOWIREEXTENSIONATPIN ON ;', '  DIVIDERCHAR "/" ;', '  BUSBITCHARS "[]" ;',
         'MACRO %s' % NAME, '  CLASS BLOCK ;', '  FOREIGN %s ;' % NAME, '  ORIGIN 0.000 0.000 ;',
         '  SIZE %.3f BY %.3f ;' % (W, H)]
    for n in sorted(pins):
        use = "SIGNAL"            # vss too: the power-grid tool cannot reach it under the Metal5 capacitors
        d = "INOUT" if n in ANALOG or n == "vss" else "OUTPUT" if n in OUTPUTS else "INPUT"
        L += ['  PIN %s' % n, '    DIRECTION %s ;' % d, '    USE %s ;' % use]
        if n in ANALOG:
            L.append('    ANTENNADIFFAREA 1.0 ;')
        L += ['    PORT', '      LAYER Metal4 ;', '        RECT %.3f %.3f %.3f %.3f ;' % pins[n], '    END', '  END %s' % n]
    L.append('  OBS')
    for m in ("Metal1", "Metal2", "Metal3", "Metal5"):
        L += ['    LAYER %s ;' % m, '      RECT 0.000 0.000 %.3f %.3f ;' % (W, H)]
    L += ['    LAYER Metal4 ;', '      RECT 0.000 %.3f %.3f %.3f ;' % (PIN_BAND, W, H - PIN_BAND)]
    L += ['  END', 'END %s' % NAME, 'END LIBRARY', '']
    open(os.path.join(OUT, "lef", NAME + ".lef"), "w").write("\n".join(L))

    # liberty: directions and capacitances only
    lib = ['library (%s) {' % NAME, '  delay_model : table_lookup;', '  time_unit : "1ns";', '  voltage_unit : "1V";',
           '  current_unit : "1mA";', '  capacitive_load_unit (1, pf);', '  nom_voltage : 5.0;', '  nom_temperature : 25.0;',
           '  input_threshold_pct_fall : 50.0;', '  input_threshold_pct_rise : 50.0;',
           '  output_threshold_pct_fall : 50.0;', '  output_threshold_pct_rise : 50.0;',
           '  slew_lower_threshold_pct_fall : 20.0;', '  slew_lower_threshold_pct_rise : 20.0;',
           '  slew_upper_threshold_pct_fall : 80.0;', '  slew_upper_threshold_pct_rise : 80.0;',
           '  cell (%s) {' % NAME, '    area : %.1f;' % (W * H), '    dont_touch : true;', '    dont_use : true;']
    for n in sorted(pins):
        d = "inout" if n in ANALOG else "output" if n in OUTPUTS else "input"
        lib.append('    pin (%s) { direction : %s; capacitance : %s; }' % (n, d, "0.0" if d == "output" else "0.005"))
    lib += ['  }', '}', '']
    open(os.path.join(OUT, "lib", NAME + ".lib"), "w").write("\n".join(lib))

    # black box
    ports = sorted(pins)
    v = ['// Black box of the analog macro for the digital flow (scripts/gen_analog_abstract.py). Pin names are the',
         '// macro\'s own. vss is its ground: the top level leaves it open and scripts/analog_straps.py joins it to VSS.',
         '(* blackbox *)', 'module %s (' % NAME]
    v.append(",\n".join("\t%s wire %s" % ("inout " if n in ANALOG else "output" if n in OUTPUTS else "input ", n) for n in ports))
    v += [');', 'endmodule', '']
    open(os.path.join(OUT, "vh", NAME + ".v"), "w").write("\n".join(v))
    print("%s: %.2f x %.2f um, %d pins (%d at the bottom, %d at the top)" % (
        NAME, W, H, len(pins), sum(1 for r in pins.values() if r[1] == 0), sum(1 for r in pins.values() if r[1] > 0)))


def port_names():
    """The macro's pins, from the stub's ports: buses become name0..nameN in lower case."""
    text = open(STUB).read()
    out = []
    for m in re.finditer(r"(input|output|inout)\s+wire\s*(\[(\d+):0\])?\s*([^;\n)]+)", text):
        width = int(m.group(3)) + 1 if m.group(3) else 0
        for n in m.group(4).split(","):
            n = n.strip().lower()
            if not n or n.startswith("dig_"):
                continue
            n = "avdd" if n == "avcc" else n
            out += ["%s%d" % (n, k) for k in range(width)] if width else [n]
    return out


if __name__ == "__main__":
    main()
