#!/usr/bin/env python3
"""Summarise a LibreLane run as Markdown: scripts/flow_report.py <run dir> > results.md"""
import glob, json, os, sys

run = sys.argv[1]
f = os.path.join(run, "final", "metrics.json")
if not os.path.exists(f):
    f = sorted(glob.glob(os.path.join(run, "*", "state_out.json")))[-1]
m = json.load(open(f))
m = m.get("metrics", m)
# timing, electrical checks and power come from the sign-off timing step, not from whichever step ran last
sta = sorted(glob.glob(os.path.join(run, "*-openroad-stapostpnr", "state_out.json")))
if sta:
    sm = json.load(open(sta[-1])); sm = sm.get("metrics", sm)
    m = {k: v for k, v in m.items() if not (k.startswith("timing__") or k.startswith("power__") or "violation__count" in k)}
    m.update({k: v for k, v in sm.items() if k.startswith("timing__") or k.startswith("power__") or "violation__count" in k})
m = m.get("metrics", m)
# results of checks that were run outside the main flow: KEY=VALUE arguments after the run directory
for kv in sys.argv[2:]:
    k, _, v = kv.partition("=")
    m[k] = int(v) if v.lstrip("-").isdigit() else v
period = float(json.load(open(os.path.join(run, "resolved.json")))["CLOCK_PERIOD"])
g = m.get

print("| Quantity | Value |\n|---|---|")
rows = [
    ("Die", "%.0f x %.0f um" % tuple(float(v) for v in str(g("design__die__bbox", "0 0 0 0")).split()[2:4])),
    ("Standard cells (incl. buffers, fill, taps)", "%d" % g("design__instance__count__stdcell", 0)),
    ("Standard-cell area", "%.2f mm2" % (g("design__instance__area__stdcell", 0) / 1e6)),
    ("Core utilisation (standard cells)", "%.0f %%" % (100 * g("design__instance__utilization__stdcell", 0))),
    ("Routed wire length", "%.2f m" % (g("route__wirelength", 0) / 1e6)),
    ("Vias", "%d" % g("route__vias", 0)) if g("route__vias") else None,
    ("Routing DRC violations", "%d" % g("route__drc_errors", -1)),
    ("Antenna violations (nets / pins)", "%s / %s" % (g("antenna__violating__nets", "-"), g("antenna__violating__pins", "-"))),
    ("Clock target", "%.0f ns (%.1f MHz)" % (period, 1000 / period)),
    ("Setup violations (endpoints, all corners)", "%s" % g("timing__setup_vio__count", "-")),
    ("Hold violations (endpoints, all corners)", "%s" % g("timing__hold_vio__count", "-")),
    ("Max slew / capacitance / fan-out violations", "%s / %s / %s" % (g("design__max_slew_violation__count", "-"),
        g("design__max_cap_violation__count", "-"), g("design__max_fanout_violation__count", "-"))),
    ("Power estimate (default activity)", "%.1f mW" % (1000 * g("power__total", 0))),
    ("Magic DRC errors", "%s" % g("magic__drc_error__count")) if g("magic__drc_error__count") is not None else None,
    ("KLayout DRC errors (foundry deck)", "%s" % g("klayout__drc_error__count")) if g("klayout__drc_error__count") is not None else None,
    ("LVS", "%s" % g("design__lvs_error__count")) if g("design__lvs_error__count") is not None else None,
    ("Unmatched devices / nets (LVS)", "%s / %s" % (g("design__lvs_device_difference__count", "-"), g("design__lvs_net_difference__count", "-")))
        if g("design__lvs_device_difference__count") is not None else None,
]
for r in rows:
    if r:
        print("| %s | %s |" % r)

corners = sorted({k.split(":")[-1] for k in m if k.startswith("timing__setup__ws__corner:")})
if corners:
    print("\n| Corner | Setup slack (ns) | Implied max clock (MHz) | Hold slack (ns) |\n|---|---|---|---|")
    for c in corners:
        s = m["timing__setup__ws__corner:" + c]; h = m.get("timing__hold__ws__corner:" + c, float("nan"))
        print("| %s | %+.2f | %.1f | %+.2f |" % (c, s, 1000 / (period - s), h))
