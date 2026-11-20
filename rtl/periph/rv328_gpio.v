// RV328 GPIO: ports B, C, D, E with AVR PIN/DDR/PORT semantics, pin-change
// interrupts (PCINT0..3, one group per port) and external interrupts INT0/INT1.
//
// Pins are indexed port*8+bit: PB0..7 = 0..7, PC0..6 = 8..14, PD0..7 = 16..23,
// PE0..3 = 24..27.
//
// Register map (32-bit, word access):
//   0x00+16p PIN    R: synchronised pin level. W: 1 toggles PORT bit
//   0x04+16p DDR    1 = output
//   0x08+16p PORT   output level; with DDR=0, 1 enables the pull-up
//   0x0C+16p PCMSK  pin-change interrupt mask
//   0x40 PCICR  [3:0] group enables      0x44 PCIFR [3:0] flags (W1C)
//   0x48 EICRA  [1:0] ISC0, [3:2] ISC1   (0 low level, 1 any edge, 2 falling, 3 rising)
//   0x4C EIMSK  [1:0]                    0x50 EIFR  [1:0] flags (W1C)
`default_nettype none
module rv328_gpio (
	input  wire        clk,
	input  wire        rst_n,
	input  wire        sel,
	input  wire        wr,
	input  wire [7:0]  addr,
	input  wire [31:0] wdata,
	output reg  [31:0] rdata,

	input  wire [31:0] pin_i,     // raw pad inputs
	output wire [31:0] pin_s,     // synchronised pad inputs
	output wire [31:0] port_o,
	output wire [31:0] ddr_o,

	output wire [3:0]  irq_pc,
	output wire [1:0]  irq_int,
	output wire        int0_evt,
	output wire        wake_async  // level, combinational from pads: for deep-sleep wake
);
	localparam [31:0] IMPL = 32'h0FFF_7FFF;

	reg  [31:0] ddr, port, pcmsk;
	reg  [31:0] s0, s1, pin_q;
	reg  [3:0]  pcicr, pcifr;
	reg  [3:0]  eicra;
	reg  [1:0]  eimsk, eifr;

	wire        w    = sel & wr;
	wire [1:0]  p    = addr[5:4];
	wire [31:0] wm   = {24'h0, wdata[7:0]} << {p, 3'b000};
	wire [31:0] bm   = 32'hFF << {p, 3'b000};

	// Pin synchronisers
	always @(posedge clk or negedge rst_n)
		if (!rst_n) begin s0 <= 32'h0; s1 <= 32'h0; pin_q <= 32'h0; end
		else begin s0 <= pin_i & IMPL; s1 <= s0; pin_q <= s1; end
	assign pin_s = s1;

	wire [31:0] chg = (s1 ^ pin_q) & pcmsk;
	wire [3:0]  pc_evt = {|chg[31:24], |chg[23:16], |chg[15:8], |chg[7:0]};

	// INT0 = PD2 (18), INT1 = PD3 (19)
	wire [1:0] ei_now  = {s1[19], s1[18]};
	wire [1:0] ei_prev = {pin_q[19], pin_q[18]};
	reg  [1:0] ei_evt;
	integer k;
	always @(*) for (k = 0; k < 2; k = k + 1)
		case (eicra[2*k +: 2])
			2'd1:    ei_evt[k] = ei_now[k] ^ ei_prev[k];
			2'd2:    ei_evt[k] = ~ei_now[k] & ei_prev[k];
			2'd3:    ei_evt[k] = ei_now[k] & ~ei_prev[k];
			default: ei_evt[k] = 1'b0;
		endcase
	wire [1:0] ei_level = {eicra[3:2] == 2'd0, eicra[1:0] == 2'd0};

	always @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			ddr <= 32'h0; port <= 32'h0; pcmsk <= 32'h0;
			pcicr <= 4'h0; pcifr <= 4'h0; eicra <= 4'h0; eimsk <= 2'h0; eifr <= 2'h0;
		end else begin
			pcifr <= pcifr | pc_evt;
			eifr  <= eifr | ei_evt;
			if (w) begin
				if (!addr[6]) case (addr[3:2])
					2'd0: port  <= (port ^ wm) & IMPL;
					2'd1: ddr   <= ((ddr   & ~bm) | wm) & IMPL;
					2'd2: port  <= ((port  & ~bm) | wm) & IMPL;
					2'd3: pcmsk <= ((pcmsk & ~bm) | wm) & IMPL;
				endcase else case (addr[4:2])
					3'd0: pcicr <= wdata[3:0];
					3'd1: pcifr <= (pcifr & ~wdata[3:0]) | pc_evt;
					3'd2: eicra <= wdata[3:0];
					3'd3: eimsk <= wdata[1:0];
					3'd4: eifr  <= (eifr & ~wdata[1:0]) | ei_evt;
					default: ;
				endcase
			end
		end
	end

	wire [4:0] sh = {p, 3'b000};
	always @(*) begin
		rdata = 32'h0;
		if (sel) begin
			if (!addr[6]) case (addr[3:2])
				2'd0: rdata = (s1    >> sh) & 32'hFF;
				2'd1: rdata = (ddr   >> sh) & 32'hFF;
				2'd2: rdata = (port  >> sh) & 32'hFF;
				2'd3: rdata = (pcmsk >> sh) & 32'hFF;
			endcase else case (addr[4:2])
				3'd0: rdata = {28'h0, pcicr};
				3'd1: rdata = {28'h0, pcifr};
				3'd2: rdata = {28'h0, eicra};
				3'd3: rdata = {30'h0, eimsk};
				3'd4: rdata = {30'h0, eifr};
				default: ;
			endcase
		end
	end

	assign port_o = port;
	assign ddr_o  = ddr;
	assign irq_pc = pcifr & pcicr;
	// Level-sensitive mode: interrupt request follows the (inverted) pin
	assign irq_int  = eimsk & ((ei_level & ~ei_now) | (~ei_level & eifr));
	assign int0_evt = ei_evt[0];

	// Asynchronous wake request: an unmasked pin differs from its last sampled
	// value, or a level interrupt is active. Purely combinational from the
	// pads so that it works with every clock stopped.
	wire [31:0] diff = ((pin_i & IMPL) ^ pin_q) & pcmsk;
	wire [3:0]  diff_g = {|diff[31:24], |diff[23:16], |diff[15:8], |diff[7:0]};
	wire [1:0]  raw_ei = {pin_i[19], pin_i[18]};
	wire [1:0]  ei_diff = raw_ei ^ ei_prev;
	assign wake_async = (|(diff_g & pcicr)) |
		(|(eimsk & ((ei_level & ~raw_ei) | (~ei_level & ei_diff))));
endmodule
`default_nettype wire
