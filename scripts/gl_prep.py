#!/usr/bin/env python3
"""Prepare a routed netlist and its SDF for gate-level simulation with Icarus Verilog.

  gl_prep.py <netlist.nl.v> <file.sdf> <pdk>/gf180mcuD <out dir>

Icarus reads only part of what OpenSTA writes, so this makes five files in <out dir>:

  netlist.v  the netlist with instance names made plain identifiers. After flattening,
             names such as "clkbuf_leaf_3_u_core.clk_cpu" contain dots, and Icarus's SDF
             reader takes a dot for a hierarchy separator even when it is escaped.
  cells.v    the standard-cell models with "posedge X => (Z:X)" / "negedge X => (Z:X)"
             pairs (mux select and XOR inputs) rewritten as plain "X => Z" paths, which is
             how the SDF describes them.
  sram.v     the SRAM model with per-bit output paths widened (Icarus rejects "CLK => Q[n]")
             and its access time set to the mean CLK-to-Q delay found in the SDF.
  io.v       the pad models without their specify blocks (fixed 1 ns pad delays instead).
  cells.sdf  cell delays only: no wire (INTERCONNECT) entries, because vvp 13 aborts on
             this design's; no top-level, pad or SRAM entries.

What the simulation then covers: cell delays as computed from the routed layout, including
each cell's wire load, and the clock tree as built. Not covered: wire RC delay, and setup or
hold checks (Icarus ignores TIMINGCHECK). It shows that the routed netlist works with real
gate delays; static timing remains the sign-off for speed.
"""
import os
import re
import sys

nl, sdf, pdk, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
here = os.path.dirname(os.path.abspath(__file__))


def plain(name):
    return re.sub(r"\W", "_", name.replace("\\", ""))


# ---- netlist: rename escaped instance names
text = open(nl).read()
scl = re.search(r"gf180mcu_fd_sc_mcu\dt5v0", text).group(0)
seen = set(re.findall(r"^\s*gf180mcu\w+\s+(\w+)\s+\(", text, re.M))
renamed = {}


def inst(m):
    new = plain(m.group(2))
    if new in seen and renamed.get(m.group(2)) != new:
        raise SystemExit("instance name clash after renaming: " + m.group(2))
    seen.add(new)
    renamed[m.group(2)] = new
    return "%s %s (" % (m.group(1), new)


text = re.sub(r"^(\s*gf180mcu\w+)\s+\\(\S+)\s+\(", inst, text, flags=re.M)
open(os.path.join(out, "netlist.v"), "w").write(text)

# ---- SDF: cell delays only
src = open(sdf).read()
head, *cells = src.split("\n (CELL\n")
kept, access = [], []
for c in cells:
    ctype = re.search(r'\(CELLTYPE "([^"]+)"\)', c).group(1)
    m = re.search(r"\(INSTANCE ?([^)]*)\)", c)
    name = m.group(1).strip()
    if not name:                       # the top level: wire delays only
        continue
    if "fd_io__" in ctype:             # pad models are used without their specify blocks
        continue
    if "ip_sram" in ctype:
        access += [float(x) for x in re.findall(r"\(IOPATH CLK Q\[\d\] \(([\d.]+):", c)]
        continue
    kept.append(c[:m.start()] + "(INSTANCE %s)" % plain(name) + c[m.end():])
body = head + "".join("\n (CELL\n" + c for c in kept)
if not body.rstrip().endswith(")\n)") and body.count("(") != body.count(")"):
    body = body.rstrip() + "\n" + ")" * (body.count("(") - body.count(")")) + "\n"
open(os.path.join(out, "cells.sdf"), "w").write(body)

# ---- cell models
lib = open(os.path.join(pdk, "libs.ref", scl, "verilog", scl + ".v")).read()
lib, n1 = re.subn(r"\(posedge (\w+) => \((\w+):\1\)\)", r"(\1 => \2)", lib)
lib, n2 = re.subn(r"ifnone\s*(?://[^\n]*\n\s*)?\(negedge (\w+) => \((\w+):\1\)\) = \([^)]*\);", "", lib)
open(os.path.join(out, "cells.v"), "w").write(lib)

# ---- SRAM model
sram = open(os.path.join(here, "..", "vendor", "gf180mcu", "sram", "gf180mcu_fd_ip_sram__sram512x8m8wm1.v")).read()
sram = sram.replace("(posedge CLK => (Q[", "(posedge CLK *> (Q[")
ta = int(1000 * sum(access) / len(access)) if access else 5000
sram, n3 = re.subn(r"specparam ta\s*=\s*[^;]*;", "specparam ta   = %d : %d : %d;" % (ta, ta, ta), sram)
open(os.path.join(out, "sram.v"), "w").write(sram)

# ---- pad models: with specify paths on the bidirectional PAD pin, Icarus re-drives the
# pin at full strength and an input-only pad then fights whatever drives it from outside
io = ""
iodir = os.path.join(here, "..", "vendor", "gf180mcu", "io")
for f in sorted(os.listdir(iodir)):
    if f.endswith(".v"):
        io += re.sub(r"\bspecify\b.*?\bendspecify\b", "", open(os.path.join(iodir, f)).read(), flags=re.S)
open(os.path.join(out, "io.v"), "w").write(io)

print("gl_prep: %d instances renamed, %d of %d SDF cells kept, %d+%d model paths rewritten, SRAM access %d ps (%d set)"
      % (len(renamed), len(kept), len(cells), n1, n2, ta, n3))
