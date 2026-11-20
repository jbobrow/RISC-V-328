| Block | Measured from | Supply current (uA) |
|---|---|---|
| Reference, disabled | 320u to 400u | 0.00 |
| Comparator, disabled, inputs at 2.5 V | 3.4m to 4m | 0.00 |
| Brown-out detector, disabled | 3.4m to 4m | 0.00 |
| RC oscillator, disabled | 320u to 400u | 0.00 |
| Crystal oscillator, disabled | 320u to 400u | 0.00 |
| Reference buffer, disabled | 320u to 400u | 0.00 |
| Temperature sensor, disabled | 320u to 400u | 0.00 |
| ADC front end, disabled | 3.4m to 4m | 0.01 |
| Power-on reset, first 0.4 ms | 320u to 400u | 29.69 |
| Power-on reset, settled (always on) | 3.4m to 4m | 1.09 |
| 128 kHz oscillator (always on) | 3.4m to 4m | 4.69 |

Sum of the two always-on blocks: 5.8 uA.

Every block's netlist is the one extracted from its layout. The whole-block run with every enable low was not made from the layouts: 4 ms of the complete extracted macro would take some three hours.
