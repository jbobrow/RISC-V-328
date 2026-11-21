# Decisions

Each decision with what was known at the time, what else was on the table and why it went the way it
did. The [build log](build_log.md) tells the same story in order.

| # | Decision | Status |
|---|---|---|
| 1 | RISC-V processor (Hazard3), not an AVR clone | settled |
| 2 | GF180MCU at 5 V through wafer.space | settled |
| 3 | Program in a serial memory die in the package, run through a cache | settled |
| 4 | Same 32 pin positions as the ATmega328PB | settled |
| 5 | Digital part first, analog blocks as one macro added later | settled |
| 6 | Speed parity with the ATmega is a requirement | settled, 20 November |
| 7 | Cache: 12 KB, three-way, interrupt handlers pinned | chosen, in layout |
| 8 | Single-cycle multiplier | chosen, thin timing margin |
| 9 | Full-height slot for the product | chosen |
| 10 | Half-height digital-only layout kept ready for tape-out | chosen, 20 November |
| 11 | Flat placement with guided regions now; finished blocks for the final chip | chosen, 20 November |
| 12 | Denser memory | 3.3 V memory: still go after the third pass (two conditions held in simulation, power-down open); second silicon, not the first |

## 1. RISC-V processor, not an AVR clone

**Chosen:** Hazard3, an open RV32IMC core with a debug module.
**Instead of:** re-implementing the AVR instruction set.
**Why:** an open, verified core with a living toolchain. **Cost:** firmware has to be recompiled; AVR
binaries and assembly do not carry over. Register names follow the ATmega where the function matches.

## 2. GF180MCU at 5 V through wafer.space

**Chosen:** GlobalFoundries GF180MCU, 5 V transistors and pads, wafer.space shuttle.
**Instead of:** Tiny Tapeout on the 1.8 V SKY130 process.
**Why:** a drop-in for a 5 V part has to run at 5 V, and the shuttle is affordable.
**Cost:** no flash memory in the open kit (decision 3), five wiring layers, and a sparse memory block
(decision 12).

## 3. Program in a serial memory die, run through a cache

**Chosen:** a 25-series serial memory die bonded inside the same package; the chip fetches code from it
into a cache.
**Instead of:** on-chip flash (not available) or an external memory on extra pins (breaks the pinout).
**Why:** keeps 32 pins and the user-programmable program. **Cost:** code not in the cache has to be
loaded first, about 29 microseconds per 32 bytes at 20 MHz. Everything in decisions 6 to 8 follows from
this.

## 4. Same pin positions as the ATmega328PB

**Chosen:** the TQFP/QFN-32 pinout, pin for pin.
**Cost:** twelve pins are both digital and analog and get two die pads each; fifteen pads (memory,
test, spares) stay inside the package.

## 5. Digital first, analog as one macro

**Chosen:** lay out the digital chip with a stub in place of the analog blocks; design, draw and check
the analog blocks separately and assemble them into one macro.
**Why:** the two need different tools and checks, and the digital part could be proven early.
**Cost:** the macro's place on the chip was left open, which is what the half-height trial ran into.

## 6. Speed parity is a requirement

**Chosen:** the chip has to keep up with an ATmega328P on real firmware, not only match its features.
**Why:** "This should feel like a drop-in replacement." **Consequence:** measured rather than assumed
([cache study](cache_study.md)); the 2 KB cache failed the measurement.

## 7. Cache: 12 KB, three-way, handlers pinned

**Chosen:** three ways of 4 KB, the line unused longest is replaced, lines from the first 2 KB of the
program are never replaced.
**Instead of:** a larger simple cache (twice as slow as ideal even at 16 KB, and lost serial bytes), or
16 KB two-way (6 % from ideal instead of 15 %, but 38 memory blocks instead of 31, too many beside the
analog macro).
**Cost:** 27 memory blocks for the cache. Firmware should link its interrupt handlers into the first
2 KB.

## 8. Single-cycle multiplier

**Chosen:** the processor's fast multiplier for both halves of the product.
**Why:** float-heavy code was 1.6 times slower than on the ATmega without it, level with it.
**Cost:** it is the tightest path in the layout, 0.64 ns of margin at the slowest corner.
**Fallback:** fast multiplier for the low half only; the float benchmark drops to 0.81 of the ATmega.

## 9. Full-height slot for the product

**Chosen:** wafer.space's full-height slot, 12.9 mm2 of core.
**Instead of:** the half-height slot (5.0 mm2), where the analog macro fits only with every margin gone
and the larger cache does not fit at all.
**Cost:** about twice the slot price.

## 10. Half-height digital-only layout kept ready

**Chosen:** the third layout (signed off, 2 KB cache, no analog) stays ready for a tape-out as a
possible first test chip while the full chip is developed.
**Why:** it would prove the processor, peripherals and pads in silicon for the lower slot price.
**Known limits:** its cache is too small for ordinary firmware; external clock and reset only.
**Open:** whether to actually send it.

## 11. Flat placement with guided regions now, finished blocks later

**Chosen:** the next full-height floorplan keeps the tool's flat placement, with the logic next to the
pads and regions that say where each part goes. Separately finished and tiled blocks (cache, processor,
peripherals, analog) are the aim for the final chip.
**Why not blocks now:** the tightest paths cross the boundary between processor and cache, and freezing
that boundary early stops the tool from optimising across it; each block also needs its own pin plan,
timing budget and hand-off files.
**Why blocks in the end:** each is closed once and reused, the top level becomes simple, and the chip
reads as designed.
**Evidence since (run `full7`, 20 November):** giving the logic more room at the edges without saying
what goes where made things worse: logic spread along the west edge and the slowest corner missed timing
by 1.73 ns; and 93 of the reference layout's 94 slow edges are logic left in the channels between memory
rows. The regions therefore have three jobs: channels for memory-interface cells only, the debug port
near its pads, edge strips kept for pad cells (`docs/layout_results.md`).
**Evidence since (runs `full8` and `full9`, 21 November):** keeping lanes free by soft obstructions
packed the logic tighter and pushed part of the processor under the analog block (-3.09 ns); pad buffers
in the reference's 60 um strips left 805 endpoints up to 8.9 ns short after global routing (the run was
stopped during repair, at +2.3 ns).
Guiding the placer by taking room away does not work in this flow; the regions need to say where logic
*goes*, not where it may not.
What did help (runs `full10`, `full11`): leaving the floorplan alone and having the repair steps put a
repeater on every wire longer than 600 um: setup met, overloads down 59 %. Regions remain the aim for
the final chip; for now the flat floorplan with tuned repair is the working layout.

## 12. Denser memory

**Question:** the foundry memory block stores 4 kilobits in 0.21 mm2. If memory were several times
denser, the whole 32 KB program could sit on the chip and cache misses would disappear.
**Found** ([memory research](memory_research.md), 20 November):

* The foundry block is sparse because of what surrounds the storage cells: the cells are 26 % of it.
* A denser memory is already in the installed design kit and unused: a 3.3 V block of 1024 x 8 bits,
  19.0 um2 per bit against 51.1, which is 2.7 times denser. The whole 32 KB program and the 2 KB RAM
  would be 34 blocks and 5.3 mm2, less than the 6.5 mm2 the 31 blocks take today.
* The catch: it needs a 3.3 V supply on a 5 V chip (a regulator, level shifters, a second supply net),
  and it has no timing data that can be trusted.
* About 70 % of the benchmark firmware is library code. Held in a read-only block made of ordinary logic
  cells it would be very small (0.3 mm2 by synthesis alone), and the cache would only have to hold the
  application. The library would be frozen at tape-out.
* Memories from flip-flops or latches are two to three times worse than the foundry block. The
  half-height slot stays out of reach on memory density alone.

**Recommended by the report, not decided:** keep the foundry block for first silicon; try the read-only
library as an experiment; plan the 3.3 V memory for a second silicon.

**Second pass on the 3.3 V block** (20 November, by simulation of its transistor netlist):

* It cannot run at 5 V: it is built only from the process's 3.3 V transistors, rated for 3.3 V plus
  10 %. It needs its own 3.3 V supply inside the chip.
* It works in simulation: writes and reads of both values at near and far addresses, at slow, typical
  and fast corners.
* It is fast: output 3.2 ns after the clock at the slow corner without wiring, an estimated 5 to 6 ns
  with wiring. The foundry block's data sheet figure is 10.3 ns.
* Signals from the memory back to the 5 V logic need a real level shifter (a plain 5 V gate driven
  from 3.0 V draws 68 to 180 uA standing current). The pad library contains such a circuit to copy;
  it adds 1 to 2 ns.
* The supply is the hard part. No regulator exists in the kit or in open designs with silicon. It must
  work without an external capacitor (the pinout has no spare pin), which takes 3.5 to 7 nF on the chip:
  0.9 to 1.75 mm2 of capacitor, against 1.27 mm2 of core that the denser memory frees.
* Power-down: either the memory stays powered (leakage up to 0.67 mA when hot, nowhere near an ATmega's
  power-down current) or it is switched off and the program is copied again on wake-up, about 30 ms.

**Verdict of the report:** go, if (1) the block stays under about 8 ns with wiring at the slow corner,
(2) a regulator without external capacitor can be designed and fitted, (3) the cost in power-down is
accepted. Not for the first tape-out. **Not decided.**

**Third pass on the 3.3 V block** (21 November, [memory research](memory_research.md), "Third pass"):

* With its own wiring (capacitance from its layout) the block answers in **5.57 ns** at the slow corner,
  3.48 ns typical, and works at 1.8 V (11.2 ns). Condition 1 held in simulation. A first extraction that
  failed every read was a fault of the extraction step, found and documented.
* The regulator: at most 8 blocks fire on one clock edge in this design, 0.55 to 0.68 nC. The 32 program
  blocks bring 2.7 nF of their own; with **2 nF more** (about 1 mm2 of MIM, or 0.5 to 0.65 mm2 of MOS
  capacitor) a first-order regulator keeps the rail at 3.04 V or more. Less than half the 3.5 to 7 nF
  feared. Condition 2 held at first order; the real circuit, a bypass switch for low VCC and start-up
  are still to design.
* The level shifter from the pad library: 1.1 to 1.3 ns at the slow corner, no standing current, about
  50 um2 each. With it the block delivers a 5 V signal about 6.9 ns after the clock, against 10.3 ns for
  today's 5 V block.
* Power-down (condition 3) is a decision, not a measurement: keep the island on (about 15 uA plus
  leakage, up to 0.67 mA hot) or reload the program on wake-up (about 30 ms).

**Verdict now:** still go, for a second silicon. **Not decided.**

**Power-down, recommended** (21 November): the ATmega keeps its program in flash (0.2 uA in power-down,
wakes in microseconds to a millisecond); this memory is RAM, so the serial memory stays the permanent
copy. Neither keeping the whole memory powered nor copying it back on every wake behaves like a drop-in.
Recommended: switch the memory off in power-down, keep only the first 2 KB (interrupt and wake-up code)
powered, and refill the rest one 32-byte line at a time on first use (a "loaded" flag per line; the whole
program fits, so nothing is evicted). Expected sleep current a few uA (estimate). Agreed with Jon as the
direction; not yet designed.

## Still open

* Switch the RTL defaults from the first layout's configuration to the full-height one.
* Send the half-height layout as a test chip, or not.
* Which serial memory die, and how it is bonded.
