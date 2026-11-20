#!/bin/bash
# Run firmware tests in simulation: scripts/runtests.sh [test ...]   (default: all)
cd "$(dirname "$0")/.."
tests=${@:-$(ls sw/tests/*.c | xargs -n1 basename | sed 's/\.c$//')}
make -s build/sim.vvp || exit 1
for t in $tests; do make -s build/$t.hex >/dev/null || { echo "[$t] BUILD FAILED"; continue; }; done
for t in $tests; do
  ( args=$(make -s -p -n 2>/dev/null | sed -n "s/^ARGS_$t := //p")
    vvp -n build/sim.vvp +firmware=build/$t.hex $args $SIMARGS 2>&1 | grep -E "PASS|FAIL|TIMEOUT|FAULT" | sed "s/^/[$t] /" ) &
done
wait
