#!/usr/bin/env python3
"""Merge the per-cell liberty files of a GF180MCU standard-cell library checkout
into one file (what open_pdks does when it installs the PDK).
usage: merge_lib.py <library repo> <corner, e.g. tt_025C_5v00> <out.lib>"""
import glob, os, sys
repo, corner, out = sys.argv[1:4]
name = os.path.basename(glob.glob(os.path.join(repo, "liberty", "*__%s.lib" % corner))[0])
hdr = open(os.path.join(repo, "liberty", name)).read().rstrip()
assert hdr.endswith("}")
cells = sorted(glob.glob(os.path.join(repo, "cells", "*", "*__%s.lib" % corner)))
with open(out, "w") as f:
    f.write(hdr[:-1])
    for c in cells:
        f.write(open(c).read())
    f.write("\n}\n")
print("merged %d cells into %s" % (len(cells), out))
