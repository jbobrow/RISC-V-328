"""ADC front end: two conversions in a row, the second one read.

The main bench (adcfe.py) converts once from rest. Here the input makes a full-scale step between two
conversions, so the second shows what is left of the first after the 10 us of tracking: with a
10 kohm source the array and its top plate have to follow within that time. Each transition is
measured as in adcfe.py, with the capacitor array as extracted from its layout.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import run, table
import adcfe
TS, TH, TBIT = adcfe.TS, adcfe.TH, adcfe.TBIT

def trials_for(vin,vref):
    acc,tr,ex=0,[],[]
    for n in range(10):
        t=acc|(1<<(9-n)); tr.append(t); keep=vin>=t*vref/1024; ex.append(int(keep))
        if keep: acc=t
    return tr,ex
def convert2(k, kprev, vref, vdd, frac=0.5, track=10e-6, **kw):
    """Two conversions in a row; the second, of (k+frac) LSB, is the one read."""
    vin2=(k+frac)*vref/1024; vin1=(kprev+0.5)*vref/1024
    T1=TH+10*TBIT            # end of first conversion = start of second tracking
    TH2=T1+track
    tr1,_=trials_for(vin1,vref); tr2,ex=trials_for(vin2,vref)
    seq=[(TH+n*TBIT,t) for n,t in enumerate(tr1)]+[(TH2+n*TBIT,t) for n,t in enumerate(tr2)]
    codes=[]
    for b in range(10):
        pts,last=[],None
        for tm,t in seq:
            v=vdd if (t>>b)&1 else 0
            if last is None: pts.append("0 %g"%v)
            elif v!=last: pts.append("%.6g %g %.6g %g"%(tm,last,tm+10e-9,v))
            last=v
        codes.append("vd%d d%d 0 pwl(%s)"%(b,b," ".join(pts)))
    tb=adcfe.TB.replace("vin src 0 {vin}","vin src 0 pwl(0 %g %.6g %g %.6g %g)"%(vin1,T1-1e-6,vin1,T1-0.9e-6,vin2))
    tb=tb.replace("vs sample 0 pwl(0 0 {ts} 0 '{ts}+10n' {vdd} {th} {vdd} '{th}+10n' 0)","vs sample 0 pwl(0 0 {ts} 0 '{ts}+10n' {vdd} {th} {vdd} '{th}+10n' 0 %.6g 0 %.6g {vdd} %.6g {vdd} %.6g 0)"%(T1,T1+10e-9,TH2,TH2+10e-9))
    meas="\n".join("meas tran c%d find v(cmp) at=%.6g"%(n,TH2+(n+1)*TBIT-50e-9) for n in range(10))
    r=run(tb.format(vdd=vdd,vref=vref,vin=0,ts=TS,th=TH,tend=TH2+10*TBIT,codes="\n".join(codes),meas=meas),vdd=vdd,**kw)
    return [int(r.get("c%d"%n,-vdd)>vdd/2) for n in range(10)],ex
def threshold2(code,kprev,vref,vdd,steps=7,**kw):
    n=9-((code&-code).bit_length()-1); lo,hi=-1.0,1.0
    for _ in range(steps):
        f=(lo+hi)/2; got,_=convert2(code,kprev,vref,vdd,frac=f,**kw)
        if got[n]==1: hi=f
        else: lo=f
    return (lo+hi)/2

if __name__ == "__main__":
    # by default with the capacitor array as extracted; --layout: the whole front end as extracted (slower, fewer conditions)
    layout = "--layout" in sys.argv[1:]
    plan = ((5.0, 5.0, "tt", 25), (1.1, 5.0, "tt", 25), (2.7, 2.7, "ss", -40), (4.5, 4.5, "ss", 125), (1.1, 2.7, "ss", 125), (1.1, 5.5, "ff", 125))
    pex, steps = ("adccap",), 7
    if layout:
        from sim import LAYOUT_ADC
        plan, pex, steps = (plan[0], plan[4], plan[5]), LAYOUT_ADC, 6
        print("The whole front end as extracted from its layout.\n")
    rows = []
    for vref, vdd, corner, temp in plan:
        up = threshold2(1023, 20, vref, vdd, steps=steps, corner=corner, temp=temp, pex=pex)
        dn = threshold2(1, 1000, vref, vdd, steps=steps, corner=corner, temp=temp, pex=pex)
        rows.append(dict(vref=vref, vdd=vdd, corner=corner, temp=temp, up=up, dn=dn))
        sys.stderr.write("%s\n" % rows[-1])
    print(table(rows, [("vref", "Reference (V)", "%.1f"), ("vdd", "AVDD (V)", "%.1f"), ("corner", "Corner", "%s"), ("temp", "Temp (C)", "%d"),
                       ("up", "1022 / 1023 after a conversion of code 20 (LSB)", "%+.2f"), ("dn", "0 / 1 after a conversion of code 1000 (LSB)", "%+.2f")]))
