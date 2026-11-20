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
| Power-on reset, first 0.4 ms | 320u to 400u | 29.24 |
| Power-on reset, settled (always on) | 3.4m to 4m | 1.09 |
| 128 kHz oscillator (always on) | 3.4m to 4m | 3.24 |

Sum of the two always-on blocks: 4.3 uA.

Whole block, every enable low, analog pins at half supply: 33 uA at 0.3 to 0.4 ms, 4.5 uA at 3.4 to 4 ms.
