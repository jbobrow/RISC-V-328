# Power grid for the SRAM macros (N orientation), after the wafer.space template.
define_pdn_grid \
    -macro \
    -instances {u_core.u_ram.u_ram0 u_core.u_ram.u_ram1 u_core.u_ram.u_ram2 u_core.u_ram.u_ram3 u_core.u_xip.u_cache.u_ram0 u_core.u_xip.u_cache.u_ram1 u_core.u_xip.u_cache.u_ram2 u_core.u_xip.u_cache.u_ram3} \
    -name sram_macros_NS \
    -starts_with POWER \
    -halo "$::env(PDN_HORIZONTAL_HALO) $::env(PDN_VERTICAL_HALO)"

add_pdn_connect \
    -grid sram_macros_NS \
    -layers "$::env(PDN_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"

add_pdn_connect \
    -grid sram_macros_NS \
    -layers "$::env(PDN_VERTICAL_LAYER) Metal3"

# Stripes on the W/E edges of each SRAM
add_pdn_stripe \
    -grid sram_macros_NS \
    -layer Metal4 \
    -width 2.36 \
    -offset 1.18 \
    -spacing 0.28 \
    -pitch 426.86 \
    -starts_with GROUND \
    -number_of_straps 2

# The stripes above block the top-level Metal4 grid over the macro, so add more
add_pdn_stripe \
    -grid sram_macros_NS \
    -layer Metal4 \
    -width 4.00 \
    -offset 65.93 \
    -spacing 0.28 \
    -pitch 50 \
    -starts_with GROUND \
    -number_of_straps 7
