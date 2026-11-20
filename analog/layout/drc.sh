#!/bin/bash
# drc.sh <gds> <topcell> : foundry KLayout DRC (all decks except antenna, density and copper pillar);
# prints the number of violations per rule. Needs PDK_DIR (gf180mcuD) or PDK_ROOT (its parent).
P="${PDK_DIR:-$PDK_ROOT/gf180mcuD}"
klayout -b -zz -r $P/libs.tech/klayout/tech/drc/gf180mcu.drc -rd input=$1 -rd topcell=$2 -rd report=${1%.gds}_drc.lyrdb -rd variant=gf180mcuD -rd workers=2 -rd threads=1 -rd decks=all,-antenna,-density,-cup > ${1%.gds}_drc.log 2>&1
python3 - ${1%.gds}_drc.lyrdb <<'PY'
import re,sys,collections
s=open(sys.argv[1]).read()
c=collections.Counter(re.findall(r"<item>.*?<category>'?([^<']*)'?</category>",s,re.S))
print(sum(c.values()),"violations",dict(c))
PY
