#!/bin/bash
# Pictures of a LibreLane run as it was built: power grid, placement, clock tree, routing,
# and the finished layout with zoom-ins.   scripts/render_stages.sh <run dir> <pdk>/gf180mcuD <output prefix>
set -e
cd "$(dirname "$0")/.."
R=$1; P=$2; O=$3
mkdir -p "$(dirname "$O")"
scl=$(python3 -c "import json;print(json.load(open('$R/resolved.json'))['STD_CELL_LIBRARY'])")
A=""
for f in $P/libs.ref/$scl/techlef/${scl}__nom.tlef $P/libs.ref/$scl/lef/*.lef $P/libs.ref/gf180mcu_fd_io/lef/*.lef \
         $P/libs.ref/gf180mcu_fd_ip_sram/lef/*.lef flow/librelane/ip/*/lef/*.lef; do A="$A --lef $(realpath $f)"; done
for f in $P/libs.ref/$scl/gds/*.gds $P/libs.ref/gf180mcu_fd_io/gds/*.gds $P/libs.ref/gf180mcu_fd_ip_sram/gds/*.gds \
         flow/librelane/ip/*/gds/*.gds; do A="$A --gds $(realpath $f)"; done
A="$A --map $P/libs.tech/klayout/tech/gf180mcu.map --lyt $P/libs.tech/klayout/tech/gf180mcu.lyt"
W=${WIDTH:-4000}
n=1
for st in generatepdn:power_grid globalplacement:placed cts:clock_tree detailedrouting:routed; do
  d=$(ls -d $R/*-openroad-${st%%:*} | head -n 1)
  python3 scripts/render_layout.py $d/chip_top.def ${O}_step${n} $A ${st##*:}:$W
  n=$((n+1))
done
g=$(ls $R/*-klayout-sealring/chip_top.gds 2>/dev/null | head -n 1)
[ -n "$g" ] && python3 scripts/render_layout.py $g $O full:8000 core:2400,1100,3000,1490:4096 sram:830,960,1130,1155:4096 cells:2606,1270,2666,1309:3000 \
  && python3 scripts/render_layout.py $g $O --upto metal2 pads_devices:1850,0,2390,351:4096
