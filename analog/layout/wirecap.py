#!/usr/bin/env python3
"""What the macro's wiring adds to each net, from its extraction: reports/macro_wiring.md.

  wirecap.py [work directory]     reads rv328_analog_map.json there and ../layout/rv328_analog_pex.spice

Per net: length of wire (tracks, trunk line, pin lines), capacitance in all, to ground, and the three largest
parts to other nets; then the largest capacitances between a small-signal net and a net that switches.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = {"f": 1.0, "p": 1e3, "a": 1e-3, "n": 1e6}
GROUPS = {0: "small-signal", 1: "ground", 2: "set once", 3: "supply", 4: "switching"}


def main(work):
    m = json.load(open(os.path.join(work, "rv328_analog_map.json")))
    g = m["group"]
    tot, pair = collections.Counter(), collections.Counter()
    for line in open(os.path.join(HERE, "rv328_analog_pex.spice")):
        if line.startswith("C"):
            t = line.split()
            v = float(t[3][:-1]) * UNIT[t[3][-1]] if t[3][-1] in UNIT else float(t[3]) * 1e15
            tot[t[1]] += v
            tot[t[2]] += v
            pair[tuple(sorted(t[1:3]))] += v
    length = collections.Counter()
    main = lambda n: next((n[:-len(b) + len(s)] for b in m.get("branches", []) for s in ("vss", "avdd") if n == b and b.startswith(s)), n)
    for t in m["tracks"]:
        length[main(t["net"])] += t["x2"] - t["x1"]             # a branch of the supply counts with its net
    for t in m["trunk"] + m["drops"]:
        length[main(t["net"])] += t["y2"] - t["y1"]
    g = {n: v for n, v in g.items() if n not in m.get("branches", [])}

    def short(n):
        return n if "/" not in n else "inside " + n.split("/")[0].replace("rv328_", "").rstrip("_0")
    out = ["# The macro's wiring, net by net", "",
           "From `rv328_analog_pex.spice` (capacitance) and the generator's own record of what it drew (length).",
           "%.1f mm of wire on %d nets." % (sum(length.values()) / 1000, len(g)), "",
           "| Net | Group | Wire (um) | Capacitance (fF) | of it to ground | Largest parts to other nets (fF) |", "|---|---|---|---|---|---|"]
    for n in sorted(g, key=lambda n: (g[n], -tot[n])):
        oth = sorted(((v, short(a if b == n else b)) for (a, b), v in pair.items() if n in (a, b) and (a if b == n else b) != "vss"), reverse=True)[:3]
        out.append("| `%s` | %s | %.0f | %.1f | %.1f | %s |" % (n, GROUPS[g[n]], length[n], tot[n], pair[tuple(sorted((n, "vss")))],
                                                              ", ".join("%s %.1f" % (o, v) for v, o in oth)))
    q, s = [n for n in g if g[n] == 0], [n for n in g if g[n] == 4]
    rows = sorted(((v, a, b) for (a, b), v in pair.items() if (a in q and b in s) or (a in s and b in q)), reverse=True)[:10]
    out += ["", "## Between a small-signal net and one that switches", "", "| Nets | fF |", "|---|---|"]
    out += ["| `%s`, `%s` | %.2f |" % (a, b, v) for v, a, b in rows]
    open(os.path.join(HERE, "reports", "macro_wiring.md"), "w").write("\n".join(out) + "\n")
    print("\n".join(out[-13:]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out"))
