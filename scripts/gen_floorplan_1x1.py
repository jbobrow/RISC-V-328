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
A strip of cell rows runs along the west, south and north edges so that the pads there have cells
(buffers, level shifters' loads) next to them, and a column of rows on the east side joins everything.
"""
import json
import math
import os
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FLOW = os.path.join(ROOT, "flow", "librelane")
NAME = "rv328_analog_blank"
SRAM = "gf180mcu_fd_ip_sram__sram512x8m8wm1"
CORE = (442.0, 442.0, 3490.0, 4680.0)
SRAM_W, SRAM_H, PITCH = 431.86, 484.88, 442.0
EDGE = 60.0       # cell rows between the core edge and the memories (west, south, north)
CHANNEL = 120.0   # between two rows of memories whose pins face each other
GAP = 30.0        # between two rows back to back
STRIP = 24.0      # wires only, between the analog block and the core's east edge
CACHE = dict(RV328_CACHE_KB=4, RV328_CACHE_WAYS=3, RV328_CACHE_PIN=2, RV328_MUL_FAST=1)


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
    rows = [
        (ya, "FS", bank(0, 0) + bank(1, 0)[:2]),
        (yb, "N",  bank(0, 1) + bank(1, 0)[2:]),
        (yc, "FS", [tag(0)] + ram + [tag(1)]),
        (yd, "FS", bank(1, 1) + bank(2, 0)[:2]),
        (ye, "N",  bank(2, 1) + bank(2, 0)[2:]),
    ]
    out = {}
    for y, o, names in rows:
        for k, n in enumerate(names):
            out[n] = (round(x0 + k * PITCH, 2), round(y, 2), o)
    band = (round(yc + SRAM_H, 2), round(yd, 2))
    out[tag(2)] = (round(x0, 2), round(band[0] + CHANNEL, 2), "N")
    return out, band


def main():
    m = json.load(open(os.path.join(ROOT, "analog", "layout", "reports", "macro.json")))
    w, h = math.ceil(m["width"]), math.ceil(m["height"])
    W, H = w + STRIP, h                                    # outline; blocked: x 0..w
    mem, band = memories()
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
    mac["PDN_MACRO_CONNECTIONS"] = ["%s VDD VSS VDD VSS" % n for n in sorted(mem)]
    open(os.path.join(FLOW, "macros_1x1.yaml"), "w").write(
        "# Macros of the full-height layout: identification cells, 31 memories, blank analog block\n"
        "# (scripts/gen_floorplan_1x1.py). Do not edit.\n" + yaml.safe_dump(mac, default_flow_style=None, width=200, sort_keys=False))

    slot = yaml.safe_load(open(os.path.join(FLOW, "slot_1x1.yaml")))
    cfg = yaml.safe_load(open(os.path.join(FLOW, "config.yaml")))
    over = {
        "VERILOG_DEFINES": slot["VERILOG_DEFINES"] + ["RV328_ANALOG_BLANK"] + ["%s=%d" % kv for kv in CACHE.items()],
        "IGNORE_DISCONNECTED_MODULES": cfg["IGNORE_DISCONNECTED_MODULES"] + [NAME],
        "PDN_CFG": "dir::pdn/pdn_cfg_1x1.tcl",
    }
    text = ("# Full-height slot with the 12 KB three-way cache and the fast multiplier; a blank block of %g x %g um at\n"
            "# (%g, %g) stands where the analog macro goes (scripts/gen_floorplan_1x1.py). Pass this file last.\n" % (W, H, x, y)
            + yaml.safe_dump(over, default_flow_style=None, width=200))
    text += ("PL_TARGET_DENSITY_PCT: 45\n"
             "# pads behind a row of memories: let the legaliser carry their buffers to the nearest rows\n"
             "PL_MAX_DISPLACEMENT_X: 3000\nPL_MAX_DISPLACEMENT_Y: 1600\n"
             "# no double spacing for the upper clock nets: where global routing finds congestion it takes that rule\n"
             "# off one net at a time and may not finish (docs/layout_results.md, trial with the analog block)\n"
             "CTS_APPLY_NDR: none\n"
             "# Timing repair works on the nominal wire model; the slowest corner with the worst-case wire model was\n"
             "# 2.0 ns slower on the multiplier in the first run (-1.57 ns), so ask for that much more margin\n"
             "PL_RESIZER_SETUP_SLACK_MARGIN: 4.0\nGRT_RESIZER_SETUP_SLACK_MARGIN: 3.5\n")
    open(os.path.join(FLOW, "full_1x1.yaml"), "w").write(text)

    pdn = open(os.path.join(FLOW, "pdn", "pdn_cfg.tcl")).read()
    assert '"pdn_sram.tcl"' in pdn
    open(os.path.join(FLOW, "pdn", "pdn_cfg_1x1.tcl"), "w").write(
        pdn.replace('"pdn_sram.tcl"', '"pdn_sram_1x1.tcl"').replace("# RV328: eight 5 V SRAM macros, all in N orientation", "# RV328, full-height layout: 31 SRAM macros (N and FS)"))
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
