#!/usr/bin/env python3
"""Extracted netlist of a generated block (devices plus wiring capacitance), ready for simulation.

  pex_block.py <gds> <cell> <schematic file with the cell's .subckt line> <output .spice>

If <gds> has a companion <cell>_named.gds (the same layout with labels on the inner nets as well, as
block.py writes), that one is extracted, so the inner nodes keep their schematic names.

magic extracts with every capacitance kept (no resistance). The result is then adjusted in three
places: the foundry bipolar primitive is reduced from nine pin labels to collector, base, emitter;
the substrate node is named after the ground pin; and the cell's pin order is made that of the
schematic, so the file can stand in for the schematic cell (sim.py, RV328_PEX).
"""
import os
import re
import subprocess
import sys

PDK = os.environ.get("PDK_DIR") or os.path.join(os.environ.get("PDK_ROOT", ""), "gf180mcuD")


MERGE_FROM = 9


def merge(lines):
    """Groups of MERGE_FROM or more transistors with the same four nodes and the same size become one line
    with m=: the hundreds of unit switches of the ADC come out of the extraction finger by finger. Smaller
    groups, the fingers of matched devices, stay as they are, because a Monte Carlo run gives every line
    its own mismatch and one line with m= would get the mismatch of a single finger."""
    groups, n = {}, 0
    for i, line in enumerate(lines):
        t = line.split()
        if t and t[0].startswith("X") and len(t) > 6 and t[5] in ("nfet_06v0", "pfet_06v0", "nfet_05v0", "pfet_05v0") and not any(a.startswith("m=") for a in t[6:]):
            d, g, s, b = t[1:5]
            groups.setdefault((min(d, s), g, max(d, s), b, t[5], " ".join(sorted(t[6:]))), []).append(i)
            n += 1
    drop = set()
    for idx in groups.values():
        if len(idx) >= MERGE_FROM:
            lines[idx[0]] += " m=%d" % len(idx)
            drop.update(idx[1:])
    return [l for i, l in enumerate(lines) if i not in drop], n


def main(gds, cell, schem, out):
    work = os.path.dirname(os.path.abspath(gds))
    named = os.path.join(work, cell + "_named.gds")
    if os.path.exists(named) and os.path.getmtime(named) >= os.path.getmtime(gds):
        gds = named
    raw = os.path.join(work, cell + ".pex.raw.spice")
    tcl = os.path.join(work, cell + ".pex.tcl")
    open(tcl, "w").write("\n".join([
        "load pnp_10p00x10p00", "gds noduplicates true", "gds read %s" % os.path.abspath(gds), "load %s" % cell, "select top cell",
        "extract all", "ext2spice lvs", "ext2spice hierarchy off", "ext2spice subcircuit top on", "ext2spice scale off",
        "ext2spice cthresh 0", "ext2spice rthresh infinite",
        "ext2spice -o %s" % raw, "quit -noprompt", ""]))
    rc = os.path.join(PDK, "libs.tech", "magic", "gf180mcuD.magicrc")
    p = subprocess.run(["magic", "-dnull", "-noconsole", "-rcfile", rc, tcl], cwd=work, capture_output=True, text=True,
                       env=dict(os.environ, PDK="gf180mcuD", PDK_ROOT=os.path.dirname(os.path.abspath(PDK))))
    open(os.path.join(work, cell + ".pex.log"), "w").write(p.stdout + p.stderr)
    ports = re.search(r"^\.subckt %s (.*)$" % cell, open(schem).read(), re.M).group(1).split()
    # a cell with parameters keeps them in its header, so that it can stand in for the schematic cell wherever
    # that is used; the layout is of the default values, and the extracted cell ignores what it is given
    params = [t for t in ports if "=" in t]
    ports = [t for t in ports if "=" not in t]
    text = open(raw).read().replace("\n+", "")
    lines, ncap, npnp, inside = [], 0, 0, False
    for line in text.splitlines():
        t = line.split()
        if t and t[0].startswith("X") and t[-1] == "pnp_10p00x10p00" and len(t) == 11:
            nodes = t[1:-1]
            assert len(set(nodes[:2] + nodes[3:])) == 1, line
            line = "%s %s %s %s pnp_10p00x10p00" % (t[0], nodes[0], nodes[0], nodes[2])
        if t and t[0].startswith("X") and t[-1] == "pnp_10p00x00p42" and len(t) == 5:
            # flat extraction looks inside the foundry 10 x 10 um cell and matches the wrong size of the same
            # device; the cell that was placed is pnp_10p00x10p00
            line, npnp = " ".join(t[:-1]) + " pnp_10p00x10p00", npnp + 1
        if t and t[0] == ".subckt" and t[1] == cell:
            assert set(ports) <= set(t[2:]), (t[2:], ports)       # labelled inner nets come out as ports too: dropped here
            line, inside = ".subckt %s %s" % (cell, " ".join(ports + params)), True
        elif t and t[0] == ".subckt" and t[1].startswith("pnp_10p00x10p00"):
            line = "* " + line                                   # leftover definition of the primitive's inside
            inside = "skip"
        elif inside == "skip":
            if t and t[0] == ".ends":
                inside = False
            line = "* " + line
        elif inside and t and t[0].startswith("C"):
            line = re.sub(r"\bVSUBS\b", "vss", line)
            if t[1] == t[2] or (set((t[1], t[2])) == {"VSUBS", "vss"}):
                continue
            ncap += 1
        elif inside and t and t[0] == ".ends":
            inside = False
        lines.append(line)
    lines, nmos = merge(lines)
    head = ["* %s with the wiring capacitance of its layout. Written by analog/layout/pex_block.py from %s;" % (cell, os.path.basename(gds)),
            "* same cell name and pins as the schematic%s. %d wiring capacitors, no wiring resistance;" %
            (" (drawn for %s; a different value given to it changes nothing)" % ", ".join(params) if params else "", ncap),
            "* %d transistor fingers; groups of %d or more identical parallel ones are one line with m=." % (nmos, MERGE_FROM)]
    open(out, "w").write("\n".join(head + lines) + "\n")
    print("%s: %d wiring capacitors, %d bipolars" % (os.path.basename(out), ncap, npnp))


if __name__ == "__main__":
    main(*sys.argv[1:5])
