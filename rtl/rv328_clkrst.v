// RV328 clock and reset generation.
//
// Clock tree:  {clk_rc, clk_x, clk_lf} -> glitch-free mux -> clk_mux
//              clk_mux -> clock gate (system prescaler + sleep) -> clk_sys
//
// Everything in this module is reset by power-on reset only, except the clock
// mux which is also forced back to the RC oscillator by any reset request, so
// a reset always recovers from a dead external clock.
`default_nettype none
// One leg of the glitch-free clock multiplexer: the request is registered on
// the rising edge and applied on the falling edge of that leg's own clock.
module rv328_clkmux_en #(
	parameter RST = 1'b0
) (
	input  wire clk,
	input  wire arst_n,
	input  wire want,
	output reg  en_p,
	output reg  en_n
);
	always @(posedge clk or negedge arst_n)
		if (!arst_n) en_p <= RST;
		else         en_p <= want;
	always @(negedge clk or negedge arst_n)
		if (!arst_n) en_n <= RST;
		else         en_n <= en_p;
endmodule

module rv328_clkrst (
	input  wire       clk_rc,      // internal RC oscillator (reset default)
	input  wire       clk_x,       // crystal oscillator / external clock
	input  wire       clk_lf,      // 128 kHz low-frequency oscillator
	input  wire       por_n,

	input  wire [1:0] clksel,      // 0 RC, 1 X, 2 LF
	input  wire [3:0] clkpr,       // system clock = clk_mux / 2^clkpr
	input  wire       x_en,
	output wire       x_rdy,       // clk_x has been seen toggling (clk_x domain level)

	input  wire       sleep_req,   // stop clk_sys (CPU is asleep in a clock-stopping mode)
	input  wire       osc_stop_en, // sleep mode also stops the oscillators
	input  wire       wake_async,  // asynchronous wake request (level)
	output wire       osc_run,     // 0 = oscillators may be powered down

	input  wire       ext_rst,     // asynchronous reset requests, active high
	input  wire       bod_rst,
	input  wire       wdt_rst,
	input  wire       sw_rst_set,  // one clk_sys cycle
	input  wire       dbg_rst,
	output wire       rst_ack,
	output reg  [5:0] cause,       // {DBG, SW, WDT, BOD, EXT, POR}
	input  wire [5:0] cause_clr,

	output wire [2:0] src_active,  // clock source still in use by the mux {LF, X, RC}
	input  wire       cpu_clk_en,  // from the CPU's power controller (clk_sys domain)

	output wire       clk_mux,
	output wire       clk_sys,
	output wire       clk_cpu,     // clk_sys gated by cpu_clk_en
	output wire       rst_sys_n
);
	// ---------------- reset requests ----------------
	reg sw_req;
	wire [4:0] req_raw = {dbg_rst, sw_req, wdt_rst, bod_rst, ext_rst};
	wire       req_any = |req_raw;
	(* keep *) wire arst_n = por_n & ~req_any;

	// ---------------- glitch-free clock mux ----------------
	wire [2:0] cki = {clk_lf, clk_x, clk_rc};
	wire [2:0] want = {clksel == 2'd2, clksel == 2'd1, clksel == 2'd0 || clksel == 2'd3};
	wire [2:0] en_p, en_n;
	genvar i;
	generate for (i = 0; i < 3; i = i + 1) begin : g_mux
		rv328_clkmux_en #(.RST(i == 0)) u_en (
			.clk (cki[i]), .arst_n (arst_n),
			.want (want[i] & ~|(en_n & ~(3'b001 << i))),
			.en_p (en_p[i]), .en_n (en_n[i])
		);
	end endgenerate
	assign src_active = en_p | en_n;
	assign clk_mux = (cki[0] & en_n[0]) | (cki[1] & en_n[1]) | (cki[2] & en_n[2]);

	// clk_x activity detector
	reg [7:0] xcnt;
	// x_en comes from the system clock domain: assert the counter's reset at once, release it
	// through a synchroniser on clk_x.
	wire x_arst_n = por_n & x_en;
	wire x_rst_n;
	rv328_rstsync u_xrst (.clk(clk_x), .arst_n(x_arst_n), .rst_n(x_rst_n));
	always @(posedge clk_x or negedge x_rst_n)
		if (!x_rst_n) xcnt <= 8'h0;
		else if (!xcnt[7]) xcnt <= xcnt + 8'h1;
	assign x_rdy = xcnt[7];

	// ---------------- reset controller (POR-only state) ----------------
	wire [4:0] req_s;
	generate for (i = 0; i < 5; i = i + 1) begin : g_req
		rv328_sync u_s (.clk(clk_mux), .rst_n(por_n), .d(req_raw[i]), .q(req_s[i]));
	end endgenerate

	reg [7:0] hold;
	reg       hold_q;
	always @(posedge clk_mux or negedge por_n)
		if (!por_n) begin
			cause <= 6'b000001; hold <= 8'hFF; hold_q <= 1'b1; sw_req <= 1'b0;
		end else begin
			cause <= (cause & ~cause_clr) | {req_s, 1'b0};
			if (|req_s)            hold <= 8'hFF;
			else if (hold != 8'h0) hold <= hold - 8'h1;
			hold_q <= (|req_s) | (hold != 8'h0);
			if (req_s[3])        sw_req <= 1'b0;
			else if (sw_rst_set) sw_req <= 1'b1;
		end
	assign rst_ack = |req_s;

	(* keep *) wire sys_arst_n = arst_n & ~hold_q;
	rv328_rstsync u_rst (.clk(clk_mux), .arst_n(sys_arst_n), .rst_n(rst_sys_n));

	// ---------------- prescaler, sleep and wake ----------------
	reg [7:0] pcnt;
	always @(posedge clk_mux or negedge por_n)
		if (!por_n) pcnt <= 8'h0;
		else        pcnt <= pcnt + 8'h1;
	wire [7:0] pmask = clkpr >= 4'd8 ? 8'hFF : ~(8'hFF << clkpr[2:0]);
	wire tick = (pcnt & pmask) == 8'h0;

	// Wake latch: set asynchronously (works with no clock), cleared once the
	// CPU is awake again or when nothing came of the wake-up.
	reg       wake_l;
	reg [4:0] wcnt;
	wire      wake_set = wake_async & sleep_req;
	wire      wake_tmo = wcnt[4];
	always @(posedge clk_mux or posedge wake_set)
		if (wake_set) wake_l <= 1'b1;
		else if (!sleep_req || wake_tmo) wake_l <= 1'b0;
	wire wake_s;
	rv328_sync u_wk (.clk(clk_mux), .rst_n(por_n), .d(wake_l), .q(wake_s));
	always @(posedge clk_mux or negedge por_n)
		if (!por_n) wcnt <= 5'h0;
		else if (!sleep_req || !wake_s || wake_tmo) wcnt <= 5'h0;
		else if (tick) wcnt <= wcnt + 5'h1;

	wire run = ~sleep_req | wake_s;
	rv328_icg u_gate (.clk(clk_mux), .en(tick & run), .gclk(clk_sys));
	// The CPU clock gate sits beside the system gate, not behind it: both clocks
	// then leave gates at the same depth and their trees balance. cpu_clk_en only
	// changes after a clk_sys edge, so this is the same waveform as gating clk_sys.
	rv328_icg u_cpugate (.clk(clk_mux), .en(tick & run & cpu_clk_en), .gclk(clk_cpu));
	assign osc_run = ~(sleep_req & osc_stop_en) | wake_l;
endmodule
`default_nettype wire
