"""Small ngspice harness for the RV328 analog blocks.

  from sim import run, corners
  r = run(netlist, corner="tt", temp=25, vdd=5.0)     # -> dict of .meas results

PDK_ROOT must point at the directory that holds gf180mcuD. Every netlist gets the model
header, `.param vdd`, `.temp` and the block library (analog/blocks/*.spice) prepended.
With pex=True every block that has a layout is replaced by the netlist extracted from it;
pex=("bgr",) or the environment variable RV328_PEX=bgr,adccap does that for the blocks named.
"""
import glob
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PDK = os.environ.get("PDK_DIR") or os.path.join(os.environ.get("PDK_ROOT", ""), "gf180mcuD")
MODELS = os.path.join(PDK, "libs.tech", "ngspice")

# name -> (MOS section, passive suffix).  Passives follow the transistors: slow with slow.
CORNERS = {"tt": ("typical", "typical"), "ss": ("ss", "ss"), "ff": ("ff", "ff"),
           "sf": ("sf", "typical"), "fs": ("fs", "typical"),
           "tt_rcmax": ("typical", "ss"), "tt_rcmin": ("typical", "ff")}


PEX = {"adccap.spice": os.path.join(HERE, "layout", "rv328_adc_caparray_pex.spice"),
       "bgr.spice": os.path.join(HERE, "layout", "rv328_bgr_pex.spice"),
       "adccmp.spice": os.path.join(HERE, "layout", "rv328_adccmp_pex.spice"),
       "adcfe.spice": os.path.join(HERE, "layout", "rv328_adcfe_pex.spice"),
       "por.spice": os.path.join(HERE, "layout", "rv328_por_pex.spice"),
       "lfosc.spice": os.path.join(HERE, "layout", "rv328_lfosc_pex.spice"),
       "rcosc.spice": os.path.join(HERE, "layout", "rv328_rcosc_pex.spice"),
       "xosc.spice": os.path.join(HERE, "layout", "rv328_xosc_pex.spice"),
       "refbuf.spice": os.path.join(HERE, "layout", "rv328_refbuf_pex.spice"),
       "bod.spice": os.path.join(HERE, "layout", "rv328_bod_pex.spice"),
       "amux.spice": os.path.join(HERE, "layout", "rv328_amux_pex.spice"),
       "tsens.spice": os.path.join(HERE, "layout", "rv328_tsens_pex.spice"),
       # The comparator's layout is of its default bias setting (mt=2, the analog comparator). The brown-out
       # detector contains its own, drawn for mt=0.5, so "cmp" must not be chosen while "bod" is a schematic.
       "cmp.spice": os.path.join(HERE, "layout", "rv328_cmp_pex.spice"),
       # The macro itself ("macro"): its gates and switches and the wiring between the blocks, from the layout.
       # The blocks inside it are whichever of the above are chosen with it.
       "rv328_analog.spice": os.path.join(HERE, "layout", "rv328_analog_pex.spice")}

# The extracted front end contains its comparator; the array stays a cell of its own, so "the ADC as laid
# out" is these two together.
LAYOUT_ADC = ("adcfe", "adccap")


ENV_PEX = [b for b in os.environ.get("RV328_PEX", "").split(",") if b]     # e.g. RV328_PEX=bgr,adccap


def header(corner="tt", temp=25, vdd=5.0, mismatch=False, seed=1, pex=False):
    mos, pas = CORNERS[corner]
    lines = ['.include "%s/design.ngspice"' % MODELS,
             '.lib "%s/sm141064.ngspice" %s' % (MODELS, mos)]
    for kind in ("res", "mimcap", "bjt", "moscap", "diode"):
        lines.append('.lib "%s/sm141064.ngspice" %s_%s' % (MODELS, kind, pas))
    lines.append('.lib "%s/sm141064.ngspice" cap_mim' % MODELS)
    if mismatch:
        lines += [".param sw_stat_mismatch=1", ".option seed=%d" % seed]
    lines += [".param vdd=%g" % vdd, ".temp %g" % temp]
    # the foundry's standard cells, which blocks/logic.spice uses for plain gates
    lines.append('.include "%s"' % os.path.join(PDK, "libs.ref", "gf180mcu_fd_sc_mcu9t5v0", "spice", "gf180mcu_fd_sc_mcu9t5v0.spice"))
    for f in sorted(glob.glob(os.path.join(HERE, "blocks", "*.spice"))):
        name = os.path.basename(f)
        key = "macro" if name == "rv328_analog.spice" else name[:-6]
        if name in PEX and (pex is True or key in (pex or ()) or key in ENV_PEX):
            f = PEX[name]                           # the same cell, extracted from its layout
        lines.append('.include "%s"' % f)
    return "\n".join(lines) + "\n"


def run(netlist, corner="tt", temp=25, vdd=5.0, mismatch=False, seed=1, keep=None, timeout=1800, pex=False):
    """Run one batch simulation and return {measure name: float}. `keep` saves the deck there.
    pex=True uses the extracted netlists of the blocks that have a layout (see PEX)."""
    deck = "* rv328 analog\n" + header(corner, temp, vdd, mismatch, seed, pex) + netlist + "\n.end\n"
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "tb.spice")
        open(path, "w").write(deck)
        if keep:
            open(keep, "w").write(deck)
        # One thread per simulation, and run the benches one at a time: on the two-core machine this was
        # developed on, two simulations side by side each ran about 25 times slower than one alone.
        env = dict(os.environ, OMP_NUM_THREADS=os.environ.get("RV328_SPICE_THREADS", "1"))
        p = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True, cwd=d, timeout=timeout, env=env)
    out = p.stdout + p.stderr
    res = {}
    for m in re.finditer(r"^\s*([a-z_][a-z0-9_]*)\s*=\s*([-+0-9.eE]+)", out, re.M):
        try:
            res[m.group(1)] = float(m.group(2))
        except ValueError:
            pass
    if "failed" in out and not res:
        res["_error"] = out[-600:]
    res["_log"] = out
    return res


def table(rows, cols):
    """rows: list of dicts; cols: list of (key, heading, format)."""
    lines = ["| " + " | ".join(h for _, h, _ in cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        lines.append("| " + " | ".join((f % r[k]) if isinstance(r.get(k), (int, float)) else str(r.get(k, "-")) for k, _, f in cols) + " |")
    return "\n".join(lines)
