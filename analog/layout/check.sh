#!/usr/bin/env bash
# Generate every analog cell that has a layout and check it: foundry KLayout DRC, magic DRC, LVS,
# extraction.  Needs klayout (with its Python module), magic, netgen, and PDK_DIR (the gf180mcuD
# directory) or PDK_ROOT (the directory that holds it).
#   analog/layout/check.sh [work directory]        (default analog/layout/out)
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
work="$(mkdir -p "${1:-$here/out}" && cd "${1:-$here/out}" && pwd)"
pdk="${PDK_DIR:-$PDK_ROOT/gf180mcuD}"
export PDK_DIR="$pdk" PDK_ROOT="$(dirname "$pdk")" PDK=gf180mcuD
mkdir -p "$here/reports"
rows=""; ok=1

check() {   # check <cell> <gds> <schematic> <what it is>
    local cell=$1 gds=$2 sch=$3 what=$4
    echo "== $cell"
    local k m why l
    k=$("$here/drc.sh" "$gds" "$cell" | tail -1)
    "$here/lvs.sh" "$gds" "$cell" "$sch" > "$work/$cell.check.log"
    m=$(grep "MAGIC_DRC" "$work/$cell.check.log" | awk '{print $2}')
    why=$(grep "MAGIC_WHY" "$work/$cell.check.log" | sed 's/MAGIC_WHY [0-9]* //' | paste -sd';' -)
    l=$(grep "Final result" "$work/$cell.check.log" | sed 's/Final result: //')
    local size; size=$(python3 -c "import klayout.db as k;l=k.Layout();l.read('$gds');b=l.cell('$cell').dbbox();print('%.0f x %.0f um' % (b.width(), b.height()))")
    echo "   KLayout: $k"; echo "   magic: $m ${why:+($why)}"; echo "   LVS: $l"
    # magic's deck reports five errors inside each foundry bipolar cell, also when that cell is checked by itself
    local mnote="$m"
    if [ -n "$why" ] && [ "$why" = "P-diffusion and N-ohmic must be over N-well or deep N-well" ] && \
       [ "$(python3 "$here/drc_inside.py" "$gds" "$cell" "$work/$cell.drcboxes")" = 0 ]; then
        mnote="0 outside the foundry bipolar cells ($m inside them, as in that cell alone)"; m=0
    fi
    rows+="| \`$cell\` | $what | $size | ${k%% *} | $mnote | $l |"$'\n'
    [ "${k%% *}" = 0 ] && [ "$m" = 0 ] && [ "$l" = "Circuits match uniquely." ] || ok=0
    gzip -9 -n -c "${gds%.gds}_drc.lyrdb" > "$here/reports/${cell}_drc.klayout.lyrdb.gz"
    cp "$work/$cell.lvs.rpt" "$here/reports/${cell}_lvs.netgen.rpt"
}

python3 "$here/caparray.py" "$work"
check rv328_adc_caparray "$work/rv328_adc_caparray.gds" "$here/../blocks/adccap.spice" "all 1920 MIM units of the ADC front end"
python3 "$here/pex.py" "$work" > /dev/null
gzip -9 -n -c "$work/rv328_adc_caparray.gds" > "$here/rv328_adc_caparray.gds.gz"

python3 "$here/devices.py" "$work"
check devtest "$work/devtest.gds" "$work/devtest.spice" "one of each generated device: six transistors, five resistors, a capacitor and a bank of twenty"

python3 "$here/bgr.py" "$work"
check rv328_bgr "$work/rv328_bgr.gds" "$work/rv328_bgr_lvs.spice" "the reference: 21 transistors, 10 bipolars, 5 resistors (140 strips), 2 capacitors"
python3 "$here/pex_block.py" "$work/rv328_bgr.gds" rv328_bgr "$here/../blocks/bgr.spice" "$here/rv328_bgr_pex.spice"
gzip -9 -n -c "$work/rv328_bgr.gds" > "$here/rv328_bgr.gds.gz"

python3 "$here/autoblock.py" rv328_adccmp "$here/../blocks/adccmp.spice" "$work"
check rv328_adccmp "$work/rv328_adccmp.gds" "$work/rv328_adccmp_lvs.spice" "the ADC comparator: 35 transistors, 2 resistors, 6 capacitors"
python3 "$here/pex_block.py" "$work/rv328_adccmp.gds" rv328_adccmp "$here/../blocks/adccmp.spice" "$here/rv328_adccmp_pex.spice"
gzip -9 -n -c "$work/rv328_adccmp.gds" > "$here/rv328_adccmp.gds.gz"

python3 "$here/adcfe.py" "$work" --pex
check rv328_adcfe "$work/rv328_adcfe.gds" "$work/rv328_adcfe_lvs.spice" "the whole ADC front end: the capacitor array, the comparator, and 73 more transistors, 88 standard cells, 3 resistors and 10 capacitors in five blocks"
gzip -9 -n -c "$work/rv328_adcfe.gds" > "$here/rv328_adcfe.gds.gz"

python3 "$here/autoblock.py" rv328_por "$here/../blocks/por.spice" "$work"
check rv328_por "$work/rv328_por.gds" "$work/rv328_por_lvs.spice" "the power-on reset: 14 transistors, 5 resistors in 212 strips, 2 capacitors"
python3 "$here/pex_block.py" "$work/rv328_por.gds" rv328_por "$here/../blocks/por.spice" "$here/rv328_por_pex.spice"
gzip -9 -n -c "$work/rv328_por.gds" > "$here/rv328_por.gds.gz"

python3 "$here/autoblock.py" rv328_lfosc "$here/../blocks/lfosc.spice" "$work"
check rv328_lfosc "$work/rv328_lfosc.gds" "$work/rv328_lfosc_lvs.spice" "the 128 kHz oscillator: 39 transistors, 5 resistors in 293 strips, 1 capacitor"
python3 "$here/pex_block.py" "$work/rv328_lfosc.gds" rv328_lfosc "$here/../blocks/lfosc.spice" "$here/rv328_lfosc_pex.spice"
gzip -9 -n -c "$work/rv328_lfosc.gds" > "$here/rv328_lfosc.gds.gz"

python3 "$here/stack.py" rv328_rcosc "$here/../blocks/rcosc.spice" "$work"
check rv328_rcosc "$work/rv328_rcosc.gds" "$work/rv328_rcosc_lvs.spice" "the 8 MHz oscillator: 123 transistors, 5 resistors in 106 strips, 328 capacitor units (six banks and seven single ones)"
python3 "$here/pex_block.py" "$work/rv328_rcosc.gds" rv328_rcosc "$here/../blocks/rcosc.spice" "$here/rv328_rcosc_pex.spice"
gzip -9 -n -c "$work/rv328_rcosc.gds" > "$here/rv328_rcosc.gds.gz"

python3 "$here/stack.py" rv328_xosc "$here/../blocks/xosc.spice" "$work"
check rv328_xosc "$work/rv328_xosc.gds" "$work/rv328_xosc_lvs.spice" "the crystal oscillator: 80 transistors, 3 resistors in 138 strips"
python3 "$here/pex_block.py" "$work/rv328_xosc.gds" rv328_xosc "$here/../blocks/xosc.spice" "$here/rv328_xosc_pex.spice"
gzip -9 -n -c "$work/rv328_xosc.gds" > "$here/rv328_xosc.gds.gz"

python3 "$here/autoblock.py" rv328_refbuf "$here/../blocks/refbuf.spice" "$work"
check rv328_refbuf "$work/rv328_refbuf.gds" "$work/rv328_refbuf_lvs.spice" "the reference buffer: 13 transistors, 2 capacitors of 5 pF"
python3 "$here/pex_block.py" "$work/rv328_refbuf.gds" rv328_refbuf "$here/../blocks/refbuf.spice" "$here/rv328_refbuf_pex.spice"
gzip -9 -n -c "$work/rv328_refbuf.gds" > "$here/rv328_refbuf.gds.gz"

python3 "$here/stack.py" rv328_bod "$here/../blocks/bod.spice" "$work" "$here/../blocks/cmp.spice" "$here/../blocks/logic.spice"
check rv328_bod "$work/rv328_bod.gds" "$work/rv328_bod_lvs.spice" "the brown-out detector with its comparator: 57 transistors, 5 resistors in 90 strips, 2 capacitors"
python3 "$here/pex_block.py" "$work/rv328_bod.gds" rv328_bod "$here/../blocks/bod.spice" "$here/rv328_bod_pex.spice"
gzip -9 -n -c "$work/rv328_bod.gds" > "$here/rv328_bod.gds.gz"

python3 "$here/autoblock.py" rv328_cmp "$here/../blocks/cmp.spice" "$work"
check rv328_cmp "$work/rv328_cmp.gds" "$work/rv328_cmp_lvs.spice" "the analog comparator: 17 transistors"
python3 "$here/pex_block.py" "$work/rv328_cmp.gds" rv328_cmp "$here/../blocks/cmp.spice" "$here/rv328_cmp_pex.spice"
gzip -9 -n -c "$work/rv328_cmp.gds" > "$here/rv328_cmp.gds.gz"

python3 "$here/stack.py" rv328_amux "$here/../blocks/amux.spice" "$work"
check rv328_amux "$work/rv328_amux.gds" "$work/rv328_amux_lvs.spice" "the input multiplexer: 21 transistors and 42 standard cells"
python3 "$here/pex_block.py" "$work/rv328_amux.gds" rv328_amux "$here/../blocks/amux.spice" "$here/rv328_amux_pex.spice"
gzip -9 -n -c "$work/rv328_amux.gds" > "$here/rv328_amux.gds.gz"

python3 "$here/autoblock.py" rv328_tsens "$here/../blocks/tsens.spice" "$work"
check rv328_tsens "$work/rv328_tsens.gds" "$work/rv328_tsens_lvs.spice" "the temperature sensor: 4 transistors, 1 resistor in 6 strips"
python3 "$here/pex_block.py" "$work/rv328_tsens.gds" rv328_tsens "$here/../blocks/tsens.spice" "$here/rv328_tsens_pex.spice"
gzip -9 -n -c "$work/rv328_tsens.gds" > "$here/rv328_tsens.gds.gz"

# The macro: macro.py draws the two cells of the macro's own gates and switches, places the thirteen cells and
# wires them, and extracts that wiring (rv328_analog_pex.spice).
python3 "$here/macro.py" "$work" --pex
check rv328_acsw "$work/rv328_acsw.gds" "$work/rv328_acsw_lvs.spice" "the switches at the comparator's inputs: 8 transistors and 2 standard cells"
check rv328_glue "$work/rv328_glue.gds" "$work/rv328_glue_lvs.spice" "the macro's enable and gating logic: 22 standard cells"
check rv328_analog "$work/rv328_analog.gds" "$work/rv328_analog_lvs.spice" "the assembled macro: the eleven blocks and the two cells above, 83 tracks in three channels, a trunk of 57 lines"
gzip -9 -n -c "$work/rv328_analog.gds" > "$here/rv328_analog.gds.gz"
python3 "$here/wirecap.py" "$work" > /dev/null

cat > "$here/reports/checks.md" <<T
# Analog layout: checks

Foundry DRC is the KLayout deck, all 162 rule decks except antenna, density and copper pillar.
LVS is magic extraction compared by netgen with the netlist that was simulated. For the macro that is the top
netlist with every block as a cell: the blocks are compared cell by cell, then the wiring between them.

| Cell | Contents | Size | Foundry DRC violations | magic DRC violations | LVS |
|---|---|---|---|---|---|
$rows
T
cat "$here/reports/checks.md"
[ $ok = 1 ]
