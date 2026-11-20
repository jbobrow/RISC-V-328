// RV328 ADC controller (10-bit SAR logic) and analog comparator control.
// The analog front end (input mux, sample/hold, capacitor DAC, comparator,
// references) lives in the analog macro; this block sequences it.
//
//   0x00 ADMUX   [7:6] REFS (0 AREF, 1 AVCC, 3 internal 1.1 V)  [5] ADLAR
//                [3:0] MUX (0-7 ADC0-7, 8 temperature, 14 1.1 V bandgap, 15 GND)
//   0x04 ADCSRA  [7] ADEN [6] ADSC [5] ADATE [4] ADIF (W1C) [3] ADIE
//                [2:0] ADPS (fADC = fclk / 2,2,4,8,16,32,64,128)
//   0x08 ADC     conversion result (left-adjusted if ADLAR)
//   0x0C ADCSRB  [6] ACME  [2:0] ADTS (0 free-run, 1 comparator, 2 INT0,
//                3 TC0 compare A, 4 TC0 overflow, 5 TC1 compare B, 6 TC1 overflow, 7 TC1 capture)
//   0x10 DIDR0   [7:0] disable digital input buffer on ADC7..0
//   0x20 ACSR    [8] ACOE (drive ACO on PE0) [7] ACD [6] ACBG [5] ACO (RO)
//                [4] ACI (W1C) [3] ACIE [2] ACIC [1:0] ACIS (0 toggle, 2 falling, 3 rising)
//   0x24 DIDR1   [1] AIN1D [0] AIN0D
//
// A normal conversion takes 13 ADC clock cycles, the first one after ADEN 25.
`default_nettype none
module rv328_adc (
	input  wire        clk,
	input  wire        rst_n,
	input  wire        sel,
	input  wire        wr,
	input  wire [7:0]  addr,
	input  wire [31:0] wdata,
	output reg  [31:0] rdata,

	input  wire [7:0]  trig_i,      // auto-trigger event pulses, index = ADTS (0 unused)

	// analog macro interface
	output wire        adc_en,
	output wire [3:0]  adc_mux,
	output wire [1:0]  adc_refs,
	output wire        adc_sample,  // high while the sample/hold tracks the input
	output wire [9:0]  adc_dac,     // SAR trial code
	input  wire        adc_cmp,     // 1 when sampled input >= DAC voltage
	output wire        ac_en,
	output wire        ac_bg,       // positive input = bandgap instead of AIN0
	output wire        ac_mux_en,   // negative input = ADC mux instead of AIN1
	input  wire        ac_out,

	output wire [7:0]  didr0,
	output wire [1:0]  didr1,
	output wire        aco,         // synchronised comparator output
	output wire        acoe,
	output wire        acic,
	output wire        irq_adc,
	output wire        irq_ac
);
	reg [1:0] refs; reg adlar; reg [3:0] mux;
	reg aden, adsc, adate, adif, adie; reg [2:0] adps;
	reg acme; reg [2:0] adts;
	reg [7:0] didr0_r; reg [1:0] didr1_r;
	reg acoe_r, acd, acbg, aci, acie, acic_r; reg [1:0] acis;

	reg [9:0] result, sar, mask;
	reg [6:0] presc;
	reg [4:0] step;
	reg       first, sampling, cmp_s;
	reg [1:0] ac_s; reg ac_q;

	wire w = sel & wr;

	reg ptick;
	always @(*) case (adps)
		3'd0, 3'd1: ptick = presc[0];
		3'd2: ptick = &presc[1:0];
		3'd3: ptick = &presc[2:0];
		3'd4: ptick = &presc[3:0];
		3'd5: ptick = &presc[4:0];
		3'd6: ptick = &presc[5:0];
		default: ptick = &presc[6:0];
	endcase

	wire [9:0] nsar = (cmp_s ? sar : (sar & ~mask)) | (mask >> 1);
	wire trig  = adate & (adts != 3'd0) & trig_i[adts];
	wire ac_evt = acis == 2'd0 ? (ac_s[1] ^ ac_q) : acis == 2'd2 ? (~ac_s[1] & ac_q) :
	              acis == 2'd3 ? (ac_s[1] & ~ac_q) : 1'b0;

	always @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			refs <= 0; adlar <= 0; mux <= 0; aden <= 0; adsc <= 0; adate <= 0; adif <= 0; adie <= 0;
			adps <= 0; acme <= 0; adts <= 0; didr0_r <= 0; didr1_r <= 0;
			acoe_r <= 0; acd <= 0; acbg <= 0; aci <= 0; acie <= 0; acic_r <= 0; acis <= 0;
			result <= 0; sar <= 0; mask <= 0; presc <= 0; step <= 0; first <= 1'b1; sampling <= 0;
			cmp_s <= 0; ac_s <= 0; ac_q <= 0;
		end else begin
			cmp_s <= adc_cmp;
			ac_s  <= {ac_s[0], ac_out & ~acd};
			ac_q  <= ac_s[1];
			if (ac_evt & ~acd) aci <= 1'b1;

			if (!aden) begin
				adsc <= 1'b0; first <= 1'b1; step <= 5'd0; sampling <= 1'b0; presc <= 7'h0;
			end else begin
				presc <= presc + 7'h1;
				if (!adsc) begin
					presc <= 7'h0;
					if (trig) begin adsc <= 1'b1; step <= first ? 5'd0 : 5'd12; end
				end else if (ptick) begin
					// steps 0..11: warm-up (first conversion after ADEN only)
					// 12,13: track input   14: hold, first trial   15..24: ten decisions
					step <= step + 5'd1;
					if (step == 5'd12) sampling <= 1'b1;
					if (step == 5'd14) begin sampling <= 1'b0; sar <= 10'h200; mask <= 10'h200; end
					if (step >= 5'd15) begin sar <= nsar; mask <= mask >> 1; end
					if (step == 5'd24) begin
						result <= nsar; adif <= 1'b1; first <= 1'b0; step <= 5'd12;
						adsc <= adate & (adts == 3'd0);
					end
				end
			end

			if (w) case (addr[5:2])
				4'd0: begin refs <= wdata[7:6]; adlar <= wdata[5]; mux <= wdata[3:0]; end
				4'd1: begin
					aden <= wdata[7]; adate <= wdata[5]; adie <= wdata[3]; adps <= wdata[2:0];
					if (wdata[6] & wdata[7] & ~adsc) begin adsc <= 1'b1; step <= first ? 5'd0 : 5'd12; end
					if (wdata[4]) adif <= 1'b0;
				end
				4'd3: begin acme <= wdata[6]; adts <= wdata[2:0]; end
				4'd4: didr0_r <= wdata[7:0];
				4'd8: begin
					acoe_r <= wdata[8]; acd <= wdata[7]; acbg <= wdata[6]; acie <= wdata[3];
					acic_r <= wdata[2]; acis <= wdata[1:0];
					if (wdata[4]) aci <= 1'b0;
				end
				4'd9: didr1_r <= wdata[1:0];
				default: ;
			endcase
		end
	end

	always @(*) begin
		rdata = 32'h0;
		if (sel) case (addr[5:2])
			4'd0: rdata = {24'h0, refs, adlar, 1'b0, mux};
			4'd1: rdata = {24'h0, aden, adsc, adate, adif, adie, adps};
			4'd2: rdata = adlar ? {16'h0, result, 6'h0} : {22'h0, result};
			4'd3: rdata = {25'h0, acme, 3'h0, adts};
			4'd4: rdata = {24'h0, didr0_r};
			4'd8: rdata = {23'h0, acoe_r, acd, acbg, ac_s[1], aci, acie, acic_r, acis};
			4'd9: rdata = {30'h0, didr1_r};
			default: ;
		endcase
	end

	assign adc_en     = aden;
	assign adc_mux    = mux;
	assign adc_refs   = refs;
	assign adc_sample = sampling;
	assign adc_dac    = sar;
	assign ac_en      = ~acd;
	assign ac_bg      = acbg;
	assign ac_mux_en  = acme & ~aden;
	assign didr0      = didr0_r;
	assign didr1      = didr1_r;
	assign aco        = ac_s[1];
	assign acoe       = acoe_r;
	assign acic       = acic_r;
	assign irq_adc    = adif & adie;
	assign irq_ac     = aci & acie;
endmodule
`default_nettype wire
