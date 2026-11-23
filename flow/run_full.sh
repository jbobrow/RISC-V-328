#!/usr/bin/env bash
# Full-height layout with the analog macro, start to sign-off, in one go.
#
#   flow/run_full.sh <tag> [options for scripts/gen_floorplan_1x1.py]
#
# Run from anywhere inside the LibreLane Nix shell, with PDK_ROOT pointing at the directory that holds
# gf180mcuD (flow/README.md, "Running it" and "On a Mac"). Writes runs/<tag>p (synthesis to power grid),
# runs/<tag> (placement to extraction) and runs/<tag>sta (sign-off timing) under flow/librelane, and
# prints the worst slack per corner at the end. Examples:
#
#   flow/run_full.sh mac1 --tags-center   # the best so far (run `tgc2`): -0.63 ns at the slowest corner only
#   flow/run_full.sh mac2                 # as run `and`: tag memories at the row ends, -1.48 ns
#   flow/run_full.sh mac3 --mulks         # pre-synthesised Kogge-Stone multiplier (run `mks`, not better)
#
# Steps: gen_floorplan_1x1.py --analog writes macros_1x1.yaml and full_1x1.yaml; LibreLane runs to the
# power grid; scripts/analog_straps.py draws the AVCC and ground straps and the thirteen analog lines into
# that database; LibreLane continues from there to parasitic extraction, then runs sign-off timing.
set -euo pipefail

TAG=${1:?usage: flow/run_full.sh <tag> [floorplan options]}
shift
: "${PDK_ROOT:?set PDK_ROOT to the directory that holds gf180mcuD}"
cd "$(dirname "$0")/librelane"
RUNS=$PWD/runs

python3 ../../scripts/gen_floorplan_1x1.py --analog "$@"

ARGS=(slot_1x1.yaml macros_1x1.yaml config.yaml full_1x1.yaml --pdk gf180mcuD --pdk-root "$PDK_ROOT" --manual-pdk
      --scl gf180mcu_fd_sc_mcu9t5v0 --pad gf180mcu_fd_io
      -S OpenROAD.STAPrePNR -S OpenROAD.STAMidPNR -S OpenROAD.STAMidPNR-1 -S OpenROAD.STAMidPNR-2 -S OpenROAD.STAMidPNR-3)
# On a machine with little disk, add: -c STA_THREADS=1 to the sign-off line below (one corner at a time).

echo "== $(date +%H:%M) synthesis to power grid: runs/${TAG}p"
librelane "${ARGS[@]}" --run-tag "${TAG}p" --to OpenROAD.GeneratePDN

PDN=$(ls -d "$RUNS/${TAG}p"/*-openroad-generatepdn | tail -1)
N=$(basename "$PDN"); LINES="$RUNS/${TAG}p/${N%%-*}b-analog-lines"
mkdir -p "$LINES"
echo "== $(date +%H:%M) analog straps and lines"
openroad -python -exit ../../scripts/analog_straps.py "$PDN/chip_top.odb" "$LINES/chip_top.odb" 2>&1 \
    | grep -E "strap|analog lines|no free|no room|would touch" || true
[ -f "$LINES/chip_top.odb" ] || { echo "analog_straps.py failed"; exit 1; }
python3 - "$PDN" "$LINES" <<'PY'
import json, sys
pdn, lines = sys.argv[1], sys.argv[2]
s = json.load(open(pdn + "/state_out.json"))
s["odb"] = lines + "/chip_top.odb"
json.dump(s, open(lines + "/state_out.json", "w"), indent=1)
PY

echo "== $(date +%H:%M) placement to extraction: runs/${TAG}"
librelane "${ARGS[@]}" --run-tag "$TAG" --from Odb.RemovePDNObstructions --to OpenROAD.RCX -i "$LINES/state_out.json"

RCX=$(ls -d "$RUNS/$TAG"/*-openroad-rcx | tail -1)
echo "== $(date +%H:%M) sign-off timing: runs/${TAG}sta"
librelane "${ARGS[@]}" --run-tag "${TAG}sta" --from OpenROAD.STAPostPNR --to OpenROAD.STAPostPNR -i "$RCX/state_out.json"

echo "== $(date +%H:%M) done"
python3 - "$RUNS/${TAG}sta" <<'PY'
import glob, os, sys
print("%-18s %10s %10s %10s %10s" % ("corner", "setup WS", "setup TNS", "hold WS", "hold TNS"))
for d in sorted(glob.glob(sys.argv[1] + "/*-openroad-stapostpnr/*_*C_*")):
    c = os.path.basename(d)
    def val(f):
        for line in open(os.path.join(d, f)):
            if line.startswith(c):
                return float(line.split()[1])
        return float("nan")
    print("%-18s %10.3f %10.2f %10.3f %10.2f" % (c, val("ws.max.rpt"), val("tns.max.rpt"), val("ws.min.rpt"), val("tns.min.rpt")))
PY
