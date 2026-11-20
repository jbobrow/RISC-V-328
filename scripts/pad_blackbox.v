// Port-only declarations of the GF180MCU I/O cells and SRAM macro, for
// elaboration checks outside the PDK (the layout flow uses the PDK views).
(* blackbox *) module gf180mcu_fd_io__bi_24t (input CS, SL, IE, OE, PU, PD, A, inout PAD, output Y); endmodule
(* blackbox *) module gf180mcu_fd_io__in_c (input PU, PD, inout PAD, output Y); endmodule
(* blackbox *) module gf180mcu_fd_io__in_s (input PU, PD, inout PAD, output Y); endmodule
(* blackbox *) module gf180mcu_fd_io__asig_5p0 (inout ASIG5V); endmodule
(* blackbox *) module gf180mcu_fd_io__dvdd (); endmodule
(* blackbox *) module gf180mcu_fd_io__dvss (); endmodule
(* blackbox *) module gf180mcu_fd_ip_sram__sram512x8m8wm1 (input CLK, CEN, GWEN, input [7:0] WEN, input [8:0] A,
	input [7:0] D, output [7:0] Q); endmodule
