#!/usr/bin/env python3
"""Summarise benchmark runs from build/bench/run/<app>.<config>.log.

  cache_report.py <app,app,...> <config,config,...> [reference config]

Per run: clocks between mark 1 and mark 2, ratio to the reference, line fills
in that window, interrupt latency (median / 95 % / longest, in clocks) and,
for the programs with the serial protocol, requests answered and bytes lost.
"""
import re, sys

def read(app, cfg):
    try:
        t = open('build/bench/run/%s.%s.log' % (app, cfg)).read()
    except OSError:
        return None
    m = {int(a): (int(c), int(f), int(v)) for a, c, f, v in re.findall(r'MARK (\d+) cyc=(\d+) fills=(\d+) acc=\d+ val=(\d+)', t)}
    if 1 not in m or 2 not in m or 'PASS' not in t:
        return {'bad': t.strip().split('\n')[-1][:40]}
    lat = sorted(int(x) for x in re.findall(r'IRQLAT (\d+)', t))
    r = {'clk': m[2][0] - m[1][0], 'fills': m[2][1] - m[1][1], 'lat': lat}
    if 3 in m:
        r['ok'], r['lost'] = m[2][2], m[3][2]
    return r

if __name__ == '__main__':
    apps, cfgs = sys.argv[1].split(','), sys.argv[2].split(',')
    ref = sys.argv[3] if len(sys.argv) > 3 else '16_2_0'
    for app in apps:
        base = read(app, ref)
        print('%s (reference %s: %d clocks)' % (app, ref, base['clk']))
        print('  %-9s %10s %6s %7s  %-20s %s' % ('config', 'clocks', 'ratio', 'fills', 'irq med/95%/max', 'serial'))
        for cfg in [ref] + [c for c in cfgs if c != ref]:
            r = read(app, cfg)
            if r is None: continue
            if 'bad' in r: print('  %-9s %s' % (cfg, r['bad'])); continue
            lat = r['lat']
            ls = '%d/%d/%d' % (lat[len(lat) // 2], lat[int(len(lat) * 0.95)], lat[-1]) if lat else '-'
            ser = ('%d answered, %d lost' % (r['ok'], r['lost'])) if 'ok' in r else ''
            print('  %-9s %10d %6.2f %7d  %-20s %s' % (cfg, r['clk'], r['clk'] / base['clk'], r['fills'], ls, ser))
