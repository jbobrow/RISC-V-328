#!/usr/bin/env python3
"""High-resolution pictures of a layout, in the colours of the layout viewer.

  render_layout.py <chip.gds | chip.def> <output prefix> [view ...]
                   [--lef a.lef ...] [--gds cells.gds ...] [--map gf180mcu.map] [--lyt gf180mcu.lyt]   (DEF input only)

A view is name:width_px for the whole die or name:x1,y1,x2,y2:width_px for a window in um.
Default: full:8000. Files are written as <prefix>_<name>.png.

KLayout (klayout -b) draws each layer on its own as a mask; the masks are then stacked in
fabrication order with one colour and one opacity per layer, so lower layers stay visible
under the wide power metal. Needs klayout on the PATH and Pillow.
"""
import argparse
import os
import subprocess
import sys
import tempfile

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# name, GDS layer, colour, opacity; bottom of the stack first
LAYERS = [
    ("nwell",   21, "#1d2f57", 1.00),
    ("active",  22, "#2e7d4f", 1.00),
    ("poly",    30, "#e0475b", 1.00),
    ("contact", 33, "#f2f2f2", 1.00),
    ("metal1",  34, "#3a86ff", 0.85),
    ("via1",    35, "#cfe6ff", 0.90),
    ("metal2",  36, "#ff6b6b", 0.70),
    ("via2",    38, "#ffd9d9", 0.90),
    ("metal3",  42, "#2ec4b6", 0.60),
    ("via3",    40, "#d5f7f3", 0.90),
    ("metal4",  46, "#ffd166", 0.42),
    ("mimtop",  75, "#ff7b00", 0.55),   # top plate of a MIM capacitor (FuseTop), between Metal4 and Metal5
    ("via4",    41, "#fff3c4", 0.90),
    ("metal5",  81, "#c77dff", 0.32),
    ("pad",     37, "#f4c77b", 0.90),   # bond pad openings in the passivation
]
BACKGROUND = "#07090d"

KLAYOUT_SCRIPT = r'''
import pya
lv = pya.LayoutView()
for key, val in (("grid-visible", "false"), ("grid-show-ruler", "false"), ("text-visible", "false"),
                 ("background-color", "#000000")):
    lv.set_config(key, val)
if SRC.endswith(".def"):
    tech = pya.Technology()
    tech.load(LYT)
    opt = tech.load_layout_options
    opt.lefdef_config.map_file = MAP
    opt.lefdef_config.macro_resolution_mode = 2 if GDS else 1
    if GDS:
        opt.lefdef_config.macro_layout_files = GDS
    opt.lefdef_config.read_lef_with_def = False
    opt.lefdef_config.lef_files = LEFS
    lv.load_layout(SRC, opt, LYT)
else:
    lv.load_layout(SRC)
lv.max_hier()
die = lv.active_cellview().layout().top_cell().dbbox()
for name, box, width in VIEWS:
    if box is None:
        m = 0.01 * die.width()
        b = pya.DBox(die.left - m, die.bottom - m, die.right + m, die.top + m)
    else:
        b = pya.DBox(*box)
    height = int(round(width * b.height() / b.width()))
    for lname, layer in LAYERS:
        it = lv.begin_layers()
        while not it.at_end():
            lv.delete_layer(it)
            it = lv.begin_layers()
        p = pya.LayerProperties()
        p.source = "%d/0" % layer
        p.fill_color = 0xffffff
        p.frame_color = 0xffffff
        p.dither_pattern = 0
        p.visible = True
        lv.insert_layer(lv.end_layers(), p)
        lv.save_image_with_options("%s/%s_%s.png" % (TMP, name, lname), width, height, 0, OVERSAMPLING, 0, b, False)
    print("VIEW %s %d %d %.3f %.3f" % (name, width, height, b.width(), b.height()))
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("prefix")
    ap.add_argument("views", nargs="*", default=["full:8000"])
    ap.add_argument("--lef", action="append", default=[])
    ap.add_argument("--gds", action="append", default=[], help="cell layouts (GDS) to place into a DEF, for stage pictures with real cell geometry")
    ap.add_argument("--map", default="")
    ap.add_argument("--lyt", default="")
    ap.add_argument("--oversampling", type=int, default=3)
    ap.add_argument("--upto", default="", help="draw the stack only up to this layer (e.g. metal2), to see the devices under wide metal")
    a = ap.parse_args()
    global LAYERS
    if a.upto:
        names = [l[0] for l in LAYERS]
        LAYERS = LAYERS[:names.index(a.upto) + 1]

    views = []
    for v in a.views:
        parts = v.split(":")
        box = tuple(float(t) for t in parts[1].split(",")) if len(parts) == 3 else None
        views.append((parts[0], box, int(parts[-1])))

    with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(a.prefix)) or ".") as tmp:
        script = os.path.join(tmp, "render.py")
        with open(script, "w") as f:
            f.write("SRC=%r\nLYT=%r\nMAP=%r\nLEFS=%r\nGDS=%r\nTMP=%r\nVIEWS=%r\nLAYERS=%r\nOVERSAMPLING=%d\n" % (
                os.path.abspath(a.src), a.lyt, a.map, a.lef, a.gds, tmp, views, [(l[0], l[1]) for l in LAYERS], a.oversampling))
            f.write(KLAYOUT_SCRIPT)
        out = subprocess.run(["klayout", "-b", "-r", script], capture_output=True, text=True)
        if out.returncode:
            sys.exit(out.stdout + out.stderr)
        for line in out.stdout.splitlines():
            if not line.startswith("VIEW "):
                continue
            _, name, w, h, wu, hu = line.split()
            img = Image.new("RGB", (int(w), int(h)), BACKGROUND)
            for lname, _, colour, alpha in LAYERS:
                mask = Image.open(os.path.join(tmp, "%s_%s.png" % (name, lname))).convert("L")
                if mask.getbbox() is None:
                    continue
                if alpha < 1.0:
                    mask = mask.point(lambda v, a=alpha: int(v * a))
                img.paste(Image.new("RGB", img.size, colour), (0, 0), mask)
            path = "%s_%s.png" % (a.prefix, name)
            img.save(path, optimize=True)
            print("wrote %s  %sx%s px  %.0f x %.0f um  %.1f MB" % (path, w, h, float(wu), float(hu), os.path.getsize(path) / 1e6))


if __name__ == "__main__":
    main()
