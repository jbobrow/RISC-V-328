# Cut a small window out of the final GDS for the viewer's 3D process view.
# Run with KLayout in batch mode:
#   klayout -b -r crop_gds.py -rd gds=chip_top.gds -rd box=x1,y1,x2,y2 -rd out=crop.json
# Coordinates are in microns. Layer heights come from the GF180MCU Magic tech file
# ("height" lines); GDS layer numbers from the GF180MCU layer table.
import json
import pya

x1, y1, x2, y2 = [float(v) for v in box.split(",")]
ly = pya.Layout()
ly.read(gds)
top = ly.top_cell()
dbu = ly.dbu
win = pya.Box(int(x1 / dbu), int(y1 / dbu), int(x2 / dbu), int(y2 / dbu))

# name, gds layer, z base (um), thickness (um), colour, opacity, fabrication step, label
LAYERS = [
    ("Nwell",   21, -0.55, 0.60, "#394a6b", 0.55, 1, "N-well"),
    ("COMP",    22,  0.00, 0.06, "#7ad17a", 1.0, 2, "Active (source/drain)"),
    ("Poly2",   30,  0.07, 0.20, "#ff5a5a", 1.0, 3, "Polysilicon gate"),
    ("Contact", 33,  0.06, 1.17, "#d9d9d9", 1.0, 5, "Contact plug"),
    ("Metal1",  34,  1.23, 0.55, "#3d9bff", 1.0, 6, "Metal1"),
    ("Via1",    35,  1.78, 0.60, "#b8d8ff", 1.0, 7, "Via1"),
    ("Metal2",  36,  2.38, 0.55, "#ff5d73", 1.0, 8, "Metal2"),
    ("Via2",    38,  2.93, 0.60, "#ffc2cb", 1.0, 9, "Via2"),
    ("Metal3",  42,  3.53, 0.55, "#3fd58a", 1.0, 10, "Metal3"),
    ("Via3",    40,  4.08, 0.60, "#bff3d6", 1.0, 11, "Via3"),
    ("Metal4",  46,  4.68, 0.55, "#f7c948", 1.0, 12, "Metal4"),
    ("Via4",    41,  5.23, 0.60, "#fff0b8", 1.0, 13, "Via4"),
    ("Metal5",  81,  5.83, 1.00, "#c78bff", 1.0, 14, "Metal5 (top)"),
]
STEPS = [
    ("Bare wafer", "A polished slice of lightly p-doped silicon. NMOS transistors will sit directly in it."),
    ("N-wells", "Phosphorus is implanted where PMOS transistors go, making islands of n-type silicon. In this 5 V process the wells are deep and wide, which is why the cells are tall."),
    ("Active areas", "Everything except the future transistor areas is turned into thick field oxide. The green islands that remain are where current will flow."),
    ("Gates", "A thin gate oxide is grown and polysilicon is deposited and etched into stripes. Wherever a red stripe crosses a green island there is a transistor; the stripe width is the 0.6 um channel length of the 5 V devices."),
    ("Source and drain implants", "With the gates acting as a mask, n+ and p+ dopants are implanted into the active areas on either side. Nothing new is drawn here: the implant is self-aligned to the polysilicon."),
    ("Contacts", "Oxide is deposited and planarised, holes are etched down to silicon and polysilicon and filled with tungsten. These plugs are the only way up."),
    ("Metal1", "The first aluminium layer. Inside each standard cell it wires the transistors into a gate and forms the horizontal power rails that abutting cells share."),
    ("Via1", "Tungsten plugs through the next oxide layer. The router drops one wherever a signal changes layer."),
    ("Metal2", "Mostly vertical tracks: the router's first real layer, used to get signals out of the cell pins."),
    ("Via2", "Plugs from Metal2 up to Metal3."),
    ("Metal3", "Mostly horizontal tracks for medium-length connections."),
    ("Via3", "Plugs from Metal3 up to Metal4."),
    ("Metal4", "Vertical again: long signal routes and the vertical stripes of the power grid."),
    ("Via4", "Larger plugs up to the top metal."),
    ("Metal5", "The thick top metal: wide, low-resistance horizontal power stripes and the bond pads. After this the chip is covered with passivation, opened only over the pads."),
]

layers_out = []
for order, (name, num, z, t, color, alpha, step, label) in enumerate(LAYERS):
    li = ly.find_layer(num, 0)
    rects = []
    if li is not None:
        reg = pya.Region(top.begin_shapes_rec_touching(li, win)) & pya.Region(win)
        reg.merge()
        for poly in reg.each():
            for trap in pya.Region(poly).decompose_trapezoids_to_region().each():
                b = trap.bbox()
                rects.append([round((b.left - win.left) * dbu, 3), round((b.bottom - win.bottom) * dbu, 3),
                              round((b.right - win.left) * dbu, 3), round((b.top - win.bottom) * dbu, 3)])
    layers_out.append({"name": name, "label": label, "z": z, "t": t, "color": color, "alpha": alpha,
                       "step": step, "order": order, "rects": rects})
    print(name, len(rects))

json.dump({"w": x2 - x1, "h": y2 - y1, "origin": [x1, y1], "layers": layers_out,
           "steps": [{"name": n, "text": t} for n, t in STEPS]}, open(out, "w"), separators=(",", ":"))
