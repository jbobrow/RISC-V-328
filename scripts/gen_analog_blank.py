#!/usr/bin/env python3
"""A blank block of the analog macro's size for a trial floorplan of the digital layout.

  gen_analog_blank.py [variant]      variant: corner (default), channels

Reads analog/layout/reports/macro.json for the macro's size, turns it on its side (it then fits beside the
memories) and writes
  flow/librelane/ip/rv328_analog_blank/   LEF (no pins, Metal1 to Metal5 blocked), empty liberty cell,
                                          blackbox Verilog, a GDS with the outline
  flow/librelane/trial_macros.yaml        macros.yaml with the block added (and, in the variant "corner",
                                          the memories moved)
  flow/librelane/trial_blank.yaml         the settings that differ from config.yaml for the trial
Run the trial from flow/librelane:
  librelane slot_1x0p5.yaml trial_macros.yaml config.yaml trial_blank.yaml --run-tag <tag> ...
The block has no pins and no content: the trial answers whether the digital layout can be placed, routed
and timed in the room that is left, not how the macro is connected.

Variants, in the order they were tried (docs/layout_results.md, "Trial with the analog block"):
  channels  the block near the south-east corner with 46 um of cell rows between it and the core's east
            and south edges; the memories where they are in the layout without the block.
  corner    the block in the south-east corner itself. Its outline is STRIP um larger than what it blocks,
            on the east and south sides: no cells there, but the wires of the pads behind the block can pass.
            The memories stand in the south-west corner with no rows beside them, the lower row upside down,
            so that all their pins face the one channel between the two rows.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FLOW = os.path.join(ROOT, "flow", "librelane")
NAME = "rv328_analog_blank"
CORE = (442.0, 442.0, 3490.0, 2089.0)
CHANNEL = 46.0          # variant "channels": cell rows between the block and the core edge
STRIP = 24.0            # variant "corner": room for wires, without rows, between the block and the core edge
SRAM = "gf180mcu_fd_ip_sram__sram512x8m8wm1"
SRAM_W, SRAM_H, SRAM_PITCH, SRAM_GAP = 431.86, 484.88, 442.0, 120.0


def main():
    import yaml
    variant = sys.argv[1] if len(sys.argv) > 1 else "corner"
    assert variant in ("corner", "channels"), variant
    m = json.load(open(os.path.join(ROOT, "analog", "layout", "reports", "macro.json")))
    w, h = math.ceil(m["height"]), math.ceil(m["width"])          # on its side
    strip = STRIP if variant == "corner" else 0.0
    W, H = w + strip, h + strip                                   # the outline; blocked: x 0..w, y strip..H
    if variant == "corner":
        x, y = CORE[2] - W, CORE[1]
    else:
        x, y = CORE[2] - CHANNEL - w, CORE[1] + CHANNEL
    ip = os.path.join(FLOW, "ip", NAME)
    for d in ("lef", "lib", "vh", "gds"):
        os.makedirs(os.path.join(ip, d), exist_ok=True)
    obs = "".join("      LAYER Metal%d ;\n        RECT 0.000 %.3f %.3f %.3f ;\n" % (k, strip, w, H) for k in range(1, 6))
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
        c.shapes(ly.layer(0, 0)).insert(kdb.DBox(0, 0, W, H))          # PR boundary
        ly.write(os.path.join(ip, "gds", NAME + ".gds"))
    except ImportError:
        print("no klayout module: GDS of the blank block not written", file=sys.stderr)
    mac = yaml.safe_load(open(os.path.join(FLOW, "macros.yaml")))
    mac["MACROS"][NAME] = dict(
        gds=["dir::ip/%s/gds/%s.gds" % (NAME, NAME)], lef=["dir::ip/%s/lef/%s.lef" % (NAME, NAME)], vh=["dir::ip/%s/vh/%s.v" % (NAME, NAME)],
        lib={"*": ["dir::ip/%s/lib/%s.lib" % (NAME, NAME)]}, instances={"u_analog_blank": dict(location=[x, y], orientation="N")})
    lost = (W + (10 if variant == "corner" else 20)) * (H + (10 if variant == "corner" else 20))
    if variant == "corner":
        y2 = round(CORE[1] + SRAM_H + SRAM_GAP, 2)
        x0 = CORE[0] + 10.0        # with the first memory on the core's edge itself the power grid step fails (PDN-0179)
        for k in range(4):
            mac["MACROS"][SRAM]["instances"]["u_core.u_ram.u_ram%d" % k] = dict(location=[x0 + k * SRAM_PITCH, CORE[1]], orientation="FS")
            mac["MACROS"][SRAM]["instances"]["u_core.u_xip.u_cache.u_ram%d" % k] = dict(location=[x0 + k * SRAM_PITCH, y2], orientation="N")
    open(os.path.join(FLOW, "trial_macros.yaml"), "w").write(
        "# macros.yaml with a blank block of the analog macro's size, variant '%s' (scripts/gen_analog_blank.py). Do not edit.\n" % variant
        + yaml.safe_dump(mac, default_flow_style=None, width=200, sort_keys=False))
    slot = yaml.safe_load(open(os.path.join(FLOW, "slot_1x0p5.yaml")))
    cfg = yaml.safe_load(open(os.path.join(FLOW, "config.yaml")))
    over = {
        "VERILOG_DEFINES": slot["VERILOG_DEFINES"] + ["RV328_ANALOG_BLANK"],
        "IGNORE_DISCONNECTED_MODULES": cfg["IGNORE_DISCONNECTED_MODULES"] + [NAME],
    }
    text = ("# Trial floorplan, variant '%s': the digital layout with a blank block of %g x %g um at (%g, %g) where the\n"
            "# analog macro would stand (scripts/gen_analog_blank.py). Pass this file last.\n" % (variant, W, H, x, y)) + yaml.safe_dump(over, default_flow_style=None, width=200)
    text += ("# Synthesis leaves 1.0 mm2 of cells and timing repair grows them to 1.4 mm2; with 1.9 mm2 of rows left\n"
             "# the cells must start out spread over all of it, so that the buffers find room where they are needed.\n"
             "# Global placement raises a target below the utilization (59 % here) to the uniform density.\n"
             "PL_TARGET_DENSITY_PCT: 33\n"
             "# Buffers for the pads behind the block have no rows near them: let the legaliser carry them to the nearest ones\n"
             "PL_MAX_DISPLACEMENT_X: 3000\nPL_MAX_DISPLACEMENT_Y: 1600\n"
             "# No double spacing for the upper clock nets: where global routing finds congestion it takes that rule off\n"
             "# one net at a time, fifty iterations each, and does not finish in hours\n"
             "CTS_APPLY_NDR: none\n"
             "# No design or timing repair after global routing: at this density the buffers it adds cannot be placed\n"
             "# without moving cells 33 um on average, and the routing that was clean is congested again\n"
             "RUN_POST_GRT_DESIGN_REPAIR: false\nRUN_POST_GRT_RESIZER_TIMING: false\n"
             "# Antennas by jumpers only: there is no room to place diodes (25 cells could not be legalised)\n"
             "GRT_ANTENNA_REPAIR_JUMPER_ONLY: true\nDRT_ANTENNA_REPAIR_JUMPER_ONLY: true\n")
    open(os.path.join(FLOW, "trial_blank.yaml"), "w").write(text)
    print("%s, variant %s: outline %g x %g um at (%g, %g) to (%g, %g), of which %g x %g um blocked for wires; with its halo it takes %.3f mm2 of the core"
          % (NAME, variant, W, H, x, y, x + W, y + H, w, h, lost * 1e-6))


if __name__ == "__main__":
    main()
