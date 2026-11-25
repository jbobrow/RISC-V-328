"""Give the strap script's vias (rv328_*) a generate rule in an existing database and write it out again.

Databases made before scripts/analog_straps.py named the rule carry these vias as plain rectangle lists, which
Magic's DEF reader streams out with a stray Metal4-Via4-Metal5 stack at each via's centre. The geometry is
not changed. Usage: openroad -python -exit scripts/via_rules.py <in.odb> <out prefix>  (writes .odb and .def)
"""
import sys, odb
from openroad import Tech, Design
src, dst = sys.argv[-2], sys.argv[-1]
t=Tech(); d=Design(t); d.readDb(src); b=d.getBlock(); tech=d.getTech().getDB().getTech()
n=0
for v in b.getVias():
    if v.getName().startswith("rv328_") and v.hasParams() and v.getViaGenerateRule() is None:
        cut=v.getViaParams().getCutLayer().getName()
        v.setViaGenerateRule(tech.findViaGenerateRule(cut+"_GEN_HH")); n+=1
print("vias given a generate rule:", n)
d.writeDb(dst+".odb")
odb.write_def(b, dst+".def")
