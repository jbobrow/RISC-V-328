// Behavioural model of the RV328 analog macro, for simulation only.
// It defines the contract the real macro has to meet (see docs/analog_macros.md).
// Analog pad voltages are not carried on wires; the testbench sets the real
// variables below (in millivolts) by hierarchical reference.
`timescale 1ns/1ps
`default_nettype none
module rv328_analog (
	inout  wire        XTAL1, XTAL2, AREF, AVCC,
	inout  wire [7:0]  ADC,
	inout  wire        AIN0, AIN1,
	input  wire        dig_clk_i,     // used by the digital-first stub only
	input  wire        dig_rstn_i,    // used by the digital-first stub only
	output reg         clk_rc,
	output reg         clk_xa,
	output reg         clk_lf,
	output reg         por_n,
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
	parameter real XTAL_PERIOD_NS = 62.5;      // 16 MHz crystal
	real vcc_mv   = 5000.0;
	real aref_mv  = 5000.0;
	real vin_mv [0:7];
	real ain0_mv  = 0.0;
	real ain1_mv  = 0.0;
	real temp_mv  = 314.0;
	real vhold    = 0.0;
	integer i;
	initial for (i = 0; i < 8; i = i + 1) vin_mv[i] = 0.0;

	// power-on reset
	// (asserted shortly after time 0 so that every flop sees the falling edge)
	initial begin por_n = 1'b1; #1 por_n = 1'b0; #20000 por_n = 1'b1; end
	task power_cycle; begin por_n = 1'b0; #20000 por_n = 1'b1; end endtask

	// 8 MHz RC oscillator: about 0.5 % per trim step, 1 us start-up
	real rc_half;
	initial clk_rc = 1'b0;
	always begin
		if (rc_en === 1'b1) begin
			rc_half = 62.5 * (1.0 + (128.0 - rc_trim) * 0.005);
			#(rc_half) clk_rc = ~clk_rc;
		end else begin
			clk_rc = 1'b0;
			wait (rc_en === 1'b1);
			#1000;
		end
	end

	// 128 kHz watchdog oscillator, always running
	initial clk_lf = 1'b0;
	always #3906.25 clk_lf = ~clk_lf;

	// crystal oscillator, 20 us start-up
	real x_half;
	initial clk_xa = 1'b0;
	always begin
		if (xo_en === 1'b1) begin
			x_half = (xo_mode == 2'd3) ? 15258.789 : XTAL_PERIOD_NS / 2.0;
			#(x_half) clk_xa = ~clk_xa;
		end else begin
			clk_xa = 1'b0;
			wait (xo_en === 1'b1);
			#20000;
		end
	end

	// brown-out detector
	reg [12:0] bod_mv;
	always @(*) case (bod_level)
		3'd0: bod_mv = 1800;
		3'd1: bod_mv = 2700;
		default: bod_mv = 4300;
	endcase
	assign bod_o = bod_en & (vcc_mv < bod_mv);

	// ADC front end
	real vsel, vref;
	always @(*) begin
		if (adc_mux < 4'd8)        vsel = vin_mv[adc_mux[2:0]];
		else if (adc_mux == 4'd8)  vsel = temp_mv;
		else if (adc_mux == 4'd14) vsel = 1100.0;
		else                       vsel = 0.0;
		case (adc_refs)
			2'd0:    vref = aref_mv;
			2'd1:    vref = vcc_mv;
			default: vref = 1100.0;
		endcase
	end
	always @(negedge adc_sample) vhold = vsel;
	assign adc_cmp = adc_en & (vhold >= (adc_dac * vref / 1024.0));

	// analog comparator
	wire real_dummy = 1'b0;
	reg ac_r;
	always @(*) ac_r = ((ac_bg ? 1100.0 : ain0_mv) > (ac_mux_en ? vin_mv[adc_mux[2:0]] : ain1_mv));
	assign ac_out = ac_en & ac_r;
endmodule
`default_nettype wire
