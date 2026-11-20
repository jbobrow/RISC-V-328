// RV328 SPI master/slave, register-compatible in spirit with the AVR SPI.
//
//   0x00 CR   [8] SPI2X [7] SPIE [6] SPE [5] DORD (1 = LSB first) [4] MSTR
//             [3] CPOL [2] CPHA [1:0] SPR   (fSCK = fclk / 4,16,64,128; x2 with SPI2X)
//   0x04 SR   [7] SPIF  [6] WCOL   (both write-1-to-clear; SPIF also clears on DATA read)
//   0x08 DATA
// Slave mode samples SCK synchronously: fSCK must stay below fclk / 4.
`default_nettype none
module rv328_spi (
	input  wire        clk,
	input  wire        rst_n,
	input  wire        sel,
	input  wire        wr,
	input  wire        rd,
	input  wire [7:0]  addr,
	input  wire [31:0] wdata,
	output reg  [31:0] rdata,
	input  wire        sck_i,    // synchronised pins
	input  wire        mosi_i,
	input  wire        miso_i,
	input  wire        ss_i,
	output wire        sck_o,
	output wire        sdo_o,    // serial data out (MOSI as master, MISO as slave)
	output wire        spe_o,
	output wire        mstr_o,
	output wire        irq
);
	reg       spi2x, spie, spe, dord, mstr, cpol, cpha;
	reg [1:0] spr;
	reg       spif, wcol;
	reg [7:0] sh, rbuf;
	reg       rx_bit;
	reg [2:0] bitc;
	reg       sck_m;          // master SCK phase (0 = idle level)
	reg [4:0] edges;          // master: SCK edges left
	reg [6:0] div;
	reg       sck_q;

	wire w = sel & wr;
	function [7:0] rev(input [7:0] d);
		rev = {d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7]};
	endfunction

	// half SCK period in clk cycles, minus one
	reg [6:0] half;
	always @(*) case ({spi2x, spr})
		3'b100: half = 7'd0;   // /2
		3'b000: half = 7'd1;   // /4
		3'b101: half = 7'd3;   // /8
		3'b001: half = 7'd7;   // /16
		3'b110: half = 7'd15;  // /32
		3'b010: half = 7'd31;  // /64
		3'b111: half = 7'd31;  // /64
		default: half = 7'd63; // /128
	endcase

	wire m_busy  = edges != 5'd0;
	wire m_edge  = mstr & m_busy & (div == 7'd0);
	// leading edge = idle -> active, trailing = active -> idle
	wire s_act   = sck_i ^ cpol;
	wire s_act_q = sck_q ^ cpol;
	wire s_en    = spe & ~mstr & ~ss_i;
	wire lead    = mstr ? (m_edge & ~sck_m) : (s_en & s_act & ~s_act_q);
	wire trail   = mstr ? (m_edge &  sck_m) : (s_en & ~s_act & s_act_q);
	wire sample  = cpha ? trail : lead;
	wire setup   = cpha ? lead : trail;
	wire din     = mstr ? miso_i : mosi_i;
	wire busy    = mstr ? m_busy : (bitc != 3'd0);
	wire [7:0] rx_full = {sh[6:0], din};
	wire m_done  = m_edge & (edges == 5'd1);

	always @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			spi2x <= 0; spie <= 0; spe <= 0; dord <= 0; mstr <= 0; cpol <= 0; cpha <= 0; spr <= 2'b00;
			spif <= 0; wcol <= 0; sh <= 8'h00; rbuf <= 8'h00; rx_bit <= 0; bitc <= 3'd0;
			sck_m <= 0; edges <= 5'd0; div <= 7'd0; sck_q <= 1'b0;
		end else begin
			sck_q <= sck_i;
			if (!spe) begin
				edges <= 5'd0; sck_m <= 1'b0; bitc <= 3'd0;
			end else begin
				if (mstr & m_busy) begin
					if (div == 7'd0) begin
						div <= half; sck_m <= ~sck_m; edges <= edges - 5'd1;
					end else div <= div - 7'd1;
				end
				if (!mstr & ss_i) bitc <= 3'd0;
				if (sample) begin
					rx_bit <= din;
					bitc <= bitc + 3'd1;
					// the shift register is left alone so the last bit stays on the
					// output until the following SCK edge
					if (bitc == 3'd7) begin
						rbuf <= dord ? rev(rx_full) : rx_full;
						if (!mstr) spif <= 1'b1;
					end
				end
				if (setup && bitc != 3'd0) sh <= {sh[6:0], rx_bit};
				if (m_done) spif <= 1'b1;
			end
			if (sel & rd & (addr[3:2] == 2'd2)) spif <= 1'b0;
			if (w) case (addr[3:2])
				2'd0: begin
					spi2x <= wdata[8]; spie <= wdata[7]; spe <= wdata[6]; dord <= wdata[5];
					mstr <= wdata[4]; cpol <= wdata[3]; cpha <= wdata[2]; spr <= wdata[1:0];
				end
				2'd1: begin
					if (wdata[7]) spif <= 1'b0;
					if (wdata[6]) wcol <= 1'b0;
				end
				2'd2: begin
					if (busy) wcol <= 1'b1;
					else begin
						sh <= dord ? rev(wdata[7:0]) : wdata[7:0];
						if (spe & mstr) begin edges <= 5'd16; div <= half; sck_m <= 1'b0; end
					end
				end
				default: ;
			endcase
		end
	end

	always @(*) begin
		rdata = 32'h0;
		if (sel) case (addr[3:2])
			2'd0: rdata = {23'h0, spi2x, spie, spe, dord, mstr, cpol, cpha, spr};
			2'd1: rdata = {24'h0, spif, wcol, 6'h0};
			2'd2: rdata = {24'h0, rbuf};
			default: ;
		endcase
	end

	assign sck_o  = sck_m ^ cpol;
	assign sdo_o  = sh[7];
	assign spe_o  = spe;
	assign mstr_o = mstr;
	assign irq    = spie & spif;
endmodule
`default_nettype wire
