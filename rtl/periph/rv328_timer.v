// RV328 timer/counter with PWM. One module serves TC0/TC2 (W=8) and
// TC1/TC3/TC4 (W=16). It implements the AVR waveform modes as two orthogonal
// fields (slope + TOP source) instead of the AVR WGM table; rv328.h provides
// the mapping.
//
//   0x00 CR   [3:0]  CS    0 stop, 1 /1, 2 /8, 3 /32, 4 /64, 5 /128, 6 /256, 7 /1024,
//                          8 Tn falling, 9 Tn rising, 10 async tick (32 kHz, TC2)
//             [5:4]  WGM   0 normal/CTC, 1 fast PWM, 2 phase-correct, 3 phase+freq-correct
//             [8:6]  TOP   0 MAX, 1 OCRA, 2 ICR, 3 0x0FF, 4 0x1FF, 5 0x3FF
//             [10:9] COMA  [12:11] COMB   0 off, 1 toggle, 2 clear/non-inv, 3 set/inv
//             [13]   ICNC  input-capture noise canceller
//             [14]   ICES  capture edge (1 = rising)
//   0x04 CNT  0x08 OCRA  0x0C OCRB  0x10 ICR
//   0x14 IER  [0] OVF [1] OCA [2] OCB [3] IC
//   0x18 IFR  same bits, write 1 to clear
//   0x1C FOC  [0] force compare A, [1] force compare B (non-PWM modes)
`default_nettype none
module rv328_timer #(
	parameter W = 16
) (
	input  wire        clk,
	input  wire        rst_n,
	input  wire        sel,
	input  wire        wr,
	input  wire [7:0]  addr,
	input  wire [31:0] wdata,
	output reg  [31:0] rdata,

	input  wire        t_i,         // external clock pin (synchronised)
	input  wire        icp_i,       // input-capture pin (synchronised)
	input  wire        async_tick,  // one-cycle pulse per low-frequency clock edge

	output reg         oca,
	output reg         ocb,
	output wire        oca_en,
	output wire        ocb_en,
	output wire        irq,
	output wire        ovf_evt,
	output wire        oca_evt,
	output wire        ocb_evt,
	output wire        ic_evt
);
	localparam [W-1:0] MAX = {W{1'b1}};

	reg [3:0]   cs;
	reg [1:0]   wgm;
	reg [2:0]   topsel;
	reg [1:0]   coma, comb;
	reg         icnc, ices;
	reg [W-1:0] cnt, ocra, ocrb, ocra_buf, ocrb_buf, icr;
	reg         down;
	reg [9:0]   presc;
	reg [3:0]   ier, ifr;

	wire w = sel & wr;

	// --- clock select -------------------------------------------------------
	reg t_q;
	always @(posedge clk or negedge rst_n)
		if (!rst_n) begin presc <= 10'h0; t_q <= 1'b0; end
		else begin presc <= presc + 10'h1; t_q <= t_i; end

	reg tick;
	always @(*) case (cs)
		4'd1:    tick = 1'b1;
		4'd2:    tick = &presc[2:0];
		4'd3:    tick = &presc[4:0];
		4'd4:    tick = &presc[5:0];
		4'd5:    tick = &presc[6:0];
		4'd6:    tick = &presc[7:0];
		4'd7:    tick = &presc[9:0];
		4'd8:    tick = t_q & ~t_i;
		4'd9:    tick = ~t_q & t_i;
		4'd10:   tick = async_tick;
		default: tick = 1'b0;
	endcase

	// --- counter ------------------------------------------------------------
	wire [15:0] top_fix = topsel == 3'd3 ? 16'h00FF : topsel == 3'd4 ? 16'h01FF : 16'h03FF;
	wire [W-1:0] top = topsel == 3'd0 ? MAX  :
	                   topsel == 3'd1 ? ocra :
	                   topsel == 3'd2 ? icr  : top_fix[W-1:0];
	wire dual = wgm[1];

	reg [W-1:0] cnt_n;
	reg         down_n, wrap, at_top, at_bot;
	always @(*) begin
		cnt_n = cnt; down_n = down; wrap = 1'b0; at_top = 1'b0; at_bot = 1'b0;
		if (!dual) begin
			down_n = 1'b0;
			if (cnt == top || cnt == MAX) begin cnt_n = {W{1'b0}}; wrap = 1'b1; end
			else cnt_n = cnt + 1'b1;
		end else if (!down) begin
			if (cnt >= top) begin
				down_n = 1'b1; at_top = 1'b1;
				cnt_n = (top == {W{1'b0}}) ? {W{1'b0}} : top - 1'b1;
			end else cnt_n = cnt + 1'b1;
		end else begin
			if (cnt == {W{1'b0}}) begin
				down_n = 1'b0;
				cnt_n = (top == {W{1'b0}}) ? {W{1'b0}} : {{W-1{1'b0}}, 1'b1};
			end else begin
				cnt_n = cnt - 1'b1;
				at_bot = cnt == {{W-1{1'b0}}, 1'b1};
			end
		end
	end

	wire ovf     = tick & (dual ? at_bot : wrap);
	wire match_a = tick & (cnt == ocra);
	wire match_b = tick & (cnt == ocrb);

	// OCR double buffering: immediate in non-PWM modes
	wire ocr_upd = wgm == 2'd0 ? 1'b1 :
	               wgm == 2'd1 ? tick & wrap :
	               wgm == 2'd2 ? tick & at_top : tick & at_bot;

	// --- input capture ------------------------------------------------------
	reg [3:0] ic_sh;
	reg       ic_f, ic_fq;
	always @(posedge clk or negedge rst_n)
		if (!rst_n) begin ic_sh <= 4'h0; ic_f <= 1'b0; ic_fq <= 1'b0; end
		else begin
			ic_sh <= {ic_sh[2:0], icp_i};
			if (!icnc)               ic_f <= icp_i;
			else if (ic_sh == 4'hF)  ic_f <= 1'b1;
			else if (ic_sh == 4'h0)  ic_f <= 1'b0;
			ic_fq <= ic_f;
		end
	wire capture = (ices ? (ic_f & ~ic_fq) : (~ic_f & ic_fq)) && topsel != 3'd2;

	// --- compare outputs ----------------------------------------------------
	function oc_next;
		input        cur;
		input [1:0]  com;
		input        match;
		input        force_m;
		input [W-1:0] ocr;
		begin
			oc_next = cur;
			if (wgm == 2'd0) begin
				if (match | force_m) case (com)
					2'd1: oc_next = ~cur;
					2'd2: oc_next = 1'b0;
					2'd3: oc_next = 1'b1;
					default: ;
				endcase
			end else if (tick) begin
				if (com == 2'd1) begin
					if (match) oc_next = ~cur;
				end else if (!dual)
					oc_next = (cnt_n <= ocr) ^ com[0];
				else
					oc_next = ((cnt_n < ocr) | (ocr >= top)) ^ com[0];
			end
		end
	endfunction

	wire foc_a = w && addr[4:2] == 3'd7 && wdata[0];
	wire foc_b = w && addr[4:2] == 3'd7 && wdata[1];

	wire [3:0] set = {capture, match_b, match_a, ovf};

	always @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			cs <= 4'h0; wgm <= 2'h0; topsel <= 3'h0; coma <= 2'h0; comb <= 2'h0;
			icnc <= 1'b0; ices <= 1'b0;
			cnt <= {W{1'b0}}; ocra <= {W{1'b0}}; ocrb <= {W{1'b0}};
			ocra_buf <= {W{1'b0}}; ocrb_buf <= {W{1'b0}}; icr <= {W{1'b0}};
			down <= 1'b0; oca <= 1'b0; ocb <= 1'b0; ier <= 4'h0; ifr <= 4'h0;
		end else begin
			if (tick) begin cnt <= cnt_n; down <= down_n; end
			if (ocr_upd) begin ocra <= ocra_buf; ocrb <= ocrb_buf; end
			if (capture) icr <= cnt;
			oca <= oc_next(oca, coma, match_a, foc_a, ocra);
			ocb <= oc_next(ocb, comb, match_b, foc_b, ocrb);
			ifr <= ifr | set;
			if (w) case (addr[4:2])
				3'd0: begin
					cs <= wdata[3:0]; wgm <= wdata[5:4]; topsel <= wdata[8:6];
					coma <= wdata[10:9]; comb <= wdata[12:11];
					icnc <= wdata[13]; ices <= wdata[14];
				end
				3'd1: begin cnt <= wdata[W-1:0]; down <= 1'b0; end
				3'd2: ocra_buf <= wdata[W-1:0];
				3'd3: ocrb_buf <= wdata[W-1:0];
				3'd4: icr <= wdata[W-1:0];
				3'd5: ier <= wdata[3:0];
				3'd6: ifr <= (ifr & ~wdata[3:0]) | set;
				default: ;
			endcase
		end
	end

	always @(*) begin
		rdata = 32'h0;
		if (sel) case (addr[4:2])
			3'd0: rdata = {17'h0, ices, icnc, comb, coma, topsel, wgm, cs};
			3'd1: rdata = {{32-W{1'b0}}, cnt};
			3'd2: rdata = {{32-W{1'b0}}, ocra_buf};
			3'd3: rdata = {{32-W{1'b0}}, ocrb_buf};
			3'd4: rdata = {{32-W{1'b0}}, icr};
			3'd5: rdata = {28'h0, ier};
			3'd6: rdata = {28'h0, ifr};
			default: ;
		endcase
	end

	assign oca_en  = coma != 2'd0;
	assign ocb_en  = comb != 2'd0;
	assign irq     = |(ifr & ier);
	assign ovf_evt = ovf;
	assign oca_evt = match_a;
	assign ocb_evt = match_b;
	assign ic_evt  = capture;
endmodule
`default_nettype wire
