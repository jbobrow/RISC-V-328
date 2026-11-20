#!/bin/bash
# Gate-level simulation of the routed netlist from a LibreLane run, with cell delays.
#   scripts/gl_sim.sh <netlist.nl.v> <file.sdf> <pdk>/gf180mcuD [test] [clock period in ns]
# GLDIR sets the work directory (default build/gl).
# The SDF comes from scripts/gl_write_sdf.tcl. See scripts/gl_prep.py for what is and is
# not covered. Needs iverilog 12 or newer; about 15 minutes per test on one core.
set -e
cd "$(dirname "$0")/.."
nl=$1; sdf=$2; pdk=$3; t=${4:-basic}; per=${5:-50}
g=${GLDIR:-build/gl}; mkdir -p $g
python3 scripts/gl_prep.py "$nl" "$sdf" "$pdk" $g
scl=$(grep -o -m1 "gf180mcu_fd_sc_mcu[0-9]t5v0" "$nl")
cat > $g/stubs.v <<'S'
// cells without function that the netlist instantiates
module gf180mcu_fd_io__cor; endmodule
module gf180mcu_fd_io__fill1; endmodule
module gf180mcu_fd_io__fill5; endmodule
module gf180mcu_fd_io__fill10; endmodule
module gf180mcu_fd_io__fillnc; endmodule
module gf180mcu_ws_ip__qrcode_id; endmodule
module gf180mcu_ws_ip__shuttle_id; endmodule
module gf180mcu_ws_ip__project_id; endmodule
module gf180mcu_ws_ip__marker; endmodule
module rv328_analog_blank; endmodule
S
iverilog -g2012 -gspecify -DRV328_GL -DRV328_ANALOG_STUB -DRV328_GL_SDF=\"$g/cells.sdf\" -s tb -o $g/sim.vvp \
  tb/tb.v tb/spi_mem.v $g/netlist.v $g/stubs.v $g/cells.v $pdk/libs.ref/$scl/verilog/primitives.v \
  $g/io.v $g/sram.v 2>&1 | grep -v "warning\|sorry" | head -20
args=$(make -s -p -n 2>/dev/null | sed -n "s/^ARGS_$t := //p")
vvp -n $g/sim.vvp +firmware=build/$t.hex $args +extclk=$per +pinreset > $g/$t.log 2>&1 || true
echo "SDF messages: $(grep -c 'SDF ERROR' $g/$t.log) errors, $(grep -c 'TIMINGCHECK not supported' $g/$t.log) timing checks ignored"
grep 'SDF ERROR' $g/$t.log | sed 's/:[0-9]*:/:/; s/ in tb\.dut\..*//; s/[0-9]\+/N/g' | sort | uniq -c | sort -rn | head -5
grep -E "PASS|FAIL|TIMEOUT|FAULT" $g/$t.log || echo "no verdict (see $g/$t.log)"
