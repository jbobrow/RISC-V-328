// RV328 chip-level testbench. Runs one firmware image and reports the verdict
// the firmware writes to GPIOR0 (0x600D600D = pass, 0xBAD0nnnn = fail at check nnnn).
//   +firmware=<file.hex>   byte-per-line image for the serial memory
//   +wiring=<n>            external loop-back wiring (see below)
//   +extclk=<period_ns>    drive an external clock into PB6/XTAL1
//   +timeout_us=<n>
//   +isp  +jtag  +pinreset   testbench-driven programming, JTAG and reset sequences
//   +trace=<file>          benchmark runs: list of program-memory lines fetched (scripts/cache_model.py)
//   +irqprobe=<n>          benchmark runs: n edges on INT0 (PD2), time to the handler's toggle of PB0
`timescale 1ns/1ps
`default_nettype none
module tb;
	wire [7:0] PB, PD;
	wire [6:0] PC;
	wire [3:0] PE;
	wire FL_CSN, FL_SCK, FL_MOSI, FL_MISO, TDO;
	reg  tck_r = 0, tms_r = 1, tdi_r = 1;
	wire TCK = tck_r, TMS = tms_r, TDI = tdi_r;
	wire [6:0] SPARE;
	wire A_XTAL1, A_XTAL2, A_AREF, A_AVCC, A_AIN0, A_AIN1;
	wire [7:0] A_ADC;

	chip_top dut (
		.PB (PB), .PC (PC), .PD (PD), .PE (PE),
		.A_XTAL1 (A_XTAL1), .A_XTAL2 (A_XTAL2), .A_AREF (A_AREF), .A_AVCC (A_AVCC),
		.A_AIN0 (A_AIN0), .A_AIN1 (A_AIN1),
		.A_ADC0 (A_ADC[0]), .A_ADC1 (A_ADC[1]), .A_ADC2 (A_ADC[2]), .A_ADC3 (A_ADC[3]),
		.A_ADC4 (A_ADC[4]), .A_ADC5 (A_ADC[5]), .A_ADC6 (A_ADC[6]), .A_ADC7 (A_ADC[7]),
		.FL_CSN (FL_CSN), .FL_SCK (FL_SCK), .FL_MOSI (FL_MOSI), .FL_MISO (FL_MISO),
		.TCK (TCK), .TMS (TMS), .TDI (TDI), .TDO (TDO), .SPARE (SPARE)
	);

	spi_mem u_mem (.csn (FL_CSN), .sck (FL_SCK), .mosi (FL_MOSI), .miso (FL_MISO));

	// ---------------- stimulus on pins ----------------
	integer wiring = 0;
	real    extclk = 0.0;
	integer timeout_us = 200000;
	reg [1023:0] fw;
	reg [7:0] drv_b = 8'hzz, drv_d = 8'hzz;
	reg [6:0] drv_c = 7'hzz;
	reg [3:0] drv_e = 4'hz;
	reg       xclk = 0;
	assign PB = drv_b; assign PC = drv_c; assign PD = drv_d; assign PE = drv_e;
	// very weak pull-downs stand in for board leakage so floating pins read 0, not X
	assign (highz1, weak0) PB = 8'h00;
	assign (highz1, weak0) PC = 7'h00;
	assign (highz1, weak0) PD = 8'h00;
	assign (highz1, weak0) PE = 4'h0;
	assign PB[6] = (extclk > 0.0) ? xclk : 1'bz;
	always begin if (extclk > 0.0) #(extclk / 2.0) xclk = ~xclk; else #100; end

	// Loop-back wiring between pins, selected per test:
	//  1  USART: TXD0(PD1)->RXD1(PB4), TXD1(PB3)->RXD0(PD0)
	//  2  SPI:   SPI0 <-> SPI1 (PB3-PE3 MOSI, PB4-PC0 MISO, PB5-PC1 SCK, PB2-PE2 SS)
	//  3  TWI:   TWI0 <-> TWI1 (PC4-PE0 SDA, PC5-PE1 SCL) with pull-ups
	//  4  timers: OC1A(PB1)->ICP1(PB0), OC0A(PD6)->T1(PD5), OC2B(PD3)->INT0(PD2)
	wire w1 = wiring == 1, w2 = wiring == 2, w3 = wiring == 3, w4 = wiring == 4;
	tranif1 (PD[1], PB[4], w1);
	tranif1 (PB[3], PD[0], w1);
	tranif1 (PB[3], PE[3], w2);
	tranif1 (PB[4], PC[0], w2);
	tranif1 (PB[5], PC[1], w2);
	tranif1 (PB[2], PE[2], w2);
	tranif1 (PC[4], PE[0], w3);
	tranif1 (PC[5], PE[1], w3);
	assign (pull1, highz0) PC[4] = w3 ? 1'b1 : 1'bz;
	assign (pull1, highz0) PC[5] = w3 ? 1'b1 : 1'bz;
	tranif1 (PB[1], PB[0], w4);
	tranif1 (PD[6], PD[5], w4);
	tranif1 (PD[3], PD[2], w4);

	// ---------------- in-system programming and JTAG (driven by the testbench) ----------------
	// +isp: hold RESET low, use PB2 (CS#), PB3 (MOSI), PB4 (MISO), PB5 (SCK) as a
	// plain SPI port into the serial memory, then release RESET.
	reg [7:0] isp_rx;
	task isp_byte(input [7:0] d);
		integer n;
		begin
			for (n = 7; n >= 0; n = n - 1) begin
				drv_b[3] = d[n]; #200 drv_b[5] = 1'b1; isp_rx = {isp_rx[6:0], PB[4]}; #200 drv_b[5] = 1'b0;
			end
		end
	endtask
	task isp_cmd4(input [7:0] c, input [23:0] a);
		begin drv_b[2] = 1'b0; #200 isp_byte(c); isp_byte(a[23:16]); isp_byte(a[15:8]); isp_byte(a[7:0]); end
	endtask
	task isp_run;
		reg [31:0] rd;
		integer n;
		begin
			drv_c[6] = 1'b0; drv_b[2] = 1'b1; drv_b[5] = 1'b0; drv_b[3] = 1'b0;
			#50000;
			// read back the first word of the image
			isp_cmd4(8'h03, 24'h0);
			for (n = 0; n < 4; n = n + 1) begin isp_byte(8'h00); rd = {isp_rx, rd[31:8]}; end
			drv_b[2] = 1'b1; #1000;
			if (rd !== {u_mem.mem[3], u_mem.mem[2], u_mem.mem[1], u_mem.mem[0]}) begin
				$display("FAIL isp read %h", rd); $finish;
			end
			// program a marker word at 0x7F00
			drv_b[2] = 1'b0; #200 isp_byte(8'h06); drv_b[2] = 1'b1; #1000;
			isp_cmd4(8'h02, 24'h007F00);
			isp_byte(8'h32); isp_byte(8'h33); isp_byte(8'h56); isp_byte(8'h52);
			drv_b[2] = 1'b1; #100000;
			$display("ISP read-back and program done");
			drv_b[2] = 1'bz; drv_b[3] = 1'bz; drv_b[5] = 1'bz; drv_c[6] = 1'bz;
		end
	endtask

	// +jtag: read the TAP IDCODE (selected by default after TAP reset)
	reg tdo_s;   // TDO sampled just before each rising TCK edge
	task jtag_clk(input tms, input tdi);
		begin tms_r = tms; tdi_r = tdi; #500 tdo_s = TDO; tck_r = 1'b1; #500 tck_r = 1'b0; end
	endtask
	task jtag_idcode;
		reg [31:0] id;
		integer n;
		begin
			for (n = 0; n < 6; n = n + 1) jtag_clk(1'b1, 1'b1);     // test-logic-reset
			jtag_clk(1'b0, 1'b1);                                   // run-test/idle
			jtag_clk(1'b1, 1'b1); jtag_clk(1'b0, 1'b1);             // select-DR, capture-DR
			jtag_clk(1'b0, 1'b1);                                   // shift-DR
			for (n = 0; n < 32; n = n + 1) begin jtag_clk(n == 31, 1'b1); id = {tdo_s, id[31:1]}; end
			jtag_clk(1'b1, 1'b1); jtag_clk(1'b0, 1'b1);
			if (id === 32'h0328_0DEB) $display("JTAG IDCODE %h ok", id);
			else begin $display("FAIL jtag idcode %h", id); $finish; end
		end
	endtask
	initial begin
		// +pinreset: reset pulse on PC6 at power-up (required by the digital-first build)
		if ($test$plusargs("pinreset")) begin #10 drv_c[6] = 1'b0; #20000 drv_c[6] = 1'bz; end
		#30000;
		if ($test$plusargs("isp")) isp_run;
		if ($test$plusargs("jtag")) jtag_idcode;
	end

`ifdef RV328_GL
	// gate-level runs are slow: show progress
	always #50000 $display("  ... t=%0t", $time);
`endif
`ifdef RV328_GL_SDF
	// delays extracted from the routed layout (scripts/gl_sim.sh)
	initial $sdf_annotate(`RV328_GL_SDF, dut);
`endif

	// ---------------- run control ----------------
	// RV328_GL: the device under test is the flattened gate-level netlist from the
	// layout flow, where every register bit is its own net (scripts/gl_sim.sh).
`ifdef RV328_GL
	wire [31:0] verdict = {dut.\u_core.dbg_gpior0[31] , dut.\u_core.dbg_gpior0[30] , dut.\u_core.dbg_gpior0[29] , dut.\u_core.dbg_gpior0[28] , dut.\u_core.dbg_gpior0[27] , dut.\u_core.dbg_gpior0[26] , dut.\u_core.dbg_gpior0[25] , dut.\u_core.dbg_gpior0[24] , dut.\u_core.dbg_gpior0[23] , dut.\u_core.dbg_gpior0[22] , dut.\u_core.dbg_gpior0[21] , dut.\u_core.dbg_gpior0[20] , dut.\u_core.dbg_gpior0[19] , dut.\u_core.dbg_gpior0[18] , dut.\u_core.dbg_gpior0[17] , dut.\u_core.dbg_gpior0[16] , dut.\u_core.dbg_gpior0[15] , dut.\u_core.dbg_gpior0[14] , dut.\u_core.dbg_gpior0[13] , dut.\u_core.dbg_gpior0[12] , dut.\u_core.dbg_gpior0[11] , dut.\u_core.dbg_gpior0[10] , dut.\u_core.dbg_gpior0[9] , dut.\u_core.dbg_gpior0[8] , dut.\u_core.dbg_gpior0[7] , dut.\u_core.dbg_gpior0[6] , dut.\u_core.dbg_gpior0[5] , dut.\u_core.dbg_gpior0[4] , dut.\u_core.dbg_gpior0[3] , dut.\u_core.dbg_gpior0[2] , dut.\u_core.dbg_gpior0[1] , dut.\u_core.dbg_gpior0[0] };
	wire [31:0] tb_g1   = {dut.\u_core.u_sys.g1[31] , dut.\u_core.u_sys.g1[30] , dut.\u_core.u_sys.g1[29] , dut.\u_core.u_sys.g1[28] , dut.\u_core.u_sys.g1[27] , dut.\u_core.u_sys.g1[26] , dut.\u_core.u_sys.g1[25] , dut.\u_core.u_sys.g1[24] , dut.\u_core.u_sys.g1[23] , dut.\u_core.u_sys.g1[22] , dut.\u_core.u_sys.g1[21] , dut.\u_core.u_sys.g1[20] , dut.\u_core.u_sys.g1[19] , dut.\u_core.u_sys.g1[18] , dut.\u_core.u_sys.g1[17] , dut.\u_core.u_sys.g1[16] , dut.\u_core.u_sys.g1[15] , dut.\u_core.u_sys.g1[14] , dut.\u_core.u_sys.g1[13] , dut.\u_core.u_sys.g1[12] , dut.\u_core.u_sys.g1[11] , dut.\u_core.u_sys.g1[10] , dut.\u_core.u_sys.g1[9] , dut.\u_core.u_sys.g1[8] , dut.\u_core.u_sys.g1[7] , dut.\u_core.u_sys.g1[6] , dut.\u_core.u_sys.g1[5] , dut.\u_core.u_sys.g1[4] , dut.\u_core.u_sys.g1[3] , dut.\u_core.u_sys.g1[2] , dut.\u_core.u_sys.g1[1] , dut.\u_core.u_sys.g1[0] };
	wire [31:0] tb_g2   = {dut.\u_core.u_sys.g2[31] , dut.\u_core.u_sys.g2[30] , dut.\u_core.u_sys.g2[29] , dut.\u_core.u_sys.g2[28] , dut.\u_core.u_sys.g2[27] , dut.\u_core.u_sys.g2[26] , dut.\u_core.u_sys.g2[25] , dut.\u_core.u_sys.g2[24] , dut.\u_core.u_sys.g2[23] , dut.\u_core.u_sys.g2[22] , dut.\u_core.u_sys.g2[21] , dut.\u_core.u_sys.g2[20] , dut.\u_core.u_sys.g2[19] , dut.\u_core.u_sys.g2[18] , dut.\u_core.u_sys.g2[17] , dut.\u_core.u_sys.g2[16] , dut.\u_core.u_sys.g2[15] , dut.\u_core.u_sys.g2[14] , dut.\u_core.u_sys.g2[13] , dut.\u_core.u_sys.g2[12] , dut.\u_core.u_sys.g2[11] , dut.\u_core.u_sys.g2[10] , dut.\u_core.u_sys.g2[9] , dut.\u_core.u_sys.g2[8] , dut.\u_core.u_sys.g2[7] , dut.\u_core.u_sys.g2[6] , dut.\u_core.u_sys.g2[5] , dut.\u_core.u_sys.g2[4] , dut.\u_core.u_sys.g2[3] , dut.\u_core.u_sys.g2[2] , dut.\u_core.u_sys.g2[1] , dut.\u_core.u_sys.g2[0] };
	wire [31:0] tb_addr = 32'hx;
`else
	wire [31:0] verdict = dut.u_core.gpior0;
	wire [31:0] tb_g1   = dut.u_core.u_sys.g1;
	wire [31:0] tb_g2   = dut.u_core.u_sys.g2;
	wire [31:0] tb_addr = dut.u_core.haddr;
`endif
	integer k;
	initial begin
		if (!$value$plusargs("firmware=%s", fw)) begin $display("no +firmware"); $finish; end
		if ($value$plusargs("wiring=%d", wiring)) ;
		if ($value$plusargs("extclk=%f", extclk)) ;
		if ($value$plusargs("timeout_us=%d", timeout_us)) ;
		$readmemh(fw, u_mem.mem);
		if ($test$plusargs("vcd")) begin $dumpfile("tb.vcd"); $dumpvars(0, tb); end
		#(timeout_us * 1000.0);
		$display("TIMEOUT verdict=%08x pc_addr=%08x", verdict, tb_addr);
		$finish;
	end
	always @(verdict) begin
		if (verdict === 32'h600D600D) begin #1000 $display("PASS t=%0t", $time); $finish; end
		if (verdict[31:16] === 16'hBAD0) begin #1000 $display("FAIL check %0d (GPIOR2=%0d) t=%0t", verdict[15:0], tb_g2, $time); $finish; end
		if (verdict[31:16] === 16'hDEAD) begin
			#1000 $display("FAULT mcause=%0d mepc=%08x", verdict[15:0], tb_g2); $finish;
		end
	end

`ifndef RV328_GL
	// ---------------- benchmark instrumentation ----------------
	// System clocks, cache fills and program-memory accesses since reset. The
	// firmware marks points with GPIOR1 = 0x50nn; each mark prints the counters.
	integer cyc = 0, fills = 0, xacc = 0, trf = 0;
	reg [1023:0] trname;
	reg [14:0]   tr_last = 15'h7fff;
	initial if ($value$plusargs("trace=%s", trname)) trf = $fopen(trname, "w");
	always @(posedge dut.u_core.clk_sys) begin
		cyc = cyc + 1;
		if (dut.u_core.u_xip.seq_end && dut.u_core.u_xip.seq == 2'd0) fills = fills + 1;
		if (dut.u_core.u_xip.a_valid) begin
			xacc = xacc + 1;
			if (trf != 0 && dut.u_core.u_xip.a_addr[19:5] != tr_last) begin
				tr_last = dut.u_core.u_xip.a_addr[19:5];
				$fdisplay(trf, "%h", tr_last);
			end
		end
	end
	always @(tb_g1) if (tb_g1[15:8] === 8'h50) begin
		$display("MARK %0d cyc=%0d fills=%0d acc=%0d val=%0d", tb_g1[7:0], cyc, fills, xacc, tb_g2);
		if (trf != 0) $fdisplay(trf, "M %0d %0d", tb_g1[7:0], cyc);
	end
	// +irqprobe: after mark 1, toggle INT0 (PD2) at irregular intervals and time the
	// handler's answer on PB0, in system clocks
	integer irq_n = 0, irq_i, irq_t0, irq_seed = 328;
	initial if ($value$plusargs("irqprobe=%d", irq_n)) begin
		drv_d[2] = 1'b0;
		wait (tb_g1 === 32'h5001);
		for (irq_i = 0; irq_i < irq_n; irq_i = irq_i + 1) begin
			repeat (9000 + {$random(irq_seed)} % 14000) @(posedge dut.u_core.clk_sys);
			irq_t0 = cyc; drv_d[2] = ~drv_d[2];
			@(PB[0]);
			$display("IRQLAT %0d", cyc - irq_t0);
		end
	end
`endif

	// Test hooks: firmware requests testbench actions through GPIOR1
	//   0x10nn drive PD[nn%8] low, 0x11nn release;   0x20xx set ADC0 mV = GPIOR2
	//   0x30nn pulse RESET low,   0x40nn drive PD[nn] high after 300 us
	wire [31:0] hook = tb_g1;
	always @(hook) begin
		case (hook[15:8])
			8'h10: drv_d[hook[2:0]] = 1'b0;
			8'h11: drv_d[hook[2:0]] = 1'bz;
			8'h12: drv_d[hook[2:0]] = 1'b1;
`ifndef RV328_ANALOG_STUB
			8'h20: dut.u_analog.vin_mv[hook[2:0]] = tb_g2;
			8'h21: dut.u_analog.ain0_mv = tb_g2;
			8'h22: dut.u_analog.ain1_mv = tb_g2;
`endif
			8'h30: begin drv_c[6] = 1'b0; #20000 drv_c[6] = 1'bz; end
			8'h60: $write("%c", tb_g2[7:0]);          // console (benchmarks)
			8'h40: begin #300000 drv_d[hook[2:0]] = 1'b1; end
			default: ;
		endcase
	end
endmodule
`default_nettype wire
