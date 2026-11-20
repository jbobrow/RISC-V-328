#!/bin/bash
# lvs.sh <gds> <topcell> <schematic.spice> : magic DRC, extraction, netgen LVS.
# Needs PDK_DIR (gf180mcuD) or PDK_ROOT (its parent).
P="${PDK_DIR:-$PDK_ROOT/gf180mcuD}"; export PDK_ROOT="$(dirname "$P")" PDK=gf180mcuD
d=$(dirname $1); t=$2
cat > $d/$t.lvs.tcl <<T
# the foundry bipolar cell is a primitive in magic's library: keep that view instead of the GDS copy
load pnp_10p00x10p00
gds noduplicates true
gds read $1
load $t
select top cell
drc style drc(full)
drc euclidean on
drc check
drc catchup
puts "MAGIC_DRC [drc listall count total]"
foreach {msg boxes} [drc listall why] { puts "MAGIC_WHY [llength \$boxes] \$msg"; foreach b \$boxes { puts "MAGIC_BOX [cif scale out] \$b" } }
extract do local
extract all
ext2spice lvs
ext2spice -o $d/$t.ext.spice
quit -noprompt
T
(cd $d && magic -dnull -noconsole -rcfile $P/libs.tech/magic/gf180mcuD.magicrc $t.lvs.tcl > $t.magic.log 2>&1)
grep "MAGIC_" $d/$t.magic.log | grep -v "MAGIC_BOX"; grep "MAGIC_BOX" $d/$t.magic.log > $d/$t.drcboxes
# magic writes the foundry bipolar primitive with one node per pin label (nine: four on the collector,
# four on the base, one emitter). Reduce it to collector, base, emitter. Only valid where base and
# collector are the same net, which the script insists on.
python3 - $d/$t.ext.spice <<'PY'
import sys, re
text = open(sys.argv[1]).read().replace("\n+", "")
out = []
for line in text.splitlines():
    t = line.split()
    if t and t[0].startswith("X") and t[-1] == "pnp_10p00x10p00" and len(t) == 11:
        nodes = t[1:-1]
        rest = set(nodes[:2] + nodes[3:])
        assert len(rest) == 1, "bipolar with base and collector on different nets: " + line
        line = "%s %s %s %s pnp_10p00x10p00" % (t[0], nodes[0], nodes[0], nodes[2])
    out.append(line)
open(sys.argv[1], "w").write("\n".join(out) + "\n")
PY
(cd $d && netgen -batch lvs "$t.ext.spice $t" "$3 $t" $P/libs.tech/netgen/gf180mcuD_setup.tcl $t.lvs.rpt > $t.netgen.log 2>&1)
grep "Final result\|mismatch\|Netlists do not\|property errors" $d/$t.lvs.rpt | head -5
