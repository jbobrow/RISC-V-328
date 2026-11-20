# RV328 timing constraints (digital-first build: analog stub, external clock).
#
# Clocks
#   clk_ext   external clock on PB6/XTAL1; feeds clk_rc (stub) and clk_x (mux input 1),
#             and through the glitch-free mux and clock gates the whole system
#   clk_lf    PB6 / 64, generated in the analog stub: watchdog and LF system clock
#   tck       JTAG test clock
# With the real analog macro, replace clk_ext/clk_lf by clocks on the macro's
# clk_rc, clk_xa and clk_lf pins and declare them asynchronous to each other.
current_design $::env(DESIGN_NAME)
set_units -time ns

set period $::env(CLOCK_PERIOD)
create_clock -name clk_ext -period $period [get_pins pad_pb6/Y]
# The divided clock starts at a dedicated buffer (rv328_clkbuf in the analog stub): a clock
# rooted directly on a flip-flop output crashes OpenROAD's clock-tree synthesis.
create_clock -name clk_lf -period [expr $period * 64] [get_pins u_analog.u_lfbuf.u_buf/Z]
create_clock -name tck -period 100 [get_pins pad_tck/Y]

# Watchdog, system and JTAG domains only talk through synchronisers
set_clock_groups -asynchronous -group {clk_ext} -group {clk_lf} -group {tck}

set_clock_uncertainty $::env(CLOCK_UNCERTAINTY_CONSTRAINT) [all_clocks]
set_clock_transition $::env(CLOCK_TRANSITION_CONSTRAINT) [all_clocks]
set_propagated_clock [all_clocks]

set_max_fanout $::env(MAX_FANOUT_CONSTRAINT) [current_design]
if { [info exists ::env(MAX_TRANSITION_CONSTRAINT)] } {
    set_max_transition $::env(MAX_TRANSITION_CONSTRAINT) [current_design]
}
if { [info exists ::env(MAX_CAPACITANCE_CONSTRAINT)] } {
    set_max_capacitance $::env(MAX_CAPACITANCE_CONSTRAINT) [current_design]
}

# GPIO: every input passes through a two-flop synchroniser and outputs are
# slow MCU I/O, so the pads get a loose budget rather than a tight one.
set gpio [get_ports {PB[0] PB[1] PB[2] PB[3] PB[4] PB[5] PB[7] PC[*] PD[*] PE[*]}]
set_input_delay  -clock clk_ext -max [expr $period * 0.3] $gpio
set_input_delay  -clock clk_ext -min 0 $gpio
set_output_delay -clock clk_ext [expr $period * 0.3] $gpio
# The pins are asynchronous to the clock, so a hold check on them means nothing; without
# this the hold repair pads every pin input with a chain of buffers to match the clock
# tree's insertion delay (and still cannot close it).
set_false_path -hold -from $gpio

# Serial memory: launched and captured on system-clock edges; with NVMCFG.SCKDIV = 0
# data has one full SCK period (two clock periods) to return, so a multicycle of 2
# applies to FL_MISO. Board/package: stacked die, a few mm of bond wire.
set_output_delay -clock clk_ext [expr $period * 0.3] [get_ports {FL_CSN FL_SCK FL_MOSI}]
set_input_delay  -clock clk_ext -max [expr $period * 0.5] [get_ports FL_MISO]
set_input_delay  -clock clk_ext -min 0 [get_ports FL_MISO]
set_multicycle_path -setup 2 -from [get_ports FL_MISO]
set_multicycle_path -hold 1 -from [get_ports FL_MISO]

# JTAG
set_input_delay  -clock tck -max 20 [get_ports {TMS TDI}]
set_input_delay  -clock tck -min 0  [get_ports {TMS TDI}]
set_output_delay -clock tck 20 [get_ports TDO]

# Asynchronous paths that are safe by construction:
#  - RESET pin to the reset controller and the in-system-programming pass-through
set_false_path -from [get_ports {PC[6]}]
#  - the crystal-mode bits select between clock inputs and only change while the
#    selected input is not in use; without this STA applies a clock-gating check
set_false_path -through [get_nets {u_analog.xo_mode[0] u_analog.xo_mode[1]}]

#  - PB6 as data. In this build PB6 is the clock pin, but it is also a GPIO input, the
#    timer-oscillator input and a pin-change wake source. All three land on synchronisers
#    or on the asynchronous wake latch, so the clock pin has no timing relation as data.
set_false_path -through [get_pins pad_pb6/Y]
#  (The crystal-ready counter needs no exception any more: its reset goes through a two-flop
#   synchroniser on the crystal clock, u_clkrst.u_xrst, and the path into that synchroniser
#   meets recovery and removal timing as it stands.)

set cap_load [expr $::env(OUTPUT_CAP_LOAD) / 1000.0]
set_load $cap_load [all_outputs]

set_timing_derate -early [expr 1 - $::env(TIME_DERATING_CONSTRAINT) / 100.0]
set_timing_derate -late  [expr 1 + $::env(TIME_DERATING_CONSTRAINT) / 100.0]
