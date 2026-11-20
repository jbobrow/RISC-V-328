#!/usr/bin/env python3
"""Draw a block straight from its netlist.

  autoblock.py <cell> <netlist file> <output directory> [more netlist files for sub-cells]

The cell is flattened to transistors, resistors and capacitors (sub-cells such as rv328_inv are
written out with their parameters). PMOS go into the upper row and NMOS into the lower one in the
order of the netlist, resistors and capacitors after them in whichever row is shorter, and
block.Block wires every net on its own track. Writes <cell>.gds, <cell>_lvs.spice (the flat netlist,
which is also what LVS compares with) and <cell>_map.json.

Conventions: a transistor wider than 16 um is drawn as equal fingers of at most 16 um, and m=
adds fingers; a resistor's s= is its number of strips; a capacitor's m= is that many capacitors
(from m=8 they share one bottom plate, in columns of 16).

Where the netlist's order is not good enough, ORDER below says how a cell is arranged: which nets
get the tracks next to ground or next to the supply, which are small-signal nodes to keep away
from logic, and which devices stand where.
"""
import json
import math
import os
import re
import sys

from block import Block
from devices import SC

HERE = os.path.dirname(os.path.abspath(__file__))
WMAX = 16.0
BANK_FROM = 8           # capacitors with m= of this or more are drawn as one bank (devices.cap), fewer as separate ones

# How a cell is arranged, where the netlist's own order is not good enough:
#   low, high   nets whose tracks come first after ground / last before the supply, in this order
#   victims     small-signal nets: their leads keep their distance from leads that switch (block.py)
#   calm        nets that do not move while the cell works (the supplies always count)
#   full        nets whose track runs the whole length of the cell, to screen its two neighbours from each other
#   top, bot    the devices of the two rows from left to right; devices not named follow as usual
#   heavy       nets that carry milliamperes: tracks 1.6 um wide instead of 0.4
#   strong      expression for the transistors that carry them: several leads per source and drain
ORDER = {
    # Right end: the two coupling capacitors, the second amplifier's input pair and the clamps, i.e. everything
    # on the capacitor nodes x and y, so that their tracks are short and nothing that switches is near them.
    # Left end: the output inverters and the delay chain. As first drawn, in netlist order, the output
    # inverter's lead ran beside the lead of one capacitor node (0.7 fF): 0.3 mV of offset. Which end is which
    # matters in the ADC: the column of lines that joins its blocks is at the left, and with the capacitor
    # nodes at that end the line of bit 0 put 0.6 fF on one of them.
    # The clamp controls az and azn have the two tracks nearest the clamps, so their leads are a few um long,
    # with the static enable line between them and the bias level vb, over the whole length. Directly beside vb,
    # 15 fF from azn kicked vb by 80 mV just as the clamps opened (0.5 mV of offset at 5.5 V). At the far side
    # of the channel their leads ran 20 um beside the clamps' other leads, one of which is the second
    # amplifier's output on one side and vb on the other (0.8 fF, 0.1 mV).
    # The two inputs lie between the bias lines vbi and vbp, which run the whole length as well: in the ADC the
    # inputs' tracks are extended to the end of the cell, and 200 um beside the second amplifier's
    # output, three tracks away, was 1.9 fF onto the reference side of the capacitor array.
    "rv328_adccmp": dict(low="az azn en vb xm ym x y tail2 n1 o1 a b tail vbi inp inn vbp oc".split(),
                         high="enb o2 o3 out d1 azd".split(),
                         victims="x y xm ym inp inn".split(),
                         calm="en vb tail2 n1 a b tail vbi vbp oc".split(), full=["en", "vbi", "vbp"],
                         top="xd2c xco xd2p xd1p xiz_xmp xi2_xmp xi1_xmp xie_xmp xpb xtb_xmp xmp4 xmbp xmt xm2 xm1 xmt2 xm3b xm3a xcb xca".split(),
                         bot="xd1c xtb_xmn xie_xmn xd2n xd1n xiz_xmn xi2_xmn xi1_xmn xmo xso xm4 xr2 xr1 xmn2 xmn1 xcv xmbn xsd xsc xsb xsa3 xsa2 xsa".split()),
    # Reset circuit: the two 10 Mohm resistors and the 30 pF of the delay in one row (all about 95 um tall), the
    # divider in the other. The divider tap, the detector node and the delay node are megohm nodes.
    "rv328_por": dict(low="nd ne det dly".split(), victims="nd ne det dly".split(),
                      top="xrl xrd xcd".split(), bot="xrt xrb xrh".split()),
    # 128 kHz oscillator: threshold string in one row, bias and timing resistors and the timing capacitor in the
    # other. The two thresholds and the timing node are megohm nodes; the bias lines beside them do not move.
    # Reference buffer: the input pair above its mirror, the compensation capacitors beside the pair, the tail
    # source (25 fingers) in the lower row. Nothing switches while it works. AREF can be asked for current by
    # whatever hangs on the pin, through the AVCC switch: wide tracks, four leads on that switch.
    "rv328_refbuf": dict(low="vref n1 tail vbg vbp".split(), high=["aref"], heavy=["aref", "avdd"], strong=r"xma$",
                         top="xm1 xm2 xcc".split(), bot="xmn1 xmn2 xmt".split()),
    # Comparator: inputs and the two first-stage nodes next to ground and the bias lines; the three nodes that
    # swing rail to rail at the far side of the channel. The output's last-but-one stage has the polarity of
    # the first stage's output, the output itself the opposite: either beside it would add hysteresis or
    # take it away.
    "rv328_cmp": dict(low="inn inp n1 o1 tail vbi vbp".split(), high="o2 o3 out".split(),
                      victims="inn inp n1 o1".split(), calm="tail vbi vbp en enb".split()),
    "rv328_tsens": dict(low="vtemp n1 vbp".split()),
    "rv328_lfosc": dict(low="vh vl vc vbn vbpl tl th".split(), victims="vh vl vc".split(), calm="vbn vbpl tl th".split(),
                        top="xrd1 xrd2 xrd3".split(), bot="xrb xrt".split()),
}


def um(text):
    """'2u' or '0.55u' or a bare number in metres -> micrometres."""
    text = text.strip("'")
    return float(text[:-1]) if text.endswith("u") else float(text) * 1e6


def value(text, env):
    """A parameter of a device line with the cell's parameters put in: a name (wp), or a quoted
    expression of numbers, names and lengths in um ('16u*mt'), which comes back as a length in um."""
    if text in env:
        return env[text]
    if not text.startswith("'"):
        return text
    expr = re.sub(r"[A-Za-z_]\w*", lambda m: "(%s)" % env[m.group()] if m.group() in env else m.group(), text.strip("'"))
    expr = re.sub(r"(\d+\.?\d*)u\b", r"(\1e-6)", expr)
    return "%gu" % (eval(expr, {"__builtins__": {}}) * 1e6)


def subckts(files):
    out = {}
    for f in files:
        text = re.sub(r"\n\+", " ", open(f).read())
        for m in re.finditer(r"^\.subckt\s+(\S+)([^\n]*)\n(.*?)^\.ends", text, re.M | re.S):
            head = m.group(2).split()
            pins = [t for t in head if "=" not in t]
            defaults = dict(t.split("=") for t in head if "=" in t)
            body = [l for l in m.group(3).splitlines() if l and not l.startswith("*")]
            out[m.group(1)] = (pins, defaults, body)
    return out


def flatten(cell, lib, prefix="", netmap=None, params=None):
    """Device lines of `cell` with the sub-cells found in lib written out:
    [(name, [nets], model, {param: text})]. A sub-cell that is not in lib stays as one line."""
    pins, defaults, body = lib[cell]
    env = dict(defaults)
    env.update(params or {})
    for line in body:
        if line.startswith(".param"):
            env.update(dict(t.split("=") for t in line.split()[1:]))
    out = []
    for line in body:
        if line.startswith(".param"):
            continue
        if not line.startswith("x"):
            raise ValueError("%s: only x lines can be drawn: %s" % (cell, line))
        t = line.split()
        args = dict(a.split("=") for a in t[1:] if "=" in a)
        words = [a for a in t[1:] if "=" not in a]
        nets, model = words[:-1], words[-1]
        args = {k: value(v, env) for k, v in args.items()}
        nets = [(netmap or {}).get(n, prefix + n if netmap is not None else n) for n in nets]
        if model in lib:
            sub_pins = lib[model][0]
            out += flatten(model, lib, prefix + t[0] + "_", dict(zip(sub_pins, nets)), args)
        else:
            out.append((prefix + t[0], nets, model, args))
    return out


def flat_lines(devices):
    lines = []
    for name, nets, model, a in devices:
        a = dict(a)
        if "r_length" in a:                               # s strips in series: LVS sees their total length
            a["r_length"] = "%gu" % (um(a["r_length"]) * int(a.pop("s", 1)))
        a.pop("par", None)
        for k in ("m", "mul"):
            if a.get(k) == "1":
                a.pop(k)
        lines.append("%s %s %s %s" % (name, " ".join(nets), model, " ".join("%s=%s" % kv for kv in a.items())))
    return lines


def std_netlists(devices):
    """The foundry netlists of the standard cells among these devices, as text for the head of an LVS netlist."""
    used = sorted(set(d[2] for d in devices if d[2].startswith(SC)))
    if not used:
        return ""
    pdk = os.environ.get("PDK_DIR") or os.path.join(os.environ.get("PDK_ROOT", ""), "gf180mcuD")
    text = open(os.path.join(pdk, "libs.ref", SC, "spice", SC + ".spice")).read()
    return "".join(re.search(r"^\.SUBCKT %s .*?^\.ENDS\n" % re.escape(c), text, re.M | re.S).group(0) for c in used) + "\n"


def write_flat(path, cell, pins, devices, extra=""):
    open(path, "w").write(std_netlists(devices) + extra + ".subckt %s %s\n%s\n.ends\n" % (cell, " ".join(pins), "\n".join(flat_lines(devices))))


def fingers(a):
    """(finger width, number of fingers) of a transistor line's parameters."""
    w, m = um(a["w"]), int(a.get("m", a.get("mul", 1)))
    k = max(1, math.ceil(w / WMAX - 1e-9))
    while abs(round(w / k * 100) - w / k * 100) > 1e-6:      # finger width must stay on the 10 nm grid
        k += 1
    return round(w / k, 3), m * k


def generate(lib, model, a):
    """[(device, pin names in the order of the line's nets, kind)] for one netlist line."""
    if model.startswith(SC):                                 # a foundry standard cell
        d = lib.std(model)
        return [(d, tuple(d.pins), "std")]
    if model in ("pfet_06v0", "nfet_06v0"):
        w, nf = fingers(a)
        return [(lib.mos(model[0], w, um(a["l"]), nf), ("D@1", "G", "S@0", "B"), model[0] + "mos")]
    if model in ("ppolyf_u_1k_6p0", "ppolyf_u"):
        d = lib.res(um(a["r_length"]), int(a.get("s", 1)), um(a["r_width"]), "1k" if model.endswith("6p0") else "pp")
        return [(d, ("A", "B", "SUB"), "res")]
    if model == "cap_mim_2f0fF":
        m = int(a.get("m", 1))
        if m >= BANK_FROM:                                   # a bank of unit capacitors on one bottom plate
            return [(lib.cap(um(a["c_width"]), um(a["c_length"]), m), ("T", "Bot"), "cap")]
        return [(lib.cap(um(a["c_width"]), um(a["c_length"])), ("T", "Bot"), "cap")] * m
    raise ValueError("no generator for %s" % model)


def order_nets(nets, low=(), high=()):
    mid = [n for n in nets if n not in ("vss", "avdd") and n not in low and n not in high]
    return ([n for n in nets if n == "vss"] + [n for n in low if n in nets] + mid +
            [n for n in high if n in nets] + [n for n in nets if n == "avdd"])


STRONG_UM = 60.0        # a transistor named in `strong` gets one source and one drain lead per this much width, up to six


def make(cell, devices, ports, lib=None, low=(), high=(), victims=(), calm=(), full=(), top=(), bot=(), rows=None, heavy=(), strong=None):
    """Block `cell` from device lines. PMOS go above the channel, NMOS below, passives into the shorter
    row; or, with rows = {device name: "top" or "bot"}, every device where that says, in the order given.
    The devices named in top and bot are placed first, from left to right. See ORDER for the rest."""
    nets = list(ports)
    for _, ns, _, _ in devices:
        for n in ns:
            if n not in nets:
                nets.append(n)
    fine = any(d[2].startswith(SC) for d in devices)             # standard cells inside: wired at minimum pitch
    b = Block(cell, order_nets(nets, low, high), ports, lib, victims=victims, calm=calm, full=full, heavy=heavy, fine=fine)
    place = (top, bot)
    byname = {d[0]: d for d in devices}
    todo, later = [], []
    for row, names in zip(("top", "bot"), place or ((), ())):
        todo += [(byname[n], row) for n in names]
    placed = set(d[0] for d, _ in todo)
    for d in devices:
        if d[0] in placed:
            continue
        kind = generate(b.lib, d[2], d[3])[0][2]
        if rows:
            todo.append((d, rows[d[0]]))
        elif kind.endswith("mos"):
            todo.append((d, "top" if kind[0] == "p" else "bot"))
        elif kind == "std":
            todo.append((d, None))                           # into whichever row is shorter, in the netlist's order
        else:
            later.append(d)
    for (name, ns, model, a), row in todo + [(d, None) for d in later]:
        for dev, pins, kind in generate(b.lib, model, a):
            pinmap = dict(zip(pins, ns))
            if kind == "std":
                b.add_std(dev, row or ("top" if b.x["top"] <= b.x["bot"] else "bot"), pinmap, name=name)
                continue
            if strong and kind.endswith("mos") and re.match(strong, name):
                # a transistor that carries milliamperes: several leads along its source and drain bars, so that no
                # lead, via or piece of a bar carries more than a fraction of the current
                w, nf = fingers(a)
                k = min(6, math.ceil(w * nf / STRONG_UM))
                if k > 1:
                    del pinmap["D@1"], pinmap["S@0"]
                    for j in range(k):
                        pinmap["S@%.3f" % (j / k)] = ns[2]
                        pinmap["D@%.3f" % ((j + 0.5) / k)] = ns[0]
            b.add(dev, row or ("top" if b.x["top"] <= b.x["bot"] else "bot"), pinmap, name=name, kind=kind)
    b.bb = b.route()
    return b


def block_map(b):
    bb = b.bb
    return {"placed": b.placed, "nets": b.nets, "h": b.h, "bbox": [bb.left, bb.bottom, bb.right, bb.top],
            "tracks": {n: b.track_y(n) for n in b.nets}}


def build(cell, files, outdir):
    lib = subckts(files)
    pins = lib[cell][0]
    devices = flatten(cell, lib)
    b = make(cell, devices, pins, **ORDER.get(cell, {}))
    os.makedirs(outdir, exist_ok=True)
    b.write(os.path.join(outdir, cell + ".gds"), os.path.join(outdir, cell + "_named.gds"))
    write_flat(os.path.join(outdir, cell + "_lvs.spice"), cell, pins, devices)
    json.dump(block_map(b), open(os.path.join(outdir, cell + "_map.json"), "w"))
    bb = b.bb
    print("%s: %.1f x %.1f um = %.4f mm2, %d devices in the netlist, %d placed cells, %d leads" %
          (cell, bb.width(), bb.height(), bb.width() * bb.height() * 1e-6, len(devices), b.count, len(b.leads)))


if __name__ == "__main__":
    cell, netlist, outdir = sys.argv[1:4]
    extra = sys.argv[4:] or [os.path.join(HERE, "..", "blocks", "logic.spice")]
    build(cell, [netlist] + extra, outdir)
