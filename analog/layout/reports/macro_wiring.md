# The macro's wiring, net by net

From `rv328_analog_pex.spice` (capacitance) and the generator's own record of what it drew (length).
82.8 mm of wire on 74 nets.

| Net | Group | Wire (um) | Capacitance (fF) | of it to ground | Largest parts to other nets (fF) |
|---|---|---|---|---|---|
| `vbp` | small-signal | 4494 | 449.3 | 252.4 | vref 116.3, adc_en 25.7, aref 19.3 |
| `vref` | small-signal | 3575 | 343.3 | 125.8 | vbp 116.3, aref 60.4, amx 10.1 |
| `aref` | small-signal | 2229 | 217.0 | 105.6 | vref 60.4, vbp 19.3, amx 19.1 |
| `amx` | small-signal | 1439 | 133.4 | 73.1 | aref 19.1, ain1 11.2, vref 10.1 |
| `acm` | small-signal | 217 | 51.2 | 10.4 | acp 11.5, ain0 10.2, vbp 4.5 |
| `acp` | small-signal | 324 | 48.2 | 19.9 | acm 11.5, mux_en 3.7, avdd 2.6 |
| `vtemp` | small-signal | 266 | 29.2 | 6.1 | vref 9.7, adc0 9.2, acp 2.5 |
| `vss` | ground | 5169 | 2269.1 | 0.0 | avdd 522.4, vbp 252.4, vref 125.8 |
| `adc_en` | set once | 2763 | 342.9 | 63.5 | ac_mux_en 115.5, adc_refs0 51.3, adc_mux0 46.3 |
| `ac_mux_en` | set once | 2050 | 297.1 | 21.9 | ac_en 120.0, adc_en 115.5, avdd 12.0 |
| `ac_en` | set once | 2006 | 263.9 | 75.8 | ac_mux_en 120.0, ac_bg 47.8, avdd 7.9 |
| `mux_en` | set once | 2016 | 253.6 | 24.0 | lv1 57.4, ok 49.9, adc_mux3 43.3 |
| `bod_en` | set once | 1921 | 231.1 | 52.0 | bod_level0 59.4, bod_level1 50.4, adc_refs1 49.6 |
| `lv1` | set once | 1676 | 211.3 | 21.1 | mux_en 57.4, bod_level0 49.8, ok 43.6 |
| `ok` | set once | 1791 | 207.9 | 40.5 | mux_en 49.9, lv1 43.6, avdd 39.7 |
| `xo_mode0` | set once | 1515 | 203.8 | 14.7 | xo_mode1 92.0, xo_en 91.8, avdd 1.3 |
| `xo_mode1` | set once | 1515 | 179.5 | 24.1 | xo_mode0 92.0, avdd 58.0, inside glue 1.8 |
| `xo_en` | set once | 1515 | 175.0 | 32.4 | xo_mode0 91.8, rc_trim7 33.1, smp 6.5 |
| `bod_level1` | set once | 1181 | 159.5 | 12.2 | bod_level2 73.9, bod_en 50.4, bod_level0 16.7 |
| `adc_refs1` | set once | 1187 | 153.1 | 14.0 | adc_refs0 75.2, bod_en 49.6, adc_sample 5.7 |
| `adc_refs0` | set once | 1189 | 152.2 | 17.4 | adc_refs1 75.2, adc_en 51.3, adc_mux3 1.8 |
| `bod_level0` | set once | 1104 | 141.4 | 11.1 | bod_en 59.4, lv1 49.8, bod_level1 16.7 |
| `bod_level2` | set once | 1179 | 138.5 | 16.6 | bod_level1 73.9, lv1 26.8, mux_en 8.1 |
| `adc_mux0` | set once | 915 | 125.7 | 8.4 | adc_mux1 56.6, adc_en 46.3, mux_en 10.6 |
| `adc_mux1` | set once | 913 | 125.4 | 8.4 | adc_mux0 56.6, adc_mux2 56.5, avdd 1.3 |
| `adc_mux2` | set once | 911 | 125.2 | 8.4 | adc_mux1 56.5, adc_mux3 56.3, avdd 1.4 |
| `adc_mux3` | set once | 909 | 124.7 | 8.4 | adc_mux2 56.3, mux_en 43.3, avdd 12.4 |
| `ac_bg` | set once | 890 | 120.3 | 48.8 | ac_en 47.8, ac_mux_en 9.8, avdd 5.9 |
| `rc_en` | set once | 946 | 100.9 | 17.0 | rc_trim0 35.7, ok 18.7, clk_rc 17.9 |
| `rc_trim1` | set once | 676 | 85.2 | 6.5 | rc_trim0 38.0, rc_trim2 37.9, avdd 0.5 |
| `rc_trim2` | set once | 675 | 85.0 | 6.5 | rc_trim1 37.9, rc_trim3 37.8, avdd 0.5 |
| `en_avcc` | set once | 623 | 84.9 | 15.9 | en_buf 43.9, vbp 13.7, cmpa 7.3 |
| `rc_trim3` | set once | 673 | 84.8 | 6.5 | rc_trim2 37.8, rc_trim4 37.7, avdd 0.5 |
| `rc_trim4` | set once | 672 | 84.6 | 6.5 | rc_trim3 37.7, rc_trim5 37.6, avdd 0.5 |
| `rc_trim5` | set once | 670 | 84.4 | 6.4 | rc_trim4 37.6, rc_trim6 37.5, avdd 0.6 |
| `rc_trim6` | set once | 669 | 84.1 | 6.4 | rc_trim5 37.5, rc_trim7 37.4, avdd 0.6 |
| `rc_trim7` | set once | 667 | 84.0 | 6.4 | rc_trim6 37.4, xo_en 33.1, avdd 4.8 |
| `rc_trim0` | set once | 678 | 83.7 | 7.0 | rc_trim1 38.0, rc_en 35.7, avdd 0.5 |
| `en_buf` | set once | 627 | 78.8 | 22.2 | en_avcc 43.9, lv1 6.2, vbp 2.7 |
| `bg_en` | set once | 235 | 44.1 | 15.3 | ok 11.8, bod_en 6.0, adc_sample 4.6 |
| `ain1` | set once | 176 | 35.8 | 4.3 | ain0 12.7, amx 11.2, acm 3.7 |
| `ain0` | set once | 175 | 33.4 | 4.2 | ain1 12.7, acm 10.2, acp 2.5 |
| `adc6` | set once | 221 | 27.4 | 2.0 | adc7 12.2, adc5 12.2, avdd 0.4 |
| `adc5` | set once | 221 | 27.3 | 2.0 | adc6 12.2, adc4 12.2, avdd 0.4 |
| `adc4` | set once | 220 | 27.3 | 2.0 | adc5 12.2, adc3 12.1, avdd 0.4 |
| `adc3` | set once | 219 | 27.2 | 2.0 | adc4 12.1, adc2 12.1, avdd 0.4 |
| `adc2` | set once | 219 | 27.1 | 2.0 | adc3 12.1, adc1 12.1, avdd 0.4 |
| `adc1` | set once | 218 | 27.1 | 1.9 | adc2 12.1, adc0 12.0, avdd 0.4 |
| `adc7` | set once | 222 | 25.8 | 3.5 | adc6 12.2, amx 8.9, avdd 0.6 |
| `adc0` | set once | 218 | 25.7 | 2.9 | adc1 12.0, vtemp 9.2, avdd 0.8 |
| `xtal2` | set once | 104 | 8.8 | 5.9 | xtal1 2.9 |
| `xtal1` | set once | 53 | 4.7 | 1.8 | xtal2 2.9 |
| `avdd` | supply | 5466 | 946.7 | 522.4 | xo_mode1 58.0, ac_out 53.0, ok 39.7 |
| `aco` | switching | 2030 | 233.6 | 49.6 | ac_out 72.3, adc_cmp 72.3, avdd 33.8 |
| `cmpa` | switching | 1986 | 230.0 | 40.3 | smp 70.7, clk_xa 45.7, por_n 15.5 |
| `smp` | switching | 1781 | 197.6 | 85.9 | cmpa 70.7, por_n 15.7, mux_en 7.2 |
| `ac_out` | switching | 1157 | 150.0 | 13.9 | aco 72.3, avdd 53.0, ac_mux_en 4.2 |
| `adc_cmp` | switching | 1153 | 146.6 | 24.3 | aco 72.3, adc_sample 36.2, adc_en 6.2 |
| `adc_sample` | switching | 1138 | 121.0 | 28.5 | adc_cmp 36.2, bod_o 16.1, clk_xa 8.1 |
| `clk_xa` | switching | 1158 | 118.2 | 25.1 | cmpa 45.7, clk_rc 31.0, adc_sample 8.1 |
| `bod_o` | switching | 1057 | 113.8 | 18.1 | por_n 35.5, avdd 27.8, adc_sample 16.1 |
| `por_n` | switching | 939 | 102.1 | 27.3 | bod_o 35.5, smp 15.7, cmpa 15.5 |
| `adc_dac8` | switching | 642 | 93.3 | 6.0 | adc_dac9 42.2, adc_dac7 42.0, avdd 1.0 |
| `adc_dac7` | switching | 640 | 92.9 | 6.0 | adc_dac8 42.0, adc_dac6 41.8, avdd 1.0 |
| `adc_dac6` | switching | 637 | 92.5 | 6.0 | adc_dac7 41.8, adc_dac5 41.6, avdd 1.0 |
| `adc_dac5` | switching | 634 | 92.1 | 5.9 | adc_dac6 41.6, adc_dac4 41.4, avdd 1.0 |
| `adc_dac4` | switching | 632 | 91.7 | 5.9 | adc_dac5 41.4, adc_dac3 41.3, avdd 1.0 |
| `adc_dac3` | switching | 629 | 91.3 | 5.9 | adc_dac4 41.3, adc_dac2 41.1, avdd 1.0 |
| `adc_dac2` | switching | 626 | 90.9 | 5.9 | adc_dac3 41.1, adc_dac1 40.9, avdd 1.0 |
| `adc_dac1` | switching | 624 | 90.5 | 5.8 | adc_dac2 40.9, adc_dac0 40.7, avdd 1.0 |
| `clk_rc` | switching | 904 | 89.1 | 19.5 | clk_xa 31.0, rc_en 17.9, bod_o 8.4 |
| `adc_dac0` | switching | 621 | 77.1 | 8.1 | adc_dac1 40.7, avdd 13.4, cmpa 11.5 |
| `adc_dac9` | switching | 645 | 74.2 | 12.5 | adc_dac8 42.2, cmpa 15.2, avdd 1.3 |
| `clk_lf` | switching | 773 | 56.8 | 52.7 | avdd 1.4, clk_rc 0.6, bod_o 0.6 |

## Between a small-signal net and one that switches

| Nets | fF |
|---|---|
| `aco`, `acp` | 1.19 |
| `aref`, `smp` | 0.50 |
| `aref`, `cmpa` | 0.44 |
| `adc_dac9`, `aref` | 0.30 |
| `adc_dac0`, `aref` | 0.26 |
| `adc_dac8`, `aref` | 0.24 |
| `adc_dac7`, `aref` | 0.24 |
| `adc_dac6`, `aref` | 0.24 |
| `adc_dac5`, `aref` | 0.24 |
| `adc_dac4`, `aref` | 0.24 |
