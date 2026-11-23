# Crystal oscillator with the chip's XTAL lines (tb/xosc_lines.py)

Extracted oscillator (pex). The lines from the full-height layout (docs/layout_results.md): 131 and 162 ohm in series, 1.4 and 1.8 pF to ground, between the amplifier and the crystal's pins. Gain margin = negative resistance over the crystal's loss; the target is 5 or more.

| Setting | Crystal | Loss (ohm) | Corner | Temp (C) | AVDD (V) | Gain margin, no lines (x) | Gain margin, with the lines (x) |
|---|---|---|---|---|---|---|---|
| 1 | 4 MHz | 150 | tt | 25 | 5.0 | 14.7 | 14.3 |
| 1 | 4 MHz | 150 | ss | 125 | 2.7 | 13.2 | 12.6 |
| 1 | 8 MHz | 80 | tt | 25 | 5.0 | 8.9 | 8.3 |
| 1 | 8 MHz | 80 | ss | 125 | 2.7 | 7.3 | 6.8 |
| 1 | 16 MHz | 40 | tt | 25 | 5.0 | 4.8 | 4.4 |
| 1 | 16 MHz | 40 | ss | 125 | 2.7 | 3.9 | 3.6 |
| 2 | 16 MHz | 40 | tt | 25 | 5.0 | 9.2 | 8.6 |
| 2 | 16 MHz | 40 | ss | 125 | 2.7 | 7.1 | 6.6 |
| 2 | 20 MHz | 30 | tt | 25 | 5.0 | 8.2 | 7.6 |
| 2 | 20 MHz | 30 | ss | 125 | 2.7 | 6.2 | 5.7 |
| 3 | 32.768 kHz | 70000 | tt | 25 | 5.0 | 11.9 | 11.9 |
| 3 | 32.768 kHz | 70000 | ss | 125 | 2.7 | 5.6 | 5.1 |

The lines take 0.0 to 0.6 off the margin. The high-drive setting stays at 5.7 or more up to 20 MHz, and the watch-crystal setting at 5.1. The low setting at 16 MHz was already below the target without the lines (3.9 at ss): use the high-drive setting there, as before.
