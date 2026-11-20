// RV328 program memory: execute-in-place from the in-package serial memory
// (SPI, command set common to 25-series EEPROM and NOR flash), through a
// read cache, plus the NVM write controller.
//
// Cache: 32-byte lines in 512x32 RAMs (2 KB each).
//   WAYS    1 = direct mapped; 2 or 3 = set associative, the least recently
//           used way is replaced
//   WAY_KB  size of one way: 2, 4, 8 or 16 KB
//   PIN_KB  0 or 2 (needs WAYS >= 2): lines from the first 2 KB of the program
//           are loaded on first use and then never replaced, so interrupt
//           handlers linked at the start of the image answer without a reload.
//           They live in the ordinary ways; a set never holds more than one.
// Valid and age bits are flops (the cache is flushed in one clock). Tags are
// flops for 2 KB ways and one 512x8 RAM per way otherwise.
// XIP window is 1 MB (address bits [19:0]).
//
// Register map:
//   0x00 NVMCR    write: [31:24] = 0xA5 key, [2:0] CMD, [5:4] NB (bytes - 1)
//                 CMD 1 = WRITE  NB+1 bytes of NVMDATA (LSB first) at NVMADDR
//                                (the bytes must not cross a 4-byte boundary)
//                 CMD 2 = ERASE  4 KB sector at NVMADDR (opcode 20h; NOR flash only)
//                 CMD 3 = FLUSH  invalidate the read cache
//   0x04 NVMSR    [0] BUSY (RO)  [1] DONE (W1C)  [2] DONEIE
//   0x08 NVMADDR  [23:0]
//   0x0C NVMDATA  [31:0]
//   0x10 NVMCFG   [3:0] SCKDIV: fSCK = fclk / (2 * (SCKDIV + 1)), reset 1
//
// A WRITE/ERASE runs WREN (06h), the command (02h/20h), then polls RDSR (05h)
// until the write-in-progress bit clears. The CPU keeps running from cached
// lines; any cache miss simply waits until the operation has finished, which
// mirrors the AVR halting during self-programming.
`default_nettype none
module rv328_xip #(
	parameter WAY_KB = 2,
	parameter WAYS   = 1,
	parameter PIN_KB = 0
) (
	input  wire        clk,
	input  wire        rst_n,

	input  wire        a_valid,    // read address phase accepted
	input  wire [19:0] a_addr,
	output wire        d_ready,
	output wire [31:0] d_rdata,

	input  wire        sel,
	input  wire        wr,
	input  wire [7:0]  addr,
	input  wire [31:0] wdata,
	output reg  [31:0] rdata,

	output reg         spi_csn,
	output reg         spi_sck,
	output wire        spi_mosi,
	input  wire        spi_miso,
	output wire        irq
);
	localparam SEQ_FILL = 2'd0, SEQ_WREN = 2'd1, SEQ_CMD = 2'd2, SEQ_POLL = 2'd3;
	localparam S_IDLE = 2'd0, S_CSL = 2'd1, S_SHIFT = 2'd2, S_CSH = 2'd3;
	localparam F_IDLE = 2'd0, F_FILL = 2'd1, F_REREAD = 2'd2;
	// LB = log2(sets), TW = tag width (address bits [19:LB+5])
	localparam LB = WAY_KB == 2 ? 6 : WAY_KB == 4 ? 7 : WAY_KB == 8 ? 8 : 9;
	localparam SETS = 1 << LB;
	localparam TW = 15 - LB;

	// ---------------- bus side ----------------
	reg        dph;
	reg [19:0] addr_q;
	reg [1:0]  fs;
	reg  [SETS-1:0]  valid0, valid1, valid2;
	reg  [SETS-1:0]  n01, n02, n12;            // age: nXY = way X used more recently than way Y
	reg  [1:0]       fway;                     // way being filled
	wire [LB-1:0]    set_q  = addr_q[LB+4:5];
	wire [TW-1:0]    atag_q = addr_q[19:LB+5];
	wire [TW-1:0]    tagq [0:2];               // tags stored for set_q
	wire             hit0   = valid0[set_q] && tagq[0] == atag_q;
	wire             hit1   = (WAYS >= 2) && valid1[set_q] && tagq[1] == atag_q;
	wire             hit2   = (WAYS >= 3) && valid2[set_q] && tagq[2] == atag_q;
	wire             hit    = hit0 | hit1 | hit2;
	// replacement: an empty way first, else the oldest way that does not hold a pinned line
	wire             pinset = (PIN_KB != 0) && (WAYS >= 2) && (set_q >> 6) == 0;
	wire             pin0   = pinset && tagq[0] == {TW{1'b0}};
	wire             pin1   = pinset && tagq[1] == {TW{1'b0}};
	wire             pin2   = pinset && tagq[2] == {TW{1'b0}};
	wire             old0   = ~n01[set_q] & ((WAYS < 3) | ~n02[set_q]);
	wire             old1   =  n01[set_q] & ((WAYS < 3) | ~n12[set_q]);
	wire [1:0]       victim =
		(WAYS == 1)                         ? 2'd0 :
		!valid0[set_q]                      ? 2'd0 :
		!valid1[set_q]                      ? 2'd1 :
		(WAYS >= 3 && !valid2[set_q])       ? 2'd2 :
		(WAYS == 2)                         ? (pin0 ? 2'd1 : pin1 ? 2'd0 : old0 ? 2'd0 : 2'd1) :
		pin0                                ? (n12[set_q] ? 2'd2 : 2'd1) :
		pin1                                ? (n02[set_q] ? 2'd2 : 2'd0) :
		pin2                                ? (n01[set_q] ? 2'd1 : 2'd0) :
		old0 ? 2'd0 : old1 ? 2'd1 : 2'd2;

	always @(posedge clk or negedge rst_n)
		if (!rst_n) begin dph <= 1'b0; addr_q <= 20'h0; end
		else if (a_valid) begin dph <= 1'b1; addr_q <= a_addr; end
		else if (d_ready) dph <= 1'b0;

	assign d_ready = ~dph | (fs == F_IDLE && hit);

	// ---------------- NVM registers ----------------
	reg        nv_busy, nv_done, nv_ie, nv_erase, nv_go;
	reg [1:0]  nv_nb;
	reg [23:0] nv_addr;
	reg [31:0] nv_data;
	reg [3:0]  sckdiv;
	wire w = sel & wr;
	wire cmd_w = w && addr[4:2] == 3'd0 && wdata[31:24] == 8'hA5 && !nv_busy;

	// ---------------- SPI sequencer ----------------
	reg [1:0]  ss, seq;
	reg [5:0]  bidx;
	reg [2:0]  bitc;
	reg [7:0]  osh, ish;
	reg [3:0]  dcnt;
	reg [1:0]  gap;
	reg [31:0] wsh;
	reg        fill_wr;
	reg [2:0]  fill_wi;
	reg        wip;

	wire tk = dcnt == 4'h0;
	wire [7:0] rxb = {ish[6:0], spi_miso};

	function [7:0] txbyte(input [1:0] s, input [5:0] i);
		begin
			txbyte = 8'h00;
			case (s)
				SEQ_FILL: case (i)
					6'd0: txbyte = 8'h03;
					6'd1: txbyte = {4'h0, addr_q[19:16]};
					6'd2: txbyte = addr_q[15:8];
					6'd3: txbyte = {addr_q[7:5], 5'h00};
					default: txbyte = 8'h00;
				endcase
				SEQ_WREN: txbyte = 8'h06;
				SEQ_CMD: case (i)
					6'd0: txbyte = nv_erase ? 8'h20 : 8'h02;
					6'd1: txbyte = nv_addr[23:16];
					6'd2: txbyte = nv_addr[15:8];
					6'd3: txbyte = nv_addr[7:0];
					6'd4: txbyte = nv_data[7:0];
					6'd5: txbyte = nv_data[15:8];
					6'd6: txbyte = nv_data[23:16];
					default: txbyte = nv_data[31:24];
				endcase
				default: txbyte = (i == 6'd0) ? 8'h05 : 8'h00;
			endcase
		end
	endfunction

	reg [5:0] last;
	always @(*) case (seq)
		SEQ_FILL: last = 6'd35;
		SEQ_WREN: last = 6'd0;
		SEQ_CMD:  last = nv_erase ? 6'd3 : 6'd4 + {4'h0, nv_nb};
		default:  last = 6'd1;
	endcase

	wire fill_start = fs == F_IDLE && dph && !hit && !nv_busy && ss == S_IDLE;
	wire byte_done  = ss == S_SHIFT && tk && spi_sck && bitc == 3'd7;
	wire seq_end    = ss == S_CSH && tk && gap == 2'd0;

	integer k;
	always @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			fs <= F_IDLE; valid0 <= {SETS{1'b0}}; valid1 <= {SETS{1'b0}}; valid2 <= {SETS{1'b0}};
			n01 <= {SETS{1'b0}}; n02 <= {SETS{1'b0}}; n12 <= {SETS{1'b0}}; fway <= 2'd0;
			nv_busy <= 0; nv_done <= 0; nv_ie <= 0; nv_erase <= 0; nv_go <= 0; nv_nb <= 2'd0;
			nv_addr <= 24'h0; nv_data <= 32'h0; sckdiv <= 4'd1;
			ss <= S_IDLE; seq <= SEQ_FILL; bidx <= 6'd0; bitc <= 3'd0; osh <= 8'h0; ish <= 8'h0;
			dcnt <= 4'h0; gap <= 2'd0; wsh <= 32'h0; fill_wr <= 1'b0; fill_wi <= 3'd0; wip <= 1'b0;
			spi_csn <= 1'b1; spi_sck <= 1'b0;
		end else begin
			fill_wr <= 1'b0;
			dcnt <= tk ? sckdiv : dcnt - 4'h1;

			// ---- registers ----
			if (w) case (addr[4:2])
				3'd1: begin if (wdata[1]) nv_done <= 1'b0; nv_ie <= wdata[2]; end
				3'd2: if (!nv_busy) nv_addr <= wdata[23:0];
				3'd3: if (!nv_busy) nv_data <= wdata;
				3'd4: sckdiv <= wdata[3:0];
				default: ;
			endcase
			if (cmd_w) case (wdata[2:0])
				3'd1: begin nv_busy <= 1'b1; nv_go <= 1'b1; nv_erase <= 1'b0; nv_nb <= wdata[5:4]; end
				3'd2: begin nv_busy <= 1'b1; nv_go <= 1'b1; nv_erase <= 1'b1; end
				3'd3: begin valid0 <= {SETS{1'b0}}; valid1 <= {SETS{1'b0}}; valid2 <= {SETS{1'b0}}; nv_done <= 1'b1; end
				default: ;
			endcase

			// ---- start of a sequence ----
			if (ss == S_IDLE) begin
				if (nv_go && fs == F_IDLE) begin
					nv_go <= 1'b0; seq <= SEQ_WREN; ss <= S_CSL; dcnt <= sckdiv;
				end else if (fill_start) begin
					fs <= F_FILL; seq <= SEQ_FILL; ss <= S_CSL; dcnt <= sckdiv; fway <= victim;
				end
			end

			// ---- byte engine (SPI mode 0, MISO captured on the falling SCK tick) ----
			case (ss)
				S_CSL: if (tk) begin
					spi_csn <= 1'b0; spi_sck <= 1'b0; bidx <= 6'd0; bitc <= 3'd0;
					osh <= txbyte(seq, 6'd0); ss <= S_SHIFT;
				end
				S_SHIFT: if (tk) begin
					if (!spi_sck) spi_sck <= 1'b1;
					else begin
						spi_sck <= 1'b0; ish <= rxb; osh <= {osh[6:0], 1'b0}; bitc <= bitc + 3'd1;
						if (bitc == 3'd7) begin
							if (bidx == last) begin ss <= S_CSH; gap <= 2'd2; end
							else begin bidx <= bidx + 6'd1; osh <= txbyte(seq, bidx + 6'd1); end
						end
					end
				end
				S_CSH: if (tk) begin
					spi_csn <= 1'b1;
					if (gap != 2'd0) gap <= gap - 2'd1;
				end
				default: ;
			endcase

			// ---- received bytes ----
			if (byte_done) begin
				if (seq == SEQ_FILL && bidx >= 6'd4) begin
					wsh <= {rxb, wsh[31:8]};
					if (bidx[1:0] == 2'd3) begin fill_wr <= 1'b1; fill_wi <= bidx[4:2] - 3'd1; end
				end
				if (seq == SEQ_POLL && bidx == 6'd1) wip <= rxb[0];
			end

			// ---- end of a sequence ----
			if (seq_end) begin
				ss <= S_IDLE;
				case (seq)
					SEQ_FILL: begin
						fs <= F_REREAD;
						case (fway)
							2'd0:    valid0[set_q] <= 1'b1;
							2'd1:    valid1[set_q] <= 1'b1;
							default: valid2[set_q] <= 1'b1;
						endcase
					end
					SEQ_WREN: begin seq <= SEQ_CMD;  ss <= S_CSL; end
					SEQ_CMD:  begin seq <= SEQ_POLL; ss <= S_CSL; end
					default: begin
						if (wip) ss <= S_CSL;
						else begin nv_busy <= 1'b0; nv_done <= 1'b1; valid0 <= {SETS{1'b0}}; valid1 <= {SETS{1'b0}}; valid2 <= {SETS{1'b0}}; end
					end
				endcase
			end
			if (fs == F_REREAD) fs <= F_IDLE;
			// a served read makes its way the youngest of the set
			if (WAYS >= 2 && dph && fs == F_IDLE && hit) begin
				if (hit0) begin n01[set_q] <= 1'b1; n02[set_q] <= 1'b1; end
				if (hit1) begin n01[set_q] <= 1'b0; n12[set_q] <= 1'b1; end
				if (hit2) begin n02[set_q] <= 1'b0; n12[set_q] <= 1'b0; end
			end
		end
	end

	// ---------------- cache RAM ----------------
	// Reads happen in the bus address phase (or in F_REREAD after a fill);
	// writes only during a fill, when the bus is stalled. Tags are read with
	// the data and written at the end of a fill; the re-read that follows
	// every fill returns the new tag.
	wire        rd_now = a_valid | (fs == F_REREAD);
	wire [19:0] rd_a   = a_valid ? a_addr : addr_q;
	wire        tag_we = seq_end && seq == SEQ_FILL;
	wire [31:0] wayq [0:2];

	// explicit blocks (no generate loop) so the floorplan and power-grid scripts
	// can name the RAMs: u_xip.g_w<way>.u_way.g_b<bank>.u_ram.u_ram<byte>
	generate if (WAYS > 0) begin : g_w0
		rv328_cache_way #(.WAY_KB (WAY_KB), .LB (LB), .TW (TW)) u_way (
			.clk (clk), .rd (rd_now), .ra (rd_a[LB+4:2]),
			.wr (fill_wr && fway == 2'd0), .wa ({set_q, fill_wi}), .wdata (wsh),
			.tag_we (tag_we && fway == 2'd0), .tag_wd (atag_q), .set_q (set_q),
			.rdata (wayq[0]), .tag (tagq[0])
		);
	end else begin : g_n0
		assign wayq[0] = 32'h0;
		assign tagq[0] = {TW{1'b0}};
	end endgenerate
	generate if (WAYS > 1) begin : g_w1
		rv328_cache_way #(.WAY_KB (WAY_KB), .LB (LB), .TW (TW)) u_way (
			.clk (clk), .rd (rd_now), .ra (rd_a[LB+4:2]),
			.wr (fill_wr && fway == 2'd1), .wa ({set_q, fill_wi}), .wdata (wsh),
			.tag_we (tag_we && fway == 2'd1), .tag_wd (atag_q), .set_q (set_q),
			.rdata (wayq[1]), .tag (tagq[1])
		);
	end else begin : g_n1
		assign wayq[1] = 32'h0;
		assign tagq[1] = {TW{1'b0}};
	end endgenerate
	generate if (WAYS > 2) begin : g_w2
		rv328_cache_way #(.WAY_KB (WAY_KB), .LB (LB), .TW (TW)) u_way (
			.clk (clk), .rd (rd_now), .ra (rd_a[LB+4:2]),
			.wr (fill_wr && fway == 2'd2), .wa ({set_q, fill_wi}), .wdata (wsh),
			.tag_we (tag_we && fway == 2'd2), .tag_wd (atag_q), .set_q (set_q),
			.rdata (wayq[2]), .tag (tagq[2])
		);
	end else begin : g_n2
		assign wayq[2] = 32'h0;
		assign tagq[2] = {TW{1'b0}};
	end endgenerate

	assign d_rdata = hit2 ? wayq[2] : hit1 ? wayq[1] : wayq[0];

	always @(*) begin
		rdata = 32'h0;
		if (sel) case (addr[4:2])
			3'd1: rdata = {29'h0, nv_ie, nv_done, nv_busy};
			3'd2: rdata = {8'h0, nv_addr};
			3'd3: rdata = nv_data;
			3'd4: rdata = {28'h0, sckdiv};
			default: ;
		endcase
	end

	assign spi_mosi = osh[7];
	assign irq = nv_done & nv_ie;
endmodule

// ----------------------------------------------------------------------------
// One way of the cache: WAY_KB / 2 RAMs of 2 KB (512x32) and the tags.
// Addresses are {set, word}; set_q is the registered set of the access being
// served and selects which RAM's output is passed on.
module rv328_cache_way #(
	parameter WAY_KB = 2,
	parameter LB = 6,
	parameter TW = 9
) (
	input  wire          clk,
	input  wire          rd,
	input  wire [LB+2:0] ra,
	input  wire          wr,
	input  wire [LB+2:0] wa,
	input  wire [31:0]   wdata,
	input  wire          tag_we,       // tag of set_q
	input  wire [TW-1:0] tag_wd,
	input  wire [LB-1:0] set_q,
	output wire [31:0]   rdata,
	output wire [TW-1:0] tag
);
	localparam NBANK = WAY_KB / 2;
	localparam TAG_RAM = WAY_KB == 4 || WAY_KB == 8 || WAY_KB == 16;
	wire [31:0] bq [0:7];
	generate if (NBANK > 0) begin : g_b0
		wire w = wr && (wa >> 9) == 0;
		rv328_ram512x32 u_ram (.clk (clk), .en (w | (rd && (ra >> 9) == 0)), .we ({4{w}}),
			.addr (w ? wa[8:0] : ra[8:0]), .wdata (wdata), .rdata (bq[0]));
	end else begin : g_n0
		assign bq[0] = 32'h0;
	end endgenerate
	generate if (NBANK > 1) begin : g_b1
		wire w = wr && (wa >> 9) == 1;
		rv328_ram512x32 u_ram (.clk (clk), .en (w | (rd && (ra >> 9) == 1)), .we ({4{w}}),
			.addr (w ? wa[8:0] : ra[8:0]), .wdata (wdata), .rdata (bq[1]));
	end else begin : g_n1
		assign bq[1] = 32'h0;
	end endgenerate
	generate if (NBANK > 2) begin : g_b2
		wire w = wr && (wa >> 9) == 2;
		rv328_ram512x32 u_ram (.clk (clk), .en (w | (rd && (ra >> 9) == 2)), .we ({4{w}}),
			.addr (w ? wa[8:0] : ra[8:0]), .wdata (wdata), .rdata (bq[2]));
	end else begin : g_n2
		assign bq[2] = 32'h0;
	end endgenerate
	generate if (NBANK > 3) begin : g_b3
		wire w = wr && (wa >> 9) == 3;
		rv328_ram512x32 u_ram (.clk (clk), .en (w | (rd && (ra >> 9) == 3)), .we ({4{w}}),
			.addr (w ? wa[8:0] : ra[8:0]), .wdata (wdata), .rdata (bq[3]));
	end else begin : g_n3
		assign bq[3] = 32'h0;
	end endgenerate
	generate if (NBANK > 4) begin : g_b4
		wire w = wr && (wa >> 9) == 4;
		rv328_ram512x32 u_ram (.clk (clk), .en (w | (rd && (ra >> 9) == 4)), .we ({4{w}}),
			.addr (w ? wa[8:0] : ra[8:0]), .wdata (wdata), .rdata (bq[4]));
	end else begin : g_n4
		assign bq[4] = 32'h0;
	end endgenerate
	generate if (NBANK > 5) begin : g_b5
		wire w = wr && (wa >> 9) == 5;
		rv328_ram512x32 u_ram (.clk (clk), .en (w | (rd && (ra >> 9) == 5)), .we ({4{w}}),
			.addr (w ? wa[8:0] : ra[8:0]), .wdata (wdata), .rdata (bq[5]));
	end else begin : g_n5
		assign bq[5] = 32'h0;
	end endgenerate
	generate if (NBANK > 6) begin : g_b6
		wire w = wr && (wa >> 9) == 6;
		rv328_ram512x32 u_ram (.clk (clk), .en (w | (rd && (ra >> 9) == 6)), .we ({4{w}}),
			.addr (w ? wa[8:0] : ra[8:0]), .wdata (wdata), .rdata (bq[6]));
	end else begin : g_n6
		assign bq[6] = 32'h0;
	end endgenerate
	generate if (NBANK > 7) begin : g_b7
		wire w = wr && (wa >> 9) == 7;
		rv328_ram512x32 u_ram (.clk (clk), .en (w | (rd && (ra >> 9) == 7)), .we ({4{w}}),
			.addr (w ? wa[8:0] : ra[8:0]), .wdata (wdata), .rdata (bq[7]));
	end else begin : g_n7
		assign bq[7] = 32'h0;
	end endgenerate
	assign rdata = bq[set_q >> 6];

	generate if (TAG_RAM) begin : g_tagram
		wire [7:0] tq;
		wire [8:0] tl_w = set_q;
		wire [8:0] tl_r = ra[LB+2:3];
		wire [7:0] tw_d = tag_wd;
		rv328_ram512x8 u_tag (
			.clk   (clk),
			.en    (tag_we | rd),
			.we    (tag_we),
			.addr  (tag_we ? tl_w : tl_r),
			.wdata (tw_d),
			.rdata (tq)
		);
		assign tag = tq[TW-1:0];
	end else begin : g_tagff
		reg [TW-1:0] tagm [0:(1 << LB)-1];
		always @(posedge clk)
			if (tag_we) tagm[set_q] <= tag_wd;
		assign tag = tagm[set_q];
	end endgenerate
endmodule
`default_nettype wire
