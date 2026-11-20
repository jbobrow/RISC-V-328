# RV328 verification report

All results below are RTL simulation (Icarus Verilog 13). Static timing and physical checks from the
layout runs are in docs/layout_results.md, together with a gate-level simulation of the routed netlist
(three tests, cell delays, 20 MHz).

## Method

The testbench (`tb/tb.v`) instantiates the complete chip - `chip_top` with the foundry I/O pad models, the
digital core and the behavioural analog model - plus a model of the in-package serial memory. Each test is a
C program (`sw/tests/`) compiled with clang for RV32IMC, loaded into the memory model and executed by the
CPU from reset. The firmware checks results itself and reports a verdict through a register the testbench
watches. External loop-back wiring between pins is selected per test.

| Test | What it exercises |
|---|---|
| basic | boot from the serial memory, .data/.bss start-up, SRAM byte/half/word access, multiply/divide, GPIO output/input/toggle/pull-up through the pads, pin-change and external interrupts, reset flags |
| timers | CTC with compare interrupt, 10-bit fast PWM duty measured by input capture, phase-correct PWM duty, external clock input, compare-toggle output, 8-bit overflow |
| uart | USART0 to USART1 and back: 8N1, 7E2 with U2X, 9O1, receive interrupt, parity-error and overrun flags |
| spi | SPI0 master with SPI1 slave in all four clock modes and both bit orders, two bytes per frame, slave interrupt, write collision |
| twi | TWI0 master with TWI1 interrupt-driven slave: NACK on unknown address, multi-byte write, repeated start, multi-byte read with final NACK, slave status sequence |
| analog | ADC codes for several inputs and references, left adjust, internal channels, free-running and timer-triggered conversions with interrupt; comparator output, edge interrupt, bandgap input, ACO pin |
| nvm | reads through the cache, EEPROM-area byte writes and rewrite, word programming with done interrupt, key protection, cache flush, serial-clock divider |
| power | idle sleep with timer wake-up, power-down with watchdog wake-up (system clock verified stopped), standby with pin-change wake-up, software reset, watchdog reset, RESET pin, reset-cause register after each |
| clock | RC, prescaler, external clock, crystal oscillator, RC trim and 128 kHz system clock, each measured against the watchdog oscillator; refusal to select a stopped source; PRR |
| isp | testbench reads and programs the memory through PB2-PB5 while RESET is low, reads the JTAG IDCODE, then the firmware checks the programmed word |

Three further configurations re-run a subset: the SRAMs replaced by the foundry macro model, and the
digital-first build (analog stub, external clock, reset from an undefined power-up state).

## Results

Re-run after the RTL changes made during layout (clock-mux restructuring, clock root buffer, renamed
flash nets, CPU clock gate moved beside the system clock gate). Simulation times are identical to
the earlier runs, cycle for cycle.

```
== RTL tests (behavioural RAM, PDK pad models, analog model)
[analog] PASS t=6387689000
[basic] PASS t=5242064000
[clock] PASS t=231394957000
[isp] PASS t=1752314000
[nvm] PASS t=12300564000
[power] PASS t=41070094000
[spi] PASS t=4101689000
[timers] PASS t=5049439000
[twi] PASS t=7457064000
[uart] PASS t=10569939000
== Subset against the foundry SRAM macro model
[basic, foundry SRAM] PASS t=5242064000
[nvm, foundry SRAM] PASS t=12300564000
[timers, foundry SRAM] PASS t=5049439000
== Digital-first build (analog stub, external 8 MHz clock, reset pulse on PC6)
[basic, digital-first] PASS t=5242039000
[timers, digital-first] PASS t=5049414000
[spi, digital-first] PASS t=4101664000
== Chip elaboration (pads + core + analog stub)
errors: 0
```

### Gate-level simulation of the routed netlist

The netlist from the third layout, with the cell delays extracted from that layout (typical corner),
a 20 MHz clock, the foundry SRAM and pad models and a reset pulse on PC6 (`make gl-sdf`, `make gl-basic`).
The first column is the RTL of the same build at the same clock.

```
[basic,  RTL digital-first, 20 MHz] PASS t=2109426000    [basic,  routed netlist] PASS t=2109431000
[timers, RTL digital-first, 20 MHz] PASS t=2032376000    [timers, routed netlist] PASS t=2032381000
[spi,    RTL digital-first, 20 MHz] PASS t=1653276000    [spi,    routed netlist] PASS t=1653281000
```

Each test ends in the same clock cycle as the RTL. Wire delays and setup/hold checks are not part of
this simulation; `scripts/gl_prep.py` lists what it covers and why.

## Bugs found by these tests and fixed

* SPI master changed MOSI half a clock early after the last bit, corrupting the slave's bit 0.
* TWI slave counted the SCL falling edge that follows START as a data bit.
* USART 9-bit frames with parity overflowed the receive shift register.
* Reset-cause flags could be read back before a clear had taken effect.
* Disabling the RC oscillator while the clock multiplexer still used it stopped the chip for good.
* Clearing the watchdog interrupt flag restarted the watchdog period.
* Digital-first build: the chip could drive its own reset pin from an undefined power-up state.

## Cache configurations and benchmark programs

The program cache is configurable (`rtl/rv328_xip.v`: size of a way, one to three ways, pinned first
2 KB) and the processor has an optional single-cycle multiplier. The ten tests above pass in the
first layout's configuration (2 KB direct-mapped, the default) and in the full-height layout's
(`make test SIMDEFS="-DRV328_CACHE_KB=4 -DRV328_CACHE_WAYS=3 -DRV328_CACHE_PIN=2 -DRV328_MUL_FAST=1"`).

Five benchmark programs and CoreMark run on a second bench, `tb/bench_top.v`, which wraps the digital
core for Verilator so that millions of clocks take seconds (docs/cache_study.md). It replaces the pads,
the analog macro and the serial memory by simple digital stand-ins. Cross-checks:

* the blink benchmark takes the same 300,827 clocks between its marks on this bench and on the
  chip-level testbench, in the full-height configuration, with the same result value;
* the line loads counted in the RTL equal those of an independent model of the cache run on the recorded
  fetch trace (159 for the logger and 760 for the full firmware on the 12 KB three-way pinned cache);
* each benchmark built without peripherals ends with the same result values on the RV328 and on an
  ATmega328P in simavr.

## What these results do not show

* Timing: see docs/layout_results.md. The third layout meets 20 MHz in static timing, and the routed
  netlist passes basic, timers and spi at 20 MHz with typical cell delays. The full-height layout's
  routed netlist passes basic the same way. Wire delays, the other
  corners and the other seven tests have not been simulated at gate level.
* The analog model is ideal; the tests prove the digital sequencing, not analog performance.
  The transistor-level analog circuits are simulated separately in ngspice (`analog/README.md`); they
  have not been simulated together with the digital core, and the behavioural model has not been
  updated to match their deviations (brown-out level, the ADC's sampling instant).
* Coverage was not measured. Known untested areas are listed in docs/tapeout_checklist.md.
* The CPU is exercised only by the test programs; Hazard3's own verification is relied on for ISA compliance.
* Debug beyond the JTAG IDCODE read is untested.
