# Write a typical-corner SDF from a finished LibreLane run, for scripts/gl_sim.sh.
#   RUN=<run dir> PDK=<pdk>/gf180mcuD SCL=gf180mcu_fd_sc_mcu9t5v0 OUT=chip_top.tt.sdf \
#     openroad -no_init -exit scripts/gl_write_sdf.tcl
set P $::env(PDK)/libs.ref
set R $::env(RUN)
read_liberty $P/$::env(SCL)/lib/$::env(SCL)__tt_025C_5v00.lib
read_liberty $P/gf180mcu_fd_io/lib/gf180mcu_fd_io__tt_025C_5v00.lib
read_liberty $P/gf180mcu_fd_ip_sram/lib/gf180mcu_fd_ip_sram__sram512x8m8wm1__tt_025C_5v00.lib
foreach f [glob [file dirname [info script]]/../flow/librelane/ip/*/lib/*.lib] { read_liberty $f }
read_db [lindex [glob $R/*-openroad-fillinsertion/chip_top.odb] 0]
array set ::env {DESIGN_NAME chip_top CLOCK_PERIOD 50 CLOCK_UNCERTAINTY_CONSTRAINT 0.25
  CLOCK_TRANSITION_CONSTRAINT 0.15 MAX_FANOUT_CONSTRAINT 10 MAX_TRANSITION_CONSTRAINT 3
  OUTPUT_CAP_LOAD 72.91 TIME_DERATING_CONSTRAINT 5}
source [file dirname [info script]]/../flow/librelane/chip_top.sdc
read_spef [lindex [glob $R/*-openroad-rcx/nom/chip_top.nom.spef] 0]
write_sdf -include_typ -divider / $::env(OUT)
