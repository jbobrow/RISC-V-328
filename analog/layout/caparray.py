#!/usr/bin/env python3
"""Layout generator for the ADC capacitor array (rv328_adc_caparray).

  caparray.py <output directory>

Writes rv328_adc_caparray.gds and caparray_map.json (which unit belongs to which net, for the
pictures). Needs klayout.db. The netlist the layout has to match is analog/blocks/adccap.spice.

The array holds every 5 um x 5 um MIM unit of the ADC front end, 48 columns by 40 rows:

  rows 36-39   comparator reference side (dum to vss), 192 units
  rows  4-35   8 columns top-to-vss | 32 columns of the converter array | 8 columns top-to-vss
  rows  0-3    comparator reference side, 192 units

so the 1024 array units have identical neighbours on all four sides and the 512 + 384 units the
circuit needs anyway serve as the surround.  Inside the array a column belongs to one bit; the
columns are interleaved in a ruler sequence and mirrored about the centre line, which removes a
linear gradient across the array for every bit, and every bit spans the full height, which removes
one along the columns.  The six smallest capacitors share the two centre columns, arranged with
point symmetry about the centre of the array.

Each unit is its own Metal4 bottom plate.  Bottom plates are driven nodes; they are wired on Metal3
directly underneath (eight tracks per column) and collected on Metal2 buses below the array.  The
top plates are joined on Metal5 with straps that run only across the gaps between columns, where
no Metal3 runs, so the sensitive node sees nothing but its own bottom plates.  Via3 lands on the
margin of a bottom plate, never under a top plate (MIMTM.10 as both rule decks check it), and stays
more than 0.6 um away from the top plate, because magic's MIMTM.3 check does not count a via as
bottom-plate metal.
"""
import json
import os
import sys

import klayout.db as kdb

# ---- layers (GDS layer, datatype) ----------------------------------------------------------------------------------
M2, M2L, V2 = (36, 0), (36, 10), (38, 0)
M3, V3 = (42, 0), (40, 0)
M4, V4 = (46, 0), (41, 0)
M5, M5L = (81, 0), (81, 10)
FUSETOP, CAP_MK, MIM_L_MK, BNDRY = (75, 0), (117, 5), (117, 10), (0, 0)

# ---- dimensions, um ------------------------------------------------------------------------------------------------
NCOL, NROW = 48, 40
ROW_LO, ROW_HI = 4, 35            # rows of the converter array and its two side blocks
COL_LO, COL_HI = 8, 39            # columns of the converter array
CW = 5.0                          # top plate (FuseTop) width and length
ENC_X, ENC_Y = 0.6, 1.0           # bottom plate beyond the top plate; the y margin carries the Via3 row
GAP = 1.2                         # between bottom plates (MIMTM.1)
PX, PY = CW + 2 * ENC_X + GAP, CW + 2 * ENC_Y + GAP      # 7.4 x 8.2
VIA, V4_PITCH, V4_N = 0.26, 0.76, 6                      # Via4 on the top plate: 0.5 apart, 0.47 from the edge
NTRK, TRK_W, TRK_PITCH = 8, 0.38, 0.70                   # Metal3 tracks under each column
V3_Y = CW / 2 + 0.65 + VIA / 2                           # Via3 centre, 0.65 clear of the top plate (see below)
STRAP = 1.0                                              # Metal5 strap width
BUS_W, BUS_PITCH, BUS_TOP = 1.0, 1.6, 2.0                # Metal2 buses below the array
SIDE_GAP, SIDE_W = 6.0, 2.0                              # Metal5 collector bars left (dum) and right (top)

BITS = ["b%d" % i for i in range(10)]
BUSES = ["vss"] + BITS[::-1] + ["bx"]                    # top to bottom; vss ends most tracks, so it is nearest


def ruler(n):
    """0 1 0 2 0 1 0 3 ...: position k gets the number of times 2 divides k+1."""
    out = []
    for k in range(n):
        v, k1 = 0, k + 1
        while k1 % 2 == 0:
            v, k1 = v + 1, k1 // 2
        out.append(v)
    return out


def assignment():
    """bottom[c][r] and topnet[r]; tracks[c] = net of each of the eight Metal3 tracks of column c."""
    half = ruler(16)                                     # left half of the array, outside to inside
    col_bit = [{0: "b9", 1: "b8", 2: "b7", 3: "b6", 4: "mix"}[v] for v in half]
    col_bit = col_bit + col_bit[::-1]
    seq = ruler(32)                                      # 16x b5, 8x b4, 4x b3, 2x b2, 1x b1, 1x single
    mixed = [{0: "b5", 1: "b4", 2: "b3", 3: "b2", 4: "b1", 5: "x"}[seq[(r + 15) % 32]] for r in range(32)]
    bottom = [["vss"] * NROW for _ in range(NCOL)]
    tracks = [["vss"] * NTRK for _ in range(NCOL)]
    first_mix = True
    for i, kind in enumerate(col_bit):
        c = COL_LO + i
        if kind != "mix":
            for r in range(ROW_LO, ROW_HI + 1):
                bottom[c][r] = kind
            tracks[c] = ["vss"] + [kind] * 7
        else:
            single = "b0" if first_mix else "bx"
            order = mixed if first_mix else mixed[::-1]   # second column is the first turned by 180 degrees
            first_mix = False
            for k, r in enumerate(range(ROW_LO, ROW_HI + 1)):
                bottom[c][r] = single if order[k] == "x" else order[k]
            tracks[c] = ["vss", "b5", "b5", "b4", "b3", "b2", "b1", single]
    topnet = ["top" if ROW_LO <= r <= ROW_HI else "dum" for r in range(NROW)]
    return bottom, tracks, topnet


def build(outdir):
    bottom, tracks, topnet = assignment()
    ly = kdb.Layout()
    ly.dbu = 0.001
    L = {k: ly.layer(*k) for k in (M2, M2L, V2, M3, V3, M4, V4, M5, M5L, FUSETOP, CAP_MK, MIM_L_MK, BNDRY)}

    def box(cell, layer, x1, y1, x2, y2):
        cell.shapes(L[layer]).insert(kdb.DBox(x1, y1, x2, y2))

    # one capacitor: top plate with its Via4 field, bottom plate, recognition layers
    unit = ly.create_cell("rv328_mim_unit")
    h = CW / 2
    box(unit, FUSETOP, -h, -h, h, h)
    box(unit, M5, -h, -h, h, h)
    box(unit, MIM_L_MK, -h, -h, h, -h + 0.1)
    box(unit, M4, -h - ENC_X, -h - ENC_Y, h + ENC_X, h + ENC_Y)
    box(unit, CAP_MK, -h - ENC_X, -h - ENC_Y, h + ENC_X, h + ENC_Y)
    v0 = -(V4_N - 1) * V4_PITCH / 2
    for i in range(V4_N):
        for j in range(V4_N):
            x, y = v0 + i * V4_PITCH, v0 + j * V4_PITCH
            box(unit, V4, x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2)

    top = ly.create_cell("rv328_adc_caparray")
    top.insert(kdb.DCellInstArray(unit.cell_index(), kdb.DTrans(kdb.DVector(0, 0)),
                                  kdb.DVector(PX, 0), kdb.DVector(0, PY), NCOL, NROW))
    cx = [c * PX for c in range(NCOL)]
    cy = [r * PY for r in range(NROW)]

    # Metal2 buses
    x_left, x_right = cx[0] - h - ENC_X, cx[-1] + h + ENC_X
    bus_y = {}
    for i, net in enumerate(BUSES):
        y2 = cy[0] - h - ENC_Y - BUS_TOP - i * BUS_PITCH
        bus_y[net] = (y2 - BUS_W, y2)
        box(top, M2, x_left - 4.0, y2 - BUS_W, x_right, y2)
        top.shapes(L[M2L]).insert(kdb.DText(net, kdb.DTrans(kdb.DVector(x_left - 3.5, y2 - BUS_W / 2))))

    # Metal3 tracks with Via3 up to the plates and Via2 down to the buses
    n_via3 = 0
    for c in range(NCOL):
        for t in range(NTRK):
            net = tracks[c][t]
            x = cx[c] + (t - (NTRK - 1) / 2) * TRK_PITCH
            yb, yt = bus_y[net]
            box(top, M3, x - TRK_W / 2, yb, x + TRK_W / 2, cy[-1] + V3_Y + VIA / 2 + 0.06)
            for yv in (yb + 0.24, yt - 0.24):            # two Via2 on the bus, 0.26 apart
                box(top, V2, x - VIA / 2, yv - VIA / 2, x + VIA / 2, yv + VIA / 2)
            for r in range(NROW):
                if bottom[c][r] != net:
                    continue
                for s in (-1, 1):
                    yv = cy[r] + s * V3_Y
                    box(top, V3, x - VIA / 2, yv - VIA / 2, x + VIA / 2, yv + VIA / 2)
                    n_via3 += 1

    # Metal5: one strap along every row, cross straps in the eight outer columns of each side, collector bars
    xl, xr = cx[0] - h, cx[-1] + h
    dum_x = (xl - SIDE_GAP - SIDE_W, xl - SIDE_GAP)
    top_x = (xr + SIDE_GAP, xr + SIDE_GAP + SIDE_W)
    for r in range(NROW):
        if topnet[r] == "top":
            box(top, M5, xl, cy[r] - STRAP / 2, top_x[1], cy[r] + STRAP / 2)
        else:
            box(top, M5, dum_x[0], cy[r] - STRAP / 2, xr, cy[r] + STRAP / 2)
    groups = [(0, ROW_LO - 1), (ROW_LO, ROW_HI), (ROW_HI + 1, NROW - 1)]
    for c in list(range(0, COL_LO)) + list(range(COL_HI + 1, NCOL)):
        for r1, r2 in groups:
            box(top, M5, cx[c] - STRAP / 2, cy[r1] - h, cx[c] + STRAP / 2, cy[r2] + h)
    box(top, M5, dum_x[0], cy[0] - h, dum_x[1], cy[-1] + h)
    box(top, M5, top_x[0], cy[ROW_LO] - h, top_x[1], cy[ROW_HI] + h)
    ymid = (cy[0] + cy[-1]) / 2
    top.shapes(L[M5L]).insert(kdb.DText("dum", kdb.DTrans(kdb.DVector(sum(dum_x) / 2, ymid))))
    top.shapes(L[M5L]).insert(kdb.DText("top", kdb.DTrans(kdb.DVector(sum(top_x) / 2, ymid))))

    y_low = bus_y[BUSES[-1]][0]
    box(top, BNDRY, dum_x[0] - 1.0, y_low - 1.0, top_x[1] + 1.0, cy[-1] + h + ENC_Y + 1.0)

    os.makedirs(outdir, exist_ok=True)
    ly.write(os.path.join(outdir, "rv328_adc_caparray.gds"))

    # netlist and map
    count = {}
    for c in range(NCOL):
        for r in range(NROW):
            key = (topnet[r], bottom[c][r])
            count[key] = count.get(key, 0) + 1
    want = {("dum", "vss"): 384, ("top", "vss"): 512, ("top", "bx"): 1}
    want.update({("top", "b%d" % i): 2 ** i for i in range(10)})
    assert count == want, count
    bb = top.dbbox()
    json.dump({"ncol": NCOL, "nrow": NROW, "px": PX, "py": PY, "bottom": bottom, "topnet": topnet,
               "tracks": tracks, "bbox": [bb.left, bb.bottom, bb.right, bb.top], "via3": n_via3},
              open(os.path.join(outdir, "caparray_map.json"), "w"))
    print("rv328_adc_caparray: %.1f x %.1f um = %.4f mm2, %d units, %d Via3" %
          (bb.width(), bb.height(), bb.width() * bb.height() * 1e-6, NCOL * NROW, n_via3))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
