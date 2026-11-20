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
not a characterisation (measured).

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
   shifters, a second supply net in the flow, and real timing for the macro. Start with the questions
   in "Open questions"; the author's measurements were presented in September 2026 and a second test
   chip is being delivered now.

**Not recommended:** memories from flip-flops or latches (2 to 3 times *worse* than the foundry macro,
measured cell areas), eFuse (87 to 166 um2 per bit and one-time), OpenRAM on GF180MCU (experimental, no
macro, no silicon), and building our own 5 V array from the foundry's cells (about 2 times denser by
estimate, but a custom-memory project with no silicon proof; reconsider it only if the 3.3 V island is
ruled out).

**The half-size slot is out of reach by memory density alone.** With the 3.3 V macros the present
contents (12 KB cache, tags, 2 KB RAM) take 2.47 mm2; with 1.88 mm2 of logic cells and the 1.30 mm2
analog block that is 5.65 mm2 in a 5.02 mm2 core (estimate from measured areas).

## Comparison

Density is area per stored bit, whole macro or block, not just the storage cell. "x" is the density
relative to the 512 x 8 foundry macro (51.1 um2 per bit); below 1 means worse.

| Option | um2 per bit | x | Speed at our corner | Status | Silicon | Effort in our flow | Main risk |
|---|---|---|---|---|---|---|---|
| 1a. Foundry 5 V macro, 512 x 8 (today) | 51.1 (measured) | 1.0 | 10.3 ns clock to output, 11.9 ns cycle (measured from liberty) | in the PDK | foundry IP; used on run 1 chips; no published measurement found | done | none new |
| 1b. 3.3 V macro `gf180mcu_ocd_ip_sram` 1024 x 8 | 19.0 (measured) | 2.7 | unknown: liberty is a copy of the 5 V macro's | in the PDK | made on run 1, reported working; partial bench test documented | LEF, GDS, netlist ready; needs regulator, level shifters, second supply, timing | supply island; no real timing; little silicon data |
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
      high for 5 V logic. The cell libraries in the PDK contain no level-shifter cell (measured: no
      such macro name in the LEF files); the dual-voltage pad library `gf180mcu_ocd_io` has no separate one either. A macro
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
2. **Real speed of the 3.3 V macro** at 3.0 V and 125 C. The September 2026 characterisation was
   presented in a talk whose content I could not read. Ask the author, or simulate the extracted
   netlist.
3. **How completely was the 3.3 V macro tested?** The written notes cover one macro size, four data
   bits and six address bits. The 1024-word macro, all addresses, write margins, temperature and
   supply range are not documented where I could read them.
4. **Read and standby current** of the 3.3 V macro, to size a regulator and to know the power-down
   current.
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
