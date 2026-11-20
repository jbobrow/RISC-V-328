#!/usr/bin/env python3
"""Cache model on a fetch trace from the benchmark bench (+trace=..., 32 KB reference run).

  cache_model.py build/bench/run/<app>.trace [...]

Prints, per trace, the number of line fills between mark 1 and mark 2 for
direct-mapped and 2-way (least recently used) caches of 1 to 32 KB. Used to
check the RTL runs and to look at organisations the RTL does not implement.
"""
import sys

def load(path):
    seq, marks = [], {}
    for ln in open(path):
        if ln[0] == 'M':
            _, n, cyc = ln.split()
            marks[int(n)] = (len(seq), int(cyc))
        else:
            seq.append(int(ln, 16))
    return seq, marks

def fills(seq, lo, hi, kb, ways, pin=0):
    """Line fills between trace positions lo and hi. kb: cache size; ways: associativity
    (least recently used way replaced); pin: KB at the start of the image whose lines are
    never replaced once loaded (they live in the ordinary ways, as in rtl/rv328_xip.v)."""
    sets = kb * 1024 // 32 // ways
    cache = [[] for _ in range(sets)]
    n = 0
    for i, line in enumerate(seq[:hi]):
        s = cache[line % sets]
        if line in s:
            if ways > 1:
                s.remove(line); s.append(line)
        else:
            if i >= lo:
                n += 1
            if len(s) >= ways:
                k = 1 if (s[0] < pin * 32 and ways > 1) else 0
                s.pop(k)
            s.append(line)
    return n

if __name__ == '__main__':
    sizes = [1, 2, 4, 8, 16, 32]
    print('%-10s %-7s %s' % ('program', 'ways', ''.join('%9d KB' % k for k in sizes)))
    for path in sys.argv[1:]:
        seq, marks = load(path)
        lo, hi = marks[1][0], marks[2][0]
        name = path.split('/')[-1].replace('.trace', '')
        for ways in (1, 2):
            print('%-10s %-7s %s' % (name, ways, ''.join('%12d' % fills(seq, lo, hi, k, ways) for k in sizes)))
        print('%-10s lines touched in window: %d, clocks in window: %d' % (name, len(set(seq[lo:hi])), marks[2][1] - marks[1][1]))
