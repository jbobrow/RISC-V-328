# From this repository to a submitted GDS

Status key: [x] done in this repository, [ ] open.

## Design
- [x] Architecture, memory map, pin assignment
- [x] RTL for the complete digital chip (CPU integration, bus, XIP/NVM, all peripherals, clock/reset/sleep, debug)
- [x] Pad ring definition, generated from one table (RTL, flow pad order and bond-out stay in sync)
- [x] Firmware support: header, start-up code, linker script, interrupt dispatch
- [ ] Decide the memory die (25-series EEPROM vs NOR flash) with the assembly house; confirm pad pitch and
      stacked or side-by-side bonding
- [x] Analog block, circuits: reference, POR, BOD, RC and 128 kHz oscillators, crystal oscillator, ADC
      front end, multiplexer, reference buffer, comparator, temperature sensor, designed at transistor
      level and simulated over corners (analog/README.md)
- [x] Second analog round: ADC front end corrected (top plate kept between the rails, offset-cancelled
      comparator, low-leakage switches) and comparator enable added (power-down 4 uA instead of 0.32 mA)
- [x] Third analog round, from what the first layouts showed: ADC comparator reverses a decision in
      0.4 us instead of 4 to 7; every resistor moved from a film this process variant does not have
      (ppolyf_u_3k) to the 1 kohm film; reference re-centred and its resistors written as strips;
      all benches re-run
- [x] Fourth analog round, from drawing the ADC: top plate now follows a full-scale step within the
      tracking time (the cause of the 0.4 LSB slope at 2.7 V, 125 C, slow corner), offset frozen 1.4 us
      after the top plate is released instead of 0.3, switches as 8 um fingers; schematic transitions
      within -0.01 to +0.29 LSB (was -0.29 to +0.41)
- [ ] Analog block, other known gaps in the circuits: 1.8 V brown-out level, trim for the 128 kHz
      oscillator, comparator input range, storage for calibration values, longer crystal-ready count
      in the RTL
- [x] Analog layout, first cell: ADC capacitor array (analog/layout/), 371 x 349 um, 0 violations in
      the foundry KLayout deck and in magic, LVS match, wiring extracted, ADC bench repeated with it
- [x] Analog layout generators (6 V transistor, resistor strips, MIM capacitor, block assembly), each
      device clean in both DRC tools and LVS
- [x] Analog layout, second cell: reference, 303 x 166 um, 0 violations in the foundry deck, LVS
      match, extracted netlist within 0.1 mV of the schematic over corners
- [x] Analog layout, third cell: ADC comparator, 327 x 83 um, clean in both DRC tools, LVS match;
      from its layout the offset left is -3 to +171 uV (schematic +5 to +108)
- [x] Analog layout, fourth cell: the whole ADC front end (array, comparator, 73 more transistors
      and 88 standard cells in five blocks drawn from the netlist), 427 x 747 um (430 x 908 um
      before its gates were standard cells), clean in both DRC tools, LVS match;
      simulated from the extracted layout: 46 of 46 conversions correct, 24 transitions within
      -0.02 to +0.45 LSB, none more than 0.18 LSB from the schematic
- [x] Analog layout, fifth and sixth cells: power-on reset (529 x 183 um) and 128 kHz oscillator
      (574 x 226 um), clean in both DRC tools, LVS match; the reset circuit behaves as its schematic;
      the oscillator was 18 % slow from its first layout (wire on its quarter-microampere
      comparators) and is retuned on the extracted netlist to 129.6 kHz
- [x] Analog layout, seventh and eighth cells: 8 MHz oscillator (229 x 335 um) and crystal oscillator
      (254 x 355 um), each a stack of three blocks drawn from the netlist (analog/layout/stack.py),
      clean in both DRC tools, LVS match. The 8 MHz oscillator was 12 % slow from its first layout and
      is retuned on the extracted netlist to 7.99 MHz; the crystal oscillator's gain margins and
      start-up are as on the schematic
- [x] Analog layout, the last five cells: brown-out detector (278 x 184 um), reference buffer
      (328 x 93 um), input multiplexer (218 x 67 um; 294 x 153 um before its gates were standard
      cells), analog comparator (104 x 48 um), temperature
      sensor (26 x 42 um), clean in both DRC tools, LVS match, re-simulated: buffer, multiplexer and
      sensor as their schematics; comparator delay 76 to 354 ns (schematic 39 to 189)
- [x] Brown-out detector: chatter on a slow supply ramp (in the schematic, found with a new test in
      time) removed with two capacitors; one edge each way, schematic and layout
- [ ] 8 MHz oscillator: from its layout the frequency falls 6.2 % from 5 V to 2.7 V (schematic 3.0 %),
      because its comparators' delay is a larger part of the period; a faster comparator, or trim at
      the operating supply
- [ ] Crystal oscillator, 32 kHz setting: 9.4 uA from the layout against 6.8 uA (slow edges into the
      Schmitt trigger); more replica current or a weaker first stage
- [ ] Confirm with the shuttle that Via3 on the margin of a MIM bottom plate is accepted (MIMTM.10 as
      both rule decks check it; analog/layout/README.md)
- [x] Analog macro, assembly: the macro's own gates and switches drawn as two cells, those two and
      the eleven blocks placed, the wiring between them in five channels and a trunk (analog/layout/macro.py;
      1345 x 1098 um, 1.48 mm2); foundry DRC 0, magic DRC 0 outside the foundry bipolar cells, LVS
      matches analog/blocks/rv328_analog.spice; whole-block test from its extraction passes with
      the same values as with ideal wires (analog/results/top_macro.md)
- [x] Smaller analog macro, first step: the plain logic of the ADC front end, the multiplexer and
      the macro as foundry standard cells (152 gates; analog/layout/README.md), cells one above the
      other within a row, a supply and ground branch of their own for the two fast oscillators:
      1380 x 927 um, 1.28 mm2, clean in both DRC tools, LVS match; re-simulated on the schematic and
      from the layouts: every ADC transition within 0.03 LSB of where it was, multiplexer unchanged,
      whole-block test ten of ten from the macro's extraction (analog/results/top_macro.md)
- [x] Trial layout with the analog macro's room reserved (blank block of 951 x 1405 um in the core,
      cells at 74 % of the rows left; docs/layout_results.md): the third floorplan tried routes
      with 0 violations, but only without the flow's repair steps after global routing. Left
      unrepaired: 2,561 slew entries, one hold violation, 79 antenna nets, and one register's
      fan-out at 17.3 MHz at the slow corner (-7.8 ns; every other path meets, by 0.02 ns or more)
- [x] Speed against an ATmega328P measured (docs/cache_study.md): five benchmark programs and CoreMark
      on the RTL and in simavr. The 2 KB direct-mapped cache is too small (a 19 KB firmware 5.9 times
      slower than with everything cached, serial bytes lost at 115200 baud); float code needs the
      single-cycle multiplier to draw level
- [x] Cache redesigned: one to three ways, least recently used line replaced, first 2 KB pinned for
      interrupt handlers (rtl/rv328_xip.v); regression passes in the old and the new configuration
- [x] Room for the analog macro and the larger cache: full-height slot. First layout with a 12 KB
      three-way cache, the fast multiplier and a blank block for the macro: cells at 41 % of their rows,
      0 routing violations, 20 MHz met at all nine corners (+0.64 ns at the slowest), hold met,
      routed netlist passes the basic test at gate level (docs/layout_results.md)
- [ ] Full-height floorplan: four variants tried against the reference `full4` (+0.64 ns, 94 slow
      edges, 646 overloads). Pad buffers with wider strips (`full7`, -1.73 ns), lanes kept free
      (`full8`, -3.09 ns) and pad buffers alone (`full9`, stopped) were worse. Repeaters every 600 um
      (`full10`) came out at -0.03 ns on one path; with more repair margin (`full11`) setup is met at
      all corners (+0.17 ns), 79 slow edges and 265 overloads, one 9 ps hold miss on FL_MISO.
- [ ] FL_MISO input constraint from the memory die's data sheet (today `-min 0`, pessimistic), then
      rerun timing on `full11` and adopt it as the reference PB0's 2.2 mm wire over
      the memories needs its driver moved or a repeater placed by hand (docs/layout_results.md)
- [ ] Full-height layout to sign-off: 94 slow edges (one at the PB0 pad, 8.2 ns; 93 inside the logic), only
      0.64 ns of margin on the multiplier at the slowest corner, DRC/LVS/density/antenna decks and the
      equivalence check not run, more supply pads for the taller die and an IR-drop check, the build
      still has the analog stub
- [ ] Decide the defaults: the RTL parameters still default to the first layout (2 KB cache, serial
      multiplier); the half-height files stay as the record of that layout
- [ ] Board support: a linker script that puts interrupt handlers in the first 2 KB and start-up code
      that sets NVMCFG = 0 (sw/bench/bench.ld.S and hal.c do this for the benchmarks only)
- [ ] Second silicon, denser memory (docs/memory_research.md, third pass): the 3.3 V 1024 x 8 block
      is 5.57 ns at the slow corner with its wiring and works at 1.8 V; a regulator needs 2 nF on chip
      besides the blocks' own 2.7 nF (first order). Still to do: the real regulator with a bypass
      switch and start-up, the level-shifter cell's layout and timing files, the rail grid, and the
      power-down decision (island on asleep, or reload in about 30 ms)
- [ ] Slot cost: the full-height slot is about twice the half-height one (wafer.space lists 7,000 to
      8,000 USD against 4,000 to 5,000 USD)
- [x] Standard-cell area corrected: 1.48 mm2, 46 % of the cell rows, not 1.99 mm2 and 62 % (the
      flow's metric counts the pad ring's four corner cells; scripts/core_area.py)
- [ ] Analog macro, still to do: supply and guard rings and pin protection; separate supply lines
      for the ADC (the two fast oscillators have theirs); pins where the chip floorplan wants them; wide
      tracks for the other paths that carry more than a few tenths of a milliampere (8 MHz
      oscillator's driver, ADC divider); standard cells for the logic inside the oscillators and
      the brown-out detector; wiring resistance in the extraction;
      capacitor matching (the foundry model has no mismatch term for it); LEF, liberty and GDS;
      swap the stub for the macro in the flow.
      Skip all analog items for the digital-first chip
- [ ] Review the alternate-function table against the ATmega328PB datasheet

## Verification
- [x] Self-checking RTL simulation of every peripheral at chip level, through the foundry pad models
- [x] Boot, RAM and NVM tests against the foundry SRAM macro model
- [x] Lint (Verilator), full-chip elaboration and synthesis estimate (Yosys)
- [ ] CPU compliance re-run in this configuration (Hazard3's own riscv-arch-test and formal results apply
      to the core, not to this integration)
- [ ] Debug: only the JTAG IDCODE path is tested; run OpenOCD against the simulation
- [ ] Clock-domain-crossing review of `rv328_clkrst`, `rv328_wdt` and the wake-up path
- [ ] FPGA prototype of `rv328_core` (the generic technology wrappers are meant for this)
- [ ] Corner cases not yet covered by tests: TWI arbitration loss and general call, SPI at fclk/2,
      USART framing errors, timer phase-and-frequency-correct mode, BOD reset, power-save, NOR erase

## Physical implementation
- [x] LibreLane configuration, macro placement, power grid scripts, SDC
- [x] First layout (7-track cells, area synthesis): routed clean, 11 MHz at the slow corner
- [x] Second layout (9-track cells, delay synthesis, rebalanced CPU clock, repair after global routing):
      setup and hold met at 20 MHz at all nine corners
- [x] Third layout (crystal clock buffered, reset synchroniser for the crystal-ready counter instead of a
      constraint exception, larger repair margins, built at 50 ns): setup and hold met at 20 MHz at all
      nine corners with the flow's own constraints; slew entries down from 691 to 16 (docs/layout_results.md)
- [x] Routing, Magic DRC, foundry KLayout DRC, antenna and density clean; LVS passes
- [x] Layout viewer built from the run (docs/layout_viewer.html); high-resolution renders (layout/renders)
- [ ] One logic net with a 6 ns transition at the slow corner: fix by hand
- [ ] 133 ordinary nets slightly over the 0.2 pF target (no timing or slew failure): accept or tighten
- [ ] Formal equivalence (Yosys.EQY) of the final netlist against the RTL
- [ ] wafer.space precheck on the final GDS
- [x] Gate-level simulation of the routed netlist with cell delays at 20 MHz: basic, timers and spi pass
- [ ] Gate-level simulation with wire delays and timing checks at the slow and fast corners, including
      clock switching and sleep modes (needs a simulator with full SDF support)
- [ ] IR-drop review: one supply domain shared by pad ring and core
- [ ] ESD and latch-up review of the double-bonded analog pins

## Package and bring-up
- [ ] Bonding diagram for TQFP/QFN-32 from docs/bondout.md; VCC and GND wires to all supply pads
- [ ] For first silicon, use wafer.space chip-on-board with the memory on the carrier PCB and the JTAG pads
      bonded out
- [ ] Bring-up plan: external clock and reset, JTAG IDCODE, load program through the RESET-low SPI path,
      run the simulation tests as firmware
