# RV328 timing constraints (digital-first build: analog stub, external clock).
#
# Clocks
#   clk_ext   external clock on PB6/XTAL1; feeds clk_rc (stub) and clk_x (mux input 1),
#             and through the glitch-free mux and clock gates the whole system
#   clk_lf    PB6 / 64, generated in the analog stub: watchdog and LF system clock
#   tck       JTAG test clock
# With the real analog macro (RV328_ANALOG_MACRO) the clocks come from the macro's
# clk_rc, clk_xa and clk_lf pins as well: see the branch below.
current_design $::env(DESIGN_NAME)
set_units -time ns

set period $::env(CLOCK_PERIOD)
create_clock -name clk_ext -period $period [get_pins pad_pb6/Y]
create_clock -name tck -period 100 [get_pins pad_tck/Y]
if {[llength [get_cells -quiet u_analog.u_lfbuf.u_buf]]} {
    # Digital-first build (analog stub). The divided clock starts at a dedicated buffer
    # (rv328_clkbuf in the stub): a clock rooted directly on a flip-flop output crashes
    # OpenROAD's clock-tree synthesis.
    create_clock -name clk_lf -period [expr $period * 64] [get_pins u_analog.u_lfbuf.u_buf/Z]
    # Watchdog, system and JTAG domains only talk through synchronisers
    set_clock_groups -asynchronous -group {clk_ext} -group {clk_lf} -group {tck}
    set sysclks {clk_ext}
} else {
    # Build with the analog macro (RV328_ANALOG_MACRO). Its oscillators are clock sources:
    #   clk_rc    internal RC oscillator, 8 MHz (the reset default system clock)
    #   clk_xtal  crystal oscillator output, up to 20 MHz
    #   clk_lf    128 kHz oscillator: watchdog and the low-frequency system clock
    # clk_ext (PB6 as an external clock input) stays as above. The system clock is one of
    # clk_rc, clk_ext/clk_xtal (a static select) and clk_lf through the glitch-free mux, which
    # synchronises its own select lines on each source: no path is timed between them.
    create_clock -name clk_rc   -period 125.0 [get_pins u_analog/clk_rc]
    create_clock -name clk_xtal -period $period [get_pins u_analog/clk_xa]
    create_clock -name clk_lf   -period 7812.5 [get_pins u_analog/clk_lf]
    set_clock_groups -asynchronous -group {clk_rc} -group {clk_ext} -group {clk_xtal} -group {clk_lf} -group {tck}
    # pins are timed against every clock that can run the system (budgets from the 50 ns period)
    set sysclks {clk_ext clk_xtal clk_rc}
}

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
foreach c $sysclks {
    set_input_delay  -clock $c -add_delay -max [expr $period * 0.3] $gpio
    set_input_delay  -clock $c -add_delay -min 0 $gpio
    set_output_delay -clock $c -add_delay [expr $period * 0.3] $gpio
}
# The pins are asynchronous to the clock, so a hold check on them means nothing; without
# this the hold repair pads every pin input with a chain of buffers to match the clock
# tree's insertion delay (and still cannot close it).
set_false_path -hold -from $gpio

# Serial memory: launched and captured on system-clock edges; with NVMCFG.SCKDIV = 0
# data has one full SCK period (two clock periods) to return, so a multicycle of 2
# applies to FL_MISO. Board/package: stacked die, a few mm of bond wire.
foreach c $sysclks {
    set_output_delay -clock $c -add_delay [expr $period * 0.3] [get_ports {FL_CSN FL_SCK FL_MOSI}]
    set_input_delay  -clock $c -add_delay -max [expr $period * 0.5] [get_ports FL_MISO]
}
# Minimum: in SPI mode 0 the memory changes MISO only after the falling SCK edge reaches it, and the
# chip captures MISO on the same system-clock edge that drives SCK low. So MISO cannot change before
# SCK has left the chip, and that time follows the clock tree's own delay, which a constant input delay
# does not. Measured on the layout with the analog macro (anc5, minimum path, from every system clock):
# the falling SCK reaches the FL_SCK pin 6.97 ns after the clock edge at the fast corner (ff, -40 C,
# 5.5 V) and 17.95 ns at the slow corner (ss, 125 C, 4.5 V). The memory's own output hold (tCLQX/tHO) is
# 0 ns minimum for 25-series parts, and the bond wires only add delay. The minimum input delay is about
# 80 % of the measured time: 14 ns at the slow corners, 6 ns otherwise (and in placement and routing,
# where the corner is not named). A constant 6 ns everywhere left the slow corner 1.15 ns short (anc5);
# 3 ns, used at first, 1.2 ns short (ana8). Re-measure if the SCK output path changes.
set miso_min 6.0
if {[info exists ::env(_CURRENT_CORNER_NAME)] && [string match "*_ss_*" $::env(_CURRENT_CORNER_NAME)]} {
    set miso_min 14.0
}
foreach c $sysclks { set_input_delay -clock $c -add_delay -min $miso_min [get_ports FL_MISO] }
set_multicycle_path -setup 2 -from [get_ports FL_MISO]
set_multicycle_path -hold 1 -from [get_ports FL_MISO]

# In-system programming: with RESET held low the programmer's SPI pins (PB2..PB5) are wired straight
# through to the serial memory (rtl/rv328_core.v: fl_csn = isp ? PB2 : ...; PB4 = FL_MISO). Those
# pin-to-pin paths run at the programmer's speed, not the system clock's, and their delay is mostly the
# two pads. Without these exceptions they are timed against every system clock with the GPIO and
# memory pin budgets, which leaves about 20 ns for two pads and a cross-chip wire: the repair after
# global routing then spent two hours on them in run ana6.
set_false_path -from [get_ports {PB[2] PB[3] PB[5]}] -to [get_ports {FL_CSN FL_SCK FL_MOSI}]
set_false_path -from [get_ports FL_MISO] -to [get_ports {PB[4]}]

# JTAG
set_input_delay  -clock tck -max 20 [get_ports {TMS TDI}]
set_input_delay  -clock tck -min 0  [get_ports {TMS TDI}]
set_output_delay -clock tck 20 [get_ports TDO]

# First stages of the two-flop synchronisers (rv328_sync, rv328_rstsync: the flop whose output net ends
# in ".s[0]"). Their inputs come from other clock domains or from pins; a timing check into them means
# nothing. In the build with the analog macro this matters: clk_lf and clk_xtal are also possible system
# clocks through the multiplexer, so a crossing from the watchdog's 128 kHz domain into the system looks
# like a same-clock path with the whole multiplexer and gating tree as skew (hold misses of up to 8.8 ns
# in run ana8).
foreach net [get_nets -quiet -hierarchical {*.s[0]}] {
    foreach drv [get_pins -quiet -of_objects $net -filter "direction == output"] {
        set d [get_pins -quiet [get_full_name [get_cells -of_objects $drv]]/D]
        if {[llength $d]} { set_false_path -to $d }
    }
}
# Both flops of each reset synchroniser (rv328_rstsync: u_clkrst.u_rst, u_clkrst.u_xrst, u_dbgrst,
# u_dmirst; output nets ".s[0]" and ".s[1]") take the asynchronous reset on their reset pin by design:
# the reset is applied at any time, and its release is what the two flops synchronise (the first flop
# may go metastable, the second holds 0 because its input is still 0). A recovery or removal check on
# those reset pins means nothing; run anc5 spent its hold repair on a 1.08 ns removal miss there.
# Every other flop's reset pin is driven from a synchroniser output and stays timed.
foreach net [get_nets -quiet -hierarchical {*rst.s[0] *rst.s[1]}] {
    foreach drv [get_pins -quiet -of_objects $net -filter "direction == output"] {
        set r [get_pins -quiet [get_full_name [get_cells -of_objects $drv]]/RN]
        if {[llength $r]} { set_false_path -to $r }
    }
}

# Asynchronous paths that are safe by construction:
#  - RESET pin to the reset controller and the in-system-programming pass-through
set_false_path -from [get_ports {PC[6]}]
#  - the crystal-mode bits select between clock inputs and only change while the
#    selected input is not in use; without this STA applies a clock-gating check
set_false_path -through [get_nets -quiet {u_analog.xo_mode[0] u_analog.xo_mode[1] u_core.u_sys.x_mode[0] u_core.u_sys.x_mode[1]}]

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
