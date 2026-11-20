// Synthesisable stand-in for the analog macro: the "digital-first" tapeout.
// With this stub the chip needs an external clock on PB6/XTAL1 and an external
// reset pulse on PC6/RESET after power-up; there is no ADC, comparator,
// brown-out detector, crystal oscillator or independent watchdog clock.
`default_nettype none
module rv328_analog (
	inout  wire        XTAL1, XTAL2, AREF, AVCC,
	inout  wire [7:0]  ADC,
	inout  wire        AIN0, AIN1,
	input  wire        dig_clk_i,
	input  wire        dig_rstn_i,
	output wire        clk_rc,
	output wire        clk_xa,
	output wire        clk_lf,
	output wire        por_n,
	output wire        bod_o,
	input  wire        rc_en,
	input  wire [7:0]  rc_trim,
	input  wire        xo_en,
	input  wire [1:0]  xo_mode,
	input  wire        bod_en,
	input  wire [2:0]  bod_level,
	input  wire        adc_en,
	input  wire [3:0]  adc_mux,
	input  wire [1:0]  adc_refs,
	input  wire        adc_sample,
	input  wire [9:0]  adc_dac,
	output wire        adc_cmp,
	input  wire        ac_en,
	input  wire        ac_bg,
	input  wire        ac_mux_en,
	output wire        ac_out
);
	assign clk_rc = dig_clk_i;
	assign clk_xa = 1'b0;
	assign por_n  = dig_rstn_i;
	assign bod_o  = 1'b0;
	assign adc_cmp = 1'b0;
	assign ac_out  = 1'b0;

	// low-frequency clock: external clock / 64
	(* keep *) reg [5:0] div;
	always @(posedge dig_clk_i or negedge dig_rstn_i)
		if (!dig_rstn_i) div <= 6'h0;
		else             div <= div + 6'h1;
	rv328_clkbuf u_lfbuf (.i(div[5]), .o(clk_lf));
endmodule
`default_nettype wire
