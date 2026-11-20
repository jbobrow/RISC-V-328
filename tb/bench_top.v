// RV328 benchmark bench for Verilator (cache study, docs/cache_study.md).
// The digital core with simple digital stand-ins for the pads, the analog
// macro and the serial memory, so that tens of millions of clocks can be run.
// The chip-level testbench (tb/tb.v, Icarus Verilog) stays the reference; the
// two give the same clock counts for the same program.
//   +firmware=<file.hex>  +wiring=1  +maxcyc=<n>  +trace=<file>  +irqprobe=<n>
`default_nettype none
module bench_top (input wire clk);
	// ---------------- clocks, reset ----------------
	reg [5:0] lfdiv = 6'd0;
	reg       clk_lf = 1'b0;
	reg [4:0] porc = 5'd0;
	always @(posedge clk) begin
		if (lfdiv == 6'd30) begin lfdiv <= 6'd0; clk_lf <= ~clk_lf; end else lfdiv <= lfdiv + 6'd1;
		if (!porc[4]) porc <= porc + 5'd1;
	end

	// ---------------- pads ----------------
	wire [31:0] pad_out, pad_oe, pad_pu, pad_ie;
	reg  [31:0] ext_en = 32'h0, ext_val = 32'h0;
	integer     wiring = 0;
	reg  [31:0] pad_in;
	integer i;
	always @(*) begin
		for (i = 0; i < 32; i = i + 1)
			pad_in[i] = pad_oe[i] ? pad_out[i] : ext_en[i] ? ext_val[i] : pad_pu[i];
		if (wiring == 1) begin
			// TXD0 (PD1) -> RXD1 (PB4), TXD1 (PB3) -> RXD0 (PD0)
			if (pad_oe[17] && !pad_oe[4])  pad_in[4]  = pad_out[17];
			if (pad_oe[3]  && !pad_oe[16]) pad_in[16] = pad_out[3];
		end
	end

	// ---------------- ADC stand-in (same rule as rtl/analog/rv328_analog_model.v) ----------------
	wire        adc_en, adc_sample;
	wire [3:0]  adc_mux;
	wire [1:0]  adc_refs;
	wire [9:0]  adc_dac;
	reg  [31:0] vin_mv [0:7];
	reg  [31:0] vhold = 32'd0;
	wire [31:0] vsel = adc_mux < 4'd8 ? vin_mv[adc_mux[2:0]] : adc_mux == 4'd8 ? 32'd314 : adc_mux == 4'd14 ? 32'd1100 : 32'd0;
	wire [31:0] vref = adc_refs[1] ? 32'd1100 : 32'd5000;
	always @(negedge adc_sample) vhold <= vsel;
	wire adc_cmp = adc_en & (vhold * 32'd1024 >= {22'd0, adc_dac} * vref);

	// ---------------- serial memory: READ (03h) only ----------------
	wire fl_csn, fl_sck, fl_mosi;
	reg  [7:0]  mem [0:131071];
	reg  [7:0]  m_sh = 8'h0, m_cmd = 8'h0, m_dout = 8'h0;
	reg  [23:0] m_addr = 24'h0;
	reg  [3:0]  m_bitc = 4'd0;
	reg  [16:0] m_bytec = 17'd0;
	wire [7:0]  m_shn = {m_sh[6:0], fl_mosi};
	always @(posedge fl_sck or posedge fl_csn)
		if (fl_csn) begin m_bitc <= 4'd0; m_bytec <= 17'd0; end
		else begin
			m_sh <= m_shn;
			if (m_bitc == 4'd7) begin
				m_bitc <= 4'd0; m_bytec <= m_bytec + 17'd1;
				if (m_bytec == 17'd0) m_cmd <= m_shn;
				else if (m_bytec <= 17'd3) m_addr <= {m_addr[15:0], m_shn};
			end else m_bitc <= m_bitc + 4'd1;
		end
	always @(negedge fl_sck)
		if (!fl_csn) begin
			if (m_bitc == 4'd0 && m_bytec >= 17'd4 && m_cmd == 8'h03) m_dout <= mem[(m_addr[16:0] + m_bytec - 17'd4)];
			else m_dout <= {m_dout[6:0], 1'b0};
		end
	wire fl_miso = m_dout[7];

	// ---------------- the core ----------------
	wire jtag_tdo_nc, rc_en_nc, xo_en_nc, bod_en_nc, ac_en_nc, ac_bg_nc, ac_mux_en_nc;
	wire [7:0] rc_trim_nc;
	wire [1:0] xo_mode_nc;
	wire [2:0] bod_level_nc;
	rv328_core u_core (
		.clk_rc (clk), .clk_xa (1'b0), .clk_lf (clk_lf), .por_n (porc[4]), .bod_i (1'b0),
		.rc_en (rc_en_nc), .rc_trim (rc_trim_nc), .xo_en (xo_en_nc), .xo_mode (xo_mode_nc),
		.bod_en (bod_en_nc), .bod_level (bod_level_nc),
		.adc_en (adc_en), .adc_mux (adc_mux), .adc_refs (adc_refs), .adc_sample (adc_sample),
		.adc_dac (adc_dac), .adc_cmp (adc_cmp),
		.ac_en (ac_en_nc), .ac_bg (ac_bg_nc), .ac_mux_en (ac_mux_en_nc), .ac_out (1'b0),
		.pad_in (pad_in), .pad_out (pad_out), .pad_oe (pad_oe), .pad_pu (pad_pu), .pad_ie (pad_ie),
		.fl_csn (fl_csn), .fl_sck (fl_sck), .fl_mosi (fl_mosi), .fl_miso (fl_miso),
		.jtag_tck (1'b0), .jtag_tms (1'b1), .jtag_tdi (1'b1), .jtag_tdo (jtag_tdo_nc)
	);

	// ---------------- run control and instrumentation ----------------
	wire        cks     = u_core.clk_sys;
	wire [31:0] verdict = u_core.gpior0;
	wire [31:0] g1      = u_core.u_sys.g1;
	wire [31:0] g2      = u_core.u_sys.g2;
	reg  [1023:0] fw, trname;
	integer cyc = 0, fills = 0, xacc = 0, trf = 0, maxcyc = 400000000;
	integer irq_n = 0, irq_done = 0, irq_t0 = 0, irq_wait = 0;
	reg  [31:0] g1_q = 32'h0, lfsr = 32'h0328_C0DE;
	reg  [14:0] tr_last = 15'h7fff;
	reg         irq_armed = 1'b0, irq_busy = 1'b0, pb0_q = 1'b0;
	initial begin
		if (!$value$plusargs("firmware=%s", fw)) begin $display("no +firmware"); $finish; end
		for (i = 0; i < 131072; i = i + 1) mem[i] = 8'hFF;
		for (i = 0; i < 8; i = i + 1) vin_mv[i] = 32'd0;
		$readmemh(fw, mem);
		if ($value$plusargs("wiring=%d", wiring)) ;
		if ($value$plusargs("maxcyc=%d", maxcyc)) ;
		if ($value$plusargs("irqprobe=%d", irq_n)) begin ext_en[18] = 1'b1; end
		if ($value$plusargs("trace=%s", trname)) trf = $fopen(trname, "w");
	end
	always @(posedge cks) begin
		cyc <= cyc + 1;
		if (u_core.u_xip.seq_end && u_core.u_xip.seq == 2'd0) fills <= fills + 1;
		if (u_core.u_xip.a_valid) begin
			xacc <= xacc + 1;
			if (trf != 0 && u_core.u_xip.a_addr[19:5] != tr_last) begin
				tr_last <= u_core.u_xip.a_addr[19:5];
				$fdisplay(trf, "%h", u_core.u_xip.a_addr[19:5]);
			end
		end
		// firmware hooks through GPIOR1 (value in GPIOR2)
		g1_q <= g1;
		if (g1 != g1_q) case (g1[15:8])
			8'h20: vin_mv[g1[2:0]] <= g2;
			8'h50: begin
				$display("MARK %0d cyc=%0d fills=%0d acc=%0d val=%0d", g1[7:0], cyc, fills, xacc, g2);
				if (trf != 0) $fdisplay(trf, "M %0d %0d", g1[7:0], cyc);
				if (g1[7:0] == 8'd1) irq_armed <= 1'b1;
			end
			8'h60: $write("%c", g2[7:0]);
			default: ;
		endcase
		// interrupt probe: edges on INT0 (PD2) at irregular intervals, answer on PB0
		pb0_q <= pad_out[0];
		if (irq_armed && irq_done < irq_n) begin
			if (!irq_busy) begin
				if (irq_wait == 0) begin ext_val[18] <= ~ext_val[18]; irq_t0 <= cyc; irq_busy <= 1'b1; end
				else irq_wait <= irq_wait - 1;
			end else if (pad_out[0] != pb0_q) begin
				$display("IRQLAT %0d", cyc - irq_t0);
				irq_busy <= 1'b0; irq_done <= irq_done + 1;
				lfsr <= {lfsr[30:0], lfsr[31] ^ lfsr[21] ^ lfsr[1] ^ lfsr[0]};
				irq_wait <= 9000 + {18'd0, lfsr[13:0]} % 14000;
			end
		end
		if (verdict == 32'h600D600D) begin $display("PASS cyc=%0d fills=%0d", cyc, fills); $finish; end
		if (verdict[31:16] == 16'hBAD0) begin $display("FAIL check %0d", verdict[15:0]); $finish; end
		if (verdict[31:16] == 16'hDEAD) begin $display("FAULT mcause=%0d mepc=%08x", verdict[15:0], g2); $finish; end
		if (cyc >= maxcyc) begin $display("TIMEOUT cyc=%0d", cyc); $finish; end
	end
endmodule
`default_nettype wire
