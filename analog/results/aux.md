Temperature sensor output (mV)

| Corner | AVDD (V) | -40 C | 25 C | 85 C | 125 C | Slope (mV/K) |
|---|---|---|---|---|---|---|
| tt | 2.7 | 249.7 | 319.2 | 383.3 | 426.0 | 1.068 |
| tt | 5.0 | 249.3 | 318.6 | 382.5 | 425.1 | 1.066 |
| ss | 2.7 | 249.5 | 318.9 | 382.9 | 425.6 | 1.067 |
| ss | 5.0 | 249.1 | 318.4 | 382.2 | 424.8 | 1.065 |
| ff | 2.7 | 250.0 | 319.5 | 383.6 | 426.4 | 1.070 |
| ff | 5.0 | 249.5 | 318.9 | 382.9 | 425.6 | 1.067 |

Reference buffer, static

| Corner | Temp (C) | AVDD (V) | Output - reference (mV) | Change with 20 uA drawn (mV) | Change with 20 uA fed in (mV) | Reference + buffer (uA) |
|---|---|---|---|---|---|---|
| tt | 25 | 5.0 | -0.38 | -39.67 | +39.66 | 113 |
| tt | 25 | 2.7 | -0.43 | -40.07 | +40.19 | 112 |
| ss | 125 | 2.7 | -0.13 | -45.85 | +46.80 | 125 |
| ff | -40 | 5.5 | -0.64 | -34.83 | +34.80 | 117 |

Reference buffer, switching on and a 20 uA load step

| Capacitor on AREF | Corner | Temp (C) | AVDD (V) | Within 1 % after (ms) | Settles at (V) | Change with the load (mV) | Undershoot beyond that (mV) |
|---|---|---|---|---|---|---|---|
| 100 nF | tt | 25 | 5.0 | 1.565 | 1.1015 | -39.7 | +0.0 |
| 100 nF | ss | 125 | 2.7 | 1.504 | 1.1042 | -45.8 | +0.0 |
| none | tt | 25 | 5.0 | 0.001 | 1.1015 | -39.7 | -5.7 |
| none | ff | -40 | 5.5 | 0.000 | 1.0993 | -34.8 | -5.6 |
| none | ss | 125 | 2.7 | 0.001 | 1.1042 | -45.8 | -4.1 |
| 1 nF | tt | 25 | 5.0 | 0.016 | 1.1015 | -39.7 | +0.0 |

Input multiplexer, resistance of a selected channel (ohm)

| Corner | Temp (C) | AVDD (V) | Input near ground | Input at half supply | Input near the supply |
|---|---|---|---|---|---|
| tt | 25 | 5.0 | 109 | 194 | 177 |
| ss | 125 | 4.5 | 191 | 442 | 307 |
| tt | 25 | 2.7 | 178 | 1215 | 307 |
| ss | -40 | 2.7 | 169 | 5323 | 303 |
| ss | 125 | 2.7 | 300 | 2630 | 524 |
