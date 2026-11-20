#!/usr/bin/env python3
"""How many of magic's DRC error boxes lie outside the foundry bipolar cells of a layout.

  drc_inside.py <gds> <top cell> <file of MAGIC_BOX lines, as lvs.sh writes it>

magic's deck reports "P-diffusion and N-ohmic must be over N-well" inside every pnp_10p00x10p00, also when
that cell is checked by itself. check.sh sets those aside, and only if this prints 0: every box inside one
of those cells.
"""
import sys

import klayout.db as kdb

gds, top, boxes = sys.argv[1:4]
ly = kdb.Layout()
ly.read(gds)
cells, it = [], ly.cell(top).begin_instances_rec()
while not it.at_end():
    if it.inst_cell().name == "pnp_10p00x10p00":
        cells.append(it.inst_cell().dbbox().transformed(it.dtrans() * it.inst_dtrans()).enlarged(0.01, 0.01))
    it.next()
out = 0
for line in open(boxes):
    t = line.split()
    k = float(t[1])
    x1, y1, x2, y2 = [float(v) * k for v in t[2:6]]
    if not any(b.contains(kdb.DPoint(x1, y1)) and b.contains(kdb.DPoint(x2, y2)) for b in cells):
        out += 1
print(out)
