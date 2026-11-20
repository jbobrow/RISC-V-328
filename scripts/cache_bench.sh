#!/bin/bash
# Run one benchmark program on one cache configuration (compiled simulation).
#   cache_bench.sh <app> <KB per way>_<ways>_<pinned KB>[_<fast multiplier 0/1>] [extra simulator args]
# Output: build/bench/run/<app>.<config>.log (and .trace for the 16_2_0 reference run)
set -e
cd "$(dirname "$0")/.."
app=$1; kb=$2; shift 2
args=""
case $app in
	comms)    args="+wiring=1" ;;
	full)     args="+wiring=1 +irqprobe=400" ;;
	coremark|*_null) ;;
	*)        args="+irqprobe=400" ;;
esac
[ "$kb" = 16_2_0 ] && args="$args +trace=build/bench/run/$app.trace"
mkdir -p build/bench/run
make -s build/vl_$kb/Vbench_top build/bench/$app.hex > /dev/null
build/vl_$kb/Vbench_top +firmware=build/bench/$app.hex $args "$@" | grep -v "Verilog .finish" > build/bench/run/$app.$kb.log
