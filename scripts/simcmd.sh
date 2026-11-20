#!/bin/bash
# Compile the testbench with optional extra files/flags: scripts/simcmd.sh out.vvp [extra args]
# ANALOG=<file> selects the analog view (default: behavioural model)
out=$1; shift
H3=vendor/hazard3/hdl
iverilog -g2012 -I $H3 -o $out -s tb "$@" tb/tb.v tb/spi_mem.v ${ANALOG:-rtl/analog/rv328_analog_model.v} \
  rtl/tech/rv328_tech.v rtl/periph/*.v rtl/rv328_xip.v rtl/rv328_clkrst.v rtl/rv328_core.v rtl/rv328_chip_top.v \
  $H3/hazard3_core.v $H3/hazard3_cpu_1port.v $H3/arith/*.v $H3/hazard3_csr.v $H3/hazard3_decode.v \
  $H3/hazard3_frontend.v $H3/hazard3_instr_decompress.v $H3/hazard3_irq_ctrl.v $H3/hazard3_pmp.v \
  $H3/hazard3_power_ctrl.v $H3/hazard3_regfile_1w2r.v $H3/hazard3_triggers.v $H3/debug/dm/hazard3_dm.v \
  $H3/debug/dtm/hazard3_jtag_dtm.v $H3/debug/dtm/hazard3_jtag_dtm_core.v $H3/debug/cdc/*.v \
  vendor/gf180mcu/io/*.v 2>&1 | grep -v "warning\|sorry" | head -20
