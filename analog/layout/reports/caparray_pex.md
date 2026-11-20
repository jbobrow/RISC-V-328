# ADC capacitor array: wiring capacitance extracted from the layout

Extracted with magic from a metal-only copy of `rv328_adc_caparray.gds` (see `analog/layout/pex.py` for why),
nominal wiring corner. One unit is 54.52 fF in the foundry model.

| Capacitor | Units | Design value (fF) | Top plate to its bottom plate, wiring (fF) | per unit (fF) | Bottom plate to ground (fF) | to other bottom plates (fF) |
|---|---|---|---|---|---|---|
| b9 | 512 | 27914.2 | 337.24 | 0.659 | 1510 | 333 |
| b8 | 256 | 13957.1 | 168.15 | 0.657 | 740 | 211 |
| b7 | 128 | 6978.6 | 84.08 | 0.657 | 374 | 127 |
| b6 | 64 | 3489.3 | 42.04 | 0.657 | 191 | 84 |
| b5 | 32 | 1744.6 | 20.27 | 0.634 | 103 | 206 |
| b4 | 16 | 872.3 | 10.17 | 0.635 | 27 | 220 |
| b3 | 8 | 436.2 | 5.29 | 0.661 | 22 | 199 |
| b2 | 4 | 218.1 | 2.85 | 0.712 | 20 | 189 |
| b1 | 2 | 109.0 | 1.57 | 0.784 | 19 | 183 |
| b0 | 1 | 54.5 | 0.95 | 0.947 | 25 | 84 |
| bx | 1 | 54.5 | 0.95 | 0.947 | 36 | 64 |

Other wiring on the two comparator inputs (nominal): top plate to ground 0.64 pF on top of the 27.9 pF of the 512 units
(the top plate then moves by 0.656 of an array step instead of 0.667); reference side to ground 0.34 pF on top of 20.9 pF;
top plate to reference side 23.9 fF; reference side to all bottom plates 15.7 fF.

## Effect on linearity

Bit weights are the design capacitance plus the wiring between the top plate and that bit's bottom plates.
Only the part of the wiring that is not in proportion to the number of units moves a transition.

| Wiring corner | Largest INL (LSB) | Largest DNL (LSB) | at code | Gain error (LSB at full scale) |
|---|---|---|---|---|
| low | -0.0265 | +0.0226 | 512 | -0.005 |
| nominal | -0.0279 | +0.0221 | 512 | -0.005 |
| high | -0.0299 | -0.0244 | 800 | -0.006 |
