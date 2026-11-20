#!/bin/bash
# Full regression: all firmware tests on the generic build, a subset against
# the foundry SRAM model and on the digital-first build, elaboration, synthesis estimate.
cd "$(dirname "$0")/.."
{
echo "== RTL tests (behavioural RAM, PDK pad models, analog model)"
SIMARGS=${SIMARGS:-} scripts/runtests.sh 2>&1 | grep "^\[" | sort
  echo "== Subset against the foundry SRAM macro model"
  scripts/simcmd.sh build/sim_gf.vvp -DRV328_TECH_GF180 -DRV328_GENERIC_ICG -DRV328_SIM_SRAM_HOLD \
    vendor/gf180mcu/sram/gf180mcu_fd_ip_sram__sram512x8m8wm1.v
  for t in basic nvm timers; do
    args=$(make -s -p -n 2>/dev/null | sed -n "s/^ARGS_$t := //p")
    vvp -n build/sim_gf.vvp +firmware=build/$t.hex $args 2>&1 | grep -E "PASS|FAIL|TIMEOUT|FAULT" | sed "s/^/[$t, foundry SRAM] /"
  done
echo "== Digital-first build (analog stub, external 8 MHz clock, reset pulse on PC6)"
ANALOG=rtl/analog/rv328_analog_stub.v scripts/simcmd.sh build/sim_stub.vvp -DRV328_ANALOG_STUB
for t in basic timers spi; do
  args=$(make -s -p -n 2>/dev/null | sed -n "s/^ARGS_$t := //p")
  vvp -n build/sim_stub.vvp +firmware=build/$t.hex $args +extclk=125 +pinreset 2>&1 | grep -E "PASS|FAIL|TIMEOUT|FAULT" | sed "s/^/[$t, digital-first] /"
done
echo "== Chip elaboration (pads + core + analog stub)"
make -s elab 2>&1 | grep -c "ERROR" | sed 's/^/errors: /'
echo "== Synthesis estimate (needs build/sc7_tt.lib, see flow/README.md)"
[ -f build/sc7_tt.lib ] && make -s synth 2>&1 | grep -E "cells|Chip area" | tail -2
} | tee build/regress.log
