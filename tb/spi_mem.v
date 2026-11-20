// Behavioural model of the in-package serial memory (25-series SPI EEPROM or
// NOR flash): READ 03h, WRITE/PAGE PROGRAM 02h, WREN 06h, RDSR 05h, SECTOR
// ERASE 20h. NOR=0 models an EEPROM (bytes are overwritten), NOR=1 a flash
// (program can only clear bits, erase sets 4 KB to FFh).
`timescale 1ns/1ps
module spi_mem #(
	parameter SIZE = 131072,
	parameter NOR  = 0,
	parameter real TW_NS = 40000.0
) (
	input  wire csn,
	input  wire sck,
	input  wire mosi,
	output wire miso
);
	reg [7:0] mem [0:SIZE-1];
	reg [7:0] cmd, sh, dout;
	reg [23:0] addr;
	reg [7:0] wbuf [0:255];
	integer   bitc, bytec, nw, nwq, i;
	reg [7:0] wq [0:255];
	reg       wel, wip, oe;
	reg [23:0] waddr;
	initial begin
		for (i = 0; i < SIZE; i = i + 1) mem[i] = 8'hFF;
		wel = 0; wip = 0; oe = 0; bitc = 0; bytec = 0; nw = 0; dout = 8'h00;
	end
	assign miso = (!csn && oe) ? dout[7] : 1'bz;

	always @(negedge csn) begin bitc = 0; bytec = 0; nw = 0; oe = 0; end

	always @(posedge sck) if (!csn) begin
		sh = {sh[6:0], mosi};
		bitc = bitc + 1;
		if (bitc == 8) begin
			bitc = 0;
			if (bytec == 0) cmd = sh;
			else if (bytec <= 3 && (cmd == 8'h03 || cmd == 8'h02 || cmd == 8'h20))
				addr = {addr[15:0], sh};
			else if (cmd == 8'h02 && nw < 256) begin wbuf[nw] = sh; nw = nw + 1; end
			bytec = bytec + 1;
		end
	end

	always @(negedge sck) if (!csn) begin
		if (bitc == 0 && bytec >= 1) begin
			if (cmd == 8'h03 && bytec >= 4) begin
				dout = wip ? 8'hxx : mem[(addr + bytec - 4) % SIZE]; oe = 1;
			end else if (cmd == 8'h05) begin
				dout = {6'h0, wel, wip}; oe = 1;
			end
		end else dout = {dout[6:0], 1'b0};
	end

	always @(posedge csn) begin
		if (bitc == 0 && !wip) begin
			if (bytec == 1 && cmd == 8'h06) wel = 1;
			else if (cmd == 8'h02 && bytec > 4 && wel) begin
				waddr = addr; wip = 1; nwq = nw;
				for (i = 0; i < nwq; i = i + 1) wq[i] = wbuf[i];
				#(TW_NS);
				for (i = 0; i < nwq; i = i + 1)
					if (NOR) mem[{waddr[23:8], waddr[7:0] + i[7:0]} % SIZE] =
						mem[{waddr[23:8], waddr[7:0] + i[7:0]} % SIZE] & wq[i];
					else mem[{waddr[23:8], waddr[7:0] + i[7:0]} % SIZE] = wq[i];
				wip = 0; wel = 0;
			end else if (cmd == 8'h20 && bytec == 4 && wel) begin
				waddr = addr; wip = 1;
				#(TW_NS);
				for (i = 0; i < 4096; i = i + 1) mem[({waddr[23:12], 12'h0} + i) % SIZE] = 8'hFF;
				wip = 0; wel = 0;
			end
		end
	end
endmodule
