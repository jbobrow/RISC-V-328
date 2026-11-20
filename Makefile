# RV328 build: firmware, RTL simulation, lint, synthesis estimate.
# Tools: iverilog, verilator, yosys, clang/lld/llvm-objcopy (RISC-V target).
SHELL := /bin/bash
H3      := vendor/hazard3/hdl
GFSIM   ?= vendor/gf180mcu
RTL     := rtl/tech/rv328_tech.v $(wildcard rtl/periph/*.v) rtl/rv328_xip.v rtl/rv328_clkrst.v \
           rtl/rv328_core.v rtl/rv328_chip_top.v
H3SRC   := $(H3)/hazard3_core.v $(H3)/hazard3_cpu_1port.v $(wildcard $(H3)/arith/*.v) \
           $(H3)/hazard3_csr.v $(H3)/hazard3_decode.v $(H3)/hazard3_frontend.v \
           $(H3)/hazard3_instr_decompress.v $(H3)/hazard3_irq_ctrl.v $(H3)/hazard3_pmp.v \
           $(H3)/hazard3_power_ctrl.v $(H3)/hazard3_regfile_1w2r.v $(H3)/hazard3_triggers.v \
           $(H3)/debug/dm/hazard3_dm.v $(H3)/debug/dtm/hazard3_jtag_dtm.v \
           $(H3)/debug/dtm/hazard3_jtag_dtm_core.v $(wildcard $(H3)/debug/cdc/*.v)
PADS    := $(wildcard $(GFSIM)/io/*.v)
TB      := tb/tb.v tb/spi_mem.v rtl/analog/rv328_analog_model.v

CC      := clang --target=riscv32-unknown-elf -march=rv32imc_zicsr -mabi=ilp32
CFLAGS  := -Os -ffreestanding -fno-builtin -nostdlib -Wall -Isw/include -ffunction-sections -fdata-sections -msmall-data-limit=0
TESTS   := $(basename $(notdir $(wildcard sw/tests/*.c)))

build/%.elf: sw/tests/%.c sw/crt0.S sw/rv328.c sw/link.ld sw/include/rv328.h
	@mkdir -p build
	$(CC) $(CFLAGS) -c sw/crt0.S -o build/crt0.o
	$(CC) $(CFLAGS) -c sw/rv328.c -o build/rv328.o
	$(CC) $(CFLAGS) -c $< -o build/$*.o
	ld.lld -T sw/link.ld --gc-sections -o $@ build/crt0.o build/rv328.o build/$*.o
build/%.hex: build/%.elf
	llvm-objcopy -O binary $< build/$*.bin
	python3 scripts/bin2hex.py build/$*.bin $@

build/sim.vvp: $(RTL) $(H3SRC) $(TB)
	@mkdir -p build; rm -f $@
	@iverilog -g2012 $(SIMDEFS) -Wall -Wno-timescale -Wno-implicit-dimensions -Wno-portbind -Wno-sensitivity-entire-array -Wno-sensitivity-entire-vector \
	  -I $(H3) -o $@ -s tb $(TB) $(RTL) $(H3SRC) $(PADS) 2>&1 | grep -v "hazard3\|gf180mcu" | head -40 ; test -f $@

# per-test simulator options
ARGS_uart   := +wiring=1
ARGS_spi    := +wiring=2
ARGS_twi    := +wiring=3
ARGS_timers := +wiring=4
ARGS_clock  := +extclk=62.5 +timeout_us=400000
ARGS_isp    := +isp +jtag

sim-%: build/sim.vvp build/%.hex
	@vvp -n build/sim.vvp +firmware=build/$*.hex $(ARGS_$*) $(SIMARGS) | grep -v "^WARNING\|readmemh" | sed "s/^/[$*] /"

test: $(addprefix sim-,$(TESTS))

lint:
	verilator --lint-only -Wall -Wno-fatal -Wno-DECLFILENAME -Wno-UNUSEDSIGNAL -Wno-UNUSEDPARAM -Wno-PINCONNECTEMPTY \
	  -I$(H3) --top-module rv328_core rtl/tech/rv328_tech.v $(wildcard rtl/periph/*.v) rtl/rv328_xip.v \
	  rtl/rv328_clkrst.v rtl/rv328_core.v $(H3SRC) 2>&1 | grep -v "hazard3" | grep -A3 "rv328" | head -80

# ---------------------------------------------------------------------------
# Cache benchmarks (docs/cache_study.md). Arduino-style programs in sw/bench,
# built with GCC and picolibc as real firmware would be (float printf, libm).
RVGCC   := riscv64-unknown-elf-gcc -march=rv32imc_zicsr -mabi=ilp32
PICO    := /usr/lib/picolibc/riscv64-unknown-elf
GCCLIB  := /usr/lib/gcc/riscv64-unknown-elf/13.2.0/rv32imac/ilp32
BFLAGS  := -ffunction-sections -fdata-sections -msmall-data-limit=0 -Wall -Isw/include -Isw/bench -isystem $(PICO)/include
BLINK    = riscv64-unknown-elf-ld -m elf32lriscv --gc-sections -Map=$(basename $@).map -T build/bench/bench$(1)k.ld -o $@ \
           build/bench/crt0.o build/bench/rv328.o build/bench/hal.o $(2) -L$(PICO)/lib/rv32imac/ilp32 -L$(GCCLIB) -lm -lc -lgcc
CM      ?= ../ext/coremark
CMSRC   := core_main core_list_join core_matrix core_state core_util

build/bench/common.stamp: sw/crt0.S sw/rv328.c sw/bench/hal.c sw/bench/hal.h sw/bench/bench.ld.S
	@mkdir -p build/bench
	$(RVGCC) -Os $(BFLAGS) -c sw/crt0.S -o build/bench/crt0.o
	$(RVGCC) -Os $(BFLAGS) -c sw/rv328.c -o build/bench/rv328.o
	$(RVGCC) -Os $(BFLAGS) -c sw/bench/hal.c -o build/bench/hal.o
	$(RVGCC) -E -P -x c -DRAM_KB=2 sw/bench/bench.ld.S -o build/bench/bench2k.ld
	$(RVGCC) -E -P -x c -DRAM_KB=4 sw/bench/bench.ld.S -o build/bench/bench4k.ld
	@touch $@
build/bench/%.elf: sw/bench/app_%.c build/bench/common.stamp
	$(RVGCC) -Os $(BFLAGS) -c $< -o build/bench/$*.o
	$(call BLINK,2,build/bench/$*.o)
# CoreMark needs 2 KB of data plus stack: 4 KB simulation-only RAM (RV328_SIM_RAM4K)
build/bench/coremark.elf: sw/bench/core_portme.c sw/bench/core_portme.h build/bench/common.stamp
	for f in $(CMSRC); do $(RVGCC) -O2 $(BFLAGS) -Isw/bench -I$(CM) -DITERATIONS=$(or $(CM_ITER),2) -c $(CM)/$$f.c -o build/bench/cm_$$f.o || exit 1; done
	$(RVGCC) -O2 $(BFLAGS) -I$(CM) -DITERATIONS=$(or $(CM_ITER),2) -c sw/bench/core_portme.c -o build/bench/cm_portme.o
	$(call BLINK,4,$(addprefix build/bench/cm_,$(addsuffix .o,$(CMSRC))) build/bench/cm_portme.o)
# the same programs without peripherals (hal_null.c): processor work only, RV328 and ATmega328P
build/bench/%_null.elf: sw/bench/app_%.c sw/bench/hal_null.c build/bench/common.stamp
	$(RVGCC) -Os $(BFLAGS) -DHAL_NULL -c sw/bench/hal_null.c -o build/bench/hal_null.o
	$(RVGCC) -Os $(BFLAGS) -DHAL_NULL -c $< -o build/bench/$*_null.o
	riscv64-unknown-elf-ld -m elf32lriscv --gc-sections -T build/bench/bench2k.ld -o $@ build/bench/crt0.o build/bench/rv328.o \
	  build/bench/hal_null.o build/bench/$*_null.o -L$(PICO)/lib/rv32imac/ilp32 -L$(GCCLIB) -lm -lc -lgcc
comma  := ,
AVRGCC := avr-gcc -idirafter /usr/include -mmcu=atmega328p -DF_CPU=20000000UL -Os -ffunction-sections -fdata-sections -Wall -Isw/bench
build/bench/avr_%.elf: sw/bench/app_%.c sw/bench/hal_null.c sw/bench/hal.h
	@mkdir -p build/bench
	$(AVRGCC) -DHAL_NULL sw/bench/hal_null.c $< -Wl,--gc-sections -Wl,--undefined=_mmcu,--section-start=.mmcu=0x910000 \
	  $(if $(filter logger full,$*),-Wl$(comma)-u$(comma)vfprintf -lprintf_flt) -lm -o $@
	@avr-size $@
.PRECIOUS: build/bench/%.elf build/bench/%_null.elf
build/bench/%.hex: build/bench/%.elf
	riscv64-unknown-elf-objcopy -O binary $< build/bench/$*.bin
	python3 scripts/bin2hex.py build/bench/$*.bin $@
	@riscv64-unknown-elf-size $<

# One compiled simulator (Verilator) per cache configuration <KB per way>_<ways>_<pinned KB>,
# e.g. build/vl_4_3_2 (three 4 KB ways, first 2 KB pinned), optional 4th field = fast multiplier; 16_2_0 is the
# "everything cached" reference. BOPT adds defines (CPU options). tb/bench_top.v wraps
# the core; build/sim_c<KB>.vvp is the chip-level testbench under Icarus Verilog (slow).
cfgw = $(word $(1),$(subst _, ,$(2)))
build/vl_%/Vbench_top: $(RTL) $(H3SRC) tb/bench_top.v tb/bench_main.cpp
	@mkdir -p build
	verilator --cc --exe --build -j 2 -O3 --top-module bench_top -Wno-fatal -Wno-lint -Wno-style -Wno-TIMESCALEMOD \
	  -DRV328_CACHE_KB=$(call cfgw,1,$*) -DRV328_CACHE_WAYS=$(call cfgw,2,$*) -DRV328_CACHE_PIN=$(call cfgw,3,$*) \
	  -DRV328_MUL_FAST=$(or $(call cfgw,4,$*),0) -DRV328_SIM_RAM4K -I$(H3) --Mdir build/vl_$* \
	  tb/bench_top.v rtl/tech/rv328_tech.v $(wildcard rtl/periph/*.v) rtl/rv328_xip.v rtl/rv328_clkrst.v rtl/rv328_core.v \
	  $(H3SRC) tb/bench_main.cpp > build/vl_$*.log 2>&1 || (tail -30 build/vl_$*.log; false)
	@find build/vl_$* -type f ! -name Vbench_top -delete
build/sim_c%.vvp: $(RTL) $(H3SRC) $(TB)
	@mkdir -p build; rm -f $@
	@iverilog -g2012 -Wno-timescale -DRV328_CACHE_KB=$* -DRV328_SIM_RAM4K \
	  -I $(H3) -o $@ -s tb $(TB) $(RTL) $(H3SRC) $(PADS) 2>&1 | grep -v "hazard3\|gf180mcu" | head -20 ; test -f $@

# Yosys area estimate of the digital core against the GF180MCU 7-track library
# (needs the per-cell liberty files merged with scripts/merge_lib.py; see flow/README.md)
synth:
	yosys -q -l build/synth.log -s scripts/synth_estimate.ys
	@grep -E "Number of cells|Chip area" build/synth_stat.txt

# Elaborate the complete chip (pads + core + analog stub) as the layout flow will see it
elab:
	@yosys -q -p "read_verilog scripts/pad_blackbox.v; read_liberty -lib build/sc7_tt.lib; \
	  verilog_defaults -add -I$(H3) -DRV328_TECH_GF180 -DRV328_ANALOG_STUB; \
	  read_verilog $(RTL) rtl/analog/rv328_analog_stub.v $(H3SRC); hierarchy -check -top chip_top; proc; \
	  check -assert; tee -o build/elab_stat.txt stat" > build/elab.log 2>&1; tail -3 build/elab.log; \
	  grep -E "gf180mcu_fd_io|sram512|icgtp" build/elab_stat.txt | sort | uniq -c

# Interactive layout viewer and results table from a LibreLane run (default: newest run)
RUN ?= $(lastword $(sort $(wildcard flow/librelane/runs/*)))
PDK_DIR ?= $(PDK_ROOT)/gf180mcuD
viewer:
	python3 scripts/layout_viewer/build.py $(RUN) --pdk $(PDK_DIR) $(if $(CROP),--crop $(CROP)) --out docs/layout_viewer.html
report:
	@python3 scripts/flow_report.py $(RUN)

# Gate-level simulation of a routed run with cell delays from the layout (scripts/gl_prep.py
# says what this covers). "make gl-sdf" once per run, then "make gl-basic", "make gl-timers", ...
SCL ?= gf180mcu_fd_sc_mcu9t5v0
PERIOD ?= 50
gl-sdf:
	@mkdir -p build
	RUN=$(RUN) PDK=$(PDK_DIR) SCL=$(SCL) OUT=build/chip_top.tt.sdf openroad -no_init -exit scripts/gl_write_sdf.tcl
gl-%: build/%.hex
	@scripts/gl_sim.sh $(firstword $(wildcard $(RUN)/*-openroad-fillinsertion/chip_top.nl.v)) build/chip_top.tt.sdf $(PDK_DIR) $* $(PERIOD)

# Pictures of a run: the four build stages and the finished layout at 8000 px with zoom-ins
# (needs klayout and Python with Pillow on the PATH). WIDTH=<px> sets the size of the stage pictures.
render:
	scripts/render_stages.sh $(RUN) $(PDK_DIR) build/render/rv328

# Analog blocks: every transistor-level test bench against the foundry models (needs ngspice;
# a few hours on two cores). One block: python3 analog/tb/<name>.py
ANALOG_TB := bgr por bod cmp adccmp rcosc lfosc xosc adcfe adcpat adcseq aux top off
analog-sim:
	@mkdir -p analog/results
	@for b in $(ANALOG_TB); do echo $$b; PDK_DIR=$(PDK_DIR) python3 analog/tb/$$b.py > analog/results/$$b.md || exit 1; done

# The same benches on the netlists extracted from the layouts (analog/layout/*_pex.spice). The ADC from
# its layout takes about two hours: every conversion is four to five times slower than on the schematic.
analog-sim-layout:
	RV328_PEX=bgr PDK_DIR=$(PDK_DIR) python3 analog/tb/bgr.py > analog/results/bgr_pex.md
	RV328_PEX=adccmp PDK_DIR=$(PDK_DIR) python3 analog/tb/adccmp.py > analog/results/adccmp_pex.md
	PDK_DIR=$(PDK_DIR) python3 analog/tb/adcfe.py --layout > analog/results/adcfe_layout.md
	PDK_DIR=$(PDK_DIR) python3 analog/tb/adcseq.py --layout > analog/results/adcseq_layout.md
	RV328_PEX=por PDK_DIR=$(PDK_DIR) python3 analog/tb/por.py > analog/results/por_pex.md
	RV328_PEX=lfosc PDK_DIR=$(PDK_DIR) python3 analog/tb/lfosc.py > analog/results/lfosc_pex.md
	RV328_PEX=rcosc PDK_DIR=$(PDK_DIR) python3 analog/tb/rcosc.py > analog/results/rcosc_pex.md
	RV328_PEX=rcosc PDK_DIR=$(PDK_DIR) python3 analog/tb/rcosc.py steps > analog/results/rcosc_steps_pex.md
	RV328_PEX=xosc PDK_DIR=$(PDK_DIR) python3 analog/tb/xosc.py > analog/results/xosc_pex.md
	RV328_PEX=bod PDK_DIR=$(PDK_DIR) python3 analog/tb/bod.py > analog/results/bod_pex.md
	RV328_PEX=cmp PDK_DIR=$(PDK_DIR) python3 analog/tb/cmp.py > analog/results/cmp_pex.md
	RV328_PEX=refbuf,amux,tsens PDK_DIR=$(PDK_DIR) python3 analog/tb/aux.py > analog/results/aux_pex.md
	RV328_PEX=bgr,adccap,adcfe,por,lfosc,rcosc,xosc,refbuf,bod,amux,tsens,cmp PDK_DIR=$(PDK_DIR) python3 analog/tb/top.py > analog/results/top_pex.md
	RV328_PEX=bgr,adccap,adcfe,por,lfosc,rcosc,xosc,refbuf,bod,amux,tsens,cmp,macro PDK_DIR=$(PDK_DIR) python3 analog/tb/top.py > analog/results/top_macro.md

# Analog layout: generate every analog cell drawn so far (ADC capacitor array, device test cell,
# every block of the analog macro), run both DRC
# tools, LVS and the extractions,
# then draw the pictures (needs klayout,
# magic, netgen; matplotlib and Pillow for the pictures). PYTHON_FIG is the Python that has
# matplotlib, if that is not the one that has klayout's module.
# Benches on the extracted cells: make analog-sim-layout
PYTHON_FIG ?= python3
analog-layout:
	PDK_DIR=$(PDK_DIR) analog/layout/check.sh build/analog_layout
	$(PYTHON_FIG) analog/layout/figures.py build/analog_layout
	python3 scripts/render_layout.py build/analog_layout/rv328_adc_caparray.gds analog/layout/renders/caparray \
	    full:5000 corner:-13,-27,37,11:4000 centre:155,150,200,184:4000
	python3 scripts/render_layout.py build/analog_layout/rv328_adc_caparray.gds analog/layout/renders/caparray_wiring \
	    corner:-13,-27,37,11:4000 --upto via3
	python3 scripts/render_layout.py build/analog_layout/rv328_bgr.gds analog/layout/renders/bgr \
	    full:6000 mirror:-1,-14,54,40:4000 pnp:104,-54,165,2:4000 detail:124,14,156,26:4000
	python3 scripts/render_layout.py build/analog_layout/rv328_adccmp.gds analog/layout/renders/adccmp \
	    full:6000 nodes:262,-30,328,56:4000
	python3 scripts/render_layout.py build/analog_layout/rv328_por.gds analog/layout/renders/por full:5000
	python3 scripts/render_layout.py build/analog_layout/rv328_lfosc.gds analog/layout/renders/lfosc full:5000
	python3 scripts/render_layout.py build/analog_layout/rv328_rcosc.gds analog/layout/renders/rcosc full:5000
	python3 scripts/render_layout.py build/analog_layout/rv328_xosc.gds analog/layout/renders/xosc full:5000
	for c in refbuf bod cmp amux tsens; do python3 scripts/render_layout.py build/analog_layout/rv328_$$c.gds analog/layout/renders/$$c full:4000; done
	python3 scripts/render_layout.py build/analog_layout/rv328_glue.gds analog/layout/renders/glue full:4000
	python3 scripts/render_layout.py build/analog_layout/rv328_analog.gds analog/layout/renders/analog_macro full:7000 foot:426,-62,534,14:4500
	python3 scripts/render_layout.py build/analog_layout/rv328_adcfe.gds analog/layout/renders/adcfe \
	    full:3000 lower:-68,-3,362,396:5000

clean:
	rm -rf build
.PRECIOUS: build/%.elf build/%.hex
.PHONY: test lint synth elab viewer report gl-sdf render analog-sim analog-sim-layout analog-layout clean site

# Documentation site: docs/*.md -> docs/*.html with shared navigation, diagrams as SVG files
# (open docs/index.html, or serve the docs folder with GitHub Pages)
site:
	/usr/bin/python3 scripts/site_diagrams.py
	/usr/bin/python3 scripts/build_site.py
