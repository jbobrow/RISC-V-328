# Analog layout: checks

Foundry DRC is the KLayout deck, all 162 rule decks except antenna, density and copper pillar.
LVS is magic extraction compared by netgen with the netlist that was simulated. For the macro that is the top
netlist with every block as a cell: the blocks are compared cell by cell, then the wiring between them.

| Cell | Contents | Size | Foundry DRC violations | magic DRC violations | LVS |
|---|---|---|---|---|---|
| `rv328_adc_caparray` | all 1920 MIM units of the ADC front end | 371 x 349 um | 0 | 0 | Circuits match uniquely. |
| `devtest` | one of each generated device: six transistors, five resistors, a capacitor and a bank of twenty | 281 x 50 um | 0 | 0 | Circuits match uniquely. |
| `rv328_bgr` | the reference: 21 transistors, 10 bipolars, 5 resistors (140 strips), 2 capacitors | 303 x 166 um | 0 | 0 outside the foundry bipolar cells (105 inside them, as in that cell alone) | Circuits match uniquely. |
| `rv328_adccmp` | the ADC comparator: 35 transistors, 2 resistors, 6 capacitors | 327 x 83 um | 0 | 0 | Circuits match uniquely. |
| `rv328_adcfe` | the whole ADC front end: the capacitor array, the comparator, and 73 more transistors, 88 standard cells, 3 resistors and 10 capacitors in five blocks | 427 x 747 um | 0 | 0 | Circuits match uniquely. |
| `rv328_por` | the power-on reset: 14 transistors, 5 resistors in 212 strips, 2 capacitors | 529 x 183 um | 0 | 0 | Circuits match uniquely. |
| `rv328_lfosc` | the 128 kHz oscillator: 39 transistors, 5 resistors in 293 strips, 1 capacitor | 574 x 226 um | 0 | 0 | Circuits match uniquely. |
| `rv328_rcosc` | the 8 MHz oscillator: 123 transistors, 5 resistors in 106 strips, 328 capacitor units (six banks and seven single ones) | 229 x 335 um | 0 | 0 | Circuits match uniquely. |
| `rv328_xosc` | the crystal oscillator: 80 transistors, 3 resistors in 138 strips | 254 x 355 um | 0 | 0 | Circuits match uniquely. |
| `rv328_refbuf` | the reference buffer: 13 transistors, 2 capacitors of 5 pF | 328 x 93 um | 0 | 0 | Circuits match uniquely. |
| `rv328_bod` | the brown-out detector with its comparator: 57 transistors, 5 resistors in 90 strips, 2 capacitors | 278 x 184 um | 0 | 0 | Circuits match uniquely. |
| `rv328_cmp` | the analog comparator: 17 transistors | 104 x 48 um | 0 | 0 | Circuits match uniquely. |
| `rv328_amux` | the input multiplexer: 21 transistors and 42 standard cells | 218 x 67 um | 0 | 0 | Circuits match uniquely. |
| `rv328_tsens` | the temperature sensor: 4 transistors, 1 resistor in 6 strips | 26 x 42 um | 0 | 0 | Circuits match uniquely. |
| `rv328_acsw` | the switches at the comparator's inputs: 8 transistors and 2 standard cells | 64 x 40 um | 0 | 0 | Circuits match uniquely. |
| `rv328_glue` | the macro's enable and gating logic: 22 standard cells | 87 x 41 um | 0 | 0 | Circuits match uniquely. |
| `rv328_analog` | the assembled macro: the eleven blocks and the two cells above, 83 tracks in three channels, a trunk of 57 lines | 1380 x 927 um | 0 | 0 outside the foundry bipolar cells (155 inside them, as in that cell alone) | Circuits match uniquely. |

