// RV328 digital core: Hazard3 RV32IMC CPU, bus, memories, all digital
// peripherals, pin multiplexing, clock/reset generation and debug.
// Everything outside this module is pads and analog.
//
// Memory map
//   0x0000_0000  1 MB   program memory (XIP serial memory, read-only, cached)
//   0x2000_0000  2 KB   SRAM
//   0x4000_0n00         peripheral slot n (256 bytes each):
//     0 SYSCTL  1 GPIO  2 TC0  3 TC1  4 TC2  5 TC3  6 TC4  7 USART0  8 USART1
//     9 SPI0  10 SPI1  11 TWI0  12 TWI1  13 ADC/AC  14 WDT  15 NVM
// Peripheral registers are 32 bits wide and must be accessed as words.
//
// Interrupts (Hazard3 external IRQ numbers)
//   0 INT0  1 INT1  2 PCINT0  3 PCINT1  4 PCINT2  5 PCINT3  6 WDT  7 TC0  8 TC1
//   9 TC2  10 TC3  11 TC4  12 SPI0  13 SPI1  14 USART0  15 USART1  16 TWI0
//   17 TWI1  18 ADC  19 AC  20 NVM
`default_nettype none
// program cache (see rv328_xip.v): KB per way (2, 4, 8 or 16), ways (1, 2 or 3),
// first 2 KB of the program pinned (0 or 2; needs 2 or 3 ways)
`ifndef RV328_CACHE_KB
`define RV328_CACHE_KB 2
`endif
`ifndef RV328_CACHE_WAYS
`define RV328_CACHE_WAYS 1
`endif
`ifndef RV328_CACHE_PIN
`define RV328_CACHE_PIN 0
`endif
// CPU options: single-cycle multiplier for MUL, and for MULH* (follows MUL unless set), branch predictor
`ifndef RV328_MUL_FAST
`define RV328_MUL_FAST 0
`endif
`ifndef RV328_MULH_FAST
`define RV328_MULH_FAST `RV328_MUL_FAST
`endif
`ifndef RV328_BRANCH_PRED
`define RV328_BRANCH_PRED 0
`endif
module rv328_core (
	// ---- clocks / reset from the analog macro ----
	input  wire        clk_rc,
	input  wire        clk_xa,       // crystal oscillator output
	input  wire        clk_lf,       // 128 kHz
	input  wire        por_n,
	input  wire        bod_i,
	output wire        rc_en,
	output wire [7:0]  rc_trim,
	output wire        xo_en,        // crystal oscillator enable
	output wire [1:0]  xo_mode,
	output wire        bod_en,
	output wire [2:0]  bod_level,
	// ---- ADC / comparator analog interface ----
	output wire        adc_en,
	output wire [3:0]  adc_mux,
	output wire [1:0]  adc_refs,
	output wire        adc_sample,
	output wire [9:0]  adc_dac,
	input  wire        adc_cmp,
	output wire        ac_en,
	output wire        ac_bg,
	output wire        ac_mux_en,
	input  wire        ac_out,
	// ---- GPIO pads, index = port*8+bit (B=0, C=1, D=2, E=3) ----
	input  wire [31:0] pad_in,
	output reg  [31:0] pad_out,
	output reg  [31:0] pad_oe,
	output reg  [31:0] pad_pu,
	output reg  [31:0] pad_ie,
	// ---- in-package serial memory ----
	output wire        fl_csn,
	output wire        fl_sck,
	output wire        fl_mosi,
	input  wire        fl_miso,
	// ---- JTAG test pads (not bonded in the 32-pin package) ----
	input  wire        jtag_tck,
	input  wire        jtag_tms,
	input  wire        jtag_tdi,
	output wire        jtag_tdo
);
	localparam NIRQ = 21;
	localparam PB = 0, PC = 8, PD = 16, PE = 24;

	// =========================================================================
	// Clock and reset
	// =========================================================================
	wire [1:0]  clksel, x_mode;
	wire [3:0]  clkpr;
	wire        x_en, rc_dis, ckout, x_rdy, osc_run, rst_ack;
	wire [7:0]  osccal;
	wire [2:0]  sm;
	wire [5:0]  cause, cause_clr;
	wire [15:0] prr;
	wire        rstdisbl, sw_rst_set;
	wire        clk_mux, clk_sys, clk_cpu, rst_n;
	wire        wdt_rst_req, dbg_rst_req;
	wire        wake_gpio, wake_wdt;
	wire [NIRQ-1:0] irq;
	wire [2:0]  src_active;

	// External clock enters through the PB6 digital pad; crystal modes use the
	// analog oscillator. The choice is static while the source is in use.
	// The selected crystal/external clock gets its own clock buffer: without one the 12 clock
	// pins on this net hang off the multiplexer's output and see a very slow edge.
	wire clk_x_sel = (x_mode == 2'd0) ? pad_in[PB+6] : clk_xa;
	wire clk_x;
	rv328_clkbuf u_xbuf (.i(clk_x_sel), .o(clk_x));

	wire pwrup_req, cpu_clk_en;
	reg  pwrup_ack, pwrup_ack_q;
	wire deep       = sm == 3'd2 || sm == 3'd3 || sm == 3'd6 || sm == 3'd7;
	wire sleep_req  = deep & ~pwrup_req & ~pwrup_ack & ~pwrup_ack_q;
	wire wake_async = wake_gpio | wake_wdt | (|irq);
`ifdef RV328_ANALOG_STUB
	// digital-first build: RESET is also the power-on reset and cannot be disabled
	wire ext_rst    = ~pad_in[PC+6];
`else
	wire ext_rst    = ~pad_in[PC+6] & ~rstdisbl;
`endif

	rv328_clkrst u_clkrst (
		.clk_rc (clk_rc), .clk_x (clk_x), .clk_lf (clk_lf), .por_n (por_n),
		.clksel (clksel), .clkpr (clkpr), .x_en (x_en), .x_rdy (x_rdy),
		.sleep_req (sleep_req), .osc_stop_en (sm == 3'd2 || sm == 3'd3),
		.wake_async (wake_async), .osc_run (osc_run),
		.ext_rst (ext_rst), .bod_rst (bod_i & bod_en), .wdt_rst (wdt_rst_req),
		.sw_rst_set (sw_rst_set), .dbg_rst (dbg_rst_req), .rst_ack (rst_ack),
		.cause (cause), .cause_clr (cause_clr), .src_active (src_active),
		.cpu_clk_en (cpu_clk_en),
		.clk_mux (clk_mux), .clk_sys (clk_sys), .clk_cpu (clk_cpu), .rst_sys_n (rst_n)
	);
	// an oscillator is never switched off while the clock mux still uses it
	assign rc_en   = (~rc_dis | src_active[0]) & osc_run;
	assign rc_trim = osccal;
	assign xo_en   = (x_en | src_active[1]) & (x_mode != 2'd0) & osc_run;
	assign xo_mode = x_mode;

	always @(posedge clk_sys or negedge rst_n)
		if (!rst_n) begin pwrup_ack <= 1'b1; pwrup_ack_q <= 1'b1; end
		else begin pwrup_ack <= pwrup_req; pwrup_ack_q <= pwrup_ack; end


	// =========================================================================
	// Debug (RISC-V debug module + JTAG DTM), reset by power-on reset only
	// =========================================================================
	wire rst_dbg_n;
	rv328_rstsync u_dbgrst (.clk(clk_mux), .arst_n(por_n), .rst_n(rst_dbg_n));

	wire        dmi_psel, dmi_penable, dmi_pwrite, dmi_pready, dmi_pslverr, dmihardreset_req;
	wire [8:0]  dmi_paddr;
	wire [31:0] dmi_pwdata, dmi_prdata;
	wire        rst_dmi_n;
	rv328_rstsync u_dmirst (.clk(clk_sys), .arst_n(rst_dbg_n & ~dmihardreset_req), .rst_n(rst_dmi_n));

	hazard3_jtag_dtm #(
		.IDCODE (32'h0328_0DEB)   // version 0, part 0x3280, placeholder manufacturer
	) u_dtm (
		.tck (jtag_tck), .trst_n (por_n), .tms (jtag_tms), .tdi (jtag_tdi), .tdo (jtag_tdo),
		.dmihardreset_req (dmihardreset_req),
		.clk_dmi (clk_sys), .rst_n_dmi (rst_dmi_n),
		.dmi_psel (dmi_psel), .dmi_penable (dmi_penable), .dmi_pwrite (dmi_pwrite),
		.dmi_paddr (dmi_paddr), .dmi_pwdata (dmi_pwdata), .dmi_prdata (dmi_prdata),
		.dmi_pready (dmi_pready), .dmi_pslverr (dmi_pslverr)
	);

	wire        sys_reset_req, hart_reset_req;
	wire        hart_req_halt, hart_req_halt_on_reset, hart_req_resume, hart_halted, hart_running;
	wire [31:0] hart_data0_rdata, hart_data0_wdata, hart_instr_data;
	wire        hart_data0_wen, hart_instr_data_vld, hart_instr_data_rdy;
	wire        hart_instr_caught_exception, hart_instr_caught_ebreak;

	hazard3_dm #(
		.N_HARTS (1), .HAVE_SBA (0), .NEXT_DM_ADDR (0)
	) u_dm (
		.clk (clk_sys), .rst_n (rst_dmi_n),
		.dmi_psel (dmi_psel), .dmi_penable (dmi_penable), .dmi_pwrite (dmi_pwrite),
		.dmi_paddr (dmi_paddr), .dmi_pwdata (dmi_pwdata), .dmi_prdata (dmi_prdata),
		.dmi_pready (dmi_pready), .dmi_pslverr (dmi_pslverr),
		.sys_reset_req (sys_reset_req), .sys_reset_done (rst_n),
		.hart_reset_req (hart_reset_req), .hart_reset_done (rst_n),
		.hart_req_halt (hart_req_halt), .hart_req_halt_on_reset (hart_req_halt_on_reset),
		.hart_req_resume (hart_req_resume), .hart_halted (hart_halted), .hart_running (hart_running),
		.hart_data0_rdata (hart_data0_rdata), .hart_data0_wdata (hart_data0_wdata),
		.hart_data0_wen (hart_data0_wen),
		.hart_instr_data (hart_instr_data), .hart_instr_data_vld (hart_instr_data_vld),
		.hart_instr_data_rdy (hart_instr_data_rdy),
		.hart_instr_caught_exception (hart_instr_caught_exception),
		.hart_instr_caught_ebreak (hart_instr_caught_ebreak),
		.sbus_addr (), .sbus_write (), .sbus_size (), .sbus_vld (), .sbus_rdy (1'b0),
		.sbus_err (1'b0), .sbus_wdata (), .sbus_rdata (32'h0)
	);
	assign dbg_rst_req = sys_reset_req | hart_reset_req;

	// =========================================================================
	// CPU
	// =========================================================================
	wire [31:0] haddr, hwdata, hrdata;
	wire        hwrite, hready;
	wire [1:0]  htrans;
	wire [2:0]  hsize;

	hazard3_cpu_1port #(
		.RESET_VECTOR        (32'h0000_0000),
		.MTVEC_INIT          (32'h0000_0000),
		.EXTENSION_A         (0),
		.EXTENSION_C         (1),
		.EXTENSION_M         (1),
		.EXTENSION_XH3IRQ    (1),
		.EXTENSION_XH3POWER  (1),
		.CSR_M_MANDATORY     (1),
		.CSR_M_TRAP          (1),
		.CSR_COUNTER         (0),
		.DEBUG_SUPPORT       (1),
		.BREAKPOINT_TRIGGERS (2),
		.NUM_IRQS            (NIRQ),
		.IRQ_PRIORITY_BITS   (0),
		.MVENDORID_VAL       (32'h0),
		.REDUCED_BYPASS      (0),
		.MULDIV_UNROLL       (2),
		.MUL_FAST            (`RV328_MUL_FAST),
		.MULH_FAST           (`RV328_MULH_FAST),
		.FAST_BRANCHCMP      (1),
		.RESET_REGFILE       (0),
		.BRANCH_PREDICTOR    (`RV328_BRANCH_PRED)
	) u_cpu (
		.clk (clk_cpu), .clk_always_on (clk_sys), .rst_n (rst_n),
		.pwrup_req (pwrup_req), .pwrup_ack (pwrup_ack), .clk_en (cpu_clk_en),
		.unblock_out (), .unblock_in (1'b0),
		.haddr (haddr), .hwrite (hwrite), .htrans (htrans), .hsize (hsize), .hburst (),
		.hprot (), .hmastlock (), .hmaster (), .hexcl (),
		.hready (hready), .hresp (1'b0), .hexokay (1'b1), .hwdata (hwdata), .hrdata (hrdata),
		.fence_i_vld (), .fence_d_vld (), .fence_rdy (1'b1),
		.dbg_req_halt (hart_req_halt), .dbg_req_halt_on_reset (hart_req_halt_on_reset),
		.dbg_req_resume (hart_req_resume), .dbg_halted (hart_halted), .dbg_running (hart_running),
		.dbg_data0_rdata (hart_data0_rdata), .dbg_data0_wdata (hart_data0_wdata),
		.dbg_data0_wen (hart_data0_wen),
		.dbg_instr_data (hart_instr_data), .dbg_instr_data_vld (hart_instr_data_vld),
		.dbg_instr_data_rdy (hart_instr_data_rdy),
		.dbg_instr_caught_exception (hart_instr_caught_exception),
		.dbg_instr_caught_ebreak (hart_instr_caught_ebreak),
		.dbg_sbus_addr (32'h0), .dbg_sbus_write (1'b0), .dbg_sbus_size (2'h0), .dbg_sbus_vld (1'b0),
		.dbg_sbus_rdy (), .dbg_sbus_err (), .dbg_sbus_wdata (32'h0), .dbg_sbus_rdata (),
		.mhartid_val (32'h0), .eco_version (4'h0),
		.irq (irq), .soft_irq (1'b0), .timer_irq (1'b0)
	);

	// =========================================================================
	// Bus: AHB-Lite decode into XIP, RAM and the peripheral register bus
	// =========================================================================
	wire a_act = hready & htrans[1];
	wire a_xip = a_act & (haddr[31:28] == 4'h0);
	wire a_ram = a_act & (haddr[31:28] == 4'h2);
	wire a_per = a_act & (haddr[31:28] == 4'h4);

	reg        d_xip, d_ram, d_per, d_write, ram_late;
	reg [11:0] d_addr;
	reg [2:0]  d_size;
	wire ram_wr_now = d_ram & d_write;
	wire ram_rd_a   = a_ram & ~hwrite;

	always @(posedge clk_sys or negedge rst_n)
		if (!rst_n) begin
			d_xip <= 0; d_ram <= 0; d_per <= 0; d_write <= 0; d_addr <= 12'h0; d_size <= 3'h0; ram_late <= 0;
		end else if (hready) begin
			d_xip <= a_xip; d_ram <= a_ram; d_per <= a_per; d_write <= hwrite & a_act;
			d_addr <= haddr[11:0]; d_size <= hsize;
			ram_late <= ram_rd_a & ram_wr_now;
		end else ram_late <= 1'b0;

	// ---- RAM: writes happen in the data phase; a read whose address phase
	// collides with a write is replayed with one wait state ----
	wire ram_rd_late = d_ram & ~d_write & ram_late;
	reg [3:0] bmask;
	always @(*) case (d_size[1:0])
		2'd0:    bmask = 4'b0001 << d_addr[1:0];
		2'd1:    bmask = d_addr[1] ? 4'b1100 : 4'b0011;
		default: bmask = 4'b1111;
	endcase
	wire [31:0] ram_q;
`ifdef RV328_SIM_RAM4K
	// Simulation only: 4 KB of RAM with the same timing, for benchmarks whose
	// rules need more data than the chip has (CoreMark: 2 KB plus stack).
	reg  [31:0] ram4k [0:1023];
	reg  [31:0] ram4k_q;
	wire [9:0]  ram4k_a = (ram_wr_now | ram_rd_late) ? d_addr[11:2] : haddr[11:2];
	always @(posedge clk_sys) if (ram_wr_now | ram_rd_a | ram_rd_late) begin
		if (ram_wr_now) begin
			if (bmask[0]) ram4k[ram4k_a][7:0]   <= hwdata[7:0];
			if (bmask[1]) ram4k[ram4k_a][15:8]  <= hwdata[15:8];
			if (bmask[2]) ram4k[ram4k_a][23:16] <= hwdata[23:16];
			if (bmask[3]) ram4k[ram4k_a][31:24] <= hwdata[31:24];
		end else ram4k_q <= ram4k[ram4k_a];
	end
	assign ram_q = ram4k_q;
`else
	rv328_ram512x32 u_ram (
		.clk   (clk_sys),
		.en    (ram_wr_now | ram_rd_a | ram_rd_late),
		.we    (ram_wr_now ? bmask : 4'b0000),
		.addr  ((ram_wr_now | ram_rd_late) ? d_addr[10:2] : haddr[10:2]),
		.wdata (hwdata),
		.rdata (ram_q)
	);
`endif

	// ---- peripheral bus ----
	wire [15:0] psel = d_per ? (16'h1 << d_addr[11:8]) : 16'h0;
	wire        pwr  = d_per & d_write;
	wire        prd  = d_per & ~d_write;
	wire [7:0]  pa   = d_addr[7:0];
	wire [31:0] rd_sys, rd_gpio, rd_tc0, rd_tc1, rd_tc2, rd_tc3, rd_tc4, rd_u0, rd_u1,
	            rd_spi0, rd_spi1, rd_twi0, rd_twi1, rd_adc, rd_wdt, rd_nvm;
	wire [31:0] prdata = rd_sys | rd_gpio | rd_tc0 | rd_tc1 | rd_tc2 | rd_tc3 | rd_tc4 | rd_u0 | rd_u1 |
	                     rd_spi0 | rd_spi1 | rd_twi0 | rd_twi1 | rd_adc | rd_wdt | rd_nvm;

	wire        xip_ready;
	wire [31:0] xip_rdata;
	assign hready = d_xip ? xip_ready : d_ram ? ~ram_rd_late : 1'b1;
	assign hrdata = d_xip ? xip_rdata : d_ram ? ram_q : d_per ? prdata : 32'h0;

	// Peripheral resets: PRR bit n holds slot n in reset
	wire [15:0] prst_n;
	genvar gi;
	generate for (gi = 0; gi < 16; gi = gi + 1) begin : g_prst
		assign prst_n[gi] = (gi >= 2 && gi <= 13) ? (rst_n & ~prr[gi]) : rst_n;
	end endgenerate

	// =========================================================================
	// Peripherals
	// =========================================================================
	wire [31:0] gpior0;
	rv328_sysctl u_sys (
		.clk (clk_sys), .rst_n (rst_n), .por_n (por_n),
		.sel (psel[0]), .wr (pwr), .addr (pa), .wdata (hwdata), .rdata (rd_sys),
		.clksel (clksel), .clkpr (clkpr), .x_en (x_en), .x_mode (x_mode), .rc_dis (rc_dis),
		.ckout (ckout), .osccal (osccal), .x_rdy (x_rdy), .sm (sm),
		.cause (cause), .cause_clr (cause_clr), .prr (prr), .rstdisbl (rstdisbl),
		.sw_rst_set (sw_rst_set), .bod_en (bod_en), .bod_level (bod_level), .bod_i (bod_i),
		.gpior0 (gpior0)
	);

	wire [31:0] pin_s, port, ddr;
	wire [3:0]  irq_pc;
	wire [1:0]  irq_int;
	wire        int0_evt;
	rv328_gpio u_gpio (
		.clk (clk_sys), .rst_n (rst_n),
		.sel (psel[1]), .wr (pwr), .addr (pa), .wdata (hwdata), .rdata (rd_gpio),
		.pin_i (pad_in), .pin_s (pin_s), .port_o (port), .ddr_o (ddr),
		.irq_pc (irq_pc), .irq_int (irq_int), .int0_evt (int0_evt), .wake_async (wake_gpio)
	);

	// ---- timers ----
	wire aco, acoe, acic;
	wire oc0a, oc0b, oc0a_en, oc0b_en, oc1a, oc1b, oc1a_en, oc1b_en, oc2a, oc2b, oc2a_en, oc2b_en;
	wire oc3a, oc3b, oc3a_en, oc3b_en, oc4a, oc4b, oc4a_en, oc4b_en;
	wire irq_tc0, irq_tc1, irq_tc2, irq_tc3, irq_tc4;
	wire tc0_ovf, tc0_oca, tc1_ovf, tc1_ocb, tc1_ic;

	// 32.768 kHz tick for TC2 asynchronous operation
	wire tosc_s; reg tosc_q;
	rv328_sync u_tosc (.clk(clk_sys), .rst_n(rst_n), .d(clk_x & (x_mode == 2'd3)), .q(tosc_s));
	always @(posedge clk_sys or negedge rst_n) if (!rst_n) tosc_q <= 1'b0; else tosc_q <= tosc_s;
	wire tosc_tick = tosc_s & ~tosc_q;

	rv328_timer #(.W(8)) u_tc0 (
		.clk (clk_sys), .rst_n (prst_n[2]),
		.sel (psel[2]), .wr (pwr), .addr (pa), .wdata (hwdata), .rdata (rd_tc0),
		.t_i (pin_s[PD+4]), .icp_i (1'b0), .async_tick (1'b0),
		.oca (oc0a), .ocb (oc0b), .oca_en (oc0a_en), .ocb_en (oc0b_en), .irq (irq_tc0),
		.ovf_evt (tc0_ovf), .oca_evt (tc0_oca), .ocb_evt (), .ic_evt ()
	);
	rv328_timer #(.W(16)) u_tc1 (
		.clk (clk_sys), .rst_n (prst_n[3]),
		.sel (psel[3]), .wr (pwr), .addr (pa), .wdata (hwdata), .rdata (rd_tc1),
		.t_i (pin_s[PD+5]), .icp_i (acic ? aco : pin_s[PB+0]), .async_tick (1'b0),
		.oca (oc1a), .ocb (oc1b), .oca_en (oc1a_en), .ocb_en (oc1b_en), .irq (irq_tc1),
		.ovf_evt (tc1_ovf), .oca_evt (), .ocb_evt (tc1_ocb), .ic_evt (tc1_ic)
	);
	rv328_timer #(.W(8)) u_tc2 (
		.clk (clk_sys), .rst_n (prst_n[4]),
		.sel (psel[4]), .wr (pwr), .addr (pa), .wdata (hwdata), .rdata (rd_tc2),
		.t_i (1'b0), .icp_i (1'b0), .async_tick (tosc_tick),
		.oca (oc2a), .ocb (oc2b), .oca_en (oc2a_en), .ocb_en (oc2b_en), .irq (irq_tc2),
		.ovf_evt (), .oca_evt (), .ocb_evt (), .ic_evt ()
	);
	rv328_timer #(.W(16)) u_tc3 (
		.clk (clk_sys), .rst_n (prst_n[5]),
		.sel (psel[5]), .wr (pwr), .addr (pa), .wdata (hwdata), .rdata (rd_tc3),
		.t_i (pin_s[PE+3]), .icp_i (pin_s[PE+2]), .async_tick (1'b0),
		.oca (oc3a), .ocb (oc3b), .oca_en (oc3a_en), .ocb_en (oc3b_en), .irq (irq_tc3),
		.ovf_evt (), .oca_evt (), .ocb_evt (), .ic_evt ()
	);
	rv328_timer #(.W(16)) u_tc4 (
		.clk (clk_sys), .rst_n (prst_n[6]),
		.sel (psel[6]), .wr (pwr), .addr (pa), .wdata (hwdata), .rdata (rd_tc4),
		.t_i (pin_s[PE+1]), .icp_i (pin_s[PE+0]), .async_tick (1'b0),
		.oca (oc4a), .ocb (oc4b), .oca_en (oc4a_en), .ocb_en (oc4b_en), .irq (irq_tc4),
		.ovf_evt (), .oca_evt (), .ocb_evt (), .ic_evt ()
	);

	// ---- USARTs ----
	wire txd0, txen0, rxen0, irq_u0, txd1, txen1, rxen1, irq_u1;
	rv328_usart u_usart0 (
		.clk (clk_sys), .rst_n (prst_n[7]),
		.sel (psel[7]), .wr (pwr), .rd (prd), .addr (pa), .wdata (hwdata), .rdata (rd_u0),
		.rxd_i (pin_s[PD+0] | ~rxen0), .txd_o (txd0), .txen_o (txen0), .rxen_o (rxen0), .irq (irq_u0)
	);
	rv328_usart u_usart1 (
		.clk (clk_sys), .rst_n (prst_n[8]),
		.sel (psel[8]), .wr (pwr), .rd (prd), .addr (pa), .wdata (hwdata), .rdata (rd_u1),
		.rxd_i (pin_s[PB+4] | ~rxen1), .txd_o (txd1), .txen_o (txen1), .rxen_o (rxen1), .irq (irq_u1)
	);

	// ---- SPI ----
	wire sck0, sdo0, spe0, mstr0, irq_spi0, sck1, sdo1, spe1, mstr1, irq_spi1;
	rv328_spi u_spi0 (
		.clk (clk_sys), .rst_n (prst_n[9]),
		.sel (psel[9]), .wr (pwr), .rd (prd), .addr (pa), .wdata (hwdata), .rdata (rd_spi0),
		.sck_i (pin_s[PB+5]), .mosi_i (pin_s[PB+3]), .miso_i (pin_s[PB+4]), .ss_i (pin_s[PB+2]),
		.sck_o (sck0), .sdo_o (sdo0), .spe_o (spe0), .mstr_o (mstr0), .irq (irq_spi0)
	);
	rv328_spi u_spi1 (
		.clk (clk_sys), .rst_n (prst_n[10]),
		.sel (psel[10]), .wr (pwr), .rd (prd), .addr (pa), .wdata (hwdata), .rdata (rd_spi1),
		.sck_i (pin_s[PC+1]), .mosi_i (pin_s[PE+3]), .miso_i (pin_s[PC+0]), .ss_i (pin_s[PE+2]),
		.sck_o (sck1), .sdo_o (sdo1), .spe_o (spe1), .mstr_o (mstr1), .irq (irq_spi1)
	);

	// ---- TWI ----
	wire scl0, sda0, twen0, irq_twi0, scl1, sda1, twen1, irq_twi1;
	rv328_twi u_twi0 (
		.clk (clk_sys), .rst_n (prst_n[11]),
		.sel (psel[11]), .wr (pwr), .addr (pa), .wdata (hwdata), .rdata (rd_twi0),
		.scl_i (pin_s[PC+5]), .sda_i (pin_s[PC+4]), .scl_o (scl0), .sda_o (sda0),
		.twen_o (twen0), .irq (irq_twi0)
	);
	rv328_twi u_twi1 (
		.clk (clk_sys), .rst_n (prst_n[12]),
		.sel (psel[12]), .wr (pwr), .addr (pa), .wdata (hwdata), .rdata (rd_twi1),
		.scl_i (pin_s[PE+1]), .sda_i (pin_s[PE+0]), .scl_o (scl1), .sda_o (sda1),
		.twen_o (twen1), .irq (irq_twi1)
	);

	// ---- ADC and analog comparator ----
	wire [7:0] didr0;
	wire [1:0] didr1;
	wire       irq_adc, irq_ac;
	reg        aco_q;
	always @(posedge clk_sys or negedge rst_n) if (!rst_n) aco_q <= 1'b0; else aco_q <= aco;
	rv328_adc u_adc (
		.clk (clk_sys), .rst_n (prst_n[13]),
		.sel (psel[13]), .wr (pwr), .addr (pa), .wdata (hwdata), .rdata (rd_adc),
		.trig_i ({tc1_ic, tc1_ovf, tc1_ocb, tc0_ovf, tc0_oca, int0_evt, aco & ~aco_q, 1'b0}),
		.adc_en (adc_en), .adc_mux (adc_mux), .adc_refs (adc_refs), .adc_sample (adc_sample),
		.adc_dac (adc_dac), .adc_cmp (adc_cmp),
		.ac_en (ac_en), .ac_bg (ac_bg), .ac_mux_en (ac_mux_en), .ac_out (ac_out),
		.didr0 (didr0), .didr1 (didr1), .aco (aco), .acoe (acoe), .acic (acic),
		.irq_adc (irq_adc), .irq_ac (irq_ac)
	);

	// ---- watchdog ----
	wire irq_wdt;
	rv328_wdt u_wdt (
		.clk (clk_sys), .rst_n (rst_n),
		.sel (psel[14]), .wr (pwr), .addr (pa), .wdata (hwdata), .rdata (rd_wdt),
		.clk_wdt (clk_lf), .por_n (por_n), .rst_ack (rst_ack), .rst_req (wdt_rst_req),
		.irq (irq_wdt), .wake_async (wake_wdt)
	);

	// ---- program memory / NVM ----
	wire xip_csn, xip_sck, xip_mosi, irq_nvm;
	rv328_xip #(.WAY_KB (`RV328_CACHE_KB), .WAYS (`RV328_CACHE_WAYS), .PIN_KB (`RV328_CACHE_PIN)) u_xip (
		.clk (clk_sys), .rst_n (rst_n),
		.a_valid (a_xip & ~hwrite), .a_addr (haddr[19:0]), .d_ready (xip_ready), .d_rdata (xip_rdata),
		.sel (psel[15]), .wr (pwr), .addr (pa), .wdata (hwdata), .rdata (rd_nvm),
		.spi_csn (xip_csn), .spi_sck (xip_sck), .spi_mosi (xip_mosi), .spi_miso (fl_miso),
		.irq (irq_nvm)
	);

	assign irq = {irq_nvm, irq_ac, irq_adc, irq_twi1, irq_twi0, irq_u1, irq_u0, irq_spi1, irq_spi0,
	              irq_tc4, irq_tc3, irq_tc2, irq_tc1, irq_tc0, irq_wdt, irq_pc[3], irq_pc[2],
	              irq_pc[1], irq_pc[0], irq_int[1], irq_int[0]};

	// =========================================================================
	// Pin multiplexing (ATmega328PB alternate-function assignment)
	// =========================================================================
	// In-system programming: while RESET is held low, PB2..PB5 are wired
	// straight through to the serial memory (PB2 = CS#, PB3 = MOSI, PB4 = MISO,
	// PB5 = SCK), so any SPI programmer can load the program image.
	wire isp = ext_rst;
	assign fl_csn  = isp ? pad_in[PB+2] : xip_csn;
	assign fl_sck  = isp ? pad_in[PB+5] : xip_sck;
	assign fl_mosi = isp ? pad_in[PB+3] : xip_mosi;

	always @(*) begin
		pad_out = port;
		pad_oe  = ddr;
		pad_pu  = port & ~ddr;
		pad_ie  = 32'h0FFF_7FFF;

		// ---- port B ----
		if (oc1a_en) pad_out[PB+1] = oc1a;
		if (oc1b_en) pad_out[PB+2] = oc1b;
		if (oc2a_en) pad_out[PB+3] = oc2a;
		if (spe0) begin
			if (mstr0) begin
				pad_out[PB+3] = sdo0; pad_out[PB+5] = sck0; pad_oe[PB+4] = 1'b0;
			end else begin
				pad_oe[PB+2] = 1'b0; pad_oe[PB+3] = 1'b0; pad_oe[PB+5] = 1'b0;
				pad_out[PB+4] = sdo0;
			end
		end
		if (txen1) begin pad_oe[PB+3] = 1'b1; pad_out[PB+3] = txd1; end
		if (rxen1) pad_oe[PB+4] = 1'b0;
		if (ckout) begin pad_oe[PB+0] = 1'b1; pad_out[PB+0] = clk_sys; end
		if (x_en) begin
			pad_oe[PB+6] = 1'b0; pad_pu[PB+6] = 1'b0;
`ifndef RV328_ANALOG_STUB
			// crystal modes hand both pins to the analog oscillator (not in the
			// digital-first build, where PB6 is the only clock input)
			if (x_mode != 2'd0) begin
				pad_ie[PB+6] = 1'b0; pad_oe[PB+7] = 1'b0; pad_pu[PB+7] = 1'b0; pad_ie[PB+7] = 1'b0;
			end
`endif
		end

		// ---- port C ----
		pad_ie[PC+5:PC] = ~didr0[5:0];
		if (spe1) begin
			if (mstr1) begin
				pad_out[PC+1] = sck1; pad_oe[PC+0] = 1'b0; pad_out[PE+3] = sdo1;
			end else begin
				pad_oe[PC+1] = 1'b0; pad_oe[PE+3] = 1'b0; pad_oe[PE+2] = 1'b0;
				pad_out[PC+0] = sdo1;
			end
		end
		if (twen0) begin
			pad_out[PC+4] = 1'b0; pad_oe[PC+4] = ~sda0;
			pad_out[PC+5] = 1'b0; pad_oe[PC+5] = ~scl0;
		end
		if (!rstdisbl) begin pad_oe[PC+6] = 1'b0; pad_pu[PC+6] = 1'b1; end

		// ---- port D ----
		if (oc3a_en) pad_out[PD+0] = oc3a;
		if (oc4a_en) pad_out[PD+1] = oc4a;
		// output compare modulator on PD2: PORTD2 selects OR (1) or AND (0)
		if (oc3b_en & oc4b_en) pad_out[PD+2] = port[PD+2] ? (oc3b | oc4b) : (oc3b & oc4b);
		else if (oc3b_en)      pad_out[PD+2] = oc3b;
		else if (oc4b_en)      pad_out[PD+2] = oc4b;
		if (oc2b_en) pad_out[PD+3] = oc2b;
		if (oc0b_en) pad_out[PD+5] = oc0b;
		if (oc0a_en) pad_out[PD+6] = oc0a;
		if (rxen0) pad_oe[PD+0] = 1'b0;
		if (txen0) begin pad_oe[PD+1] = 1'b1; pad_out[PD+1] = txd0; end
		if (didr1[0]) pad_ie[PD+6] = 1'b0;
		if (didr1[1]) pad_ie[PD+7] = 1'b0;

		// ---- port E ----
		if (acoe) begin pad_oe[PE+0] = 1'b1; pad_out[PE+0] = aco; end
		if (twen1) begin
			pad_out[PE+0] = 1'b0; pad_oe[PE+0] = ~sda1;
			pad_out[PE+1] = 1'b0; pad_oe[PE+1] = ~scl1;
		end
		if (didr0[6]) pad_ie[PE+2] = 1'b0;
		if (didr0[7]) pad_ie[PE+3] = 1'b0;

		// ---- in-system programming ----
		if (isp) begin
			pad_oe = 32'h0; pad_pu = 32'h0; pad_pu[PC+6] = 1'b1;
			pad_ie = 32'h0FFF_7FFF;
			pad_out[PB+4] = fl_miso; pad_oe[PB+4] = ~pad_in[PB+2];
		end

`ifdef RV328_ANALOG_STUB
		// Digital-first build: with no power-on reset cell, every flop starts in
		// an unknown state. The reset and clock pins must therefore be inputs
		// unconditionally, or the chip could block its own reset.
		pad_oe[PC+6] = 1'b0; pad_pu[PC+6] = 1'b1; pad_ie[PC+6] = 1'b1;
		pad_oe[PB+6] = 1'b0; pad_pu[PB+6] = 1'b0; pad_ie[PB+6] = 1'b1;
`endif
	end

	// simulation/debug visibility
	wire [31:0] dbg_gpior0 = gpior0;
endmodule
`default_nettype wire
