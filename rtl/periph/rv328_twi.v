// RV328 two-wire (I2C) interface: byte-oriented master and slave with the AVR
// TWI programming model (TWINT handshake, TWSR status codes, clock stretching
// while TWINT is set).
//
//   0x00 TWBR  [7:0]   fSCL = fclk / (16 + 2 * TWBR * 4^TWPS)
//   0x04 TWSR  [7:3] status  [1:0] TWPS
//   0x08 TWAR  [7:1] slave address  [0] TWGCE general-call enable
//   0x0C TWDR
//   0x10 TWCR  [7] TWINT (W1C = "go") [6] TWEA [5] TWSTA [4] TWSTO [3] TWWC (RO)
//              [2] TWEN [0] TWIE
//   0x14 TWAMR [7:1] address mask (1 = don't care)
//
// Status codes implemented: 08 10 18 20 28 30 38 40 48 50 58 (master),
// 60 70 80 88 90 98 A0 (slave receiver), A8 B8 C0 C8 (slave transmitter), F8.
// Not implemented: arbitration-lost-then-addressed codes (68/78/B0).
`default_nettype none
module rv328_twi (
	input  wire        clk,
	input  wire        rst_n,
	input  wire        sel,
	input  wire        wr,
	input  wire [7:0]  addr,
	input  wire [31:0] wdata,
	output reg  [31:0] rdata,
	input  wire        scl_i,   // synchronised bus levels
	input  wire        sda_i,
	output wire        scl_o,   // 0 = pull low, 1 = release
	output wire        sda_o,
	output wire        twen_o,
	output wire        irq
);
	localparam ST_IDLE = 3'd0, ST_START = 3'd1, ST_RSTART = 3'd2, ST_STOP = 3'd3,
	           ST_BYTE = 3'd4, ST_HOLD = 3'd5;

	reg [7:0]  twbr, twdr;
	reg [1:0]  twps;
	reg [6:0]  twa, twam;
	reg        twgce;
	reg        twint, twea, twsta, twsto, twen, twie, twwc;
	reg [4:0]  tws;

	reg [2:0]  st, ph;
	reg [13:0] tcnt;
	reg        scl_r, sda_r;        // our drive (1 = released)
	reg        scl_q, sda_q, busy;
	reg        master, slave_sel, tx, mrx, stx, gc, is_addr, addr_ph, rw, cont, pend_addr, ack_out, ack_in, armed;
	reg [3:0]  bitc;
	reg [7:0]  rsh, tsh;

	wire w = sel & wr;
	wire [13:0] half = 14'd8 + ({6'h0, twbr} << {twps, 1'b0});

	wire scl_rise  = scl_i & ~scl_q;
	wire scl_fall  = ~scl_i & scl_q;
	wire start_det = scl_i & scl_q & sda_q & ~sda_i;
	wire stop_det  = scl_i & scl_q & ~sda_q & sda_i;

	wire cr_w  = w && addr[4:2] == 3'd4;
	wire go    = cr_w && wdata[7] && twint;
	wire w_ea  = wdata[6], w_sta = wdata[5], w_sto = wdata[4];
	wire tz    = tcnt == 14'd0;

	wire addr_match = twea && (((rsh[7:1] ^ twa) & ~twam) == 7'h0 || (twgce && rsh[7:1] == 7'h0));

	task set_status(input [7:0] code);
		begin tws <= code[7:3]; twint <= 1'b1; st <= ST_HOLD; end
	endtask

	always @(posedge clk or negedge rst_n) begin
		if (!rst_n) begin
			twbr <= 8'h0; twdr <= 8'hFF; twps <= 2'b00; twa <= 7'h7F; twam <= 7'h0; twgce <= 1'b0;
			twint <= 0; twea <= 0; twsta <= 0; twsto <= 0; twen <= 0; twie <= 0; twwc <= 0;
			tws <= 5'h1F; st <= ST_IDLE; ph <= 3'd0; tcnt <= 14'd0; scl_r <= 1'b1; sda_r <= 1'b1;
			scl_q <= 1'b1; sda_q <= 1'b1; busy <= 1'b0;
			master <= 0; slave_sel <= 0; tx <= 0; mrx <= 0; stx <= 0; gc <= 0; is_addr <= 0;
			addr_ph <= 0; rw <= 0; cont <= 0; pend_addr <= 0; ack_out <= 0; ack_in <= 1'b1; armed <= 0;
			bitc <= 4'd0; rsh <= 8'h0; tsh <= 8'h0;
		end else begin
			scl_q <= scl_i; sda_q <= sda_i;
			if (start_det) busy <= 1'b1;
			if (stop_det)  busy <= 1'b0;
			if (!tz) tcnt <= tcnt - 14'd1;

			// ---- register writes (the state machine below may override) ----
			if (w) case (addr[4:2])
				3'd0: twbr <= wdata[7:0];
				3'd1: twps <= wdata[1:0];
				3'd2: begin twa <= wdata[7:1]; twgce <= wdata[0]; end
				3'd3: if (twint || st == ST_IDLE) begin twdr <= wdata[7:0]; twwc <= 1'b0; end
				      else twwc <= 1'b1;
				3'd4: begin
					twea <= wdata[6]; twsta <= wdata[5]; twsto <= wdata[4];
					twen <= wdata[2]; twie <= wdata[0];
					if (wdata[7]) twint <= 1'b0;
				end
				3'd5: twam <= wdata[7:1];
				default: ;
			endcase

			if (!twen) begin
				st <= ST_IDLE; scl_r <= 1'b1; sda_r <= 1'b1; master <= 0; slave_sel <= 0;
				pend_addr <= 0; twsto <= 1'b0; tws <= 5'h1F;
				if (!(cr_w && wdata[2])) twint <= 1'b0;
			end else case (st)
			// ----------------------------------------------------------------
			ST_IDLE: begin
				scl_r <= 1'b1; sda_r <= 1'b1; master <= 1'b0;
				if (twsto) twsto <= 1'b0;
				if (start_det) begin
					st <= ST_BYTE; bitc <= 4'd0; is_addr <= 1'b1; tx <= 1'b0; ph <= 3'd7; armed <= 1'b0;
				end else if (twsta && !busy && !twint && scl_i && sda_i) begin
					st <= ST_START; ph <= 3'd0; sda_r <= 1'b0; tcnt <= half;
				end
			end
			// ----------------------------------------------------------------
			ST_START: if (tz) case (ph)
				3'd0: begin scl_r <= 1'b0; tcnt <= 14'd4; ph <= 3'd1; end
				default: begin
					master <= 1'b1; addr_ph <= 1'b1; mrx <= 1'b0; slave_sel <= 1'b0;
					set_status(8'h08);
				end
			endcase
			// ----------------------------------------------------------------
			ST_RSTART: case (ph)
				3'd0: if (tz) begin scl_r <= 1'b1; ph <= 3'd1; end
				3'd1: if (scl_i) begin tcnt <= half; ph <= 3'd2; end
				3'd2: if (tz) begin sda_r <= 1'b0; tcnt <= half; ph <= 3'd3; end
				3'd3: if (tz) begin scl_r <= 1'b0; tcnt <= 14'd4; ph <= 3'd4; end
				default: if (tz) begin
					addr_ph <= 1'b1; mrx <= 1'b0;
					set_status(8'h10);
				end
			endcase
			// ----------------------------------------------------------------
			ST_STOP: case (ph)
				3'd0: if (tz) begin scl_r <= 1'b1; ph <= 3'd1; end
				3'd1: if (scl_i) begin tcnt <= half; ph <= 3'd2; end
				3'd2: if (tz) begin sda_r <= 1'b1; tcnt <= half; ph <= 3'd3; end
				default: if (tz) begin master <= 1'b0; twsto <= 1'b0; st <= ST_IDLE; end
			endcase
			// ----------------------------------------------------------------
			ST_BYTE: begin
				// SCL generation: master toggles, slave releases after data setup
				case (ph)
					3'd0: if (tz) begin scl_r <= 1'b1; ph <= 3'd1; end
					3'd1: if (scl_i) begin tcnt <= half; ph <= 3'd2; end
					3'd2: if (tz) begin scl_r <= 1'b0; tcnt <= half; ph <= 3'd0; end
					3'd3: if (tz) begin scl_r <= 1'b1; ph <= 3'd7; end
					default: ;
				endcase

				if (scl_rise) begin
					armed <= 1'b1;
					if (bitc < 4'd8) begin
						rsh <= {rsh[6:0], sda_i};
						if (master && tx && sda_r && !sda_i) begin
							// arbitration lost
							master <= 1'b0; scl_r <= 1'b1; sda_r <= 1'b1;
							set_status(8'h38);
						end
					end else ack_in <= sda_i;
				end

				// a falling edge only ends a bit once that bit's rising edge was seen
				if (scl_fall && armed) begin
					if (bitc < 4'd7) begin
						bitc <= bitc + 4'd1;
						if (tx) begin sda_r <= tsh[6]; tsh <= {tsh[6:0], 1'b0}; end
					end else if (bitc == 4'd7) begin
						bitc <= 4'd8;
						if (tx) sda_r <= 1'b1;
						else if (is_addr) begin
							if (addr_match) begin
								sda_r <= 1'b0; slave_sel <= 1'b1; gc <= rsh[7:1] == 7'h0;
							end else begin
								is_addr <= 1'b0; st <= ST_IDLE;
							end
						end else sda_r <= ~ack_out;
					end else begin
						// byte + ack complete: hold SCL low and report
						sda_r <= 1'b1; scl_r <= 1'b0; ph <= 3'd7;
						if (master) begin
							if (tx) begin
								addr_ph <= 1'b0;
								if (addr_ph) begin
									mrx <= rw;
									set_status(rw ? (ack_in ? 8'h48 : 8'h40) : (ack_in ? 8'h20 : 8'h18));
								end else set_status(ack_in ? 8'h30 : 8'h28);
							end else begin
								twdr <= rsh;
								set_status(ack_out ? 8'h50 : 8'h58);
							end
						end else if (is_addr) begin
							is_addr <= 1'b0; stx <= rsh[0]; twdr <= rsh; cont <= 1'b1;
							set_status(rsh[0] ? 8'hA8 : (gc ? 8'h70 : 8'h60));
						end else if (stx) begin
							cont <= ~ack_in & ack_out;
							set_status(ack_in ? 8'hC0 : (ack_out ? 8'hB8 : 8'hC8));
						end else begin
							twdr <= rsh; cont <= ack_out;
							set_status(gc ? (ack_out ? 8'h90 : 8'h98) : (ack_out ? 8'h80 : 8'h88));
						end
					end
				end

				// START / STOP seen while acting as a slave
				if (!master && (start_det || stop_det)) begin
					if (slave_sel) begin
						slave_sel <= 1'b0; sda_r <= 1'b1;
						pend_addr <= start_det;
						scl_r <= ~start_det;      // stretch after a repeated START
						set_status(8'hA0);
					end else if (start_det) begin
						bitc <= 4'd0; is_addr <= 1'b1; tx <= 1'b0; armed <= 1'b0;
					end else st <= ST_IDLE;
				end
			end
			// ----------------------------------------------------------------
			ST_HOLD: if (go) begin
				ack_out <= w_ea; armed <= 1'b0;
				if (master) begin
					if (w_sto) begin
						st <= ST_STOP; ph <= 3'd0; sda_r <= 1'b0; tcnt <= half;
					end else if (w_sta) begin
						st <= ST_RSTART; ph <= 3'd0; sda_r <= 1'b1; tcnt <= half;
					end else begin
						st <= ST_BYTE; ph <= 3'd0; tcnt <= half; bitc <= 4'd0; is_addr <= 1'b0;
						tx <= ~mrx; tsh <= twdr; rw <= twdr[0];
						sda_r <= mrx ? 1'b1 : twdr[7];
					end
				end else if (slave_sel && cont && !w_sto) begin
					st <= ST_BYTE; ph <= 3'd3; tcnt <= 14'd4; bitc <= 4'd0; is_addr <= 1'b0;
					tx <= stx; tsh <= twdr;
					sda_r <= stx ? twdr[7] : 1'b1;
				end else if (pend_addr && !w_sto) begin
					pend_addr <= 1'b0;
					st <= ST_BYTE; ph <= 3'd7; bitc <= 4'd0; is_addr <= 1'b1; tx <= 1'b0;
					scl_r <= 1'b1; sda_r <= 1'b1;
				end else begin
					slave_sel <= 1'b0; pend_addr <= 1'b0;
					st <= ST_IDLE; scl_r <= 1'b1; sda_r <= 1'b1;
				end
			end
			default: st <= ST_IDLE;
			endcase
		end
	end

	always @(*) begin
		rdata = 32'h0;
		if (sel) case (addr[4:2])
			3'd0: rdata = {24'h0, twbr};
			3'd1: rdata = {24'h0, tws, 1'b0, twps};
			3'd2: rdata = {24'h0, twa, twgce};
			3'd3: rdata = {24'h0, twdr};
			3'd4: rdata = {24'h0, twint, twea, twsta, twsto, twwc, twen, 1'b0, twie};
			3'd5: rdata = {24'h0, twam, 1'b0};
			default: ;
		endcase
	end

	assign scl_o  = scl_r;
	assign sda_o  = sda_r;
	assign twen_o = twen;
	assign irq    = twint & twie;
endmodule
`default_nettype wire
