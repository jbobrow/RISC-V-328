#!/usr/bin/env python3
"""Processor-only comparison: the benchmark programs built without peripherals
(sw/bench/hal_null.c), on RV328 configurations and on an ATmega328P in simavr.
Prints clocks between the marks and the speed relative to the ATmega; checks
that every run ended with the same result value."""
import re, sys
CFG = [('2_1_0_0', '2 KB today'), ('4_3_2_0', '12 KB 3-way'), ('4_3_2_1', '12 KB + fast mult.'),
       ('16_2_0_1', 'all cached + fast mult.'), ('16_2_0_0', 'all cached')]
def win(path):
    t = open(path).read()
    m = dict((int(a), (int(c), int(v))) for a, c, v in re.findall(r'MARK (\d+) cyc=(\d+).*?val=(\d+)', t))
    return m[2][0] - m[1][0], m[2][1]
print('%-9s %9s | %s' % ('program', 'ATmega', '  '.join('%-23s' % n for _, n in CFG)))
for a in ['blink', 'display', 'comms', 'logger', 'full']:
    av, vv = win('build/bench/run/avr_%s.log' % a)
    row = []
    for c, _ in CFG:
        r, v = win('build/bench/run/%s_null.%s.log' % (a, c))
        assert v == vv, (a, c, v, vv)
        row.append('%9d (%5.2fx)       ' % (r, av / r))
    print('%-9s %9d | %s' % (a, av, '  '.join(row)))
for c, n in CFG:
    r, _ = win('build/bench/run/coremark.%s.log' % c)
    print('CoreMark, %-24s %8d clocks for 10 iterations = %.2f CoreMark/MHz' % (n, r, 10e6 / r))
