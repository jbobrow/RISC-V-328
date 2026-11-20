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
| 12 | Denser memory | first report in; nothing decided |

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

## Still open

* Switch the RTL defaults from the first layout's configuration to the full-height one.
* Send the half-height layout as a test chip, or not.
* Which serial memory die, and how it is bonded.
