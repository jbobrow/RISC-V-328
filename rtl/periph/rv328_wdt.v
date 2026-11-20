// RV328 watchdog timer. The counter runs in its own clock domain (clk_wdt,
// the always-on 128 kHz oscillator) so that it survives a stopped or failed
// system clock and can wake the chip from power-down.
//
//   0x00 WDTCSR  [7] WDIF (W1C) [6] WDIE [4] WDE [3:0] WDP
//                timeout = 2048 * 2^WDP cycles of clk_wdt (16 ms .. 8 s, WDP 0..9)
//                Writes are ignored unless bits [31:24] = 0xA5.
//                Changing WDIE/WDE/WDP restarts the period.
//   0x04 WDR     write 0x5A to restart the counter (the AVR "wdr" instruction)
//
// WDE=0 WDIE=1: interrupt.  WDE=1 WDIE=0: system reset.
// WDE=1 WDIE=1: interrupt first; if WDIF is still set at the next timeout, reset.
`default_nettype none
module rv328_wdt (
	input  wire        clk,
	input  wire        rst_n,
	input  wire        sel,
	input  wire        wr,
	input  wire [7:0]  addr,
	input  wire [31:0] wdata,
	output reg  [31:0] rdata,

	input  wire        clk_wdt,
	input  wire        por_n,       // power-on reset: the only reset of the request flop
	input  wire        rst_ack,     // reset controller has latched the request (async level)
	output wire        rst_req,     // watchdog reset request (clk_wdt domain, held until ack)
	output wire        irq,
	output wire        wake_async   // timeout seen but not yet synchronised
);
	reg        wdif, wdie, wde;
	reg [3:0]  wdp;
	reg        kick_t;              // toggles on every WDR / config write

	wire w = sel & wr;

	// ---------------- clk_wdt domain ----------------
	wire rst_w_n, en_w, kick_w, armed_w;
	rv328_rstsync u_rs  (.clk(clk_wdt), .arst_n(rst_n), .rst_n(rst_w_n));
	rv328_sync    u_en  (.clk(clk_wdt), .rst_n(rst_w_n), .d(wde | wdie), .q(en_w));
	rv328_sync    u_kk  (.clk(clk_wdt), .rst_n(rst_w_n), .d(kick_t), .q(kick_w));
	// "reset on this timeout": WDE without WDIE, or WDE with the interrupt still pending
	rv328_sync    u_arm (.clk(clk_wdt), .rst_n(rst_w_n), .d(wde & (~wdie | wdif)), .q(armed_w));

	reg [20:0] cnt;
	reg        kick_q, evt_t;
	wire       timeout = cnt[11 + wdp];
	always @(posedge clk_wdt or negedge rst_w_n)
		if (!rst_w_n) begin cnt <= 21'h0; kick_q <= 1'b0; evt_t <= 1'b0; end
		else begin
			kick_q <= kick_w;
			if (!en_w || (kick_w ^ kick_q) || timeout) cnt <= 21'h0;
			else cnt <= cnt + 21'h1;
			if (en_w && timeout) evt_t <= ~evt_t;
		end

	// Reset request survives the reset it causes; cleared once acknowledged.
	wire ack_w;
	reg  req;
	rv328_sync u_ack (.clk(clk_wdt), .rst_n(por_n), .d(rst_ack), .q(ack_w));
	always @(posedge clk_wdt or negedge por_n)
		if (!por_n) req <= 1'b0;
		else if (ack_w) req <= 1'b0;
		else if (rst_w_n && en_w && timeout && armed_w) req <= 1'b1;
	assign rst_req = req;

	// ---------------- system domain ----------------
	wire evt_s;
	reg  evt_q;
	rv328_sync u_evt (.clk(clk), .rst_n(rst_n), .d(evt_t), .q(evt_s));
	wire evt = evt_s ^ evt_q;
	wire key = wdata[31:24] == 8'hA5;
	wire [3:0] wdp_w = wdata[3:0] > 4'd9 ? 4'd9 : wdata[3:0];

	always @(posedge clk or negedge rst_n)
		if (!rst_n) begin
			wdif <= 0; wdie <= 0; wde <= 0; wdp <= 4'h0; kick_t <= 1'b0; evt_q <= 1'b0;
		end else begin
			evt_q <= evt_s;
			if (evt) wdif <= 1'b1;
			if (w && addr[2] == 1'b0 && key) begin
				wdie <= wdata[6]; wde <= wdata[4]; wdp <= wdp_w;
				if (wdata[7]) wdif <= evt;
				// a configuration change restarts the period; clearing WDIF alone does not
				if ({wdata[6], wdata[4], wdp_w} != {wdie, wde, wdp}) kick_t <= ~kick_t;
			end
			if (w && addr[2] && wdata[7:0] == 8'h5A) kick_t <= ~kick_t;
		end

	always @(*) begin
		rdata = 32'h0;
		if (sel && !addr[2]) rdata = {24'h0, wdif, wdie, 1'b0, wde, wdp};
	end

	assign irq = wdif & wdie;
	// evt_t and evt_q are flops in different domains; their XOR is a level
	// that stays high from the timeout until the system clock has run again.
	assign wake_async = (evt_t ^ evt_q) & wdie;
endmodule
`default_nettype wire
