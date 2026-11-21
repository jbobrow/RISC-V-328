// RV328 technology wrappers.
// Everything that must map to a specific library cell or macro lives here, so
// porting to another PDK means editing this one file.
//   RV328_TECH_GF180 : instantiate GF180MCU cells/macros (synthesis, GL sim)
//   (undefined)      : generic behavioural models (RTL simulation, FPGA)
//   RV328_GENERIC_ICG: with RV328_TECH_GF180, keep the behavioural clock gate
//                      (simulating against the foundry SRAM model only)
`ifdef RV328_SIM_SRAM_HOLD
`timescale 1ns/1ps
`endif
`default_nettype none

// Standard-cell library: 7-track by default, 9-track with RV328_SC9T
`ifdef RV328_SC9T
`define RV328_ICG_CELL    gf180mcu_fd_sc_mcu9t5v0__icgtp_2
`define RV328_CLKBUF_CELL gf180mcu_fd_sc_mcu9t5v0__clkbuf_4
`define RV328_PADBUF_CELL gf180mcu_fd_sc_mcu9t5v0__buf_8
`endif
`ifndef RV328_ICG_CELL
`define RV328_ICG_CELL gf180mcu_fd_sc_mcu7t5v0__icgtp_2
`endif
`ifndef RV328_CLKBUF_CELL
`define RV328_CLKBUF_CELL gf180mcu_fd_sc_mcu7t5v0__clkbuf_4
`define RV328_PADBUF_CELL gf180mcu_fd_sc_mcu7t5v0__buf_8
`endif

// ----------------------------------------------------------------------------
// Integrated clock gate (latch + AND). Enable is sampled while clk is low.
module rv328_icg (
	input  wire clk,
	input  wire en,
	output wire gclk
);
`ifdef RV328_GENERIC_ICG
	reg en_l;
	always @(*) if (!clk) en_l = en;
	assign gclk = clk & en_l;
`elsif RV328_TECH_GF180
	(* keep *) `RV328_ICG_CELL u_icg (.CLK(clk), .E(en), .TE(1'b0), .Q(gclk));
`else
	reg en_l;
	// verilator lint_off LATCH
	always @(*) if (!clk) en_l = en;
	// verilator lint_on LATCH
	assign gclk = clk & en_l;
`endif
endmodule

// ----------------------------------------------------------------------------
// Clock root buffer: gives a derived clock a dedicated cell to start its tree
// from (clock-tree synthesis wants a buffer, not a flip-flop, as the root).
module rv328_clkbuf (
	input  wire i,
	output wire o
);
`ifdef RV328_TECH_GF180
	(* keep *) `RV328_CLKBUF_CELL u_buf (.I(i), .Z(o));
`else
	assign o = i;
`endif
endmodule

// ----------------------------------------------------------------------------
// Buffer that the floorplan places beside a pad (rv328_chip_top.v, RV328_PADBUF):
// the place-and-route flow does not buffer a net that ends at a pad.
module rv328_padbuf (
	input  wire i,
	output wire o
);
`ifdef RV328_TECH_GF180
	(* keep *) `RV328_PADBUF_CELL u_buf (.I(i), .Z(o));
`else
	assign o = i;
`endif
endmodule

// ----------------------------------------------------------------------------
// Two-flop synchroniser
module rv328_sync #(
	parameter RST = 1'b0
) (
	input  wire clk,
	input  wire rst_n,
	input  wire d,
	output wire q
);
	(* keep *) reg [1:0] s;
	always @(posedge clk or negedge rst_n)
		if (!rst_n) s <= {2{RST}};
		else        s <= {s[0], d};
	assign q = s[1];
endmodule

// ----------------------------------------------------------------------------
// Reset synchroniser: asynchronous assert, synchronous release
module rv328_rstsync (
	input  wire clk,
	input  wire arst_n,
	output wire rst_n
);
	(* keep *) reg [1:0] s;
	always @(posedge clk or negedge arst_n)
		if (!arst_n) s <= 2'b00;
		else         s <= {s[0], 1'b1};
	assign rst_n = s[1];
endmodule

// ----------------------------------------------------------------------------
// 512 x 32 synchronous single-port RAM with byte write enables.
// GF180: four gf180mcu_fd_ip_sram__sram512x8m8wm1 macros, one per byte lane.
module rv328_ram512x32 (
	input  wire        clk,
	input  wire        en,
	input  wire [3:0]  we,
	input  wire [8:0]  addr,
	input  wire [31:0] wdata,
	output wire [31:0] rdata
);
`ifdef RV328_TECH_GF180
	// Explicit instance names (no generate loop) so the floorplan and power-grid
	// scripts can refer to them. Power is connected by PDN_MACRO_CONNECTIONS.
`ifdef RV328_SIM_SRAM_HOLD
	// RTL simulation against the foundry model only: the model samples its
	// inputs a little after the clock edge, so give them the hold time that
	// place-and-route provides in silicon.
	wire        en_i;
	wire [3:0]  we_i;
	wire [8:0]  addr_i;
	wire [31:0] wdata_i;
	assign #1 en_i = en;
	assign #1 we_i = we;
	assign #1 addr_i = addr;
	assign #1 wdata_i = wdata;
`else
	wire        en_i = en;
	wire [3:0]  we_i = we;
	wire [8:0]  addr_i = addr;
	wire [31:0] wdata_i = wdata;
`endif
	gf180mcu_fd_ip_sram__sram512x8m8wm1 u_ram0 (.CLK (clk), .CEN (~en_i), .GWEN (~we_i[0]), .WEN (8'h00),
		.A (addr_i), .D (wdata_i[7:0]),   .Q (rdata[7:0]));
	gf180mcu_fd_ip_sram__sram512x8m8wm1 u_ram1 (.CLK (clk), .CEN (~en_i), .GWEN (~we_i[1]), .WEN (8'h00),
		.A (addr_i), .D (wdata_i[15:8]),  .Q (rdata[15:8]));
	gf180mcu_fd_ip_sram__sram512x8m8wm1 u_ram2 (.CLK (clk), .CEN (~en_i), .GWEN (~we_i[2]), .WEN (8'h00),
		.A (addr_i), .D (wdata_i[23:16]), .Q (rdata[23:16]));
	gf180mcu_fd_ip_sram__sram512x8m8wm1 u_ram3 (.CLK (clk), .CEN (~en_i), .GWEN (~we_i[3]), .WEN (8'h00),
		.A (addr_i), .D (wdata_i[31:24]), .Q (rdata[31:24]));
`else
	reg [31:0] mem [0:511];
	reg [31:0] q;
	always @(posedge clk) if (en) begin
		if (we[0]) mem[addr][7:0]   <= wdata[7:0];
		if (we[1]) mem[addr][15:8]  <= wdata[15:8];
		if (we[2]) mem[addr][23:16] <= wdata[23:16];
		if (we[3]) mem[addr][31:24] <= wdata[31:24];
		if (~|we)  q <= mem[addr];
	end
	assign rdata = q;
`endif
endmodule

// ----------------------------------------------------------------------------
// 512 x 8 synchronous single-port RAM (cache tags).
// GF180: one gf180mcu_fd_ip_sram__sram512x8m8wm1 macro.
module rv328_ram512x8 (
	input  wire        clk,
	input  wire        en,
	input  wire        we,
	input  wire [8:0]  addr,
	input  wire [7:0]  wdata,
	output wire [7:0]  rdata
);
`ifdef RV328_TECH_GF180
`ifdef RV328_SIM_SRAM_HOLD
	wire        en_i;
	wire        we_i;
	wire [8:0]  addr_i;
	wire [7:0]  wdata_i;
	assign #1 en_i = en;
	assign #1 we_i = we;
	assign #1 addr_i = addr;
	assign #1 wdata_i = wdata;
`else
	wire        en_i = en;
	wire        we_i = we;
	wire [8:0]  addr_i = addr;
	wire [7:0]  wdata_i = wdata;
`endif
	gf180mcu_fd_ip_sram__sram512x8m8wm1 u_ram0 (.CLK (clk), .CEN (~en_i), .GWEN (~we_i), .WEN (8'h00),
		.A (addr_i), .D (wdata_i), .Q (rdata));
`else
	reg [7:0] mem [0:511];
	reg [7:0] q;
	always @(posedge clk) if (en) begin
		if (we) mem[addr] <= wdata;
		else    q <= mem[addr];
	end
	assign rdata = q;
`endif
endmodule

`default_nettype wire
