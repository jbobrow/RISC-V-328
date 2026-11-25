#!/usr/bin/env python3
"""Floorplan of the full-height slot (1x1) with the 12 KB three-way cache.

  gen_floorplan_1x1.py

Writes, under flow/librelane:
  ip/rv328_analog_blank/   a blank block of the analog macro's size, lying down, with a strip for wires
                           on its east side (LEF without pins, Metal1 to Metal5 blocked)
  macros_1x1.yaml          the identification cells, the 31 memories and the blank block
  full_1x1.yaml            the settings that differ from config.yaml
  pdn/pdn_cfg_1x1.tcl, pdn/pdn_sram_1x1.tcl   the power grid with the new memory names
Run from flow/librelane:
  librelane slot_1x1.yaml macros_1x1.yaml config.yaml full_1x1.yaml --run-tag <tag> ...

The plan, bottom to top (core 3048 x 4238 um):
  rows A, B   two rows of six memories, the lower one upside down, pins facing one channel
  row C       six memories upside down, pins facing the logic
  middle      cell rows; the analog block at the east edge; one more memory at the west edge
  rows D, E   two rows of six memories, pins facing one channel
A strip of cell rows runs along the west, south and north edges so that the pads there have cells next
to them, and a column of rows on the east side joins everything.

Options (none: the reference full-height layout, run full11: 60 um strips, repeaters every 600 um,
4.5 ns repair margin after global routing; the earlier reference full4 is --wire 0 --grt-margin 3.5):
  --padbuf     one buffer per pad signal (RV328_PADBUF) set down in front of its pad
  --edge N     width of the edge strips in um (default 60)
  --lanes      soft placement obstructions: the first placement keeps logic out of the edge strips, out
               of the 30 um gap between memory rows B and C and out of the middle 60 um of the two
               channels, which stay free for the repeaters, hold buffers and clock buffers the later
               steps add. In the reference layout 93 of 94 slow edges are on nets whose repeaters had no
               room in those places.
  --wire N     the design-repair steps after placement and after global routing break every wire longer
               than N um with a repeater (default 600; 0 turns this off, as the flow's own default does)
  --grt-margin N  setup margin the timing repair after global routing aims for (default 4.5 ns)
  --analog     the analog macro itself (flow/librelane/ip/rv328_analog, scripts/gen_analog_abstract.py) in
               place of the blank block, at the same place; the build drops the analog stub
               (RV328_ANALOG_MACRO). Its ground pin is joined to the grid's VSS stripes and its AVCC pin
               to the AVCC pad by scripts/analog_straps.py, which runs between the power grid and
               placement (flow/README.md); it also draws the thirteen analog lines
  --tags-center  the cache's three tag memories side by side in the middle of the cache row (the
               slowest path of run `and` ran from the cache's hit logic at the west edge to the processor)
  --mulks      the fast multiplier from rtl/tech/hazard3_mul_fast_gf180.v (scripts/gen_mul_fast.py): synthesised
               on its own with a Kogge-Stone final adder, 35 ns against 45 ns without Booth (slow corner)
  --remove-buffers  remove the buffers synthesis put in (DESIGN_REPAIR_REMOVE_BUFFERS) before the repair
               after global placement rebuilds the trees from where the cells are. In run dio a cache address
               bit's buffer chain, built by synthesis, crossed the die four times between the top and bottom
               memory rows (24.9 mm) and the later repair could not reorder it
  --booth      keep Yosys's Booth multiplier mapping (the flow's default, used up to runs full11, ana8 and
               anc5); without it the build sets SYNTH_MUL_BOOTH false, which shortens the multiplier
Runs: full7 = --padbuf --edge 120 (pad wires fast, but logic spread into the wider strips and the
slowest corner missed timing by 1.7 ns); full8 = --padbuf --lanes. See docs/layout_results.md.
"""
import json
import math
import os
import re
import sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FLOW = os.path.join(ROOT, "flow", "librelane")
NAME = "rv328_analog_blank"
SRAM = "gf180mcu_fd_ip_sram__sram512x8m8wm1"
CORE = (442.0, 442.0, 3490.0, 4680.0)
SRAM_W, SRAM_H, PITCH = 431.86, 484.88, 442.0
PADBUF = "--padbuf" in sys.argv
LANES = "--lanes" in sys.argv
EDGE = float(sys.argv[sys.argv.index("--edge") + 1]) if "--edge" in sys.argv else 60.0   # cell rows between the core edge and the memories (west, south, north)
WIRE = float(sys.argv[sys.argv.index("--wire") + 1]) if "--wire" in sys.argv else 600.0
GRT_MARGIN = float(sys.argv[sys.argv.index("--grt-margin") + 1]) if "--grt-margin" in sys.argv else 4.5
ANALOG = "--analog" in sys.argv
BOOTH = "--booth" in sys.argv     # the flow's default Booth multiplier mapping (runs up to full11, ana8, anc5)
TAGS = "--tags-center" in sys.argv   # the three tag memories side by side in the middle of the cache row
REMOVE_BUFFERS = "--remove-buffers" in sys.argv   # synthesis buffers out before the post-placement repair
MULKS = "--mulks" in sys.argv     # the multiplier as a pre-synthesised netlist with a Kogge-Stone adder
LANE_SIDE = 30.0  # left open for cells on each side of a channel, next to the memory pins
CHANNEL = 120.0   # between two rows of memories whose pins face each other
GAP = 30.0        # between two rows back to back
STRIP = 24.0      # wires only, between the analog block and the core's east edge
ANALOG_STRIP = 64.0  # the same for the real macro: the east-side analog pads' nets reach it through here
CACHE = dict(RV328_CACHE_KB=4, RV328_CACHE_WAYS=3, RV328_CACHE_PIN=2, RV328_MUL_FAST=1)
PORT_BASE = dict(b=0, c=8, d=16, e=24)
CLOCK_INPUTS = {6}          # PB6: no input buffer (see gen_padring.py)


def pad_buffers(blank):
    """Where the buffer of every pad signal goes (rv328_chip_top.v, RV328_PADBUF): in the cell rows right
    inside the core edge, in front of its pad. Pad positions are those of the pad ring as the flow places
    it (flow/librelane/pads_1x1.json, read once from a routed layout). blank = (x0, y0, x1, y1) of the
    analog block, which has no rows: pads behind it get their buffers just above or below it."""
    pads = json.load(open(os.path.join(FLOW, "pads_1x1.json")))
    out = {}
    for name, (x, y, _) in sorted(pads.items()):
        m = re.fullmatch(r"pad_p([bcde])(\d)", name)
        if m:
            idx = PORT_BASE[m.group(1)] + int(m.group(2))
            insts = ["u_pb_%s_%d.u_buf" % (t, idx) for t in ("aeui" if idx in CLOCK_INPUTS else "aeuiy")]
        elif name.startswith("pad_fl_"):
            insts = ["u_pb_fl_%s.u_buf" % name[7:]]
        else:
            continue
        for k, inst in enumerate(insts):
            off = (k - (len(insts) - 1) / 2) * 12.0
            if y < CORE[1]:                      # south
                px, py = x + 37.5 + off, CORE[1] + 10
            elif y > CORE[3]:                    # north
                px, py = x + 37.5 + off, CORE[3] - 20
            elif x < CORE[0]:                    # west
                px, py = CORE[0] + 10, y + 37.5 + off
            else:                                # east
                px, py = CORE[2] - 30, y + 37.5 + off
                if blank[1] - 10 < py < blank[3] + 10:
                    py = blank[1] - 20 - k * 11 if py - blank[1] < blank[3] - py else blank[3] + 20 + k * 11
            out[inst] = dict(location=[round(px, 1), round(py, 1)], orientation="N")
    return out


def memories():
    """instance name -> (x, y, orientation)"""
    x0 = CORE[0] + EDGE
    ya = CORE[1] + EDGE
    yb = ya + SRAM_H + CHANNEL
    yc = yb + SRAM_H + GAP
    ye = CORE[3] - EDGE - SRAM_H
    yd = ye - CHANNEL - SRAM_H
    ram = ["u_core.u_ram.u_ram%d" % k for k in range(4)]
    bank = lambda w, b: ["u_core.u_xip.g_w%d.u_way.g_b%d.u_ram.u_ram%d" % (w, b, k) for k in range(4)]
    tag = lambda w: "u_core.u_xip.g_w%d.u_way.g_tagram.u_tag.u_ram0" % w
    # The tag memories feed the cache's hit logic, which decides every instruction fetch. By default two
    # sit at the two ends of the middle row and the third in the middle band's west slot (up to 2.6 mm
    # apart); --tags-center puts all three side by side in the middle of the row, and the last block of
    # the data memory takes the west slot instead.
    mid = [ram[0], tag(0), tag(1), tag(2), ram[1], ram[2]] if TAGS else [tag(0)] + ram + [tag(1)]
    west = ram[3] if TAGS else tag(2)
    rows = [
        (ya, "FS", bank(0, 0) + bank(1, 0)[:2]),
        (yb, "N",  bank(0, 1) + bank(1, 0)[2:]),
        (yc, "FS", mid),
        (yd, "FS", bank(1, 1) + bank(2, 0)[:2]),
        (ye, "N",  bank(2, 1) + bank(2, 0)[2:]),
    ]
    out = {}
    for y, o, names in rows:
        for k, n in enumerate(names):
            out[n] = (round(x0 + k * PITCH, 2), round(y, 2), o)
    band = (round(yc + SRAM_H, 2), round(yd, 2))
    out[west] = (round(x0, 2), round(band[0] + CHANNEL, 2), "N")
    x1 = x0 + 6 * PITCH
    r = lambda *v: [round(a, 2) for a in v]
    lanes = [
        r(CORE[0], CORE[1], CORE[0] + EDGE, CORE[3]),                              # west strip
        r(CORE[0] + EDGE, CORE[1], CORE[2], CORE[1] + EDGE),                       # south strip
        r(CORE[0] + EDGE, CORE[3] - EDGE, CORE[2], CORE[3]),                       # north strip
        r(x0, yb + SRAM_H, x1, yc),                                                # gap between rows B and C
        r(x0, ya + SRAM_H + LANE_SIDE, x1, yb - LANE_SIDE),                        # channel A-B, middle
        r(x0, yd + SRAM_H + LANE_SIDE, x1, ye - LANE_SIDE),                        # channel D-E, middle
    ]
    return out, band, lanes


def main():
    m = json.load(open(os.path.join(ROOT, "analog", "layout", "reports", "macro.json")))
    w, h = math.ceil(m["width"]), math.ceil(m["height"])
    W, H = w + STRIP, h                                    # outline; blocked: x 0..w
    mem, band, lanes = memories()
    x, y = CORE[2] - W, round((band[0] + band[1] - H) / 2)
    ip = os.path.join(FLOW, "ip", NAME)
    for d in ("lef", "lib", "vh", "gds"):
        os.makedirs(os.path.join(ip, d), exist_ok=True)
    obs = "".join("      LAYER Metal%d ;\n        RECT 0.000 0.000 %.3f %.3f ;\n" % (k, w, H) for k in range(1, 6))
    open(os.path.join(ip, "lef", NAME + ".lef"), "w").write(
        'VERSION 5.7 ;\n  NOWIREEXTENSIONATPIN ON ;\n  DIVIDERCHAR "/" ;\n  BUSBITCHARS "[]" ;\n'
        "MACRO %s\n  CLASS BLOCK ;\n  FOREIGN %s ;\n  ORIGIN 0.000 0.000 ;\n  SIZE %.3f BY %.3f ;\n  OBS\n%s  END\nEND %s\nEND LIBRARY\n"
        % (NAME, NAME, W, H, obs, NAME))
    open(os.path.join(ip, "lib", NAME + ".lib"), "w").write(
        "library (%s) {\n  input_threshold_pct_fall: 50.0;\n  input_threshold_pct_rise: 50.0;\n  output_threshold_pct_fall: 50.0;\n"
        "  output_threshold_pct_rise: 50.0;\n  slew_lower_threshold_pct_fall: 20.0;\n  slew_lower_threshold_pct_rise: 20.0;\n"
        "  slew_upper_threshold_pct_fall: 80.0;\n  slew_upper_threshold_pct_rise: 80.0;\n\n  cell (%s) {\n  }\n}\n" % (NAME, NAME))
    open(os.path.join(ip, "vh", NAME + ".v"), "w").write("(* blackbox *)\nmodule %s;\nendmodule\n" % NAME)
    try:
        import klayout.db as kdb
        ly = kdb.Layout()
        ly.dbu = 0.001
        c = ly.create_cell(NAME)
        c.shapes(ly.layer(0, 0)).insert(kdb.DBox(0, 0, W, H))
        ly.write(os.path.join(ip, "gds", NAME + ".gds"))
    except ImportError:
        print("no klayout module: GDS of the blank block not written")

    mac = yaml.safe_load(open(os.path.join(FLOW, "macros.yaml")))
    mac["MACROS"][SRAM]["instances"] = {n: dict(location=[px, py], orientation=o) for n, (px, py, o) in mem.items()}
    mac["MACROS"][NAME] = dict(
        gds=["dir::ip/%s/gds/%s.gds" % (NAME, NAME)], lef=["dir::ip/%s/lef/%s.lef" % (NAME, NAME)], vh=["dir::ip/%s/vh/%s.v" % (NAME, NAME)],
        lib={"*": ["dir::ip/%s/lib/%s.lib" % (NAME, NAME)]}, instances={"u_analog_blank": dict(location=[x, y], orientation="N")})
    if ANALOG:
        A = "rv328_analog"
        x = round(CORE[2] - m["width"] - ANALOG_STRIP, 2)
        del mac["MACROS"][NAME]
        mac["MACROS"][A] = dict(
            gds=["dir::ip/%s/gds/%s.gds" % (A, A)], lef=["dir::ip/%s/lef/%s.lef" % (A, A)], vh=["dir::ip/%s/vh/%s.v" % (A, A)],
            lib={"*": ["dir::ip/%s/lib/%s.lib" % (A, A)]}, instances={"u_analog": dict(location=[x, y], orientation="N")})
    mac["PDN_MACRO_CONNECTIONS"] = ["%s VDD VSS VDD VSS" % n for n in sorted(mem)]
    open(os.path.join(FLOW, "macros_1x1.yaml"), "w").write(
        "# Macros of the full-height layout: identification cells, 31 memories, blank analog block\n"
        "# (scripts/gen_floorplan_1x1.py). Do not edit.\n" + yaml.safe_dump(mac, default_flow_style=None, width=200, sort_keys=False))

    slot = yaml.safe_load(open(os.path.join(FLOW, "slot_1x1.yaml")))
    cfg = yaml.safe_load(open(os.path.join(FLOW, "config.yaml")))
    over = {
        "VERILOG_DEFINES": ([d for d in slot["VERILOG_DEFINES"] if d != "RV328_ANALOG_STUB"] + ["RV328_ANALOG_MACRO"] if ANALOG
                            else slot["VERILOG_DEFINES"] + ["RV328_ANALOG_BLANK"]) + (["RV328_PADBUF"] if PADBUF else []) + ["%s=%d" % kv for kv in CACHE.items()],
        # the analog macro has no power pins by design: its supply comes through scripts/analog_straps.py
        "IGNORE_DISCONNECTED_MODULES": cfg["IGNORE_DISCONNECTED_MODULES"] + (["rv328_analog"] if ANALOG else [NAME]),
        "PDN_CFG": "dir::pdn/pdn_cfg_1x1.tcl",
        # Yosys's Booth mapping of the fast multiplier ends in a slow final adder: alone, at the slow corner
        # and without wires, the multiplier takes 53.3 ns with it and 45.1 ns without (0.12 against
        # 0.17 mm2). It was the slowest path of every full-height layout (docs/layout_results.md).
        "SYNTH_MUL_BOOTH": BOOTH,
    }
    if MULKS:
        # rtl/tech/hazard3_mul_fast_gf180.v (scripts/gen_mul_fast.py) in place of the multiplier's RTL
        over["VERILOG_FILES"] = [("dir::../../rtl/tech/hazard3_mul_fast_gf180.v" if f.endswith("arith/hazard3_mul_fast.v") else f)
                                 for f in cfg["VERILOG_FILES"]]
    if ANALOG:
        # placement and routing with one system clock (chip_top_pnr.sdc); sign-off with all of them
        over["PNR_SDC_FILE"] = "dir::chip_top_pnr.sdc"
        # the analog lines: never buffered or resized (they are special nets drawn by scripts/analog_straps.py,
        # which the resizer skips anyway; this keeps it so if a later step makes them ordinary)
        over["RSZ_DONT_TOUCH_LIST"] = ["A_ADC%d" % k for k in range(8)] + ["A_AIN0", "A_AIN1", "A_XTAL1", "A_XTAL2", "A_AREF"]
    if REMOVE_BUFFERS:
        over["DESIGN_REPAIR_REMOVE_BUFFERS"] = True
    if LANES:
        over["PL_SOFT_OBSTRUCTIONS"] = lanes
    if WIRE:
        over["DESIGN_REPAIR_MAX_WIRE_LENGTH"] = WIRE
        over["GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH"] = WIRE
    if PADBUF:
        # one buffer per pad signal, set down beside its pad (not marked "don't touch": the repair
        # steps then refuse to buffer the net that feeds it)
        over["MANUAL_GLOBAL_PLACEMENTS"] = pad_buffers((x, y, x + W, y + H))
    text = ("# Full-height slot with the 12 KB three-way cache and the fast multiplier; a blank block of %g x %g um at\n"
            "# (%g, %g) stands where the analog macro goes (scripts/gen_floorplan_1x1.py). Pass this file last.\n" % (W, H, x, y)
            + yaml.safe_dump(over, default_flow_style=None, width=200))
    text += ("PL_TARGET_DENSITY_PCT: %d\n" % (52 if LANES else 45) +
            
             "# pads behind a row of memories: let the legaliser carry their buffers to the nearest rows\n"
             "PL_MAX_DISPLACEMENT_X: 3000\nPL_MAX_DISPLACEMENT_Y: 1600\n"
             "# no double spacing for the upper clock nets: where global routing finds congestion it takes that rule\n"
             "# off one net at a time and may not finish (docs/layout_results.md, trial with the analog block)\n"
             "CTS_APPLY_NDR: none\n"
             "# Timing repair works on the nominal wire model; the slowest corner with the worst-case wire model was\n"
             "# 2.0 ns slower on the multiplier in the first run (-1.57 ns), so ask for that much more margin\n"
             "PL_RESIZER_SETUP_SLACK_MARGIN: 4.0\nGRT_RESIZER_SETUP_SLACK_MARGIN: %g\n" % GRT_MARGIN)
    open(os.path.join(FLOW, "full_1x1.yaml"), "w").write(text)

    pdn = open(os.path.join(FLOW, "pdn", "pdn_cfg.tcl")).read()
    assert '"pdn_sram.tcl"' in pdn
    pdn = pdn.replace('"pdn_sram.tcl"', '"pdn_sram_1x1.tcl"').replace("# RV328: eight 5 V SRAM macros, all in N orientation", "# RV328, full-height layout: 31 SRAM macros (N and FS)")
    open(os.path.join(FLOW, "pdn", "pdn_cfg_1x1.tcl"), "w").write(pdn)
    sram = open(os.path.join(FLOW, "pdn", "pdn_sram.tcl")).read().split("\n")
    k = [i for i, ln in enumerate(sram) if ln.strip().startswith("-instances")]
    assert len(k) == 1
    sram[k[0]] = "    -instances {%s} \\" % " ".join(sorted(mem))
    open(os.path.join(FLOW, "pdn", "pdn_sram_1x1.tcl"), "w").write("\n".join(sram))

    rows_mm2 = (CORE[2] - CORE[0]) * (CORE[3] - CORE[1]) * 1e-6 - len(mem) * (SRAM_W + 10) * (SRAM_H + 10) * 1e-6 - (W + 10) * (H + 20) * 1e-6
    print("%d memories; middle band y %g to %g; blank block %g x %g um at (%g, %g); about %.2f mm2 left for cell rows"
          % (len(mem), band[0], band[1], W, H, x, y, rows_mm2))


if __name__ == "__main__":
    main()
