# RV328 analog macro specification

The digital core talks to one analog block, `rv328_analog`, through the ports below. Two views exist today:
`rtl/analog/rv328_analog_model.v` (behavioural, used in simulation - treat it as the executable version of
this specification) and `rtl/analog/rv328_analog_stub.v` (synthesisable placeholder for the digital-first
tapeout).

**Status.** A transistor-level design of every block now exists in `analog/`, simulated against the
foundry models over corners, supply and temperature, and assembled into one netlist with these ports
(`analog/blocks/rv328_analog.spice`). `analog/README.md` has the results against the targets below and
the list of deviations. Every block has a layout, and the blocks are assembled into one macro layout with these ports (`analog/layout/`: 1380 x 927 um, DRC and LVS clean, simulated from its extraction). It has no supply or guard rings, its pins are where its wires end (44 at the foot of a trunk on one edge, the ten analog inputs on the same edge, the crystal pins on the opposite one), and there is
no LEF or liberty file, so the chip layout still uses the stub. At 1.28 mm2 there is barely room for it beside the digital layout in the half-height slot: a trial layout with its room reserved (cells at 74 % of the rows left, against 46 % today) routes, but has no room for the flow's repair steps, and one register's fan-out misses 20 MHz at the slow corner (`docs/layout_results.md`, "Trial with the analog block"). The targets it does not meet as designed: the 1.8 V brown-out
level (2.3 V instead), the accuracy of the 128 kHz oscillator without trim, and a rail-to-rail comparator
input. The ADC front end and the power-down current, which were wrong after the first design round,
were corrected in the second. A third round followed the first layouts: the ADC comparator, which
took most of a bit time to reverse a decision, was made ten times faster, and every large resistor was
moved to the 1 kohm-per-square film, the only high-resistance film this process variant has. The ADC's
code transitions are within half an LSB in simulation.

Supply: AVCC pad (analog), VSS. All digital ports are 5 V-domain CMOS levels (the core runs from the pad supply).

## Ports

| Port | Dir | Function | Target |
|---|---|---|---|
| XTAL1, XTAL2 | analog | crystal pins (asig_5p0 pads, double-bonded with PB6/PB7) | |
| AREF, AVCC | analog | reference input / analog supply | |
| ADC[7:0] | analog | ADC inputs (double-bonded with PC0-PC5, PE2, PE3) | |
| AIN0, AIN1 | analog | comparator inputs (double-bonded with PD6, PD7) | |
| por_n | out | power-on reset, low until VCC is valid and stable | threshold about 1.4 V rising, at least 1 ms after the RC oscillator runs, glitch-free (the designed circuit releases after 0.2 to 0.3 ms; the rest of the delay belongs in the reset controller) |
| bod_o | out | supply below the selected level (level, asynchronous) | levels 1.8 / 2.7 / 4.3 V, 2 % hysteresis |
| bod_en, bod_level[2:0] | in | brown-out enable and level | below 25 uA when enabled |
| clk_rc | out | 8 MHz RC oscillator, gated cleanly by rc_en (no runt pulses) | +/-2 % after trim at 25 C, +/-10 % over range; start-up below 10 us |
| rc_en, rc_trim[7:0] | in | enable and frequency trim (0x80 = centre, monotonic) | about 0.5 % per step |
| clk_lf | out | 128 kHz oscillator, always running | +/-10 %, below 2 uA |
| clk_xa | out | crystal oscillator output, released only when amplitude is stable | |
| xo_en, xo_mode[1:0] | in | enable; 1 low-power crystal (0.4-16 MHz), 2 full-swing (to 20 MHz), 3 32.768 kHz | |
| adc_en | in | power up ADC front end and reference | |
| adc_mux[3:0] | in | 0-7 pins, 8 temperature sensor, 14 bandgap 1.1 V, 15 ground | |
| adc_refs[1:0] | in | 0 AREF, 1 AVCC, 3 internal 1.1 V (driven onto AREF for decoupling) | |
| adc_sample | in | high: track selected input; falling edge: hold | two ADC clock periods of tracking (ADC clock 50-200 kHz); the internal channels (8, 14) need 40 us. As designed, the input is actually sampled 0.9 to 2.0 us after the falling edge, and the first trial code must already be on adc_dac then; the first decision is taken one ADC clock period after the edge |
| adc_dac[9:0] | in | SAR trial code | DAC settles within one ADC clock period |
| adc_cmp | out | 1 when held input >= adc_dac / 1024 x reference | 10-bit monotonic, +/-2 LSB absolute accuracy |
| ac_en, ac_bg, ac_mux_en | in | comparator enable; positive input = bandgap instead of AIN0; negative input = ADC mux instead of AIN1 | |
| ac_out | out | 1 when positive input > negative input (asynchronous) | offset below 10 mV, delay below 500 ns |
| dig_clk_i, dig_rstn_i | in | used only by the stub (external clock and reset) | leave unconnected in the real macro |

## Integration notes

* Every output of the macro crosses into the digital core through a synchroniser except the clocks and `por_n`.
* `clk_rc`, `clk_xa` and `clk_lf` feed a glitch-free clock multiplexer; each must stop and start without
  partial pulses when its enable changes.
* In power-down the core drives `rc_en` and `xo_en` low and raises them again asynchronously on a wake event.
* The pads carrying analog signals are plain `gf180mcu_fd_io__asig_5p0` cells; the digital function of the
  same package pin uses a separate `bi_24t` pad and a second bond wire, so no custom pad cell is needed.
* For layout, the macro needs a LEF with the ports above, a liberty file for the digital ports (clock
  outputs declared as clocks) and GDS; add it to `flow/librelane/macros.yaml`, remove the stub from
  `config.yaml` and replace the stub clocks in `chip_top.sdc`.
