#!/usr/bin/env python3
"""Turn a placed/routed DEF (plus LEFs) into the data file of the RV328 layout viewer.

Pure Python: no EDA tools needed.

    extract.py --def chip_top.def --lef '<glob>' [--lef ...] [--pads pads.json] [--summary summary.json]
               [--crop crop.json] --out layout.json

What it extracts
  * every placed instance with its size, split into pads, macros, logic cells and
    physical-only cells (fill, taps, end caps)
  * signal and clock routing as rectangles per metal layer, vias per cut layer,
    each tagged with its net
  * the power grid (special nets)
  * a functional block for every logic cell, inferred from the hierarchical net
    names that survive synthesis (the cells themselves are flattened and renamed)

Coordinates are quantised to 0.1 um and stored as base64(deflate(typed array)).
"""
import argparse, base64, glob, json, os, re, struct, sys, zlib
from array import array
from collections import Counter, defaultdict

Q = 10  # quantisation: units per micron

# Functional blocks: (id, label, net-name prefixes, description)
BLOCKS = [
    ("cpu", "CPU (Hazard3 RV32IMC)", ["u_core.u_cpu."],
     "Fetches instructions through the cache, executes them and takes interrupts. Three-stage pipeline, "
     "register file, multiplier/divider, CSRs and the interrupt controller."),
    ("debug", "Debug (DM + JTAG)", ["u_core.u_dm.", "u_core.u_dtm."],
     "RISC-V debug module and JTAG transport: halt, single-step and register access from the four test pads."),
    ("xip", "Program memory + cache", ["u_core.u_xip."],
     "Reads code from the serial memory die over SPI, keeps 64 lines of 32 bytes in the cache SRAM, and "
     "programs the memory (NVM controller)."),
    ("clk", "Clock and reset", ["u_core.u_clkrst.", "u_core.u_cpugate.", "u_analog."],
     "Glitch-free clock switch, prescaler, sleep clock gate with asynchronous wake-up, reset controller and "
     "reset-cause flags. In this build the analog stub lives here too."),
    ("sys", "System control", ["u_core.u_sys."],
     "Clock, sleep, reset and brown-out configuration registers, PRR and the general-purpose registers."),
    ("gpio", "GPIO + pin interrupts", ["u_core.u_gpio."],
     "PIN/DDR/PORT registers for ports B, C, D, E, input synchronisers, 27 pin-change interrupts, INT0/INT1."),
    ("tc0", "Timer 0 (8-bit)", ["u_core.u_tc0."], "8-bit timer with two PWM outputs (OC0A/OC0B)."),
    ("tc1", "Timer 1 (16-bit)", ["u_core.u_tc1."], "16-bit timer with two PWM outputs and input capture."),
    ("tc2", "Timer 2 (8-bit)", ["u_core.u_tc2."], "8-bit timer with two PWM outputs and 32 kHz tick input."),
    ("tc3", "Timer 3 (16-bit)", ["u_core.u_tc3."], "16-bit timer with two PWM outputs and input capture."),
    ("tc4", "Timer 4 (16-bit)", ["u_core.u_tc4."], "16-bit timer with two PWM outputs and input capture."),
    ("usart0", "USART 0", ["u_core.u_usart0."], "Asynchronous serial port on PD0/PD1."),
    ("usart1", "USART 1", ["u_core.u_usart1."], "Asynchronous serial port on PB3/PB4."),
    ("spi0", "SPI 0", ["u_core.u_spi0."], "SPI master/slave on PB2-PB5."),
    ("spi1", "SPI 1", ["u_core.u_spi1."], "SPI master/slave on PC0, PC1, PE2, PE3."),
    ("twi0", "TWI 0 (I2C)", ["u_core.u_twi0."], "I2C master/slave on PC4/PC5."),
    ("twi1", "TWI 1 (I2C)", ["u_core.u_twi1."], "I2C master/slave on PE0/PE1."),
    ("adc", "ADC + comparator control", ["u_core.u_adc."],
     "10-bit successive-approximation sequencer and comparator control; the analog front end is not in this build."),
    ("wdt", "Watchdog", ["u_core.u_wdt."], "Watchdog counter in its own clock domain, with reset and interrupt."),
    ("bus", "Bus, RAM glue, pin mux", ["u_core."],
     "Address decode between program memory, SRAM and peripherals, read-data multiplexing, and the pin "
     "multiplexer that routes peripheral signals to the pads."),
    ("cts", "Clock tree buffers", [], "Buffers inserted by clock-tree synthesis to balance clock arrival."),
    ("opt", "Timing and signal repair", [],
     "Buffers and resized cells added by the tools to fix slew, capacitance, hold and antenna problems."),
]
BLOCK_ID = {b[0]: i for i, b in enumerate(BLOCKS)}


def b64(arr):
    raw = arr.tobytes() if hasattr(arr, "tobytes") else bytes(arr)
    return base64.b64encode(zlib.compress(raw, 9)).decode()


def parse_lefs(paths):
    """macro name -> (w, h, class);  layer -> default width;  via name -> cut layer"""
    macros, widths, vias = {}, {}, {}
    for path in paths:
        cur = None; layer = None; via = None
        with open(path, errors="replace") as f:
            for line in f:
                t = line.split()
                if not t:
                    continue
                if t[0] == "MACRO":
                    cur = [t[1], 0.0, 0.0, "CORE"]
                elif cur is not None:
                    if t[0] == "CLASS":
                        cur[3] = " ".join(t[1:]).rstrip(" ;")
                    elif t[0] == "SIZE":
                        cur[1], cur[2] = float(t[1]), float(t[3])
                    elif t[0] == "END" and len(t) > 1 and t[1] == cur[0]:
                        macros[cur[0]] = (cur[1], cur[2], cur[3]); cur = None
                elif t[0] == "LAYER" and len(t) == 2:
                    layer = t[1]
                elif t[0] == "VIA" and len(t) >= 2:
                    via = t[1]
                elif via is not None:
                    if t[0] == "LAYER" and t[1].lower().startswith("via"):
                        vias[via] = t[1].rstrip(";")
                    elif t[0] == "END":
                        via = None
                elif layer is not None:
                    if t[0] == "WIDTH" and layer not in widths:
                        widths[layer] = float(t[1])
                    elif t[0] == "END":
                        layer = None
    return macros, widths, vias


def statements(f, first_kw):
    """Yield the '- ... ;' statements of a DEF section as token lists."""
    buf = []
    for line in f:
        s = line.strip()
        if s.startswith("END " + first_kw):
            return
        buf.extend(s.split())
        if s.endswith(";"):
            if buf and buf[0] == "-":
                yield buf
            buf = []


class Shapes:
    def __init__(self):
        self.rect = defaultdict(lambda: array("H"))
        self.net = defaultdict(lambda: array("H"))

    def add(self, layer, x1, y1, x2, y2, net):
        if x1 > x2: x1, x2 = x2, x1
        if y1 > y2: y1, y2 = y2, y1
        self.rect[layer].extend((x1, y1, x2, y2)); self.net[layer].append(net)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--def", dest="deff", required=True)
    ap.add_argument("--lef", action="append", default=[])
    ap.add_argument("--summary")
    ap.add_argument("--crop")
    ap.add_argument("--pads")
    ap.add_argument("--note", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    lefs = sorted({p for g in a.lef for p in glob.glob(g)})
    macros, widths, viadef = parse_lefs(lefs)
    print("LEF: %d macros, %d layers, %d vias" % (len(macros), len(widths), len(viadef)), file=sys.stderr)

    dbu = 2000.0
    die = [0, 0, 0, 0]
    insts = []            # (name, master, x, y, orient)
    inst_idx = {}
    nets = []             # name
    net_use = array("B")
    net_cells = []        # list of arrays of instance indices
    wires, pdn = Shapes(), Shapes()
    vias = defaultdict(lambda: array("H")); via_net = defaultdict(lambda: array("H"))
    top_pins = {}

    def q(v):
        return max(0, min(65535, int(round(v / dbu * Q))))

    with open(a.deff, errors="replace") as f:
        for line in f:
            t = line.split()
            if not t:
                continue
            if t[0] == "UNITS":
                dbu = float(t[3])
            elif t[0] == "DIEAREA":
                nums = [float(x) for x in t if re.fullmatch(r"-?\d+", x)]
                die = [nums[0], nums[1], nums[-2], nums[-1]]
            elif t[0] == "VIAS":
                for st in statements(f, "VIAS"):
                    cut = next((x for x in st if x.lower().startswith("via") and x != st[1]), None)
                    if cut:
                        viadef[st[1]] = cut.rstrip(";")
            elif t[0] == "COMPONENTS":
                for st in statements(f, "COMPONENTS"):
                    name, master = st[1], st[2]
                    try:
                        i = next(k for k, x in enumerate(st) if x in ("PLACED", "FIXED", "COVER"))
                        x, y, orient = float(st[i + 2]), float(st[i + 3]), st[i + 5]
                    except StopIteration:
                        continue
                    inst_idx[name] = len(insts)
                    insts.append((name, master, x, y, orient))
            elif t[0] == "PINS":
                for st in statements(f, "PINS"):
                    top_pins[st[1]] = True
            elif t[0] in ("NETS", "SPECIALNETS"):
                special = t[0] == "SPECIALNETS"
                for st in statements(f, t[0]):
                    name = st[1].replace("\\", "")
                    nid = len(nets)
                    use = 0
                    cells = array("I")
                    i = 2
                    n = len(st)
                    # connections
                    while i < n and st[i] == "(":
                        if st[i + 1] != "PIN":
                            k = inst_idx.get(st[i + 1])
                            if k is not None:
                                cells.append(k)
                        while st[i] != ")":
                            i += 1
                        i += 1
                    layer = None; px = py = None; width = 0
                    while i < n:
                        tok = st[i]
                        if tok == "+":
                            kw = st[i + 1]
                            if kw == "USE":
                                u = st[i + 2]
                                use = 1 if u == "CLOCK" else 2 if u in ("POWER", "GROUND") else 0
                                i += 3; continue
                            if kw in ("ROUTED", "FIXED", "COVER"):
                                layer = st[i + 2]; px = py = None; i += 3
                                if special:
                                    width = float(st[i]); i += 1
                                continue
                            if kw == "SHAPE":
                                i += 3; continue
                            i += 2; continue
                        if tok == "NEW":
                            layer = st[i + 1]; px = py = None; i += 2
                            if special:
                                width = float(st[i]); i += 1
                            continue
                        if layer is None:
                            i += 1; continue
                        if tok == "(":
                            j = i + 1
                            vals = []
                            while st[j] != ")":
                                vals.append(st[j]); j += 1
                            x = px if vals[0] == "*" else float(vals[0])
                            y = py if vals[1] == "*" else float(vals[1])
                            if px is not None and (x != px or y != py):
                                w = width if special else widths.get(layer, 0.28) * dbu
                                h = w / 2.0
                                tgt = pdn if special else wires
                                if x == px:
                                    tgt.add(layer, q(x - h), q(min(y, py)), q(x + h), q(max(y, py)), nid)
                                else:
                                    tgt.add(layer, q(min(x, px)), q(y - h), q(max(x, px)), q(y + h), nid)
                            px, py = x, y
                            i = j + 1; continue
                        if tok == "RECT":
                            r = [float(v) for v in st[i + 2:i + 6]]
                            if px is not None and not special:
                                wires.add(layer, q(px + r[0]), q(py + r[1]), q(px + r[2]), q(py + r[3]), nid)
                            i += 7; continue
                        if tok in ("TAPER", "VIRTUAL", ";"):
                            i += 1; continue
                        if tok in ("TAPERRULE", "MASK", "STYLE", "DO", "BY"):
                            i += 2; continue
                        if tok == "STEP":
                            i += 3; continue
                        # anything else here is a via name at the previous point
                        if px is not None and not special:
                            cut = viadef.get(tok)
                            if cut is None:
                                m = re.match(r"(Via\d)", tok, re.I)
                                cut = m.group(1) if m else None
                            if cut:
                                vias[cut].extend((q(px), q(py))); via_net[cut].append(nid)
                        i += 1
                    if special:
                        use = 2
                    nets.append(name); net_use.append(use); net_cells.append(cells)
    assert len(nets) < 65536, "too many nets for 16-bit ids"
    print("DEF: %d instances, %d nets" % (len(insts), len(nets)), file=sys.stderr)

    # ---------------- classify instances ----------------
    pads, macro_list = [], []
    cells_rect = array("H"); cells_master = array("H"); cells_names = []; cell_of_inst = {}
    phys_rect = array("H"); ring_rect = array("H")
    master_names, master_id = [], {}
    phys_count = Counter()
    for k, (name, master, x, y, orient) in enumerate(insts):
        w, h, cls = macros.get(master, (1.0, 1.0, "CORE"))
        if orient in ("E", "W", "FE", "FW"):
            w, h = h, w
        r = (q(x), q(y), q(x + w * dbu), q(y + h * dbu))
        short = master.split("__")[-1]
        if "_fd_io__" in master and re.match(r"(fill|cor|brk)", short):
            ring_rect.extend(r)
        elif cls.startswith("PAD") or "_fd_io__" in master:
            pads.append({"name": name, "master": short, "r": r})
        elif cls.startswith("BLOCK") or "_ip_sram__" in master or "_ws_ip__" in master:
            macro_list.append({"name": name, "master": short, "r": r})
        elif "SPACER" in cls or "WELLTAP" in cls or "ENDCAP" in cls or re.match(r"(fill|filltie|endcap|fillcap|decap)", short):
            phys_rect.extend(r); phys_count[re.sub(r"_\d+$", "", short)] += 1
        else:
            if master not in master_id:
                master_id[master] = len(master_names); master_names.append(short)
            cell_of_inst[k] = len(cells_names)
            cells_rect.extend(r); cells_master.append(master_id[master]); cells_names.append(name)
    ncell = len(cells_names)
    print("cells %d, physical %d, pads %d, macros %d" % (ncell, len(phys_rect) // 4, len(pads), len(macro_list)),
          file=sys.stderr)

    # ---------------- functional blocks from net names ----------------
    def block_of_name(nm):
        for bi, (_, _, prefixes, _) in enumerate(BLOCKS):
            for p in prefixes:
                if nm.startswith(p):
                    return bi
        return None

    votes = [Counter() for _ in range(ncell)]
    cell_nets = [[] for _ in range(ncell)]
    for nid, cl in enumerate(net_cells):
        if net_use[nid] == 2:
            continue
        b = block_of_name(nets[nid])
        members = [cell_of_inst[c] for c in cl if c in cell_of_inst]
        for c in members:
            cell_nets[c].append(nid)
        # a net shared by hundreds of cells (reset, clock, enables) says nothing about
        # which block a cell belongs to; small nets say a lot
        if b is None or len(cl) > 64:
            continue
        wgt = (1.0 if len(cl) <= 8 else 8.0 / len(cl)) * (0.4 if b == BLOCK_ID["bus"] else 1.0)
        for c in members:
            votes[c][b] += wgt
    group = array("b", [-1] * ncell)
    for c in range(ncell):
        nm = cells_names[c]
        if nm.startswith("clkbuf_") or nm.startswith("clkload") or "delaybuf" in nm:
            group[c] = BLOCK_ID["cts"]
        elif re.match(r"(hold|input|output|wire|rebuffer|split|max_cap|max_length|fanout|place|ANTENNA|antenna|clone)", nm):
            group[c] = BLOCK_ID["opt"]
        elif votes[c]:
            group[c] = votes[c].most_common(1)[0][0]
    # propagate to cells that only touch anonymous nets
    for _ in range(12):
        changed = 0
        for c in range(ncell):
            if group[c] >= 0:
                continue
            v = Counter()
            for nid in cell_nets[c]:
                cl = net_cells[nid]
                if len(cl) > 24:
                    continue
                for o in cl:
                    oc = cell_of_inst.get(o)
                    if oc is not None and group[oc] >= 0 and group[oc] not in (BLOCK_ID["cts"], BLOCK_ID["opt"]):
                        v[group[oc]] += 1
            if v:
                group[c] = v.most_common(1)[0][0]; changed += 1
        if not changed:
            break
    for c in range(ncell):
        if group[c] < 0:
            group[c] = BLOCK_ID["bus"]
    area = Counter(); count = Counter()
    for c in range(ncell):
        r = cells_rect[4 * c:4 * c + 4]
        area[group[c]] += (r[2] - r[0]) * (r[3] - r[1]) / (Q * Q); count[group[c]] += 1

    # macros belong to blocks by name
    for m in macro_list:
        nm = m["name"].replace("\\", "")
        m["name"] = nm
        m["block"] = ("xip" if ".u_xip." in nm else "bus" if ".u_ram." in nm else None)
        m["label"] = ("Cache SRAM (512 x 8)" if ".u_xip." in nm else "Data SRAM (512 x 8)" if ".u_ram." in nm
                      else {"qrcode_id": "QR code", "shuttle_id": "Shuttle ID", "project_id": "Project ID",
                            "marker": "Alignment marker"}.get(nm, nm))

    # ---------------- pads: package pin and function ----------------
    padfile = json.load(open(a.pads)) if a.pads else {"pads": {}, "pins": []}
    pad_of_inst = {}
    for p in pads:
        nm = p["name"].replace("\\", "")
        pad_of_inst[inst_idx[p["name"]]] = p
        p["name"] = nm
        p["nets"] = []
        p.update(padfile["pads"].get(nm, {}))
    for nid, cl in enumerate(net_cells):
        if net_use[nid] != 2:
            for c in cl:
                if c in pad_of_inst:
                    pad_of_inst[c]["nets"].append(nid)

    # ---------------- nets: cell membership (CSR) ----------------
    ptr = array("I", [0]); mem = array("I")
    for nid, cl in enumerate(net_cells):
        for c in cl:
            k = cell_of_inst.get(c)
            if k is not None:
                mem.append(k)
        ptr.append(len(mem))

    order = ["Metal1", "Metal2", "Metal3", "Metal4", "Metal5"]
    out = {
        "meta": {"design": "chip_top", "q": Q, "die": [q(die[2] - die[0]), q(die[3] - die[1])],
                 "source": os.path.basename(a.deff), "note": a.note},
        "blocks": [{"id": b[0], "name": b[1], "desc": b[3], "cells": count.get(i, 0),
                    "area": round(area.get(i, 0.0))} for i, b in enumerate(BLOCKS)],
        "masters": master_names,
        "cells": {"n": ncell, "rect": b64(cells_rect), "master": b64(cells_master), "group": b64(group),
                  "names": cells_names},
        "phys": {"n": len(phys_rect) // 4, "rect": b64(phys_rect), "kinds": dict(phys_count)},
        "pads": pads, "macros": macro_list, "ring": {"n": len(ring_rect) // 4, "rect": b64(ring_rect)},
        "nets": {"names": nets, "use": b64(net_use), "ptr": b64(ptr), "mem": b64(mem)},
        "wires": [{"layer": L, "n": len(wires.net[L]), "rect": b64(wires.rect[L]), "net": b64(wires.net[L])}
                  for L in order if L in wires.rect],
        "vias": [{"layer": L, "n": len(via_net[L]), "xy": b64(vias[L]), "net": b64(via_net[L])}
                 for L in sorted(vias)],
        "pdn": [{"layer": L, "n": len(pdn.net[L]), "rect": b64(pdn.rect[L]), "net": b64(pdn.net[L])}
                for L in order if L in pdn.rect],
    }
    out["pins"] = padfile["pins"]
    if a.summary and os.path.exists(a.summary):
        out["summary"] = json.load(open(a.summary))
    if a.crop and os.path.exists(a.crop):
        out["crop"] = json.load(open(a.crop))
    json.dump(out, open(a.out, "w"), separators=(",", ":"))
    print("wrote %s (%.1f MB): wires %s, vias %s" % (
        a.out, os.path.getsize(a.out) / 1e6,
        {w["layer"]: w["n"] for w in out["wires"]}, {v["layer"]: v["n"] for v in out["vias"]}), file=sys.stderr)


if __name__ == "__main__":
    main()
