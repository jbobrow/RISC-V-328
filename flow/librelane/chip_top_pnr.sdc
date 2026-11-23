# RV328 timing constraints for placement and routing (PNR_SDC_FILE): chip_top.sdc, and in the build with the
# analog macro one representative clock for the system.
#
# With the macro, four clocks reach the system flip-flops through the clock multiplexers (clk_rc, clk_ext,
# clk_xtal and clk_lf). Sign-off checks all of them (SIGNOFF_SDC_FILE is chip_top.sdc), but carrying four
# sets of arrival times through every incremental timing update makes the repair steps several times slower
# (in run ana3 the setup repair after clock-tree synthesis ran for over half an hour on margins alone). For
# placement and routing the multiplexers are fixed on the crystal input: clk_xtal at 50 ns is the fastest
# system clock, and clk_ext reaches the same flip-flops with the same period through the same buffer.
source [file join [file dirname $::env(PNR_SDC_FILE)] chip_top.sdc]

if {[llength [get_cells -quiet u_analog.u_lfbuf.u_buf]] == 0} {
    foreach {net value} {
        u_core.u_clkrst.g_mux[0].u_en.en_n 0
        u_core.u_clkrst.g_mux[1].u_en.en_n 1
        u_core.u_clkrst.g_mux[2].u_en.en_n 0
        u_core.u_sys.x_mode[0]             1
    } {
        set drv [get_pins -quiet -of_objects [get_nets -quiet $net] -filter "direction == output"]
        if {[llength $drv]} { set_case_analysis $value $drv }
    }
}
