// RV328 system control: clock source and prescaler, sleep mode, reset cause,
// peripheral disable, brown-out control, general-purpose registers.
//
//   0x00 CLKCR   [1:0] CLKSEL (0 RC 8 MHz, 1 crystal/external, 2 128 kHz)
//                [4] XEN  [6:5] XMODE (0 external clock on XTAL1, 1 low-power crystal,
//                2 full-swing crystal, 3 32.768 kHz crystal)  [7] RCDIS  [8] CKOUT (PB0)
//                [16] XRDY (RO)   CLKSEL=1 is only accepted while XRDY is set.
//   0x04 CLKPR   [3:0] system clock prescaler 2^n, n = 0..8
//   0x08 OSCCAL  [7:0] RC oscillator trim (reset 0x80)
//   0x0C SMCR    [2:0] sleep mode entered by WFI: 0 idle, 1 ADC noise reduction (= idle),
//                2 power-down, 3 power-save, 6 standby, 7 extended standby
//   0x10 MCUSR   [0] PORF [1] EXTRF [2] BORF [3] WDRF [4] SWRF [5] DBGRF  (write 1 to clear)
//   0x14 PRR     [15:0] hold peripheral slot n in reset
//   0x18 RSTCR   [0] RSTDISBL (PC6 becomes GPIO)   write 0xA5000100 for a software reset
//   0x1C BODCR   [3] BODEN [2:0] BODLEVEL  [8] BOD comparator output (RO). POR reset only.
//   0x20 GPIOR0  0x24 GPIOR1  0x28 GPIOR2   general-purpose registers
//   0x2C CHIPID  (RO)
`default_nettype none
module rv328_sysctl (
	input  wire        clk,
	input  wire        rst_n,
	input  wire        por_n,
	input  wire        sel,
	input  wire        wr,
	input  wire [7:0]  addr,
	input  wire [31:0] wdata,
	output reg  [31:0] rdata,

	output wire [1:0]  clksel,
	output wire [3:0]  clkpr,
	output wire        x_en,
	output wire [1:0]  x_mode,
	output wire        rc_dis,
	output wire        ckout,
	output wire [7:0]  osccal,
	input  wire        x_rdy,       // asynchronous level
	output wire [2:0]  sm,
	input  wire [5:0]  cause,
	output wire [5:0]  cause_clr,
	output wire [15:0] prr,
	output wire        rstdisbl,
	output wire        sw_rst_set,
	output wire        bod_en,
	output wire [2:0]  bod_level,
	input  wire        bod_i,       // asynchronous level
	output wire [31:0] gpior0
);
	localparam [31:0] CHIPID = 32'h5233_3238;   // "R328"

	reg [1:0]  clksel_r, xmode_r;
	reg        xen_r, rcdis_r, ckout_r;
	reg [3:0]  clkpr_r;
	reg [7:0]  osccal_r;
	reg [2:0]  sm_r;
	reg [15:0] prr_r;
	reg        rstdisbl_r, swrst_r;
	reg [3:0]  bodcr_r;
	reg [31:0] g0, g1, g2;

	wire w = sel & wr;
	wire x_rdy_s, bod_s;
	rv328_sync u_xr (.clk(clk), .rst_n(rst_n), .d(x_rdy), .q(x_rdy_s));
	rv328_sync u_bd (.clk(clk), .rst_n(rst_n), .d(bod_i), .q(bod_s));

	always @(posedge clk or negedge rst_n)
		if (!rst_n) begin
			clksel_r <= 2'd0; xmode_r <= 2'd0; xen_r <= 0; rcdis_r <= 0; ckout_r <= 0;
			clkpr_r <= 4'd0; osccal_r <= 8'h80; sm_r <= 3'd0; prr_r <= 16'h0;
			rstdisbl_r <= 0; swrst_r <= 0; g0 <= 32'h0; g1 <= 32'h0; g2 <= 32'h0;
		end else begin
			swrst_r <= 1'b0;
			if (w) case (addr[5:2])
				4'd0: begin
					if (wdata[1:0] != 2'd1 || x_rdy_s) clksel_r <= wdata[1:0];
					xen_r <= wdata[4]; xmode_r <= wdata[6:5]; rcdis_r <= wdata[7]; ckout_r <= wdata[8];
				end
				4'd1: clkpr_r <= wdata[3:0] > 4'd8 ? 4'd8 : wdata[3:0];
				4'd2: osccal_r <= wdata[7:0];
				4'd3: sm_r <= wdata[2:0];
				4'd5: prr_r <= wdata[15:0];
				4'd6: begin
					rstdisbl_r <= wdata[0];
					if (wdata[31:24] == 8'hA5 && wdata[8]) swrst_r <= 1'b1;
				end
				4'd8:  g0 <= wdata;
				4'd9:  g1 <= wdata;
				4'd10: g2 <= wdata;
				default: ;
			endcase
		end

	always @(posedge clk or negedge por_n)
		if (!por_n) bodcr_r <= 4'h0;
		else if (w && addr[5:2] == 4'd7) bodcr_r <= wdata[3:0];

	always @(*) begin
		rdata = 32'h0;
		if (sel) case (addr[5:2])
			4'd0:  rdata = {15'h0, x_rdy_s, 7'h0, ckout_r, rcdis_r, xmode_r, xen_r, 2'b00, clksel_r};
			4'd1:  rdata = {28'h0, clkpr_r};
			4'd2:  rdata = {24'h0, osccal_r};
			4'd3:  rdata = {29'h0, sm_r};
			4'd4:  rdata = {26'h0, cause};
			4'd5:  rdata = {16'h0, prr_r};
			4'd6:  rdata = {31'h0, rstdisbl_r};
			4'd7:  rdata = {23'h0, bod_s, 4'h0, bodcr_r};
			4'd8:  rdata = g0;
			4'd9:  rdata = g1;
			4'd10: rdata = g2;
			4'd11: rdata = CHIPID;
			default: ;
		endcase
	end

	assign clksel = clksel_r;  assign clkpr = clkpr_r;  assign x_en = xen_r;  assign x_mode = xmode_r;
	assign rc_dis = rcdis_r & (clksel_r != 2'd0);
	assign ckout = ckout_r;    assign osccal = osccal_r; assign sm = sm_r;
	assign cause_clr = (w && addr[5:2] == 4'd4) ? wdata[5:0] : 6'h0;   assign prr = prr_r;       assign rstdisbl = rstdisbl_r;
	assign sw_rst_set = swrst_r;
	assign bod_en = bodcr_r[3]; assign bod_level = bodcr_r[2:0];
	assign gpior0 = g0;
endmodule
`default_nettype wire
