# RV328 — a RISC-V microcontroller in the ATmega328PB footprint

Preliminary design data. Nothing here has been measured on silicon; speed and size figures come from the
third place-and-route run of the digital-first build and, where it says so, from the first full-height
layout (docs/layout_results.md); speed against an ATmega328P is measured in simulation (docs/cache_study.md).

## 1. Summary

| | RV328 |
|---|---|
| CPU | Hazard3 RV32IMC (3-stage, machine mode), 21 vectored interrupt lines. Measured in simulation: 1.74 CoreMark/MHz with the serial multiplier, 2.37 with the single-cycle multiplier of the full-height layout |
| Program memory | 32 KB reserved in a serial memory die inside the package, executed in place through a cache (2 KB in the first layout, 12 KB three-way in the full-height layout; section 6) |
| Data EEPROM | 1 KB area of the same die, byte-writable |
| SRAM | 2 KB |
| I/O | 27 lines on ports B, C, D, E; pin-change interrupt on every pin; INT0, INT1 |
| Timers | TC0, TC2 (8-bit), TC1, TC3, TC4 (16-bit); 10 PWM outputs; 3 input captures |
| Serial | 2 USART, 2 SPI (master/slave), 2 TWI/I2C (master/slave) |
| Analog | 10-bit SAR ADC controller (8 pins + internal channels), analog comparator control |
| System | watchdog on its own clock domain, 3 clock sources + prescaler, 6 sleep modes, reset-cause register |
| Package | 32 pins, pin-compatible with ATmega328PB TQFP/QFN-32 |
| Process | GlobalFoundries GF180MCU (5 V devices). Third layout: wafer.space half-height slot, 3.93 x 2.53 mm die. The chip is moving to the full-height slot, 3.93 x 5.12 mm |
| Size | third layout: 60,200 standard cells (1.5 mm2 with buffers and taps, without fill; 9-track library) plus eight 512x8 SRAM macros (1.7 mm2) in a 5.0 mm2 core. Full-height layout: 1.9 mm2 of cells (first full-height layout), 31 SRAM macros (6.5 mm2) and the analog macro in a 12.9 mm2 core |
| Clock | third layout meets 20 MHz at all corners in static timing (5.9 ns margin at 125 C, 4.5 V; about 28 MHz on typical silicon). Digital-first build, external clock; three tests pass at 20 MHz in gate-level simulation with typical cell delays. Full-height layout with a blank block for the analog macro (`full11`): 20 MHz met at all nine corners (+0.17 ns at 125 C, 4.5 V); three tests pass at gate level. With the analog macro in place (`tgc2`): 20 MHz met at eight of nine corners, 0.63 ns short at the slowest one (19.75 MHz there). Sign-off checks not run |

## 2. Feature parity with the ATmega328PB

"Digital" = implemented in RTL and exercised in simulation. "Analog macro" = the digital side exists and is
tested against a behavioural model; the transistor-level block is designed and simulated (analog/README.md) and
laid out as one macro (analog/layout/). There is barely room for it beside the digital layout in the half-height slot (a trial routes, but cannot be repaired). In the full-height layout the macro itself is placed, with hand-off files made from its layout and its analog lines wired (docs/build_log.md, stages 16 and 17); it still has no supply or guard rings, and the chip has not been through DRC, LVS or gate-level simulation with it.

| ATmega328PB feature | RV328 | Status |
|---|---|---|
| 32 KB self-programmable flash | 32 KB XIP area in an in-package SPI memory; NVM controller for self-programming | Digital. Different technology: see section 6 |
| 1 KB EEPROM | 1 KB area of the same memory, byte write without erase when a 25-series EEPROM die is used | Digital |
| 2 KB SRAM | 2 KB (four 512x8 macros) | Digital |
| 27 GPIO, pull-ups, PIN-toggle | same, same register semantics | Digital |
| PCINT0-27, INT0/INT1 | same, 4 groups; wake from every sleep mode | Digital |
| TC0, TC2 8-bit with PWM | normal, CTC, fast PWM, phase-correct; 2 compare outputs each | Digital |
| TC2 asynchronous 32 kHz operation | counts 32 kHz ticks while the system clock runs | Partial: does not keep counting in power-save |
| TC1, TC3, TC4 16-bit with PWM, input capture | all 16 AVR waveform modes are expressible; capture with noise canceller | Digital |
| Output compare modulator (PD2) | OC3B and/or OC4B, AND/OR selected by PORTD2 | Digital |
| 2 USART | asynchronous, 5-9 data bits, parity, 1/2 stop bits, U2X | Partial: no synchronous, SPI-master or multi-processor mode, no start-frame wake |
| 2 SPI | master and slave, 4 modes, both bit orders, 7 clock rates | Digital. No automatic master-to-slave switch on SS |
| 2 TWI | master and slave, AVR status codes, address mask, general call | Digital. No arbitration-lost-and-addressed codes, no address-match wake from power-down |
| 10-bit ADC, 8 channels, 1.1 V reference, temperature sensor | SAR controller, auto-trigger sources, 13-cycle conversion | Analog macro. As designed: code transitions within 0.3 LSB in simulation over corners, with offset cancellation; the whole front end is laid out and re-simulated from the layout (46 of 46 conversions correct, transitions within 0.5 LSB, within 0.11 LSB outside the hot fast corner at the 1.1 V reference); capacitor matching not simulated (analog/README.md) |
| Analog comparator, ACO pin, capture trigger | control, interrupt, routing to TC1 capture and ADC trigger | Analog macro. As designed: inputs from 0 V to AVCC - 1.5 V, not rail to rail |
| Peripheral touch controller | - | Not implemented |
| Watchdog with separate oscillator | interrupt, reset, interrupt-then-reset; 16 ms to 8 s | Digital; oscillator is an analog macro |
| Power-on reset, brown-out detector | reset controller and BOD control register | Analog macro. As designed: brown-out levels 2.3 / 2.7 / 4.3 V (no 1.8 V level) |
| 8 MHz RC, 128 kHz RC, crystal and 32 kHz oscillators | glitch-free 3-way clock switch, ready detection, prescaler 1-256, OSCCAL | Analog macro (external clock on XTAL1 works without it). As laid out: the 8 MHz oscillator needs a per-chip trim value and is 6 % slower at 2.7 V than at 5 V; the 128 kHz one is untrimmed (-22 to +34 % over process); the 32 kHz crystal setting draws 2 to 9 uA |
| Clock failure detection | - | Not implemented. A watchdog reset always returns the chip to the RC oscillator |
| Idle, ADC noise reduction, power-down, power-save, standby, extended standby | idle; power-down (oscillators off, asynchronous wake); standby (oscillator on, clock gated) | Digital. ADC-NR behaves as idle, power-save as power-down, extended standby as standby |
| PRR power reduction | PRR holds a peripheral in reset | Partial: no clock gating, registers are lost |
| debugWIRE | RISC-V debug module with JTAG on four test pads | Different: the JTAG pads are not bonded out in the 32-pin package |
| SPI in-system programming | plain SPI access to the memory die while RESET is low | Different protocol (any SPI flash programmer; not avrdude's) |
| Fuses, lock bits | run-time registers (RSTDISBL, clock, BOD) | Not implemented as non-volatile bits |
| Unique serial number | fixed CHIPID only | Not implemented |
| 1.8-5.5 V, 20 MHz | 5 V library and pads; the third layout meets 20 MHz at the slow 4.5 V, 125 C corner in static timing | Partial: 20 MHz at 4.5-5.5 V; operation below 4.5 V is uncharacterised |
| AVR instruction set and register addresses | RISC-V; AVR register names kept where the function matches | Not binary or register-address compatible |

## 3. Pinout

Same positions as the ATmega328PB (pin 1 = PD3). Alternate functions in the order the pin multiplexer applies them.

| Pin | Name | Functions | Pin | Name | Functions |
|---|---|---|---|---|---|
| 1 | PD3 | INT1, OC2B | 17 | PB5 | SCK0 |
| 2 | PD4 | T0 | 18 | AVCC | analog supply |
| 3 | PE0 | ACO, SDA1, ICP4 | 19 | PE2 | ADC6, ICP3, SS1 |
| 4 | VCC | supply | 20 | AREF | ADC reference |
| 5 | GND | ground | 21 | GND | ground |
| 6 | PE1 | SCL1, T4 | 22 | PE3 | ADC7, T3, MOSI1 |
| 7 | PB6 | XTAL1, external clock, TOSC1 | 23 | PC0 | ADC0, MISO1 |
| 8 | PB7 | XTAL2, TOSC2 | 24 | PC1 | ADC1, SCK1 |
| 9 | PD5 | OC0B, T1 | 25 | PC2 | ADC2 |
| 10 | PD6 | OC0A, AIN0 | 26 | PC3 | ADC3 |
| 11 | PD7 | AIN1 | 27 | PC4 | ADC4, SDA0 |
| 12 | PB0 | ICP1, CLKO | 28 | PC5 | ADC5, SCL0 |
| 13 | PB1 | OC1A | 29 | PC6 | RESET |
| 14 | PB2 | SS0, OC1B | 30 | PD0 | RXD0, OC3A |
| 15 | PB3 | MOSI0, TXD1, OC2A | 31 | PD1 | TXD0, OC4A |
| 16 | PB4 | MISO0, RXD1 | 32 | PD2 | INT0, OC3B/OC4B |

The alternate-function table was written from the ATmega328PB documentation as recalled and from the
Microchip migration note for pins 3, 6, 19 and 22; check it line by line against datasheet DS40001906
before committing to layout. XCK0/XCK1 are not implemented.

Die pads differ from package pins: the 12 pins that are both digital and analog have two die pads each,
and 15 pads (serial memory, JTAG, spares) stay inside the package. See docs/bondout.md.

## 4. Memory map and interrupts

| Address | Size | Contents |
|---|---|---|
| 0x0000_0000 | 1 MB window | serial memory, read-only, cached. Reset vector at 0. Program area 32 KB, EEPROM area at 0x1FC00 |
| 0x2000_0000 | 2 KB | SRAM |
| 0x4000_0000 + 0x100 n | 256 B each | peripheral slot n |

Peripheral slots: 0 SYSCTL, 1 GPIO, 2 TC0, 3 TC1, 4 TC2, 5 TC3, 6 TC4, 7 USART0, 8 USART1, 9 SPI0, 10 SPI1,
11 TWI0, 12 TWI1, 13 ADC/AC, 14 WDT, 15 NVM. Registers are 32 bits wide and must be read and written as
words. The register description of each block is the comment header of its RTL file (rtl/periph/*.v,
rtl/rv328_xip.v); sw/include/rv328.h is the C view of the same map.

Interrupt lines (Hazard3 Xh3irq numbers; lowest number first): 0 INT0, 1 INT1, 2-5 PCINT0-3, 6 WDT, 7 TC0,
8 TC1, 9 TC2, 10 TC3, 11 TC4, 12 SPI0, 13 SPI1, 14 USART0, 15 USART1, 16 TWI0, 17 TWI1, 18 ADC, 19 AC,
20 NVM. One line per peripheral: the handler reads the peripheral's flag register to find the source.

## 5. Clock, reset and sleep

* Sources: RC oscillator (reset default), crystal oscillator or external clock on XTAL1, 128 kHz oscillator.
  Switching is glitch-free; a source cannot be selected until it has been seen running, and an
  oscillator cannot be switched off while it is in use. Any reset forces the RC oscillator.
* Prescaler: divide by 1 to 256 (CLKPR), implemented as a clock gate.
* Reset sources: power-on, RESET pin, brown-out, watchdog, software, debugger. MCUSR records the cause.
  The reset is held for 255 clock cycles after the last request.
* Sleep: `wfi` enters the mode selected in SMCR. In power-down the oscillators stop; an enabled pin change,
  a level on INT0/INT1 or the watchdog restarts them asynchronously. A pin pulse shorter than the
  oscillator start-up time wakes the chip but is not recorded as an interrupt.
* Keep peripheral interrupt enables and the CPU's interrupt enables consistent before sleeping: a pending
  peripheral interrupt that is masked in the CPU keeps the clocks running.

## 6. Program memory: what is different from an AVR

GF180MCU's open PDK has no embedded flash, so the program lives in a separate serial memory die
(recommended: a 1 Mbit 25-series SPI EEPROM rated 1.8-5.5 V, for example 25AA1024/25LC1024 class, or an
SPI NOR flash if the supply stays at or below 3.6 V) stacked or placed side by side in the same package and
wired to four internal pads. The package therefore keeps 32 pins.

Consequences for firmware:

* Code runs from a cache of 32-byte lines. A cache miss costs about 580 system clocks with NVMCFG = 0 and
  about 1150 with the reset value NVMCFG = 1 (29 and 58 us at 20 MHz).
* **First layout (half-height slot): 2 KB, direct-mapped.** Loops that fit run at full speed. Measured on
  five test programs (docs/cache_study.md), this is not enough for firmware of ordinary size: a 19 KB
  firmware runs 5.9 times slower than with everything cached, a float-heavy logger 25 times slower than
  on an ATmega328P, and a serial receiver at 115200 baud loses bytes because an interrupt whose handler
  has left the cache takes several misses (up to 3271 clocks measured) to answer.
* **Full-height layout (routed; with the analog macro in place 20 MHz is met at eight of nine corners
  and 0.63 ns short at the slowest; sign-off checks not yet run; see docs/layout_results.md): 12 KB, three-way, least recently used line replaced, the first 2 KB of the
  program pinned, single-cycle multiplier.** Measured on the same programs: within 15 % of
  everything cached; level with an ATmega328P on the float-heavy logger and two to four times faster on
  the others; no serial bytes lost; an interrupt whose handler is linked into the first 2 KB is answered
  in 48 clocks typically and within one line load (597 clocks measured, 30 us at 20 MHz) at worst, against
  a handful of clocks on an AVR. Firmware should link its interrupt handlers into the first 2 KB and set
  NVMCFG = 0 at start-up.
* On either cache, the first use of any code after reset costs one miss per 32 bytes, and code that must
  never wait (bit-timed protocols) should run from SRAM or with its lines already loaded.
* Writes go through the NVM controller (word or byte program, 4 KB sector erase for NOR devices). The CPU
  keeps running from cached code during a write; an uncached fetch waits until the write has finished.
* In-system programming: hold RESET low and talk SPI to the memory on PB2 (CS#), PB3 (MOSI), PB4 (MISO),
  PB5 (SCK).

## 7. Known limitations of this revision

* No scan chains or other production test structures.
* No noise filter on RESET; no start-up delay for crystals beyond the oscillator-ready detection.
* Peripheral registers reject nothing: byte-wide writes to a peripheral register write replicated data.
* In the digital-first build (section 8) there is no power-on reset cell: all state, including pin
  directions, is undefined until RESET has been pulsed low with the clock running. RESET doubles as
  power-on reset and PC6 and PB6 are inputs unconditionally (RSTDISBL has no effect), the watchdog is not
  independent of the system clock, and MCUSR shows PORF after a pin reset.

## 8. Build variants

| Variant | Analog block | What works | Layout status |
|---|---|---|---|
| Digital-first | `rtl/analog/rv328_analog_stub.v` | everything digital; external clock on XTAL1 (up to the timing-closure limit), external reset; no ADC, comparator, BOD, crystal or RC oscillator | placed and routed three times; the third layout meets 20 MHz and is clean in DRC and LVS (docs/layout_results.md) |
| Full | analog hard macro meeting docs/analog_macros.md | complete feature set of section 2 | circuits designed and simulated in four rounds (analog/README.md; deviations: no 1.8 V brown-out level, analog from 2.7 V); all eleven blocks laid out, checked and re-simulated from their layouts, and assembled into one macro layout (1380 x 927 um, 1.28 mm2, its plain logic as foundry standard cells; DRC and LVS clean; whole-block test passes from its extraction). In the half-height slot there is no room for it (a trial with its room reserved routes, but leaves no room for timing and antenna repair). In the full-height layout, with the 12 KB cache and the fast multiplier, the macro is placed with hand-off files made from its layout and its 13 analog lines wired; the best run so far (`tgc2`) is 0.63 ns short of 20 MHz at the slowest corner. Not done: supply and guard rings and pin protection, and DRC, LVS and gate-level simulation of the chip with the macro (docs/layout_results.md, docs/tapeout_checklist.md) |
