# RV328 first layout: results

The digital-first build (analog stub, external clock and reset) has been through the LibreLane
flow for the wafer.space GF180MCU half-height slot: synthesis, floorplan with pad ring and eight SRAM
macros, placement, clock-tree synthesis, routing, parasitic extraction, multi-corner timing, GDS
stream-out and the physical checks listed below. Tools: LibreLane 3.1.0.dev3 from the wafer.space
project template's Nix environment, PDK gf180mcuD at the template's pinned revision.

**This is a first pass, not a sign-off layout.** Routing, both DRC decks (Magic and the foundry KLayout deck), antenna, density and
layout-versus-schematic are clean (see the note on LVS below), but timing is not closed and the electrical-rule items below are
open. Do not submit this GDS.

Open `docs/layout_viewer.html` in a browser to look at the result. The outputs of the run are in
`layout/` (final GDS, routed DEF, a full-chip render, the metrics and timing reports).

## Numbers

| Quantity | Value |
|---|---|
| Die | 3932 x 2531 um |
| Standard cells (incl. buffers, fill, taps) | 63936 |
| Standard-cell area | 1.61 mm2 |
| Core utilisation (standard cells) | 50 % |
| Routed wire length | 3.12 m |
| Vias | 279586 |
| Routing DRC violations | 0 |
| Antenna violations (nets / pins) | 0 / 0 |
| Clock target | 80 ns (12.5 MHz) |
| Setup violations (endpoints, all corners) | 211 |
| Hold violations (endpoints, all corners) | 12 |
| Max slew / capacitance / fan-out violations | 7312 / 257 / 263 |
| Power estimate (default activity) | 12.1 mW |
| Magic DRC errors | 0 |
| KLayout DRC errors (foundry deck) | 0 |
| LVS | match after net rename (4 net mismatches before) |

| Corner | Setup slack (ns) | Implied max clock (MHz) | Hold slack (ns) |
|---|---|---|---|
| max_ff_n40C_5v50 | +24.48 | 18.0 | -0.39 |
| max_ss_125C_4v50 | -12.12 | 10.9 | +0.07 |
| max_tt_025C_5v00 | +20.59 | 16.8 | -0.19 |
| min_ff_n40C_5v50 | +25.20 | 18.2 | -0.25 |
| min_ss_125C_4v50 | -2.47 | 12.1 | +0.27 |
| min_tt_025C_5v00 | +21.68 | 17.1 | -0.04 |
| nom_ff_n40C_5v50 | +24.87 | 18.1 | -0.31 |
| nom_ss_125C_4v50 | -6.80 | 11.5 | +0.18 |
| nom_tt_025C_5v00 | +21.18 | 17.0 | -0.11 |

Corner names: `nom/min/max` are the interconnect corners, `tt_025C_5v00` typical silicon at 25 C and 5.0 V,
`ss_125C_4v50` slow silicon at 125 C and 4.5 V, `ff_n40C_5v50` fast silicon at -40 C and 5.5 V.

## What the numbers say

* **Speed.** The run targets 80 ns (12.5 MHz). Typical silicon has 21 ns to spare, which corresponds to
  about 17 MHz; the slow corner misses by 12 ns, about 10.9 MHz. The ATmega328PB's 20 MHz is out of reach
  for this netlist. The limiting path is inside the CPU, from the instruction register through decode and
  the ALU, about 80 gates deep.
* **Why it is slow, and what to try.** Synthesis was run for area (`SYNTH_STRATEGY: AREA 0`) and every
  gate is the smallest drive strength of a 7-track 5 V library. A delay-oriented synthesis strategy, the
  9-track library, and Hazard3's own speed options are the obvious next experiments. An earlier attempt at
  50 ns was within reach at the typical corner before routing and about 28 ns short at the slow corner.
* **Hold.** A dozen endpoints violate hold by up to 0.4 ns at the fast corner. Raising
  `PL_RESIZER_HOLD_SLACK_MARGIN` / `GRT_RESIZER_HOLD_SLACK_MARGIN` should clear them; they must be zero
  before tapeout because hold failures cannot be fixed by slowing the clock.
* **Slew, capacitance, fan-out.** Thousands of nets exceed the library's maximum transition time at the
  slow corner. Most sit behind weak drivers on long wires; they need another repair pass (the flow's
  post-global-route design repair is off by default) and probably a less dense placement.
* **Physical checks.** The router finished with no violations, Magic's full DRC deck reports 0 errors on
  the final GDS (with seal ring and metal fill), and the KLayout antenna and density checks report 0.
  The foundry KLayout deck (162 rule groups) reports 0 violations. That is every deck except antenna and
  density, which the flow checks in their own steps, and the circuit-under-pad deck, which the wafer.space
  template leaves out. It was run on its own after the flow hit the session time limit and took an hour
  on two cores.
* **Layout versus schematic.** Netgen finds the same 42,162 devices on both sides. Its first comparison
  reported four net mismatches, all on the flash pins: the top level had a pad net `FL_CSN` and a core-side
  net `fl_csn` (likewise SCK, MOSI, MISO), and Netgen ignores case when it mixes SPICE and Verilog, so it
  merged each pair on the schematic side. The layout was right. With the core-side nets renamed in the
  netlist the result is "Circuits match uniquely". The rename (`core_fl_*`) is now in
  `scripts/gen_padring.py` and `rtl/rv328_chip_top.v`; the layout in `layout/` was built before it and
  differs only in those four net names, so the next run should pass LVS inside the flow.
* **Clock skew.** The CPU clock is gated a second time after the system clock gate, so CPU flip-flops see
  the clock several nanoseconds later than peripheral flip-flops. The tools fix the resulting hold paths
  with buffers ("Timing and signal repair" is a fifth of the cell area in the viewer). Dropping the second
  gate, or letting clock-tree synthesis balance across it, would save area and power.

## Problems found and fixed on the way

| Problem | Fix |
|---|---|
| Lint error: clock-mux enable flops were bits of one vector clocked by different clocks | one small module per clock source (`rv328_clkmux_en`) |
| `SYNTH_HIERARCHY_MODE: deferred_flatten` silently dropped every cell without ports (power pads, ID macros) | back to the default flatten mode |
| Placement could not legalise repeaters in the 10 um slivers between SRAM macros | macros now abut; wider legalisation range |
| Clock-tree synthesis crashed on a clock rooted at a flip-flop output (the divided low-frequency clock) | dedicated clock buffer `rv328_clkbuf` as the root |
| The repair steps chose `dlyb_1`, a delay cell, as their fan-out buffer and added about 34 ns to the critical path | delay cells excluded with `EXTRA_EXCLUDED_CELLS` |
| A false 20 ns "hold" violation: static crystal-mode bits gating a clock input | `set_false_path` in the SDC |
| 50 ns (20 MHz) target was about 28 ns short at the slow corner | target relaxed to 80 ns for this pass |
| LVS mismatch on the four flash pins: pad nets and core nets whose names differed only in case | core-side nets renamed `core_fl_*` |

## Not covered by this run

* The steps of the flow after LVS: formal equivalence of the final netlist against the RTL (`Yosys.EQY`)
  and the manufacturability report. The run was stopped by the session's time limit before them.
* Gate-level simulation of the routed netlist with back-annotated delays.
* Any analog content: the analog macro is still the stub.
* Review of the pad ring against wafer.space's current bonding rules, and the wafer.space precheck.
* IR-drop and electromigration analysis beyond the flow's default report.
