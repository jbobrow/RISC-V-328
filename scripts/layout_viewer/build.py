#!/usr/bin/env python3
"""Build the self-contained layout viewer from a LibreLane run directory.

    scripts/layout_viewer/build.py <run dir> [--pdk <gf180mcuD dir>] [--out layout_viewer.html]
                                   [--crop x1,y1,x2,y2] [--stage <step dir>]

Needs only Python for the 2D views. The 3D process view needs KLayout on PATH
(to cut a window out of the GDS); without it that tab stays empty.
"""
import argparse, glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")


def newest(run, pattern):
    hits = sorted(glob.glob(os.path.join(run, pattern)))
    return hits[-1] if hits else None


def summarise(run, metrics, sta_run=None):
    """Pick the handful of numbers worth showing from LibreLane's metrics."""
    g = metrics.get
    chips, facts = [], []
    period = 50.0
    try:
        period = float(json.load(open(os.path.join(sta_run or run, "resolved.json")))["CLOCK_PERIOD"])
    except Exception:
        pass
    ws = {k.split(":")[-1]: v for k, v in metrics.items() if k.startswith("timing__setup__ws__corner:")}
    hs = {k.split(":")[-1]: v for k, v in metrics.items() if k.startswith("timing__hold__ws__corner:")}
    if ws:
        corner, slack = min(ws.items(), key=lambda kv: kv[1])
        fmax = 1000.0 / (period - slack)
        chips.append({"label": "setup slack", "value": "%+.1f ns" % slack, "cls": "good" if slack >= 0 else "bad"})
        chips.append({"label": "max clock", "value": "%.1f MHz" % fmax, "cls": "good" if slack >= 0 else "warn"})
        facts.append(["clock target", "%.0f ns (%.1f MHz)" % (period, 1000.0 / period)])
        facts.append(["worst setup slack", "%+.2f ns at %s" % (slack, corner)])
        facts.append(["implied max clock", "%.1f MHz" % fmax])
    if hs:
        corner, slack = min(hs.items(), key=lambda kv: kv[1])
        facts.append(["worst hold slack", "%+.2f ns at %s" % (slack, corner)])
    for key, label, fmt in [("design__instance__count__stdcell", "standard cells", "%d"),
                            ("design__instance__area__stdcell", "standard-cell area", "%.0f um2"),
                            ("design__instance__utilization__stdcell", "core utilisation", None),
                            ("route__wirelength", "routed wire", None),
                            ("route__drc_errors", "routing DRC errors", "%d"),
                            ("klayout__drc_error__count", "KLayout DRC errors", "%d"),
                            ("magic__drc_error__count", "Magic DRC errors", "%d"),
                            ("design__lvs_error__count", "LVS errors", "%d"),
                            ("antenna__violating__nets", "antenna violations (nets)", "%d")]:
        v = g(key)
        if v is None:
            continue
        if key.endswith("utilization__stdcell"):
            facts.append([label, "%.1f %%" % (100 * v)])
        elif key == "route__wirelength":
            facts.append([label, "%.2f m" % (v / 1e6)])
        else:
            facts.append([label, fmt % v])
    for key, label in [("route__drc_errors", "route DRC"), ("magic__drc_error__count", "Magic DRC"),
                       ("klayout__drc_error__count", "KLayout DRC"), ("design__lvs_error__count", "LVS")]:
        if g(key) is not None:
            chips.append({"label": label, "value": "%d" % g(key), "cls": "good" if g(key) == 0 else "bad"})
    return {"chips": chips, "facts": facts}


def critical_path(run, corner):
    """Instances along the worst setup path, from the newest post-route STA report."""
    rpt = newest(run, "*-openroad-stapostpnr/%s/max.rpt" % corner) or newest(run, "*-openroad-sta*/%s/max.rpt" % corner)
    if not rpt:
        return None
    names, start, end, slack = [], "", "", ""
    for line in open(rpt, errors="replace"):
        if line.startswith("Startpoint:"):
            if names:
                break
            start = line.split()[1]
        elif line.startswith("Endpoint:"):
            end = line.split()[1]
        elif start:
            m = re.search(r"[\^v] (\S+)/\S+ \(", line)
            if m and (not names or names[-1] != m.group(1)):
                names.append(m.group(1))
            m = re.search(r"(-?\d+\.\d+)\s+slack", line)
            if m:
                slack = "%+.2f ns" % float(m.group(1)); break
    # keep the data path only: from the launching flop to the end
    if start in names:
        names = names[names.index(start):]
    if end in names:
        names = names[:names.index(end) + 1]
    return {"names": names, "start": start, "end": end, "slack": slack, "corner": corner,
            "text": "The chain of gates with the least timing margin in this layout. Signals leave the first "
                    "flip-flop on a clock edge and must settle at the last one before the next edge."}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--pdk", default=os.environ.get("PDK_DIR", ""))
    ap.add_argument("--out", default=os.path.join(ROOT, "layout_viewer.html"))
    ap.add_argument("--crop", default="")
    ap.add_argument("--stage", default="")
    ap.add_argument("--headline", default="")
    ap.add_argument("--caveat", default="")
    ap.add_argument("--sta", default="", help="run directory of a separate sign-off timing run (its clock period, "
                    "timing metrics and slowest path replace those of the main run)")
    ap.add_argument("--chip", action="append", default=[], metavar="LABEL=VALUE[:good|warn|bad]",
                    help="add or replace a status chip, for results that come from a separate run")
    ap.add_argument("--fact", action="append", default=[], metavar="LABEL=VALUE", help="add or replace a summary row")
    ap.add_argument("--inline-three", default="", help="directory holding three.min.js and OrbitControls.js (offline use)")
    a = ap.parse_args()

    run = a.run
    deff = (newest(run, os.path.join(a.stage, "*.def")) if a.stage else None) or newest(run, "final/def/*.def") \
        or newest(run, "*-openroad-detailedrouting/*.def") or newest(run, "*-openroad-*/*.def")
    gds = newest(run, "final/gds/*.gds") or newest(run, "*-klayout-streamout/*.gds") or newest(run, "*streamout*/*.gds")
    mfile = newest(run, "final/metrics.json") or newest(run, "*/state_out.json")
    metrics = {}
    if mfile:
        metrics = json.load(open(mfile))
        metrics = metrics.get("metrics", metrics)
    build = os.path.join(ROOT, "build", "viewer"); os.makedirs(build, exist_ok=True)

    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import gen_padring
    json.dump(gen_padring.pad_info(), open(os.path.join(build, "pads.json"), "w"))
    sta_run = a.sta or run
    if a.sta:
        sf = newest(a.sta, "*-openroad-stapostpnr/state_out.json")
        sm = json.load(open(sf)); sm = sm.get("metrics", sm)
        metrics = {k: v for k, v in metrics.items() if not k.startswith("timing__") and "violation__count" not in k}
        metrics.update({k: v for k, v in sm.items() if k.startswith("timing__") or "violation__count" in k})
    summary = summarise(run, metrics, a.sta or None)
    ws = {k.split(":")[-1]: v for k, v in metrics.items() if k.startswith("timing__setup__ws__corner:")}
    if ws:
        cp = critical_path(sta_run, min(ws.items(), key=lambda kv: kv[1])[0])
        if cp and len(cp["names"]) > 1:
            summary["critical"] = cp
    for spec in a.chip:
        label, _, rest = spec.partition("=")
        value, _, cls = rest.rpartition(":") if rest.rsplit(":", 1)[-1] in ("good", "warn", "bad") else (rest, "", "")
        summary["chips"] = [c for c in summary["chips"] if c["label"] != label] + [{"label": label, "value": value, "cls": cls}]
    for spec in a.fact:
        label, _, value = spec.partition("=")
        summary["facts"] = [f for f in summary["facts"] if f[0] != label] + [[label, value]]
    summary["headline"] = a.headline
    summary["caveat"] = a.caveat
    json.dump(summary, open(os.path.join(build, "summary.json"), "w"))

    crop = os.path.join(build, "crop.json")
    if a.crop and gds:
        subprocess.run(["klayout", "-b", "-r", os.path.join(HERE, "crop_gds.py"), "-rd", "gds=" + gds,
                        "-rd", "box=" + a.crop, "-rd", "out=" + crop], check=True)
        c = json.load(open(crop))
        c["source"] = os.path.basename(gds)
        c["caption"] = ("A %.0f x %.0f um window cut from the real layout at (%s) um: a few rows of standard cells "
                        "and all the wiring above them, drawn to scale from the GDS file that would go to the foundry."
                        % (c["w"], c["h"], ", ".join(a.crop.split(",")[:2])))
        json.dump(c, open(crop, "w"), separators=(",", ":"))

    lefs = []
    if a.pdk:
        scl = "gf180mcu_fd_sc_mcu7t5v0"
        try:
            scl = json.load(open(os.path.join(run, "resolved.json")))["STD_CELL_LIBRARY"]
        except Exception:
            pass
        lefs += [os.path.join(a.pdk, "libs.ref/%s/techlef/*nom.tlef" % scl),
                 os.path.join(a.pdk, "libs.ref/%s/lef/*.lef" % scl),
                 os.path.join(a.pdk, "libs.ref/gf180mcu_fd_io/lef/*.lef"),
                 os.path.join(a.pdk, "libs.ref/gf180mcu_fd_ip_sram/lef/*.lef")]
    lefs.append(os.path.join(ROOT, "flow/librelane/ip/*/lef/*.lef"))
    layout = os.path.join(build, "layout.json")
    cmd = [sys.executable, os.path.join(HERE, "extract.py"), "--def", deff, "--pads", os.path.join(build, "pads.json"),
           "--summary", os.path.join(build, "summary.json"), "--out", layout]
    if os.path.exists(crop):
        cmd += ["--crop", crop]
    for l in lefs:
        cmd += ["--lef", l]
    subprocess.run(cmd, check=True)

    data = open(layout).read().replace("</", "<\\/")
    html = open(os.path.join(HERE, "viewer.template.html")).read().replace("/*DATA*/", data, 1)
    if a.inline_three:
        for url, fn in [("https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js", "three.min.js"),
                        ("https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js", "OrbitControls.js")]:
            html = html.replace('<script src="%s"></script>' % url,
                                "<script>" + open(os.path.join(a.inline_three, fn)).read().replace("</script", "<\\/script") + "</script>")
    open(a.out, "w").write(html)
    print("wrote %s (%.1f MB) from %s" % (a.out, os.path.getsize(a.out) / 1e6, deff))


if __name__ == "__main__":
    main()
