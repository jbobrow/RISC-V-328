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
# A layout with the analog macro itself (gen_floorplan_1x1.py --analog) instantiates rv328_analog with the
# layout's pin names, buses split into bits. Simulate it with the behavioural model behind a wrapper that has
# those pins. The testbench's hooks into the model (ADC voltages) stay off (RV328_ANALOG_STUB), as before.
: > $g/analog.v
if grep -q "^ *rv328_analog u_analog" $g/netlist.v; then
  sed 's/^module rv328_analog (/module rv328_analog_beh (/' rtl/analog/rv328_analog_model.v > $g/analog.v
  cat >> $g/analog.v <<'A'
`default_nettype wire
module rv328_analog (
	inout xtal1, xtal2, aref, avdd, vss, adc0, adc1, adc2, adc3, adc4, adc5, adc6, adc7, ain0, ain1,
	output clk_rc, clk_xa, clk_lf, por_n, bod_o, adc_cmp, ac_out,
	input rc_en, xo_en, bod_en, adc_en, adc_sample, ac_en, ac_bg, ac_mux_en,
	input rc_trim0, rc_trim1, rc_trim2, rc_trim3, rc_trim4, rc_trim5, rc_trim6, rc_trim7,
	input xo_mode0, xo_mode1, bod_level0, bod_level1, bod_level2, adc_mux0, adc_mux1, adc_mux2, adc_mux3,
	input adc_refs0, adc_refs1, adc_dac0, adc_dac1, adc_dac2, adc_dac3, adc_dac4, adc_dac5, adc_dac6,
	input adc_dac7, adc_dac8, adc_dac9);
	rv328_analog_beh m (.XTAL1(xtal1), .XTAL2(xtal2), .AREF(aref), .AVCC(avdd),
		.ADC({adc7, adc6, adc5, adc4, adc3, adc2, adc1, adc0}), .AIN0(ain0), .AIN1(ain1),
		.dig_clk_i(1'b0), .dig_rstn_i(1'b1), .clk_rc(clk_rc), .clk_xa(clk_xa), .clk_lf(clk_lf), .por_n(por_n),
		.bod_o(bod_o), .rc_en(rc_en), .rc_trim({rc_trim7, rc_trim6, rc_trim5, rc_trim4, rc_trim3, rc_trim2, rc_trim1, rc_trim0}),
		.xo_en(xo_en), .xo_mode({xo_mode1, xo_mode0}), .bod_en(bod_en), .bod_level({bod_level2, bod_level1, bod_level0}),
		.adc_en(adc_en), .adc_mux({adc_mux3, adc_mux2, adc_mux1, adc_mux0}), .adc_refs({adc_refs1, adc_refs0}),
		.adc_sample(adc_sample), .adc_dac({adc_dac9, adc_dac8, adc_dac7, adc_dac6, adc_dac5, adc_dac4, adc_dac3,
		adc_dac2, adc_dac1, adc_dac0}), .adc_cmp(adc_cmp), .ac_en(ac_en), .ac_bg(ac_bg), .ac_mux_en(ac_mux_en),
		.ac_out(ac_out));
endmodule
A
  echo "analog macro: behavioural model (rtl/analog/rv328_analog_model.v) behind its layout pins"
fi
iverilog -g2012 -gspecify -DRV328_GL -DRV328_ANALOG_STUB -DRV328_GL_SDF=\"$g/cells.sdf\" -s tb -o $g/sim.vvp \
  tb/tb.v tb/spi_mem.v $g/netlist.v $g/stubs.v $g/analog.v $g/cells.v $pdk/libs.ref/$scl/verilog/primitives.v \
  $g/io.v $g/sram.v 2>&1 | grep -v "warning\|sorry" | head -20
args=$(make -s -p -n 2>/dev/null | sed -n "s/^ARGS_$t := //p")
vvp -n $g/sim.vvp +firmware=build/$t.hex $args +extclk=$per +pinreset > $g/$t.log 2>&1 || true
echo "SDF messages: $(grep -c 'SDF ERROR' $g/$t.log) errors, $(grep -c 'TIMINGCHECK not supported' $g/$t.log) timing checks ignored"
grep 'SDF ERROR' $g/$t.log | sed 's/:[0-9]*:/:/; s/ in tb\.dut\..*//; s/[0-9]\+/N/g' | sort | uniq -c | sort -rn | head -5
grep -E "PASS|FAIL|TIMEOUT|FAULT" $g/$t.log || echo "no verdict (see $g/$t.log)"
