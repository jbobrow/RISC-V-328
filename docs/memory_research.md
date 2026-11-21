# Denser on-chip memory for RV328: options on GF180MCU

Research report, 20 November 2026. Nothing in this report has been placed and routed, and nothing was
simulated at transistor level. Every number is marked as one of:

* **measured**: taken by me from files in the installed PDK (process design kit) or the project, with the
  method in "What I measured";
* **cited**: stated by a source, with its URL in "Sources";
* **estimate**: my own arithmetic on measured numbers, for something that does not exist yet.

## Summary and recommendation

**The foundry memory is sparse because of its surroundings, not its storage cell.** In the 512 x 8 macro
the cells that store bits take 26 % of the area; the other 74 % is the row decoder, the read and write
circuits and the guard ring (measured). Thirty-one small macros pay that overhead thirty-one times.

**There is a denser memory already in the installed PDK**, which the project does not use: the 3.3 V
macros of library `gf180mcu_ocd_ip_sram`, redrawn from the foundry macro by Tim Edwards (Open Circuit
Design). The largest, 1024 x 8, holds twice the bits of our macro in three quarters of its area:
19.0 um2 per bit against 51.1, which is 2.7 times denser (measured). It has the same pin arrangement as
the foundry macro. With it, the whole 32 KB program plus the 2 KB RAM is 34 macros and 5.28 mm2, less
than the 6.49 mm2 the 31 macros take today (measured macro areas, no routing channels). It was made on
the first wafer.space run, and its author's test notes and conference abstract say it works (cited).
But it needs a 3.3 V supply on a 5 V chip, and its timing files are copies of the 5 V macro's files,
not a characterisation (measured). A second pass (next section) simulated the macro at transistor
level: it works at three corners and answers in 3.2 ns at the slow corner without wiring, an estimated
5 to 6 ns with it, and draws 0.7 to 0.9 mA when read at 20 MHz, more with wiring. The open cost is a
regulator without external capacitor and 3.5 to 7 nF of capacitance on the chip (estimate).

**Recommendation, in three steps.**

1. **First silicon: keep the 5 V foundry macro.** It is the only memory here with foundry timing at our
   corner (slow silicon, 4.5 V, 125 C: output 10.3 ns after the clock, shortest cycle 11.9 ns, measured
   from the liberty file) and it needs no second supply. The run 3 deadline is 16 December 2026 (cited);
   no denser option can be adopted and verified by then. Do not make the tape-out wait for memory.
2. **Next, try the cheapest gain, which needs no new memory at all: a read-only library built from
   ordinary logic cells.** In the benchmark firmware 13.5 KB of 19.1 KB is library code (C library and
   software floating point); only 5.7 KB is the application (measured from the linker map).
   Synthesised as logic, the complete 19.4 KB firmware image is 0.31 mm2 of cells, 2.0 um2 per bit,
   against 8.2 mm2 for the same bytes in foundry SRAM (measured by synthesis only: no buffering, no
   placement, and the unbuffered netlist does not meet 50 ns). A library in such a ROM would leave the
   cache holding only application code. This changes what the chip is: the library is frozen at tape-out
   and the tool chain must link against it. It is worth one experiment: a ROM block through the flow,
   and the cache study repeated with the library outside the cache.
3. **For the whole program on the chip, plan a 3.3 V memory island with the `gf180mcu_ocd_ip_sram`
   1024 x 8 macro, for a second silicon.** It needs a voltage regulator in the analog macro, level
   shifters, a second supply net in the flow, and real timing for the macro. The second pass below
   gives it a "go, if" verdict and lists the next steps; the author's measurements were presented in
   September 2026 and a second test chip is being delivered now.

**Not recommended:** memories from flip-flops or latches (2 to 3 times *worse* than the foundry macro,
measured cell areas), eFuse (87 to 166 um2 per bit and one-time), OpenRAM on GF180MCU (experimental, no
macro, no silicon), and building our own 5 V array from the foundry's cells (about 2 times denser by
estimate, but a custom-memory project with no silicon proof; reconsider it only if the 3.3 V island is
ruled out).

**The half-size slot is out of reach by memory density alone.** With the 3.3 V macros the present
contents (12 KB cache, tags, 2 KB RAM) take 2.47 mm2; with 1.88 mm2 of logic cells and the 1.30 mm2
analog block that is 5.65 mm2 in a 5.02 mm2 core (estimate from measured areas).

## The 3.3 V memory, second pass

Added 20 November 2026 after the first pass, for option 1b (the `gf180mcu_ocd_ip_sram` 1024 x 8 macro).
New here: transistor-level simulation of the macro's own netlist. The same marks apply: **measured**
(here that includes "simulated by me"), **cited**, **estimate**. The work was cut short; what was not
done is listed as **not done**. Verdict at the end of the section.

**In short.** In simulation the macro works at all three corners and is fast: at slow silicon, 3.0 V and
125 C the output follows the clock by 3.2 ns without wiring and by an estimated 5 to 6 ns with it, against
10.3 ns for the 5 V foundry macro. One access takes 36 to 45 pC from the supply without wiring, about
1.75 times that with it. A level shifter that is already drawn inside the 3.3 V pad library adds 1.0 to
1.9 ns. Nothing found so far kills the idea. What remains is engineering that this project has not done
before: a regulator without an external capacitor, a few nanofarads of decoupling, and a second supply
in the flow.

### 1. Does it work and how fast (simulation)

**What was simulated.**

* The PDK ships one SPICE netlist per macro. It is the schematic exported from xschem (its first line
  names the schematic file): transistors with their own junction areas, **no wiring capacitance or
  resistance**. The PDK ships no extracted netlist (measured: file list).
* To see what wiring does, I extracted the 64 x 8 and 1024 x 8 layouts from the PDK's Magic files
  myself: flattened, with capacitance between wires and to the substrate, without wire resistance.
  A hierarchical extraction was unusable (it contains large negative correction capacitors). Only the
  64 x 8 extracted netlist was simulated; **the extracted 1024 x 8 run was not done.**
* Simulator ngspice 42 with the PDK models (`sm141064.ngspice`, sections `ss`, `typical`, `ff`).
* One change to the netlist was needed. ngspice picks a transistor's model bin from its total width
  but evaluates it with the width of one finger; two device sizes in the macro then get an invalid
  model and one is wider than any bin, and the simulation fails at the first time step. I rewrote every
  multi-finger transistor as parallel single-finger ones with the same total junction area
  (`fixnet.py`). A check on one device gave the same current within 0.5 %.
* Bench (`bench.py`): supply ramped up in 10 ns, CEN high at power-up as the author's notes require,
  input edges 0.5 ns, 50 fF on every output, inputs changing 5 ns before the clock unless stated. One
  operation per clock: write A5 to address 0, write 5A to the highest address, read both, read the
  first again; then the same with the two values exchanged. So every bit is written and read as 0 and
  as 1 at the first row and at the last row. The 1024 x 8 runs use the first half of that sequence.

**Results (all reads correct in every run of this table).**

| Macro, netlist | Corner | Clock to output | Read, per access | Write, per access | Clocked but not selected |
|---|---|---|---|---|---|
| 64 x 8, schematic | slow, 3.0 V, 125 C | 2.76 ns | 29.0 pC | 33.1 pC | 0.51 pC |
| 64 x 8, schematic | typical, 3.3 V, 25 C | 1.73 ns | 32.1 pC | 36.6 pC | 0.61 pC |
| 64 x 8, schematic | fast, 3.6 V, -40 C | 1.19 ns | 36.2 pC | 41.2 pC | 0.77 pC |
| 64 x 8, extracted (capacitance) | slow, 3.0 V, 125 C | 4.12 ns | 50.5 pC | 59.6 pC | 0.93 pC |
| 1024 x 8, schematic | slow, 3.0 V, 125 C | 3.17 ns | 36.1 pC | 41.6 pC | 0.52 pC |
| 1024 x 8, schematic | typical, 3.3 V, 25 C | 1.98 ns | 40.0 pC | 45.9 pC | 0.61 pC |
| 1024 x 8, schematic | fast, 3.6 V, -40 C | 1.36 ns | 44.8 pC | 51.4 pC | 0.75 pC |

* Clock to output is from the clock's half level to the last output crossing its half level, the
  slowest of the eight bits and of the near and far address. Near and far differ by less than 0.1 ns.
* **Wiring matters.** On the 64 x 8 macro the extracted netlist is 1.49 times slower and takes 1.74
  times the read charge and 1.80 times the write charge. Applying the same factors to the 1024 x 8
  macro gives 4.7 ns and 63 pC per read at the slow corner (estimate). Its bit lines are sixteen times
  longer than the 64 x 8 macro's, so the factor for delay is probably larger; I use **5 to 6 ns** as the
  working figure. The extracted 1024 x 8 netlist exists (59,873 transistors, 123,595 capacitors) and
  the bench runs it unchanged; it needs about an hour per corner.
* **Cycle.** The 1024 x 8 schematic netlist also passes the sequence with an 8 ns clock period (4 ns
  high) at the slow corner. Shorter periods, and the shortest clock pulse, were **not done**.
* **Set-up of address and data** (64 x 8, schematic, slow corner, 10 ns period): correct with the
  input's half level 0.25 ns before the clock's, wrong at 0 ns, for address and for data alike. So the
  need is between 0 and 0.25 ns without wiring. Hold times were **not done**.
* Wire resistance is in neither netlist. It should matter little: the word line is strapped at every
  eighth cell (measured in the first pass), and a 390 um bit line in Metal2 is on the order of 100 ohm
  against about 100 fF (estimate).

**What this means for the 50 ns clock.** After the clock edge the path is: macro output 5 to 6 ns
(estimate), level shifter 1.0 to 1.9 ns (simulated, below), then the read multiplexing and the
processor's fetch path at 5 V as today. That is 6 to 8 ns where the foundry macro takes 10.3 ns, so the
memory would be **no slower than today's, with a margin of about 2 ns**. Before the edge, the address
passes one buffer on the 3.3 V rail (0.4 to 0.6 ns, simulated) and needs a few tenths of a nanosecond of
set-up, where the foundry macro asks for 2.0 ns. The memory clock passes the same kind of buffer, which
the clock tree has to balance.

**How far to trust it.** The function and the order of magnitude are solid: two netlists, three
corners, two macro sizes. The absolute delay of the 1024 x 8 macro with wiring is an estimate until the
extracted run is done. Nothing here covers transistor mismatch, which decides whether a sense amplifier
reads a weak cell correctly; that is what silicon measurements are for.

### 2. Current

Per macro, from the same runs. Current at 20 MHz is charge per access times 20 million.

| 1024 x 8 | Slow, 3.0 V | Typical, 3.3 V | Fast, 3.6 V | With wiring (estimate, x 1.75) |
|---|---|---|---|---|
| read every clock at 20 MHz | 0.72 mA | 0.80 mA | 0.90 mA | 1.3 to 1.6 mA |
| written every clock at 20 MHz | 0.83 mA | 0.92 mA | 1.03 mA | 1.5 to 1.8 mA |
| clocked, not selected | 10 uA | 12 uA | 15 uA | 18 to 27 uA |

Standby, clock stopped, chip enable off, 1024 x 8 schematic netlist, 3 us after the last clock:

| Corner | Per macro | 34 macros |
|---|---|---|
| typical, 3.3 V, 25 C | below 0.19 uA | below 6.5 uA |
| slow, 3.0 V, 125 C | below 0.32 uA | below 11 uA |
| typical, 3.3 V, 125 C | 1.7 uA | 59 uA |
| fast, 3.6 V, 125 C | 19.7 uA | 0.67 mA |

* The two "below" values are the simulator's own floor (its default 1 pS across every junction gives
  about 0.3 uA for 100,000 junctions), not the transistors. Runs with that floor lowered were
  **not done**, so the 25 C leakage is not known; the two larger values are well above the floor.
* **Load on a regulator, 34 macros, 20 MHz.**
    * (a) One macro read per clock, the others clocked but not selected: 0.8 + 33 x 0.012 = 1.2 mA
      typical without wiring, about 2.1 mA with it (estimate).
    * (b) Realistic worst case: a 32-bit instruction is four macros read at once (one per byte), and a
      store to RAM in the same clock is four macros written. At the fast corner that is
      4 x 0.90 + 4 x 1.03 + 26 x 0.015 = 8.1 mA without wiring, about 14 mA with it (estimate).
      Gating the clock of macros that are not selected would save 0.4 to 0.7 mA.
    * Design figure: **15 to 20 mA**, plus up to 0.7 mA of leakage at 125 C.
* The current comes in a burst of one to two nanoseconds after the clock, which no regulator follows.
  The charge of one clock, 0.38 nC in case (b) without wiring and about 0.7 nC with it, has to come
  from capacitance on the 3.3 V rail: 3.5 nF for a 0.2 V dip, 7 nF for 0.1 V (estimate). The capacitance
  the 34 macros bring themselves was **not done** (the run was prepared).

### 3. Silicon evidence

What I could find about measurements on run 1 silicon (all cited unless marked):

* The test chip's commit of 4 July 2026 says the first test chip has been tested on silicon. The one
  finding it reports is in the power-on reset block: working, but 14 to 16 seconds long at a 3.3 V
  supply, redesigned for run 2. No memory fault is reported.
* The written test notes cover one bench set-up: one pattern generator at 3.3 V on core and pads, the
  256-word macros, four data bits, six address bits, with a note that the core can also be tried at
  1.8 V and that further tests with two instruments are still to do. The screenshot of 30 June 2026
  shows correct counting at about 40 ns per value (my reading). I found **no** result for the
  1024-word macro, no speed limit, no voltage or temperature sweep, and no failure report.
* The ORConf talk of 12 September 2026 announces characterisation of the 3.3 V memory; I could not
  read its content (video only). **Not verified.**
* The library's own history confirms the timing files: its first commit says timing has not been
  updated from the original, and a merged change of May 2026 by another user notes that the Verilog
  timing block was a verbatim copy of the 5 V model and replaces it with values from the specification
  tables in the repository. Those tables are the 5 V macro's (measured: the same 18.2595 ns period at
  3.0 V and 125 C as the foundry liberty file). The change reports no simulation and no silicon, and
  points out one implausible pair of entries.
* Other users: that same user builds a chip with 16 of these macros at a 10 MHz target; a Tiny Tapeout
  project carries the 256-word macro with a 50 MHz clock entry. Neither reports silicon results.
* The foundry asked for one rule fix in the cell array (enclosed implant area) on 2 January 2026, before
  the masks; it was made.
* The wafer.space "BondView" page for the test chip (20 of 50 boards passing) is about wire bonding of
  the boards, not about the memory (my reading; the page does not explain itself).

So: silicon exists, its author says it works, and one partial functional test is documented. Speed
and margins on silicon are **not verified** by anything I could read.

### 4. The boundary between 5 V and 3.3 V

**Down, 5 V into the island.** No special cell is needed.

* A cell of `gf180mcu_fd_sc_mcu9t5v0` supplied from the 3.3 V rail can take a 5 V input: the input
  touches only gates, and the cells are built from the thick-oxide transistors (`nfet_05v0`,
  `pfet_05v0` in the library netlist, measured). These cells need rows of their own with the n-well on
  3.3 V.
* Speed (simulated, `buf_2`, 30 fF load, 5 V swing at the input): 0.21/0.39 ns rise/fall typical at
  3.3 V, 0.42/0.59 ns at slow silicon, 3.0 V, 125 C, 0.46/0.67 ns at 2.7 V. The library has liberty
  files for 3.0, 3.3 and 3.6 V, so the flow can time such cells; in those files the cells are about 1.4
  to 1.9 times slower at 3.0 V than at 4.5 V (measured, first and last table entries of `buf_2`).

**Up, 3.3 V into the 5 V core.**

* A plain 5 V gate will not do. Simulated: a 5 V inverter at 5.5 V with its input held at 3.0 V still
  gives a low output (0.2 to 0.5 V), but draws 68 to 180 uA continuously, depending on the corner. On
  272 memory outputs that is up to 49 mA.
* Level-shifter cells in the installed PDK (measured, all of `libs.ref` searched by cell name):
    * `gf180mcu_osu_sc_gp12t3v3__lshifup` and `__lshifdown` exist, but are built only from 3.3 V
      transistors, for a lower core voltage. **Not usable at 5 V.** (My first pass said the PDK has no
      level-shifter cell; that was wrong in the letter, and is corrected below.)
    * The dual-voltage pad library `gf180mcu_ocd_io` has the right circuit inside its pads
      (`io_lvlshft`: a 3.3 V inverter, two thick-oxide n-transistors and two cross-coupled thick-oxide
      p-transistors, each 1.5 um wide and 0.7 um long). Its layout cell `lvlshift_up` is 5.53 x 12.91 um,
      71 um2, plus 12 um2 for the inverter. It is not a library cell: no LEF, no liberty file. It has
      been made on run 1 inside the pads of the test chip.
* That circuit simulated alone, 30 fF load: 0.6 ns typical; 1.0 to 1.3 ns at slow silicon, 125 C, 3.0 V
  in, 4.5 or 5.5 V out; 1.9 ns in the worst cases tried (slow n with fast p at -40 C, or a 2.7 V input).
  It switched fully in all ten cases, with no static current.
* So the smallest safe circuit is this one, redrawn as a standard cell with two wells, with LEF and a
  liberty file made by simulation. About 85 um2 each (measured from the pad library's cells).

**How many signals.** One macro has 29 inputs and 8 outputs (measured). Per macro that would be 986
inputs and 272 outputs for 34 macros. With shared buses it is far fewer (estimate):

| | Down | Up |
|---|---|---|
| program store, 32 macros as 4 bytes x 8 banks | 10 address, 8 bank enables, 32 data, 4 byte enables, write, clock: 56 | 32 if the 8-to-1 read selection is built inside the island, 256 if each output is shifted |
| RAM, 4 x 512 x 8 | 9 address, 32 data, 4 byte enables, enable, write, clock: 48 | 32 |
| total | about 100 buffers | 64 to 288 level shifters, 0.005 to 0.025 mm2 |

A 32-bit bus needs four macros side by side, so the RAM is better built from four 512 x 8 macros than
from two 1024 x 8: 36 macros, 5.36 mm2, instead of the 34 and 5.28 mm2 of the first pass (measured areas).

### 5. The supply

* **Nothing usable exists.** The installed PDK has no regulator (measured: library list). The open
  designs I found are unfinished: a capless 5 V to 3.3 V regulator for 10 mA from a student design
  challenge, at the stage of target specifications, and a 3.3 V to 1.8 V regulator that needs an
  external capacitor and has no layout (both cited). Neither has silicon. The 3.3 V test chips of run 1
  and run 2 take their 3.3 V from pins (cited: pin list), so no silicon here proves an on-chip supply.
* **What a regulator for this island needs** (estimates from small simulations):
    * Load 15 to 20 mA at most, a few microamperes in standby.
    * Pass transistor: a thick-oxide p-transistor 1000 um wide and 0.55 um long passes 16 mA with
      2.0 V of gate drive and 54 mA with 3.5 V at slow silicon, 125 C, 4.5 V in, 3.3 V out (simulated).
      So about 1000 to 1500 um, a few thousandths of a mm2.
    * Below about 3.6 V at the pin it can only pass the supply through. To lose no more than 0.1 V at
      15 mA and 3.0 V it would need about 3000 um (simulated: 5.4 mA per 1000 um). The chip promises
      20 MHz only from 4.5 V, so this matters only for low-voltage operation, where the macro's own
      limit is also unknown.
    * **Capacitance on the chip: 3.5 to 7 nF** for the bursts of section 2. Gate capacitance from the
      models is 4.0 fF per um2 for a 3.3 V transistor and 2.1 fF per um2 for a thick-oxide one
      (simulated), so 0.9 to 1.75 mm2 of capacitor, less whatever the macros bring themselves
      (**not done**). This is the largest cost of the island and takes back much of the area it frees.
      Accepting a larger dip, or spreading the accesses, reduces it.
    * No external capacitor is possible on the 32-pin package, so the loop has to be stable with the
      on-chip capacitance alone over a load range of more than 1000 to 1. That is a known but not
      trivial design. The project's bandgap can serve as its reference.
    * Power-down: either the island stays on, with the regulator's own current and the leakage above
      (not near an ATmega's power-down current when hot), or it is switched off and the program is
      copied again on wake-up, about 30 ms. A separate low-current keeper is a third way. Not designed.

### 6. Floorplan arithmetic

No placement or routing; the rules of `scripts/gen_floorplan_1x1.py` applied to the new macro (60 um of
cell rows at three edges, 120 um channel between two rows whose pins face each other, 10 um between
neighbours).

* The macro (measured from its LEF): 301.30 x 515.81 um, all 37 signal pins on Metal2 on the south
  edge, each 0.78 um wide and 3.0 um long, spread from x = 6.9 to 291.2 um, closest pair 1.37 um apart.
  Obstruction on Metal1 to Metal3 over the whole macro inside a 3 um rim, and on Nwell. Power on Metal3
  stripes and Metal2 and Metal1 rings. Metal4 and Metal5 are free above it, as with the foundry macro.

| | Today: 31 foundry macros | 32 x 1024 x 8 in rows, RAM in the band | 36 places in rows |
|---|---|---|---|
| per row, rows | 6, five rows | 8, four rows | 9, four rows |
| left at the east side for logic | 336 um | 496 um | 185 um |
| core height used by memory rows | 2814 um | 2423 um | 2423 um |
| band left for logic and the analog block | 1424 um high | 1815 um high | 1815 um high |
| core outside memory | 5.08 mm2 | 6.35 mm2 | 5.98 mm2 |
| difference | | +1.27 mm2 | +0.90 mm2 |

* Two pairs of rows replace today's two pairs and a single row, so there are two pin channels instead
  of two and a half, and each channel serves 16 macros instead of 12.
* The gain of about 1.3 mm2 has to hold the capacitors of section 5 (0.9 to 1.75 mm2 as estimated), the
  island's rows and the regulator. On these numbers the 32 KB chip fits about as tightly as today's,
  not more loosely. The cache controller's logic disappears; I did not estimate how much that is.
* The island needs its own 3.3 V power grid over the memory rows and a keep-apart between the two
  n-well potentials. Not looked at.

### Verdict: go, if three things hold

Nothing in simulation, in the documented silicon or in the arithmetic rules the 3.3 V memory out. It is
faster than the foundry macro, the boundary circuits exist as drawn silicon to copy, and it fits. It is
not ready to adopt, and not for the first tape-out.

**Go if:**

1. the 1024 x 8 macro still works and stays under about 8 ns with wiring at the slow corner, and the
   author's measurements confirm function across voltage and temperature;
2. a regulator without external capacitor and its on-chip capacitance can be designed and fitted
   (the largest unknown, and the only part without any silicon example);
3. the project accepts what power-down then costs.

**Next steps, in order.**

1. Run the extracted 1024 x 8 netlist at the three corners with the existing bench (about an hour
   each), with the shortest cycle, set-up and hold, the standby runs with the simulator's floor lowered,
   and the macro's own supply capacitance. Ask the author for the characterisation shown at ORConf.
2. Design study of the regulator and its capacitance in the project's analog flow: decide the
   allowed dip, then size.
3. Draw and characterise the level-shifter cell, and try the second supply in LibreLane on a small
   block with two macros before touching the chip.

**Confidence in the numbers.**

| Number | Value | How obtained | Confidence |
|---|---|---|---|
| Works: writes and reads both values, near and far | yes, 3 corners, 2 sizes | simulated, schematic netlist | high for the circuit as drawn; says nothing about mismatch |
| Clock to output, 1024 x 8, slow corner, no wiring | 3.17 ns | simulated | high for what it is |
| The same with wiring | 5 to 6 ns | estimate from the 64 x 8 extracted run (x 1.49) | medium; could be 7 to 8 ns |
| Shortest cycle shown | 8 ns | simulated, schematic | a lower bound on speed only; with wiring not done |
| Set-up of address and data | 0 to 0.25 ns | simulated, 64 x 8 schematic | medium; with wiring probably under 1 ns |
| Read charge, 1024 x 8 | 36 to 45 pC, about 1.75 x with wiring | simulated; factor from 64 x 8 | medium |
| Regulator load, 34 macros, 20 MHz | 1 to 2 mA light, 8 to 14 mA worst, design for 15 to 20 mA | arithmetic on the above | medium |
| Leakage, 34 macros, 125 C | 59 uA typical, 0.67 mA fast at 3.6 V | simulated, model leakage | low to medium: depends on the models' leakage accuracy |
| Leakage at 25 C | below 6.5 uA | simulator floor | low: real value not obtained |
| Level shifter delay | 1.0 to 1.9 ns slow cases | simulated, pad library's circuit, no wiring | medium |
| Static current of a plain 5 V gate at 3.0 V input | 68 to 180 uA | simulated | high |
| On-chip capacitance needed | 3.5 to 7 nF | charge per clock over allowed dip | low to medium: macro's own capacitance not included |
| Free core gained | +1.27 mm2 before capacitors | arithmetic from LEF sizes | high |
| Silicon: works on run 1 | reported | author's notes and abstract | medium; speed and margins not verified |

Files: `/home/claude/memres_scripts/spice` (`bench.py`, `fixnet.py`, decks, logs, `results_batch1..3.txt`,
extracted netlists in `ext64/` and `ext1024/`, small circuits in `small/`), `floor33.py`, `libcell.py`.

## Third pass

Added 21 November 2026 for the 3.3 V memory (`gf180mcu_ocd_ip_sram__sram1024x8m8wm1`): the three
conditions of the second pass's verdict, worked through one by one. Written as each item was finished;
the order below is the order asked for, the verdict is at the end. Marks as before: **measured**
(includes "simulated by me"), **cited**, **estimate**, and **not done**.

### 1. The 1024 x 8 block with its wiring

**In short.** With the capacitance of its layout the block works at all three corners and at 1.8 V, and
answers in **5.57 ns at the slow corner** (slow silicon, 3.0 V, 125 C), under the 8 ns of the
condition. The first extracted run, which failed, was the fault of my extraction, not of the block.

**Why the first extracted run failed (measured).** That run (geometry flattened in Magic, then
extracted) read 0xBF at every address and drew 26.4 mA with the clock stopped.

* Not the bench. The extracted sub-circuit's 38 pins are in the same order as the `Xdut` line
  (VSS, VDD, A9..A0, CLK, GWEN, Q7..Q0, WEN7..WEN0, D7..D0, CEN). All 21,790 p-transistors have
  their body on VDD and all 38,083 n-transistors on VSS. Both supplies are connected.
* The netlist itself. I compared it with the PDK's schematic netlist (netgen 1.5.323 with the PDK's
  setup file). It has 9 nets fewer than the schematic (19,757 against 19,766), and its VSS net carries
  138 p-transistor source or drain terminals that the schematic's VSS does not have. The largest of them
  is the output stage of `men`, the block's internal enable. The clock generator drives `men` to every
  decoder and column through 20 p-transistors of 8.57 um (171.4 um in all). In this netlist `men` is
  VSS. So the enable never rises (every read fails), and once it should, the 171 um p-transistor
  connects VDD to VSS (the 26 mA).
* The same layout extracted hierarchically (Magic 8.3.677, `extract all`, netlist flattened by
  `ext2spice hierarchy off`) **matches the schematic** in netgen: 56,808 devices and 19,766 nets on
  both sides, "Circuits match uniquely". So the short comes from the geometric flattening step. It is
  not drawn in the layout. Which feature of the flattening causes it I did not find out. Extracted
  alone, the clock generator and the control block are correct both ways.
* A second fault in my new netlist: `ext2spice` left the substrate as a net of its own, holding 19,484
  capacitors (9.6 pF of them from VDD) and no transistor. I tied it to VSS. With it floating, the slow
  corner gave 5.54 ns instead of 5.57 ns. The second pass's 64 x 8 netlist does not have this fault.

**What was simulated.** The hierarchical extraction with capacitance: 59,873 transistors and 137,377
capacitors of 0.02 fF or more, 53.9 pF in all, no negative values, no wire resistance. The bench and
the multi-finger rewrite are as in the second pass. The short sequence is used: write A5 at address 0
and 5A at address 1023, then read 0, 1023, 0, with a 12 ns clock period (50 ns at 1.8 V), 50 fF on each
output, and inputs changing 5 ns before the clock. One run takes 15 to 23 minutes.

| Corner | Clock to output | Read, per access | Write, per access | Clocked, not selected | Schematic, clock to output (second pass) |
|---|---|---|---|---|---|
| slow, 3.0 V, 125 C | **5.57 ns** | 58.7 pC | 70.9 pC | 1.09 pC | 3.17 ns |
| typical, 3.3 V, 25 C | 3.48 ns | 64.9 pC | 78.1 pC | 1.21 pC | 1.98 ns |
| fast, 3.6 V, -40 C | 2.40 ns | 72.6 pC | 87.0 pC | 1.41 pC | 1.36 ns |
| slow, 1.8 V, 125 C, 50 ns clock | 11.2 ns | 33.9 pC | 40.0 pC | 0.63 pC | not run |

* All reads were correct in all four runs, at the near and the far address (**measured**). Clock to
  output is defined as in the second pass: the slowest of the eight bits, near and far within 0.1 ns.
* Wiring makes the block 1.75 to 1.76 times slower than its schematic, about the 1.49 of the 64 x 8
  block plus the longer lines. The second pass's working figure of 5 to 6 ns holds. Wiring takes 1.62
  to 1.70 times the schematic's charge, a little below the 1.75 assumed in the second pass.
* **Supply capacitance of one block** (typical, 25 C, clock stopped): during a 0.1 V supply ramp over
  20 ns the block takes a steady 0.427 mA, which makes **85 pF** (measured). The bench's own printout
  (37.7 pF) is wrong: it subtracts a current read during the ramp. This includes the n-wells, the
  block's own MOS capacitors and the bit lines that are held at the supply.
* **Wire resistance (estimate).** Metal1 to Metal3 have 90 milliohms per square and poly 7.3 ohms per
  square (Magic's technology file). The extracted capacitance of the longest nets: a bit line 150 to
  167 fF, a word-line half 55 to 58 fF (strapped), `men` 809 fF, the clock pin 117 fF. A 390 um bit
  line 0.3 um wide is about 120 ohms, so its distributed delay is about 0.38 x 120 ohm x 160 fF = 7 ps.
  `men` across the block at about 1 um width gives about 8 ps. Resistance should add **under 0.1 ns**.
  That has not been simulated: an extraction with resistance was **not done**.
* Not done: the shortest cycle and pulse with wiring (only 12 ns was run), set-up and hold with wiring,
  mismatch.

**Lowest supply.**

* The storage cell alone (static margins, all four corners typical, slow, fast and slow-n-fast-p,
  -40 and 125 C, 3.6 V down to 1.5 V; the fast-n-slow-p corner was not run) can always be written and
  is never flipped by a read. Writing flips it when the bit line falls to 0.325 V or less, so the driver
  pulling to 0 V has at least 0.325 V of margin. The worst case is slow n with fast p, -40 C, 1.5 V. When
  read, the node holding 0 rises to at most 0.40 V below the other inverter's switching point. The worst
  case for that is fast, 125 C, 1.5 V. Both margins shrink smoothly with the supply, without a cliff
  (**measured**, `pass3/cellmargin.txt`). Mismatch between the cell's transistors is not included, and
  it is what limits a real array at low voltage.
* The whole block with wiring works at 1.8 V, slow silicon, 125 C, at 11.2 ns (table above).
* **Statement:** the block works over the chip's full supply range of 1.8 to 5.5 V (`docs/datasheet.md`, section
  2) if its rail stays at 1.8 V or more. Below the regulator's dropout the rail follows VCC, so the rail
  falls to the chip's own 1.8 V minimum and no lower, provided the regulator passes VCC through with
  little loss (item 2). At 1.8 V the block is fast enough for the 4 MHz that an ATmega328PB allows
  there. The cold slow corner at 1.8 V, the fast-n-slow-p cell corner, and anything below 1.8 V for the
  whole block were **not done**.

**Condition 1: held, as far as simulation goes.** 5.57 ns at the slow corner with wiring capacitance,
plus under 0.1 ns for resistance (estimate), against the 8 ns asked. With the level shifter (1.1 to
1.3 ns at the slow corner, section 3 below) that is about 6.9 ns from clock to a 5 V signal, where the
foundry 5 V block takes 10.3 ns. The condition's second half, the author's measurements across
voltage and temperature, is still not available to me.

Files: `memres_work/topext/` (extraction scripts `t.tcl` and `fc.tcl`, netlist `sram1024_hc.spice`),
`memres_work/lvs/` (the failed netlist's comparison, `lvs.out`), `memres_work/h1024_*.out`.

### 2. The regulator and its capacitance

**In short.** One clock edge can take up to 0.68 nC from the memory rail (measured charges, worst
corner). The 36 blocks bring 2.7 nF of their own to the rail. With that alone, a simple regulator keeps
the rail at 2.99 V or more at every corner tried. **About 2 nF more** keeps it at 3.04 V or more, a
first-order design and simulation result. That is roughly 1 mm2 of MIM capacitor, or 0.5 to 0.65 mm2 of
MOS capacitor, against the 3.5 to 7 nF and 0.9 to 1.75 mm2 estimated in the second pass. The regulator
here has a real output transistor but an idealised amplifier. It is not a design.

**The load step (from the RTL and the measured charges).**

* The core is `hazard3_cpu_1port` (`rtl/rv328_core.v`): one bus. On one clock edge there is at most one
  access in its address phase (an instruction fetch, or a load) plus the data phase of an earlier store
  to RAM (`ram_wr_now`). A RAM read cannot meet a RAM write on the same edge; the core delays it
  (`ram_late`). The RAM's four byte blocks share one enable, so a byte store enables all four.
* **The island of the second pass** (program store of 32 x 1024 x 8 as 8 banks of 4 bytes, RAM of 4 x
  512 x 8): at most **8 blocks enabled on one edge**, 4 read and 4 written. The other 28 blocks see the
  clock without being selected, unless their clocks are gated.
* **The present cache, if built from these blocks** (`rtl/rv328_xip.v`, full layout: 3 ways of 4 KB):
  within a way only one bank fires per access. But all three ways are read at once, each with its tag
  block, so a fetch enables 15 blocks, and 19 with a store in the same edge. That is 1.29 nC at the
  typical corner, twice the island's. So the island, not the cache, is the case sized here.
* Charge on the worst edge (8 enabled, 28 clocked; measured per-block charges of item 1; the RAM's
  512 x 8 blocks counted as 1024 x 8, which overstates them):

| Corner | 4 reads + 4 writes + 28 clocked | as current, every edge at 20 MHz | usual edge: one fetch, 32 clocked |
|---|---|---|---|
| slow, 3.0 V, 125 C | 0.549 nC | 11.0 mA | 0.27 nC, 5.4 mA |
| typical, 3.3 V, 25 C | 0.606 nC | 12.1 mA | 0.30 nC, 6.0 mA |
| fast, 3.6 V, -40 C | 0.678 nC | 13.6 mA | 0.33 nC, 6.6 mA |

* The charge comes in a burst of about 2 ns after the edge (second pass). In the simulations below it
  is a triangle with that base, repeated every 50 ns. Every edge is taken as a worst one, which no
  program sustains.
* **The rail's working range** taken here is 3.0 to 3.6 V: the range in which item 1's timing holds,
  and below the 3.63 V that the 3.3 V oxide allows. The block works down to 1.8 V more slowly. A dip
  below 3.0 V makes the access that causes it slower, not wrong: 5.6 ns at 3.0 V and 11.2 ns at 1.8 V at
  the slow corner.

**Capacitance the blocks bring.** 85 pF per 1024 x 8 block (item 1), so 32 x 85 = **2.7 nF** on the
rail from the program store alone (measured per block, arithmetic for 32). The RAM blocks' share was
not measured and is left out.

**The regulator simulated** (`pass3/reg2.py`, ngspice, PDK models for the transistor):

* Output stage: a native thick-oxide n-transistor (`nfet_06v0_nvt`, 10,000 um / 1.8 um, body on the
  substrate) as a source follower from VCC. A follower answers a fast load by itself: when the rail
  dips, its gate-source voltage grows and it conducts more, without waiting for the loop. A p-type
  pass transistor (the second pass's idea, and variant P of the first attempt) depends on the loop for
  that, and in the first attempt it lost 0.3 to 0.8 V under load.
* Error amplifier: **behavioural**, a transconductor of 80 uS limited to 40 uA, 100 pF from the gate
  to ground, its output clamped between 0 V and VCC - 0.2 V. Reference 1.1 V (the project's bandgap),
  divider 2 Mohm / 1 Mohm.
* A bleed current of 0.5 mA from the rail while awake, and 5 uA in a sleep setting (with the amplifier
  at 8 uS / 4 uA). The bleed keeps the follower's transconductance up, so that the step from idle to
  full load costs less. With 50 uA of bleed the first dip at the typical corner was 0.06 V deeper
  (3.053 against 3.110 V, 5 nF, earlier load estimate of 0.55 nC).

**Load step, 20 us of worst edges after rest** (rail at rest 3.300 V at every corner; capacitance =
the blocks' 2.7 nF plus what is added; measured in simulation):

| Corner, VCC | Added | Lowest, at the start of the load | Steady ripple, low to high | Highest after the load stops |
|---|---|---|---|---|
| typical, 25 C, 5.0 V | none | 3.030 V | 3.156 to 3.361 V | 3.420 V |
| slow, 125 C, 4.5 V | none | **2.988 V** | 3.182 to 3.372 V | 3.482 V |
| slow, -40 C, 4.5 V (fast charge) | none | 2.999 V | 3.145 to 3.376 V | 3.441 V |
| fast, -40 C, 5.5 V | none | 3.056 V | 3.133 to 3.343 V | 3.374 V |
| typical, 25 C, 5.0 V | 2 nF | 3.093 V | 3.223 to 3.345 V | 3.421 V |
| slow, 125 C, 4.5 V | 2 nF | **3.043 V** | 3.234 to 3.346 V | 3.476 V |
| slow, -40 C, 4.5 V (fast charge) | 2 nF | 3.069 V | 3.216 to 3.353 V | 3.439 V |

* The lowest point comes in the first microsecond. It is the follower moving from 0.5 mA to 12 mA
  (a larger gate-source voltage) before the loop has raised its gate. The per-edge ripple after that
  is the charge over the capacitance, about 0.2 V with the blocks alone and 0.12 V with 2 nF added.
  More capacitance helps the first dip less than it helps the ripple. A wider follower helps a little
  (typical, 5 nF, 50 uA bleed: 3.026, 3.048 and 3.059 V for 5,000, 10,000 and 20,000 um).
* After the load stops the rail rises by up to 0.18 V and returns in about 10 us; 3.48 V at most,
  inside the 3.63 V limit.
* **Stability**: at a light load (0.4 mA of bursts) the rail stays within 3.27 to 3.32 V at the slow and
  the fast corner, with and without added capacitance. In the sleep setting, with almost no load, it
  rests at 3.27 to 3.31 V. No oscillation in any run. This is a time-domain check with an ideal
  amplifier, not a phase margin.
* **Needed capacitance (estimate from these runs).** To stay at 3.0 V or above at every corner tried:
  the blocks' own 2.7 nF is just short at the slow corner (2.988 V). Adding **2 nF** gives a margin of
  40 mV or more. Allowing dips to 2.9 V (a slower first access) needs no added capacitor in these runs.
  Charge per edge 20 % lower than assumed (stores do not come every edge) gives the same margin with
  less.

**Capacitor type and area** (densities **measured** from the PDK's ngspice models, area **estimate**):

| Type | Density | Spread in the models | 2 nF takes |
|---|---|---|---|
| MIM, `cap_mim_2f0_m4m5_noshield` (between Metal4 and Metal5; Magic's generator for this PDK makes the 2 fF/um2 one) | 1.99 fF/um2 | +/- 10 % | 1.0 to 1.1 mm2 |
| MOS, 3.3 V gate oxide (`cap_nmos_03v3`, in inversion) | 3.98 fF/um2 | +/- 10 % | 0.5 to 0.56 mm2 of gate, about 0.65 mm2 drawn |
| MOS, 6 V gate oxide (`cap_nmos_06v0`) | 2.18 fF/um2 | +/- 10 % | 0.9 to 1.0 mm2 |
| MIM over MOS, stacked | about 6 fF/um2 | | about 0.35 to 0.4 mm2 |

* A MOS capacitor on the 3.3 V oxide is right for this rail, which never exceeds 3.48 V in the runs.
* The macros leave Metal4 and Metal5 free above them (second pass, section 6), and MIM lies between
  those two layers. 2 nF is about a fifth of the 5.36 mm2 of the 36 blocks, so the capacitor could sit
  over the memory and cost no core area, if the power grid can give up that much of Metal4 and Metal5
  there. Not checked against the grid or the density rules.
* The core area left for capacitors in section 6 (+1.27 mm2) now holds the 2 nF with room to spare.

**Quiescent current (estimate; the amplifier is behavioural, its own current is assumed).**

* Awake: bleed 0.5 mA, amplifier about 80 uA, divider 1.1 uA, about **0.6 mA** from VCC, plus the
  bandgap's share. The simulator shows 0.52 mA at rest (bleed, divider and the 20 uA load), the
  amplifier excluded.
* Asleep (sleep setting): bleed 5 uA, amplifier about 8 uA, divider 1.1 uA, about **15 uA**, plus
  memory leakage (second pass: 59 uA for 34 blocks at 125 C typical, 0.67 mA at the fast corner,
  25 C unknown below the simulator's 6.5 uA floor). The simulator shows 7.1 uA at -40 C and 26 uA at
  125 C at rest, including the load.
* Going from sleep to full load must not happen in the sleep setting. Simulated at the slow corner,
  -40 C, with the blocks' capacitance only: the rail falls to 2.892 V, and it still averages only
  3.16 V after 20 us. After the load stops it is at 3.40 V 13 us later. So on waking, the regulator
  goes to its awake setting first, and a few microseconds later the memory clock starts. The wait is
  an estimate, not simulated. It is short against the oscillators' start-up.

**From 5.5 V down through dropout (DC, measured in simulation, gate limit VCC - 0.2 V).**

| VCC | typical 25 C, 0.02 / 15 mA | slow 125 C, 0.02 / 15 mA | slow -40 C, 0.02 / 15 mA | fast -40 C, 0.02 / 15 mA |
|---|---|---|---|---|
| 5.5 to 4.0 V | 3.30 / 3.30 | 3.30 / 3.30 | 3.30 / 3.30 | 3.30 / 3.30 |
| 3.8 V | 3.30 / 3.30 | 3.30 / 3.20 | 3.30 / 3.16 | 3.30 / 3.30 |
| 3.6 V | 3.30 / 3.22 | 3.22 / 3.01 | 3.12 / 2.97 | 3.30 / 3.30 |
| 3.0 V | 2.80 / 2.65 | 2.67 / 2.45 | 2.55 / 2.40 | 2.95 / 2.85 |
| 2.7 V | 2.52 / 2.37 | 2.39 / 2.18 | 2.26 / 2.11 | 2.67 / 2.56 |
| 1.8 V | 1.67 / 1.51 | 1.55 / 1.34 | 1.40 / 1.25 | 1.79 / 1.69 |

* It regulates over the whole 20 MHz range (4.5 to 5.5 V) at every corner and load. Below about 3.8 V
  the rail follows VCC, but 0.1 to 0.55 V lower. A follower cannot pass VCC through, and at 1.8 V
  the rail would be down to 1.25 V at the cold slow corner, below anything the block was simulated at.
* So "the memory supply follows VCC" needs a **bypass switch**: a thick-oxide p-transistor from VCC
  to the rail, turned on below about 3.5 V by a comparator with hysteresis (the brown-out detector's
  kind of circuit). From the second pass (5.4 mA per 1000 um at 0.1 V drop, 3.0 V) and the load at
  the clock allowed there (about 1 to 3 mA at 4 to 10 MHz), it would be 1000 to 3000 um. That is an
  estimate. The switch, its comparator and the hand-over without a step were **not designed**.

**What remains unproven.** A real error amplifier: its output must swing to VCC - 0.2 V, and its gain,
poles, current and offset are assumed here. Stability as a phase margin over load and corners. Supply
rejection from the noisy 5 V rail through the follower's drain. Start-up: the reset must hold until the
rail is up, because the level shifter does not switch with a low rail (section 3). The bypass switch.
The resistance of the rail's grid between the capacitors and the blocks. The 512 x 8 RAM blocks'
charge and capacitance. The capacitors' leakage and layout. None of it has silicon.

**Condition 2: held at first order, still open as a design.** On the measured load a follower regulator
and 2 nF added to the blocks' own 2.7 nF keep the rail at 3.04 V or more at the corners tried. The
capacitor fits, in about 1 mm2 of MIM, perhaps over the memory, or in 0.5 to 0.65 mm2 of MOS
capacitor. The circuit, the bypass switch and the layout still have to be designed.

Files: `pass3/reg2.py`, results in `memres_work/reg/` (`sweep1..4.txt`, `dc2.txt`, `wake.txt`).

### 3. The level shifter

**Up, 3.3 V to 5 V.** The circuit is the one inside the pads of `gf180mcu_ocd_io` (sub-circuit
`io_lvlshft`), with devices from the installed PDK:

| Device | Type | W / L |
|---|---|---|
| inverter making the complement, on the 3.3 V rail | `nfet_03v3`, `pfet_03v3` | 0.6 / 0.28 um, 1.2 / 0.28 um |
| two pull-down transistors, gates on the input and its complement | `nfet_06v0` | 1.5 / 0.7 um |
| two cross-coupled pull-up transistors on the 5 V rail | `pfet_06v0` | 1.5 / 0.7 um |

Simulated alone (ngspice, schematic, no wiring), 30 fF load, 0.5 ns input edge, input to output at
half levels:

| Corner | Rise | Fall | Charge per cycle from 5 V | Standing current |
|---|---|---|---|---|
| slow, 125 C, 3.0 V in, 4.5 V out | 1.10 ns | 0.95 ns | 0.37 pC | at the simulator's floor, about 10 pA |
| typical, 25 C, 3.3 V in, 5.0 V out | 0.70 ns | 0.59 ns | 0.41 pC | the same |
| fast, -40 C, 3.6 V in, 5.5 V out | 0.50 ns | 0.41 ns | 0.47 pC | the same |
| slow, 125 C, 3.0 V in, 5.5 V out | 1.27 ns | 1.34 ns | 0.54 pC | the same |
| slow n with fast p, -40 C, 3.0 V in, 5.5 V out (worst tried) | 2.01 ns | 1.42 ns | 0.98 pC | the same |
| slow, 125 C, both rails at 1.8 V | 3.28 ns | 1.00 ns | 0.12 pC | the same |

* **No standing current** in either state: one side of the cross-coupled pair is always fully off.
  The values are the simulator's own leakage floor, not a result.
* A variant without the 3.3 V inverter, taking the complement from an ordinary library inverter on the
  3.3 V rail, gives the same delays within 0.1 ns. Then the cell holds only the four thick-oxide
  transistors and sits entirely in a 5 V well.
* **One limit found.** With the 5 V rail at 5.5 V and the memory rail at 2.3 V or 1.8 V (slow silicon,
  -40 C) the cell does **not** switch: the pull-down cannot overcome the pull-up. In operation this
  combination does not occur, because the memory rail is 3.3 V whenever the supply is high, and when
  the supply is low both rails are low together (the 1.8 V row above works). It does occur while the
  regulator starts. The reset has to hold until the memory rail is up.
* **Area (estimate).** In the pad library the four thick-oxide transistors are drawn in 5.53 x 12.91 um
  (71 um2) and the inverter in 12 um2 (measured in the second pass). As a cell in a 9-track row
  (5.04 um high) the four-transistor variant should be about 8 to 10 um wide, 40 to 50 um2. It needs
  LEF, a liberty file made by simulation, and layout checks; none of that exists.
* **How many.** One per memory output that crosses: 288 if all 36 macros' outputs are shifted
  (36 x 8), 64 if the read selection is done inside the island (32 for the program store, 32 for the
  RAM). At 50 um2 that is 0.014 or 0.003 mm2. Switching all 64 every clock at 20 MHz takes about 0.6 mA
  from the 5 V rail and under 0.1 mA from the memory rail (from the charges above).

**Down, 5 V to 3.3 V.** The memory's inputs do **not** tolerate 5 V.

* Evidence from the macro's netlist: an address pin leads straight to the source of a transmission
  gate built from `nfet_03v3` and `pfet_03v3` whose n-well is on the memory rail (sub-circuit
  `alatch`); data, enables and clock lead to gates of the same 3.3 V transistors. All 383 transistor
  lines of the netlist are these two types. The layout adds 18 small n-diffusion diodes to ground on
  the inputs (cell `antenna_tiedown`). A 5 V level would put 5 V across a 3.3 V gate oxide (rated
  3.3 V plus 10 %, as you established) and would forward-bias the p-transistor's source into its well.
* Nothing new has to be designed for this direction. A cell of `gf180mcu_fd_sc_mcu9t5v0` standing on
  the 3.3 V rail takes the 5 V signal on its thick-oxide gates and delivers a 3.3 V swing: 0.4 to 0.6 ns
  at slow silicon and 3.0 V (simulated in the second pass). It needs rows of its own whose n-well is on
  the memory rail. About 100 such buffers for shared buses (second pass, section 4).

### Verdict of the third pass

| Condition (second pass) | Status | The number |
|---|---|---|
| 1. The 1024 x 8 block stays under about 8 ns with wiring at the slow corner; the author's measurements confirm it across voltage and temperature | **held** for the simulation; the silicon half **still open** | 5.57 ns at slow silicon, 3.0 V, 125 C, extracted capacitance (measured); under 0.1 ns more for resistance (estimate); works at all three corners and at 1.8 V (11.2 ns). No silicon characterisation seen. |
| 2. A regulator without external capacitor and its on-chip capacitance can be designed and fitted | **held at first order, still open as a design** | rail at 3.04 V or more at the corners tried on the worst load of 0.68 nC per edge, with a native follower and 2 nF added to the blocks' own 2.7 nF (simulated, behavioural amplifier); 2 nF is about 1 mm2 of MIM or 0.5 to 0.65 mm2 of MOS capacitor (estimate); a bypass switch for VCC below about 3.5 V is still needed and not designed |
| 3. The project accepts what power-down then costs | **still open**: a decision for the project, not a measurement | island kept on: regulator about 15 uA asleep (estimate) plus memory leakage, below 6.5 uA at 25 C (simulator floor) up to 59 uA typical and 0.67 mA fast at 125 C (second pass); or island off and the program copied again on wake-up, about 30 ms (second pass) |

**Overall: still go, and the case is stronger than after the second pass.** The block is fast enough
with its wiring, and the capacitor is less than half of what was feared, because the blocks bring 2.7 nF
of their own. Nothing found rules it out. It remains work for a second silicon, not the first. The
next steps, in order:

1. A real error amplifier, the bypass switch and the start-up in the analog flow, with stability over
   load and corner.
2. The resistance of the rail grid between capacitors and blocks.
3. The shortest cycle, set-up and hold of the extracted block.
4. The cold slow corner at 1.8 V.
5. The decision on power-down.

### Power-down: recommendation (added 21 November, after the third pass)

The ATmega328PB keeps its program in flash and its 2 KB RAM powered: 0.2 uA in power-down (typical,
1.8 V, 25 C, watchdog off, Microchip's product page) and it resumes within microseconds to about a
millisecond. Neither option above matches that: keeping the 3.3 V memory powered costs about 75 times
that current at room temperature and far more hot; copying the whole program back costs about 30 ms of
full power on every wake.

**Recommended: switch the memory off in power-down and refill it on demand.** The on-chip memory holds
the whole program, with a "loaded" flag per 32-byte line. Power-up and wake from power-down clear the
flags; a line is fetched from the serial memory the first time it is used (about 29 us), and since the
whole program fits, a line is never thrown out. The first 2 KB (interrupt handlers and the wake-up path,
already pinned in today's cache) sit in a small block that stays powered, with the regulator in a
low-current sleep mode.

* A pin or timer interrupt is answered at once; other code is slower the first time it runs after a wake
  and at full speed after that. A device that wakes, reads a sensor and sleeps refills only the few
  hundred bytes it uses.
* Sleep current: a few uA, from the small block's leakage and the sleep regulator (**estimate** from the
  leakage simulated in the second pass; not simulated as such). Not 0.2 uA, and it should be in the
  datasheet as a difference from the ATmega.
* The logic is today's cache controller with one way of the full program size: fill on miss, never
  evict. **Not designed or simulated.**
* True "nothing to load" would need non-volatile memory on the chip, which the open kit does not offer
  for user programs (section 5: mask ROM and logic ROM are fixed at manufacture, eFuse is one-time).

## Comparison

Density is area per stored bit, whole macro or block, not just the storage cell. "x" is the density
relative to the 512 x 8 foundry macro (51.1 um2 per bit); below 1 means worse.

| Option | um2 per bit | x | Speed at our corner | Status | Silicon | Effort in our flow | Main risk |
|---|---|---|---|---|---|---|---|
| 1a. Foundry 5 V macro, 512 x 8 (today) | 51.1 (measured) | 1.0 | 10.3 ns clock to output, 11.9 ns cycle (measured from liberty) | in the PDK | foundry IP; used on run 1 chips; no published measurement found | done | none new |
| 1b. 3.3 V macro `gf180mcu_ocd_ip_sram` 1024 x 8 | 19.0 (measured) | 2.7 | 3.2 ns clock to output without wiring (simulated), 5 to 6 ns with it (estimate); liberty is a copy of the 5 V macro's | in the PDK | made on run 1, reported working; partial bench test documented; speed not verified | LEF, GDS, netlist ready; needs regulator, on-chip capacitance, level shifters, second supply, timing files | supply island without a silicon example; little silicon data |
| 2. OpenRAM for GF180MCU | none published | ? | unknown | open repository, experimental | none found | large: no working configuration | may not produce a usable macro |
| 2b. Other generators (Arrakeen, 2AM Logic) | none published | ? | unknown | test chips on run 2; one array without timing files | none yet | not available as macros | unknown |
| 3. Latch array (DFFRAM style), 7-track cells | 99 to 121 (estimate from measured cells) | 0.4 to 0.5 | standard-cell timing | open repository; GF180 not sign-off clean | none on GF180 | small | worse than today |
| 4. Own 5 V array from foundry cells, 4 KB or 8 KB blocks | 25.5 or 22.2 (estimate) | 2.0 or 2.3 | unknown; must be simulated | does not exist | none | very large: design, checks, timing files | custom memory without silicon proof |
| 4b. The same in 3.3 V, 8 KB blocks | 10.6 (estimate) | 4.8 | unknown | does not exist | none | very large, plus the 3.3 V island | as 4 and 1b together |
| 5a. eFuse macros `gf180mcu_re_efuse` | 87 to 166 (measured) | 0.3 to 0.6 | not examined | in the PDK | test chip on run 1, no results found | macros ready | one-time; larger than SRAM |
| 5b. Mask ROM array | about 3 to 6 with periphery (rough estimate) | 8 to 17 | unknown | no macro, no verified generator | none | very large | custom design; fixed content |
| 5c. ROM from logic cells | 2.0 cells only; about 3 to 5 placed (measured by synthesis; placed figure is an estimate) | 10 to 17 | not met without buffering; unverified | needs nothing new | ordinary logic | small | fixed content; timing not shown |

## 1. The foundry SRAM and its relatives

### 1a. The 5 V foundry macros

Library `gf180mcu_fd_ip_sram` in the installed PDK holds four macros, all 8 bits wide and all
431.86 um wide (measured from the LEF files):

| Macro | Size (um) | Area (mm2) | Bits | um2 per bit |
|---|---|---|---|---|
| 64 x 8 | 431.86 x 232.88 | 0.1006 | 512 | 196.4 |
| 128 x 8 | 431.86 x 268.88 | 0.1161 | 1024 | 113.4 |
| 256 x 8 | 431.86 x 340.88 | 0.1472 | 2048 | 71.9 |
| 512 x 8 | 431.86 x 484.88 | 0.2094 | 4096 | 51.1 |

* The other PDK variants on this machine (gf180mcuA, B, C) hold the same four macros (measured: same
  file names). The foundry's documentation lists only these four (cited).
* No larger 5 V macro exists in any source I found. A Google repository named as the foundry's "SRAM
  build space" (`gf180mcu_fd_bd_sram`) holds only a placeholder README from July 2022 (measured from a
  clone).
* Inside the 512 x 8 macro (measured from the GDS):
    * The storage cell (`018SRAM_cell1`) repeats every 3.00 um by 4.50 um: 13.5 um2. The foundry's design
      manual gives the same size for its 5 V cell (cited).
    * 4096 storing cells cover 55,296 um2: **26.4 % of the macro**.
    * With the well-tap columns, the unused edge rows and columns, the two array blocks cover 33.0 %.
    * The row decoder and word-line drivers, a 180 um column between the two array halves: 25.6 %.
    * The 176 um band below the array (column selection, sense amplifiers, write drivers, input and
      output latches, control and address pre-decoding): 36.3 %.
    * Guard ring at the top and sides: 5.1 %.
* The four macros follow one size law (measured, exact for all four): height = 196.88 um + 4.50 um per
  row, at 8 words per row. The 196.88 um is paid by every macro.
* Timing at slow silicon, 4.5 V, 125 C (measured from the liberty file): output valid 8.8 to 10.3 ns
  after the clock depending on load, shortest clock period 11.89 ns, address set-up up to 2.0 ns, hold
  up to 2.2 ns. From 64 to 512 words the largest output delay grows only from 9.29 to 10.30 ns. The
  same macro is also characterised at 3.0 V (15.9 ns, period 18.3 ns) and 1.62 V.
* Silicon: the liberty header is dated June 2014 (measured), so this is the foundry's own older IP.
  Run 1 of wafer.space carried it in several chips, among them RISCBoy-180 with 60 blocks and the
  TZ01 test chip with eight (cited). I found no published measurement of it.

### 1b. The 3.3 V macros of Open Circuit Design

Library `gf180mcu_ocd_ip_sram` is installed in the same PDK directory and is listed by wafer.space next
to the foundry macros (cited). It is the foundry macro redrawn with 3.3 V transistors by Tim Edwards
(cited); the netlist uses `nfet_03v3` and `pfet_03v3` at 0.28 um gate length where the foundry macro
uses 6 V transistors at 0.60 um (measured).

| Macro | Size (um) | Area (mm2) | Bits | um2 per bit | x |
|---|---|---|---|---|---|
| 64 x 8 | 301.30 x 152.21 | 0.0459 | 512 | 89.6 | 0.6 |
| 256 x 8 | 301.30 x 224.93 | 0.0678 | 2048 | 33.1 | 1.5 |
| 512 x 8 | 301.30 x 321.89 | 0.0970 | 4096 | 23.7 | 2.2 |
| 1024 x 8 | 301.30 x 515.81 | 0.1554 | 8192 | 19.0 | 2.7 |

* Storage cell 2.18 um by 3.03 um: 6.6 um2, half the 5 V cell (measured). In the 1024 x 8 macro the
  storing cells are 34.8 % of the area (measured).
* Same architecture as the foundry macro: two array halves around a row decoder, eight words per row.
  Size law: height = 127.97 um + 3.03 um per row (measured, exact for all four).
* Same integration as the foundry macro: signal pins on Metal2 along the south edge, obstruction on
  Metal1 to Metal3, power on Metal2 and Metal3 (measured from the LEF). The floorplan scripts would
  need new sizes only.
* **What it would save** (measured macro areas, no channels):
    * today's contents, 14 macros of 1024 x 8 and 3 of 512 x 8: 2.47 mm2 instead of 6.49 mm2;
    * the whole 32 KB program plus 2 KB RAM, 34 macros: 5.28 mm2. In 5 V foundry macros that would be
      68 macros and 14.2 mm2, more than the core.
    * wafer.space's own table gives 108 of these macros in a full slot against 80 of the 5 V macro, or
      108 KB against 40 KB (cited).
* **History and silicon** (all cited):
    * Added to the PDK build in November 2025, three macros finished 18 December 2025, rule fixes in
      February 2026, the 64-word macro in June 2026.
    * Test chip OCD2 on wafer.space run 1 with one 1024, one 512 and two 256-word macros; wafers came
      back 6 April 2026.
    * The test chip's own notes describe a bench set-up for the run 1 chip that exercises the 256-word
      macros with four data bits and six address bits at 3.3 V. A logic-analyser picture in the same
      repository, dated 30 June 2026, shows the four outputs counting. By my reading of its time axis
      one value lasts about 40 ns (25 MHz); that is my reading of a picture, not a stated result.
    * The author's ORConf talk of 12 September 2026 announces characterisation results for the 3.3 V
      SRAM and says the circuits are functional. I could not read the results themselves (only the
      abstract and a video link).
    * A second test chip (OCD3, with all four macros, 3.3 V transistors only) went on run 2; first
      bare dies of that run were shipped 30 October 2026. Other designers have
      weighed or used the macros for run 2 (cited: one design write-up); I found no silicon report
      from them.
* **The timing files are placeholders (measured).** The liberty file of the 3.3 V 1024 x 8 macro is the
  5 V foundry 512 x 8 file of the same corner with the name, header and address width changed: same
  delay tables, same 18.26 ns period at 3.0 V, even the 5 V macro's area. The 3.3 V transistors are
  not the transistors those numbers were made for. Real timing must come from simulation of the
  extracted netlist or from the author's measurements.
* **What adopting it takes.**
    * *A 3.3 V supply on the chip.* The ATmega328PB package has no spare pin, so a regulator without
      an external capacitor, added to the analog macro. Nothing of the kind is in the PDK libraries.
      It must carry the read current of the active macros, which the placeholder files do not tell.
    * *Level shifters.* A 5 V signal must not reach a 3.3 V gate, and a 3.3 V output is not a valid
      high for 5 V logic. Corrected in the second pass: the PDK has no level-shifter cell usable at
      5 V. The two in `gf180mcu_osu_sc_gp12t3v3` are built from 3.3 V transistors, and the right
      circuit exists only inside the pads of `gf180mcu_ocd_io`. A macro
      has 29 inputs and 8 outputs (measured from the LEF). The inputs can share shifters across a
      bank; every output needs one, unless the read multiplexing is also built at 3.3 V.
    * *A second supply net in LibreLane*: power grid for the island, power pins of the macros on the
      new net, LVS with two supplies.
    * *Low supply.* The ATmega328PB runs from 1.8 V and our analog blocks are designed from 2.7 V.
      Below about 3.5 V a regulator only passes the supply through; whether the macro works there is
      not known.
    * *Standby current* of 34 KB at 3.3 V and 125 C is not known, and it flows in power-down unless the
      island is switched off and reloaded on wake-up.
* A different way to use the same macros is to build the whole core at 3.3 V with the 3.3 V cell
  library (`gf180mcu_as_sc_mcu7t3v3`) and the dual-voltage pads (`gf180mcu_ocd_io`), as the OCD3 test
  chip does (cited). That removes the level shifters inside the core but replaces the cell library,
  the pads and every timing result of this project. I did not look into it further.

### What the whole program on the chip would mean

A static memory forgets at power-off, so the program still lives in the serial memory die and is copied
at reset. By the cache study's figure of 580 clocks per 32-byte line, 32 KB takes about 594,000 clocks:
30 ms at 20 MHz (estimate), but 0.6 s if the copy ran at a 1 MHz start-up clock. After that there are
no misses, no tags and no cache controller.

## 2. Memory compilers

* **OpenRAM** (University of California Santa Cruz and Oklahoma State University). Its stable branch
  has a `technology/gf180mcu` directory (measured from a clone of 27 October 2026). It contains one
  single-port storage cell, which is the foundry's 5 V cell (3.00 x 4.50 um pitch, 6 V transistors),
  one decoder gate named as a 3.3 V cell, and a technology file that names 3.3 V transistors
  and a 1.8 V nominal supply. There is no GF180MCU SRAM configuration among its example macros, only
  one 1 KB ROM configuration whose common settings switch the DRC and LVS checks off. The project's own
  2023 status slides call the port under way with basic arrays and note that only the 5 V cell exists
  (cited). I found no GF180MCU macro, tape-out or measurement. The same slides report an earlier
  OpenRAM test chip, in a process they do not name, free of errors below 34 MHz at 1.7 V (cited).
* **Arrakeen / c4m-flexmem** (Chips4Makers, Staf Verhaegen). A memory generator with three test chips
  on wafer.space run 2 (July 2026): 3.3 V blocks drawn with the ordinary rules, 3.3 V blocks with the
  SRAM rules, and 5 V blocks (cited). The generator is described by its author as experimental (cited).
  I found no block sizes, densities or results. Worth watching; nothing to adopt today.
* **2AM Logic `gf180-sram`**. One 256 x 32 block with its own storage cell, laid out and checked by
  software agents; array clean in DRC and LVS, no timing files, no tape-out (cited). Not usable.
* **DFFRAM** is a standard-cell generator; see the next section.

## 3. Memories from standard cells

Cell areas from the PDK's LEF files (measured):

| Cell | 9-track 5 V | 7-track 5 V |
|---|---|---|
| latch (`latq_1`) | 56.4 um2 | 43.9 um2 |
| flip-flop (`dffq_1`) | 79.0 um2 | 63.7 um2 |
| tri-state buffer (`bufz_1`) | 36.7 um2 | 30.7 um2 |
| 4-input multiplexer (`mux4_1`) | 87.5 um2 | 70.2 um2 |

* A bare latch is already as large as a whole bit of the foundry macro (51.1 um2), before anything can
  read it.
* DFFRAM builds a byte from eight latches, eight tri-state buffers, a clock gate and a gate for the
  write enable, plus inverters I did not count (read from its GF180MCU cell definitions). That is 84.5 um2 per bit in 7-track cells
  and 105.5 in 9-track cells, without word decoders, output buffers, taps or routing space (estimate
  from measured cells). At 70 to 85 % row fill: 99 to 121 um2 per bit in 7-track cells, 124 to 151 in
  9-track: **1.9 to 2.9 times worse than the foundry macro**.
* DFFRAM's README lists its GF180MCU platform as not sign-off clean (hold violations in the netlist)
  and not silicon-proven (cited).
* The 3.3 V cell libraries have the same row heights and similar latch sizes (41.7 um2 in
  `gf180mcu_as_sc_mcu7t3v3`, measured), so they do not change this.

As expected: confirmed worse, with numbers. Useful only for very small memories such as a register file.

## 4. Our own array from the foundry's cells

**The idea.** Keep the storage cell and the leaf cells of the foundry macro (row decoder slice, column
multiplexer, sense amplifier, write driver, control), and build fewer, larger arrays so the periphery is
shared. The leaf cells are in the PDK as separate layout cells (measured: `xdec`, `ypass_gate`,
`mux821`, `sa`, `wen_wm1`, `din`, `outbuf_oe` and others inside the macro GDS and as Magic files).

**What it could save (estimate).** I extended the macro family's own size law: fixed periphery plus
4.50 um per row, and 27.0 um per group of eight columns with its well-tap column (measured pitches).

| Array (5 V cell) | Size (um) | mm2 | um2 per bit | x |
|---|---|---|---|---|
| 1 KB, 1024 x 8 (128 rows) | 432 x 773 | 0.334 | 40.7 | 1.25 |
| 2 KB, 2048 x 8 (256 rows) | 432 x 1349 | 0.583 | 35.6 | 1.4 |
| 4 KB, 1024 x 32 (128 rows, 256 columns) | 1080 x 773 | 0.835 | 25.5 | 2.0 |
| 8 KB, 2048 x 32 (256 rows, 256 columns) | 1080 x 1349 | 1.457 | 22.2 | 2.3 |
| 32 KB in one array (512 rows, 512 columns) | 1944 x 2501 | 4.861 | 18.5 | 2.8 |
| limit for an endless array | | | 15.2 | 3.4 |

* On the chip: 12 KB of cache as three 4 KB blocks, RAM as one 2 KB block, tags unchanged: about
  3.7 mm2 instead of 6.5. The whole program as four 8 KB blocks plus RAM: about 6.4 mm2, the area
  the memories take today.
* **These are estimates and optimistic.** They assume the periphery does not grow. In a real design the
  word-line drivers must drive four times as many cells, the bit lines are two to four times longer,
  the address decoding gains bits and the self-timing of the read must be redone. Expect 10 to 25 %
  more area, and the 32 KB single array is not credible without a redesign of the periphery.
* The same law for the 3.3 V cell gives 12.1 um2 per bit for a 4 KB block and 10.6 for 8 KB (estimate).

**What it involves.**

* Draw the new assemblies: decoder for 128 or 256 rows, 32 column slices, wider control and power.
  Only adding rows is the simple part: the 3.3 V 1024 x 8 macro is the 512 x 8 with twice the rows
  (measured), added in December 2025 (cited). In 5 V that step brings only 1.25 times.
* Simulate read, write and the self-timing at transistor level with extracted wiring at all corners,
  including cell stability with the longer bit lines.
* DRC with the foundry deck. The storage cell uses tighter rules that the deck applies only inside
  the "SRAM core" marker layer (measured from the deck: rule files `sram_5p0` and `sram_3p3`, layer
  108/5). Reusing the foundry cell unchanged inside the marker is how the existing macros pass. A run 2
  test chip from Chips4Makers whose 3.3 V memory blocks use these rules passed the wafer.space
  precheck (cited); whether wafer.space or the foundry restricts the rules to foundry cells I could
  not find stated.
* LVS of the array, then LEF, liberty (from simulation) and a Verilog model for the flow.

**Risks.** No silicon proof; a failure in memory makes the whole chip useless; the people on this
project are not memory designers; it needs its own test chip to be trusted, which costs a run.

## 5. Read-only and one-time-programmable storage

A chip whose program the user writes cannot keep that program in ROM or in one-time memory. These
options are only for content that is the same in every chip: a boot loader or a runtime library.

### eFuse

* Library `gf180mcu_re_efuse` is in the installed PDK: seven macros made by an open eFuse compiler
  (cited), with LEF, GDS, netlists and liberty files at our corners (measured: file list).
* Density (measured from the LEF sizes): the bare 64 x 32 array is 87 um2 per bit; the complete
  1024 x 32 memory with its bus interface is 3.75 mm2, 114 um2 per bit; the small ones 132 to 166.
  **Worse than SRAM**, and each bit can be written once.
* Silicon: an earlier version went on the first open GF180MCU shuttle (GFMPW-0) in an FPGA project, and a test chip with
  2,424 eFuses was on wafer.space run 1 (cited). I found no results. The compiler's README lists open
  improvements to wiring and timing (cited).
* Use for RV328: a few dozen bits of calibration or configuration (oscillator trim), not program
  storage.

### One-time-programmable memory

The foundry DRC deck has rules for an OTP marker layer (measured), but the PDK contains no OTP cell or
macro, and wafer.space's statistics list OTP as drawn by no design (cited). Not available.

### Mask ROM as a custom array

* No ROM macro exists in the PDK, and the only generator I found with a GF180MCU entry is the
  unverified OpenRAM configuration above.
* Rough size of a ROM cell from the ordinary design rules in the DRC deck (gate length 0.60 um at 5 V
  or 0.28 um at 3.3 V, contact 0.22 um, contact to gate 0.15 um, diffusion width and space): about
  0.8 um2 at 5 V and 0.5 um2 at 3.3 V, against 13.5 and 6.6 um2 for the SRAM cells. With decoders and
  sensing a block of 8 to 32 KB might reach 3 to 6 um2 per bit. This is a rough estimate of something
  nobody has drawn.
* Same effort and risk as section 4. Not worth it while the next option exists.

### ROM built from logic cells (measured by synthesis)

A ROM is a fixed truth table; the synthesis tool can build it from ordinary cells. I synthesised real
RV328 code from the benchmark firmware (`build/bench/full.bin`) as a 32-bit-wide ROM with registered
output, with Yosys and the 9-track 5 V library:

| Content | Bits | Cell area | um2 per bit |
|---|---|---|---|
| 2 KB slice | 16,384 | 0.052 mm2 | 3.15 |
| 8 KB slice | 65,536 | 0.155 mm2 (0.121 in 7-track cells) | 2.36 (1.85) |
| whole image, 19,852 bytes (19.4 KB) | 158,816 | 0.310 mm2 | 1.95 |

* The same 19.4 KB in foundry SRAM is 39 macros, 8.2 mm2. Even at 50 % row fill the ROM is about
  0.6 mm2 (estimate).
* **Limits of this measurement.** Cell area after synthesis only. No buffers were inserted: a static
  timing run without wires at the slow corner misses a 50 ns cycle by 55 ns, because each address bit
  drives thousands of gates. A real block needs buffer trees or two clock cycles per read; both add
  area or cost speed, and neither was tried. The area per bit depends on the content.
* **Why it matters here.** In the benchmark firmware `full` the linker map gives 5.7 KB for the
  application and the project's runtime, 7.4 KB for the C library (printf, logarithm) and 6.0 KB for
  the compiler's arithmetic library (software floating point and 64-bit helpers): 70 % library
  (measured; KB of 1024 bytes as elsewhere in the project). In `logger` 13.5 of 15.0 KB is library. The cache study found that programs under 4 KB never reload a
  line with any cache of 4 KB or more.
* **What it would mean for the product.**
    * The library is fixed at tape-out. A fault in it cannot be repaired except by linking a replacement
      into the user's program, which then goes through the cache as today.
    * The tool chain must know the ROM: a symbol file per chip revision, and a linker script that
      resolves library calls to it. The user sees nothing of this in an Arduino-style package. The
      RP2040 keeps floating-point routines in its boot ROM in the same way (from memory, not checked).
    * Which routines to include is a guess about users' programs; the benchmarks are our own.
    * The user's program stays fully programmable.

## 6. Anything else

* **Another process option on the same shuttle.** wafer.space offers one variant (gf180mcuD, five metal
  layers). The 3.3 V transistors are part of it, which is what option 1b uses. There is no embedded
  flash, and no denser foundry memory is offered (cited: technology page lists only the macros above).
* **Dynamic memory.** One- to three-transistor cells with refresh would be denser than six-transistor
  SRAM. I found a compiler paper for such memories but no GF180MCU cell, generator or silicon. Not
  credible for this chip.
* **A smaller cache instead of a denser one.** Section 5's ROM library is really this: it does not make
  memory denser, it removes the need for most of it.

## What I measured

Scripts are in `/home/claude/memres_scripts` (outside the project, nothing in the project was changed):
`cells.py`, `array.py`, `lefpins.py`, `lefcells.py`, `libtime.py`, `model.py`, and `romtest/`. Run with
`source /home/claude/env_ll.sh` and `python3 -I`. PDK: `/home/claude/pdk/gf180mcuD`, open_pdks revision
`792ef67`.

**Macro sizes.** `SIZE` lines of the LEF files in `libs.ref/gf180mcu_fd_ip_sram/lef`,
`gf180mcu_ocd_ip_sram/lef` and `gf180mcu_re_efuse/lef`. Tables in sections 1 and 5.

**Storage cell and array** (`array.py <gds> <cell name>`): reads the GDS with KLayout's Python module,
walks the hierarchy, and lists every placement of the named cell in top-level coordinates.

* 5 V 512 x 8: cell `018SRAM_cell1_512x8m81`, drawn box 3.68 x 5.18 um (it overlaps its neighbours by
  0.34 um on each side). 4164 placements: 64 columns by 64 rows that store, plus unused edge cells. Column
  step 3.00 um, with a 6.00 um step after every eighth column where a well-tap column stands; row step
  4.50 um. Array blocks from x = 8.87 to 123.55 um and 303.75 to 421.43 um, y = 175.79 to 473.47 um.
  Row decoder cell `xdec` 121 um wide, 64 placements, between the blocks.
* 3.3 V 1024 x 8: cell `018SRAM_cell1_3v1024x8m81`, 8324 placements, column step 2.18 um (19.54 um per
  eight columns with the tap column), 128 rows in 387.84 um: 3.03 um per row. Array blocks x = 5.72 to
  87.55 um and 209.47 to 292.98 um, y = 113.02 to 508.90 um.
* Break-down (`model.py`):

| Part | 5 V 512 x 8 | 3.3 V 1024 x 8 |
|---|---|---|
| macro | 209,400 um2 | 155,414 um2 |
| storing cells | 55,296 um2, 26.4 % | 54,111 um2, 34.8 % |
| array blocks with taps and edge cells | 33.0 % | 42.1 % |
| row decoder column between the halves | 25.6 % (180.2 um wide) | 31.1 % (121.9 um wide) |
| band below the array | 36.3 % (175.8 um high) | 21.9 % (113.0 um high) |
| top and side margins | 5.1 % | 4.9 % |
| periphery share (all but storing cells) | 73.6 % | 65.2 % |

* Size laws, checked against all four macros of each family: 5 V height = 196.88 + 4.50 x rows,
  width = 215.86 + 27.00 x (columns / 8); 3.3 V height = 127.97 + 3.03 x rows,
  width = 144.98 + 19.54 x (columns / 8). The estimates in section 4 are these formulas with more rows
  and columns.

**Transistor types.** Counted device names in the SPICE netlists: 5 V macro `nfet_06v0`/`pfet_06v0`,
most at L = 0.6 um; 3.3 V macro `nfet_03v3`/`pfet_03v3`, most at L = 0.28 um.

**Pins and obstructions** (`lefpins.py`): both families have all signal pins on Metal2 within 2 um of
the south edge and obstructions on Nwell and Metal1 to Metal3.

**Timing** (`libtime.py`): largest clock-to-output table value, `min_period` and set-up values of the
liberty files.

| File | Clock to output, max | Shortest period |
|---|---|---|
| 5 V 512 x 8, ss 125 C 4.5 V | 10.30 ns | 11.89 ns |
| 5 V 64 x 8, ss 125 C 4.5 V | 9.29 ns | 10.28 ns |
| 5 V 512 x 8, tt 25 C 5.0 V | 5.68 ns | 6.59 ns |
| 5 V 512 x 8, ss 125 C 3.0 V | 15.87 ns | 18.26 ns |
| 3.3 V 1024 x 8, ss 125 C 3.0 V | 15.87 ns (copy) | 18.26 ns (copy) |

`diff` of the last two files, after replacing the macro names, shows differences only in the header
comments, the date, the comment string and the address bus width. The `area` in the 3.3 V file is
209400.2768, the 5 V macro's.

**Standard cells** (`lefcells.py`): table in section 3. DFFRAM's byte composition from
`platforms/gf180mcuD/gf180mcu_fd_sc_mcu7t5v0/block_definitions.v` of its repository.

**ROM from logic cells** (`romtest/`): `gen_rom.py` writes a Verilog case statement from a slice of
`build/bench/full.bin`; Yosys 0.69 `synth -flatten`, `dfflibmap`, `abc -liberty`, `stat -liberty` with
the typical 5 V library; results in the table of section 5. OpenSTA on the netlist with the slow-corner
library, a 50 ns clock and no wires: worst slack -55.3 ns from an address input.

**Firmware by origin.** Summed the input sections of `build/bench/full.map` and `logger.map` by the
archive they come from: `full` 5,793 bytes project objects, 7,607 `libc.a` (picolibc), 6,190 `libgcc`;
`logger` 1,579 / 7,585 / 6,190.

**DRC deck.** Read `libs.tech/klayout/tech/drc/rule_decks/`: `sram_5p0.rb` and `sram_3p3.rb` apply their
rules to shapes under layer 108/5; `otp_mk.rb` and `efuse.rb` exist; rule values used in the ROM
estimate from `poly2.rb`, `comp.rb`, `contact.rb`.

**Cloned and removed again** (shallow, without file contents except the few files read): OpenRAM,
DFFRAM, `gf180mcu_ocd_sram_test`, `globalfoundries-pdk-libs-gf180mcu_fd_bd_sram`. Nothing from them was
executed.

## Open questions

1. **Does the 5 V foundry macro have published silicon results?** I found none, only its use on run 1
   chips. Not a reason to doubt it, but it is not shown here.
2. **Real speed of the 3.3 V macro** at 3.0 V and 125 C (simulated in the second pass; silicon still open). The September 2026 characterisation was
   presented in a talk whose content I could not read. Ask the author, or simulate the extracted
   netlist.
3. **How completely was the 3.3 V macro tested?** The written notes cover one macro size, four data
   bits and six address bits. The 1024-word macro, all addresses, write margins, temperature and
   supply range are not documented where I could read them.
4. **Read and standby current** of the 3.3 V macro, to size a regulator and to know the power-down
   current (simulated in the second pass; leakage at 25 C still open).
5. **Regulator without an external capacitor and level-shifter cells**: neither exists in the PDK. How
   much area and design time they take was not estimated.
6. **May designs use the SRAM rules for cells that are not the foundry's?** Not stated in the open
   design manual. Matters only for section 4 with a changed cell.
7. **ROM from logic cells after buffering and placement**: area, and whether one 50 ns cycle is
   enough. One block through the flow would answer it.
8. **How much smaller can the cache be with the library in ROM?** Repeat the cache study with the
   library addresses served without misses.
9. **Arrakeen's block sizes and results** are not published yet.
10. **Run 3 silicon and later runs**: I found dates for run 3 only (submission 16 December 2026,
    parts in the second quarter of 2027).

## Sources

PDK and foundry documentation

* GF180MCU design manual, 5 V SRAM core cell (3 x 4.5 um cell, rule list):
  https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_11_1.html
* GF180MCU design manual, 3.3 V SRAM rules:
  https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_11_2.html
* Foundry SRAM documentation (four macros):
  https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/SRAM/gf180mcu_fd_ip_sram/index.html
* open_pdks change log (dates of the 3.3 V SRAM and eFuse libraries):
  https://opencircuitdesign.com/open_pdks/history.html
* Placeholder "SRAM build space" repository:
  https://github.com/google/globalfoundries-pdk-libs-gf180mcu_fd_bd_sram

3.3 V SRAM

* Library: https://github.com/RTimothyEdwards/gf180mcu_ocd_ip_sram
* Test chip, notes in `doc/README`, picture `doc/4bit_count_bench_test.png`:
  https://github.com/RTimothyEdwards/gf180mcu_ocd_sram_test
* Test chip on run 1: https://wafer.space/ws-run1/projects/OCD2.html
* Test chip on run 2: https://wafer.space/ws-run2/projects/OCD3.html
* ORConf 2026 programme, talk by R. Timothy Edwards, 12 September 2026 (video
  https://youtu.be/77NwPPjNKZY, not viewed): https://fossi-foundation.org/orconf/2026
* A run 2 design that weighed these macros (sizes agree with mine):
  https://essenceia.github.io/projects/ethernet_switch_asic/

wafer.space

* Technology page (SRAM table, origin of the 3.3 V macros): https://wafer.space/technology.html
* Run 3 dates and slot prices: https://wafer.space/
* Run 1 (dates, designs, SRAM totals): https://wafer.space/ws-run1/
* Run 2 (dates, memory test chips): https://wafer.space/ws-run2/
* eFuse and SRAM test chip TZ01: https://wafer.space/ws-run1/projects/TZ01.html
* Chips4Makers test chips: https://wafer.space/ws-run2/projects/FS01.html,
  https://wafer.space/ws-run2/projects/FS02.html, https://wafer.space/ws-run2/projects/FS03.html
* Earlier shuttles (eFuse use, no OTP): https://wafer.space/google-gf180mcu-mpw0/
* RISCBoy-180 design notes (5 V macro density as the limit):
  https://github.com/Wren6991/RISCBoy-180/blob/main/notes.md

Second pass

* Test chip history and notes (commit messages of 1 and 4 July 2026, `doc/README`):
  https://github.com/RTimothyEdwards/gf180mcu_ocd_sram_test
* Library history (first commit of 18 November 2025; rule fix of 2 January 2026):
  https://github.com/RTimothyEdwards/gf180mcu_ocd_ip_sram
* Change to the Verilog timing block, May 2026: https://github.com/RTimothyEdwards/gf180mcu_ocd_ip_sram/issues/1
* Tiny Tapeout project with the 256-word macro: https://tinytapeout.com/chips/ttgf0p3/tt_um_essen/
* Bonding results page of the run 1 test chip: https://wafer.space/ws-run1-cob/OCD2/
* Capless 5 V to 3.3 V regulator, design challenge entry: https://github.com/Vaticori/chipalooza3-ldo-gf180
* 3.3 V to 1.8 V regulator without layout: https://github.com/2AMLogic/gf180-ldo

Compilers and generators

* OpenRAM (directory `technology/gf180mcu`, `macros/rom_configs/gf180mcu_rom_*.py`):
  https://github.com/VLSIDA/OpenRAM
* OpenRAM request for GF180MCU support: https://github.com/VLSIDA/OpenRAM/issues/167
* OpenRAM status slides, 2023:
  https://open-source-eda-birds-of-a-feather.github.io/doc/slides_2023/Guthaus-DAC-BoaF-2023.pdf
* DFFRAM (platform status table, GF180MCU cell definitions): https://github.com/AUCOHL/DFFRAM
* Arrakeen test chip repository: https://gitlab.com/Chips4Makers/arrakeen-sram-testchip
* c4m-flexmem: https://pypi.org/project/c4m-flexmem/
* 2AM Logic SRAM block: https://github.com/2AMLogic/gf180-sram
* eFuse compiler: https://github.com/egorxe/gf180_efuse_compiler and
  https://egorxe.github.io/gf180_efuse_compiler
* Gain-cell memory compiler paper (no GF180MCU content found): https://arxiv.org/abs/2602.21278
