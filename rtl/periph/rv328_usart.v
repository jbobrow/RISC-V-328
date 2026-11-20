// RV328 USART (asynchronous mode). Frame formats and flags follow the AVR USART.
//
//   0x00 DATA [8:0]  read: receive buffer, write: transmit buffer
//   0x04 SR   [7] RXC  [6] TXC (W1C)  [5] UDRE  [4] FE  [3] DOR  [2] UPE
//   0x08 CR   [7] RXCIE [6] TXCIE [5] UDRIE [4] RXEN [3] TXEN [1] U2X
//   0x0C FMT  [2:0] CHSIZE (0..4 = 5..9 data bits)  [3] USBS (1 = two stop bits)
//             [5:4] UPM (0 none, 2 even, 3 odd)
//   0x10 BRR  [15:0]  baud = fclk / (16 * (BRR + 1)), or / (8 * (BRR + 1)) with U2X
`default_nettype none
module rv328_usart (
	input  wire        clk,
	input  wire        rst_n,
	input  wire        sel,
	input  wire        wr,
	input  wire        rd,
	input  wire [7:0]  addr,
	input  wire [31:0] wdata,
	output reg  [31:0] rdata,
	input  wire        rxd_i,   // synchronised
	output wire        txd_o,
	output wire        txen_o,
	output wire        rxen_o,
	output wire        irq
);
	reg        rxcie, txcie, udrie, rxen, txen, u2x;
	reg [2:0]  chsize;
	reg        usbs;
	reg [1:0]  upm;
	reg [15:0] brr;

	wire w = sel & wr;
	wire [3:0] nbits = 4'd5 + {1'b0, chsize};

	// --- baud generator: one tick per 1/16 (or 1/8) bit ---------------------
	reg [15:0] bcnt;
	wire btick = bcnt == 16'h0;
	always @(posedge clk or negedge rst_n)
		if (!rst_n) bcnt <= 16'h0;
		else if (btick || (w && addr[4:2] == 3'd4)) bcnt <= (w && addr[4:2] == 3'd4) ? wdata[15:0] : brr;
		else bcnt <= bcnt - 16'h1;
	wire [3:0] os_last = u2x ? 4'd7 : 4'd15;
	wire [3:0] os_mid  = u2x ? 4'd4 : 4'd8;

	// --- transmitter ----------------------------------------------------------
	reg [8:0]  tbuf;
	reg        udre, txc;
	reg [11:0] tsh;     // {stop bits/parity/data..., start}
	reg [3:0]  tleft;   // bits left to send, 0 = idle
	reg [3:0]  tos;
	reg        txd;

	function [8:0] mask_data(input [8:0] d);
		case (chsize)
			3'd0: mask_data = {4'h0, d[4:0]};
			3'd1: mask_data = {3'h0, d[5:0]};
			3'd2: mask_data = {2'h0, d[6:0]};
			3'd3: mask_data = {1'h0, d[7:0]};
			default: mask_data = d;
		endcase
	endfunction

	wire [8:0]  tdat  = mask_data(tbuf);
	wire        tpar  = (^tdat) ^ upm[0];
	// frame, LSB first: start, data, [parity], stop(s); unused high bits are 1
	reg [11:0] tframe;
	always @(*) begin
		tframe = 12'hFFF;
		tframe[0] = 1'b0;
		tframe[9:1] = tdat | (9'h1FF << nbits);
		if (upm[1]) tframe[nbits + 1] = tpar;
	end
	wire [3:0] tlen = nbits + 4'd2 + {3'h0, upm[1]} + {3'h0, usbs};

	// --- receiver -------------------------------------------------------------
	reg [3:0]  ros, rbit;
	reg        rbusy;
	reg [10:0] rsh;    // data (up to 9) + parity + stop, LSB first from the top
	reg [2:0]  rsamp;
	reg [8:0]  rbuf;
	reg        rxc, fe, dor, upe;
	reg        rxd_q;
	wire [3:0] rlen = nbits + {3'h0, upm[1]} + 4'd1;   // data + parity + first stop
	wire       maj  = (rsamp[0] & rsamp[1]) | (rsamp[1] & rsamp[2]) | (rsamp[0] & rsamp[2]);

	wire rd_data = sel & rd & (addr[4:2] == 3'd0);
	// completed frame, right-aligned: {stop, [parity], data}
	wire [10:0] rfr = {maj, rsh[10:1]} >> (4'd11 - rlen);

	always @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			rxcie <= 0; txcie <= 0; udrie <= 0; rxen <= 0; txen <= 0; u2x <= 0;
			chsize <= 3'd3; usbs <= 0; upm <= 0; brr <= 16'h0;
			tbuf <= 9'h0; udre <= 1'b1; txc <= 1'b0; tsh <= 12'hFFF; tleft <= 4'h0; tos <= 4'h0; txd <= 1'b1;
			ros <= 4'h0; rbit <= 4'h0; rbusy <= 1'b0; rsh <= 11'h0; rsamp <= 3'h0;
			rbuf <= 9'h0; rxc <= 0; fe <= 0; dor <= 0; upe <= 0; rxd_q <= 1'b1;
		end else begin
			// ---------------- TX ----------------
			if (!txen) begin
				tleft <= 4'h0; txd <= 1'b1; udre <= 1'b1;
			end else if (btick) begin
				// tleft = bit periods remaining in the current frame (0 = idle)
				if (tleft == 4'h0) begin
					if (!udre) begin
						tsh <= {1'b1, tframe[11:1]}; txd <= tframe[0];
						tleft <= tlen; tos <= 4'h0; udre <= 1'b1;
					end
				end else if (tos == os_last) begin
					tos <= 4'h0; tleft <= tleft - 4'd1;
					if (tleft != 4'h1) begin txd <= tsh[0]; tsh <= {1'b1, tsh[11:1]}; end
					else if (udre) txc <= 1'b1;
				end else tos <= tos + 4'd1;
			end

			// ---------------- RX ----------------
			rxd_q <= rxd_i;
			if (!rxen) begin
				rbusy <= 1'b0; rxc <= 1'b0; fe <= 0; dor <= 0; upe <= 0;
			end else if (!rbusy) begin
				if (rxd_q & ~rxd_i) begin rbusy <= 1'b1; ros <= 4'h0; rbit <= 4'h0; end
			end else if (btick) begin
				if (ros == os_mid - 4'd1) rsamp[0] <= rxd_i;
				if (ros == os_mid)        rsamp[1] <= rxd_i;
				if (ros == os_mid + 4'd1) rsamp[2] <= rxd_i;
				if (ros == os_mid + 4'd2) begin
					if (rbit == 4'h0) begin
						if (maj) rbusy <= 1'b0;       // false start
						else rbit <= 4'h1;
					end else begin
						rsh <= {maj, rsh[10:1]};
						if (rbit == rlen) begin
							rbusy <= 1'b0;
							if (rxc) dor <= 1'b1;
							else begin
								rxc <= 1'b1;
								rbuf <= mask_data(rfr[8:0]);
								fe  <= ~maj;
								upe <= upm[1] & ((^mask_data(rfr[8:0])) ^ upm[0] ^ rsh[10]);
							end
						end else rbit <= rbit + 4'd1;
					end
				end
				ros <= (ros == os_last) ? 4'h0 : ros + 4'd1;
			end
			if (rd_data) begin rxc <= 1'b0; fe <= 0; dor <= 0; upe <= 0; end

			// ---------------- bus ----------------
			if (w) case (addr[4:2])
				3'd0: begin tbuf <= wdata[8:0]; udre <= 1'b0; end
				3'd1: if (wdata[6]) txc <= 1'b0;
				3'd2: begin
					rxcie <= wdata[7]; txcie <= wdata[6]; udrie <= wdata[5];
					rxen <= wdata[4]; txen <= wdata[3]; u2x <= wdata[1];
				end
				3'd3: begin chsize <= wdata[2:0]; usbs <= wdata[3]; upm <= wdata[5:4]; end
				3'd4: brr <= wdata[15:0];
				default: ;
			endcase
		end
	end

	always @(*) begin
		rdata = 32'h0;
		if (sel) case (addr[4:2])
			3'd0: rdata = {23'h0, rbuf};
			3'd1: rdata = {24'h0, rxc, txc, udre, fe, dor, upe, 2'b00};
			3'd2: rdata = {24'h0, rxcie, txcie, udrie, rxen, txen, 1'b0, u2x, 1'b0};
			3'd3: rdata = {26'h0, upm, usbs, chsize};
			3'd4: rdata = {16'h0, brr};
			default: ;
		endcase
	end

	assign txd_o  = txd;
	assign txen_o = txen;
	assign rxen_o = rxen;
	assign irq    = (rxcie & rxc) | (txcie & txc) | (udrie & udre);
endmodule
`default_nettype wire
