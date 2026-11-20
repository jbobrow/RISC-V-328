# Layout outputs (third layout)

From LibreLane run `run4` of the digital-first build on GF180MCU (wafer.space half-height slot,
9-track cells). Timing is closed at 20 MHz, DRC and LVS are clean and three tests pass on the routed
netlist. It contains a stub where the analog block will go;
see `docs/layout_results.md` for what is still open.

| File | What it is |
|---|---|
| `chip_top.gds.gz` | final GDS with seal ring and metal fill. Open with KLayout and the gf180mcuD layer properties |
| `chip_top.routed.def.gz` | routed design in DEF with fill cells |
| `chip_top.nl.v.gz` | final gate-level netlist (after timing repair and fill) |
| `chip_top.tt.sdf.gz` | cell and wire delays at the typical corner (`make gl-sdf`); the gate-level simulation uses the cell delays |
| `chip_top.png` | KLayout render of the whole die (the flow's own, 2048 px) |
| `renders/` | high-resolution pictures from `make render`: `step1_power_grid` to `step4_routed` (4000 px), `full` (8000 px, 0.5 um per pixel), and zooms `core`, `sram`, `pads_devices` (transistor layers of the pads), `cells` |
| `metrics.json` | every metric the flow recorded, with the LVS and foundry DRC counts added |
| `sta_summary_20MHz.rpt` | the flow's post-route timing summary at 50 ns, nine corners |
| `sta_slow_corner_setup.rpt.gz` | setup paths at the slowest corner (`max_ss_125C_4v50`), 50 ns |
| `sta_fast_corner_hold.rpt.gz` | hold paths at the corner with the least hold margin (`min_ff_n40C_5v50`) |
| `sta_slow_corner_checks.rpt.gz` | slew, capacitance and fan-out entries at the slowest corner |
| `lvs.netgen.rpt.gz` | Netgen LVS report ("Circuits match uniquely") |
| `drc_beol.klayout.lyrdb.gz`, `drc_feol.klayout.lyrdb.gz` | foundry KLayout DRC reports, back-end and front-end rule decks (no entries) |
| `first_layout/` | metrics, timing summary and write-up of the first layout (7-track cells), for comparison |
| `second_layout/` | metrics and timing summary of the second layout (run3), for comparison |

The large files in the table (`chip_top.gds.gz`, `chip_top.routed.def.gz`, `chip_top.nl.v.gz`,
`chip_top.tt.sdf.gz`, `sta_slow_corner_setup.rpt.gz`, `sta_fast_corner_hold.rpt.gz`, about 30 MB
together), `chip_top.png` and the pictures in `renders/` (59 MB) are not kept in the git repository,
so that each new layout run does not add tens of megabytes to its history. Web-sized copies of the
renders are in `docs/images/`. The run directories (several GB of intermediate databases) are not
included either; `flow/README.md` says how to reproduce them.
