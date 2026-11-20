| Check | Result | Pass |
|---|---|---|
| Reset held while the supply settles (por_n at 100 us) | 0.00 V | yes |
| Reset released | 242 us after power-on | yes |
| 128 kHz oscillator | 129.6 kHz | yes |
| Brown-out detector at the 4.3 V level, supply 5 V | bod_o = 0 | yes |
| Comparator, 1.1 V reference against AIN1 = 0.9 V then 1.3 V | ac_out = 1 then 0 | yes |
| AREF pin with AVCC selected | 5.000 V | yes |
| ADC conversion of 3.3325 V on ADC2 (expected code 682) | decisions 1010101010 | yes |
| RC oscillator silent until enabled | peak 0.01 V | yes |
| RC oscillator after rc_en | running, 16 periods in 1.92 us | yes |
| Supply current: reset, 128 kHz, reference, brown-out, ADC and comparator on | 159 uA | yes |
