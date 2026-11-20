"""Size estimate of the analog block from its netlists: device area per block, and a to-scale picture.

Not a layout. Each device's drawn area is multiplied by a factor for what a layout adds around it
(contacts, wells, guard rings, spacing, local wiring). The factors are assumptions, stated in FACTOR:
they come from typical analog layout practice in this kind of process, not from this PDK's rule deck.

  python3 analog/floorplan.py            -> table on stdout, analog/results/floorplan.png
"""
import glob, os, re, sys, math

HERE = os.path.dirname(os.path.abspath(__file__))
UNITS = {"meg": 1e6, "k": 1e3, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}
# layout area per unit of drawn device area
FACTOR = {"mos": 3.0,      # gate area + source/drain (1.6 um added to L) then wells, guard ring, spacing
          "res": 1.0,      # 1 um strips: 1.74 um2 per um of strip measured on the reference's drawn resistor blocks (ring included)
          "cap": 2.0,      # 5 um units on a 7 um pitch
          "bjt": 1.0}      # 20 x 20 um per PNP cell including its ring
BLOCK_WIRING = 1.25        # routing channels inside a block
NAMES = {"xpor": "Power-on reset", "xlf": "128 kHz oscillator", "xbgr": "Reference", "xbod": "Brown-out detector", "xrc": "RC oscillator",
         "xxo": "Crystal oscillator", "xts": "Temperature sensor", "xmux": "Input multiplexer", "xrb": "Reference buffer", "xfe": "ADC front end",
         "xac": "Analog comparator"}

def num(s, env):
    s = s.strip().strip("'").lower()
    s = re.sub(r"(\d+(?:\.\d*)?|\.\d+)(meg|k|m|u|n|p|f)\b", lambda m: "(%s*%g)" % (m.group(1), UNITS[m.group(2)]), s)
    return float(eval(s, {"__builtins__": {}}, env))

def load():
    subs = {}
    for f in sorted(glob.glob(os.path.join(HERE, "blocks", "*.spice"))):
        cur, pend = None, ""
        for raw in open(f):
            line = raw.rstrip("\n")
            if line.startswith("+"):
                pend += " " + line[1:]; continue
            for l in ([pend] if pend else []):
                cur = feed(l, subs, cur)
            pend = line
        if pend: cur = feed(pend, subs, cur)
    return subs

def feed(l, subs, cur):
    t = l.split()
    if not t or l.startswith("*"): return cur
    if t[0].lower() == ".subckt":
        cur = dict(name=t[1], params={}, lines=[])
        for x in t[2:]:
            if "=" in x: k, v = x.split("=", 1); cur["params"][k.lower()] = v
        subs[t[1]] = cur
    elif t[0].lower() == ".ends": cur = None
    elif cur is not None:
        if t[0].lower() == ".param":
            for x in t[1:]:
                k, v = x.split("=", 1); cur["params"][k.lower()] = v
        elif t[0][0].lower() == "x": cur["lines"].append(l)
    return cur

def walk(subs, name, over, mult, acc, path):
    sub = subs[name]
    env = {}
    for k, v in sub["params"].items():
        env[k] = num(v, env)
    env.update(over)
    for l in sub["lines"]:
        toks = re.findall(r"(?:[^\s']+|'[^']*')+", l)
        pos = [x for x in toks[1:] if "=" not in x]
        par = dict(x.split("=", 1) for x in toks[1:] if "=" in x)
        model = pos[-1]
        p = {k.lower(): num(v, env) for k, v in par.items()}
        m = mult * p.get("m", 1) * p.get("mul", 1) if model in subs else mult * p.get("m", 1)
        key = path or toks[0].lower()
        if model in subs:
            sub_over = {k: v for k, v in p.items() if k != "m"}
            walk(subs, model, sub_over, mult * p.get("m", 1), acc, key)
        elif model.startswith(("nfet", "pfet")):
            acc.setdefault(key, {}).setdefault("mos", 0); acc[key]["mos"] += m * p["w"] * (p["l"] + 1.6e-6)
        elif model.startswith("ppolyf"):
            acc.setdefault(key, {}).setdefault("res", 0); acc[key]["res"] += m * p.get("s", 1) * p["r_length"] * 1.8e-6
        elif model.startswith("cap_mim"):
            acc.setdefault(key, {}).setdefault("cap", 0); acc[key]["cap"] += m * p["c_width"] * p["c_length"]
        elif model.startswith("pnp"):
            acc.setdefault(key, {}).setdefault("bjt", 0); acc[key]["bjt"] += m * 400e-12

def estimate():
    subs = load(); acc = {}
    walk(subs, "rv328_analog", {}, 1, acc, None)
    rows = []
    for key, d in acc.items():
        a = BLOCK_WIRING * sum(FACTOR[k] * v for k, v in d.items()) * 1e12
        rows.append(dict(key=key, name=NAMES.get(key, "glue"), um2=a, **{k: v * 1e12 for k, v in d.items()}))
    glue = sum(r["um2"] for r in rows if r["name"] == "glue")
    rows = [r for r in rows if r["name"] != "glue"] + [dict(key="glue", name="Top-level switches and logic", um2=glue)]
    return sorted(rows, key=lambda r: -r["um2"])

def draw(rows, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    INK, INK2, GRID, SURF, FILL, EDGE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb", "#dbe7f7", "#2a78d6"
    total = sum(r["um2"] for r in rows)
    width = 700.0                                  # um: a strip that would sit along one side of the core
    # shelf packing, largest first
    x = y = shelf = 0.0; placed = []
    for r in rows:
        h = max(60.0, math.sqrt(r["um2"] / 1.6)); w = r["um2"] / h
        if x + w > width and x > 0: x, y, shelf = 0.0, y + shelf + 8, 0.0
        placed.append((r, x, y, w, h)); x += w + 8; shelf = max(shelf, h)
    height = y + shelf
    fig, ax = plt.subplots(figsize=(12, 12 * (height + 150) / (width + 60)), dpi=200)
    fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
    small, x_end = [], 0.0
    for r, px, py, w, h in placed:
        yy = height - py - h                      # largest block at the top
        ax.add_patch(Rectangle((px, yy), w, h, facecolor=FILL, edgecolor=EDGE, linewidth=1.2))
        if w > 110:
            ax.text(px + w / 2, yy + h / 2, "%s\n%.3f mm2" % (r["name"], r["um2"] / 1e6), ha="center", va="center", fontsize=8.5, color=INK)
        else:                                     # too narrow for its name: a letter, explained beside the row
            letter = "ABCDEF"[len(small)]; small.append((letter, r, yy, h)); x_end = max(x_end, px + w)
            ax.text(px + w / 2, yy + h / 2, letter, ha="center", va="center", fontsize=8.5, fontweight="bold", color=INK)
    for i, (letter, r, yy, h) in enumerate(small):
        ax.text(x_end + 14, small[0][2] + small[0][3] - 6 - i * 20, "%s  %s, %.3f mm2" % (letter, r["name"], r["um2"] / 1e6), ha="left", va="top", fontsize=8.5, color=INK)
    ax.plot([0, 100], [-22, -22], color=INK2, linewidth=2); ax.text(50, -30, "100 um", ha="center", va="top", fontsize=8, color=INK2)
    ax.set_xlim(-20, width + 20); ax.set_ylim(-70, height + 40); ax.set_aspect("equal"); ax.axis("off")
    ax.text(0, height + 14, "RV328 analog block: estimated size by block, to scale (%.2f mm2 in total; an estimate from device areas, not a layout)"
            % (total / 1e6), fontsize=10.5, fontweight="bold", color=INK, va="bottom")
    fig.savefig(out, bbox_inches="tight", facecolor=SURF)
    return width, height

if __name__ == "__main__":
    rows = estimate()
    print("| Block | Transistors (um2 drawn) | Resistors (um2) | Capacitors (um2) | Bipolars (um2) | Estimated layout area (mm2) |\n|---|---|---|---|---|---|")
    for r in rows:
        print("| %s | %s | %s | %s | %s | %.4f |" % (r["name"], *("%.0f" % r[k] if k in r else "-" for k in ("mos", "res", "cap", "bjt")), r["um2"] / 1e6))
    total = sum(r["um2"] for r in rows)
    print("\nTotal: %.2f mm2 (a square of %.0f um). Factors applied to drawn area: transistors x%.1f, resistors x%.1f, capacitors x%.1f, then x%.2f for wiring inside each block."
          % (total / 1e6, math.sqrt(total), FACTOR["mos"], FACTOR["res"], FACTOR["cap"], BLOCK_WIRING))
    if "--no-plot" not in sys.argv:
        draw(rows, os.path.join(HERE, "results", "floorplan.png"))
