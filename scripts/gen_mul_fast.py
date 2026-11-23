#!/usr/bin/env python3
"""Gate-level netlist of the processor's fast multiplier with a Kogge-Stone final adder.

    source scripts/env (or the Nix shell);  python3 scripts/gen_mul_fast.py
    -> rtl/tech/hazard3_mul_fast_gf180.v

The flow's Yosys maps the multiplier through Booth encoding, which ends in a slow final adder; without
Booth it is an array whose final adder ripples. Alone, at the slow corner and without wires, the
multiplier (MUL_FAST and MULH_FAST, registers to result) takes 53.3 ns with Booth, 45.1 ns without, and
35.2 ns with Yosys's Kogge-Stone carry-lookahead in place of the ripple adders (docs/layout_results.md).
The flow cannot choose the adder for one module, so this script synthesises the multiplier on its own
with that choice and writes the result as a module the flow reads in place of the RTL (VERILOG_FILES in
full_1x1.yaml, scripts/gen_floorplan_1x1.py --mulks). Standard cells only: the flow's later steps size
and buffer it like any other logic.

The module keeps the RTL's parameter list (hazard3_config.vh), so the processor's instantiation is
unchanged; the netlist is built for MUL_FAST = 1, MULH_FAST = 1, MUL_FASTER = 0 and stops the build
otherwise. A random-vector comparison against the RTL runs at the end (iverilog, the PDK's cell models).
"""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HDL = os.path.join(ROOT, "vendor", "hazard3", "hdl")
SRC = os.path.join(HDL, "arith", "hazard3_mul_fast.v")
OUT = os.path.join(ROOT, "rtl", "tech", "hazard3_mul_fast_gf180.v")
PDK = os.environ.get("PDK_DIR") or os.path.join(os.environ.get("PDK_ROOT", "/home/claude/pdk"), "gf180mcuD")
SC = os.path.join(PDK, "libs.ref", "gf180mcu_fd_sc_mcu9t5v0")
LIB = os.path.join(SC, "lib", "gf180mcu_fd_sc_mcu9t5v0__ss_125C_4v50.lib")
EXCLUDE = os.path.join(PDK, "libs.tech", "librelane", "gf180mcu_fd_sc_mcu9t5v0", "synth_exclude.cells")

YS = """
read_verilog -I{hdl} {src}
chparam -set MUL_FAST 1 -set MULH_FAST 1 -set MUL_FASTER 0 hazard3_mul_fast
hierarchy -check -top hazard3_mul_fast
rename -top hazard3_mul_fast
proc; flatten; opt_expr; opt_clean; opt -nodffe -nosdff; opt; wreduce; peepopt; opt_clean
alumacc
share; opt; opt -fast -full; memory_map; opt -full
techmap -map +/techmap.v -map +/choices/kogge-stone.v
opt -fast; opt -fast
dfflibmap -liberty {lib} {dont}
abc -D 50000 -liberty {lib} {dont}
opt_clean -purge
hilomap -hicell gf180mcu_fd_sc_mcu9t5v0__tieh Z -locell gf180mcu_fd_sc_mcu9t5v0__tiel ZN
stat -liberty {lib}
write_verilog -noattr -noexpr {out}
"""

TB = """
`timescale 1ns/1ps
module tb;
  reg clk = 0, rst_n = 0, op_vld = 0;
  reg [2:0] op; reg [31:0] a, b;
  wire [31:0] r_ref, r_gl; wire v_ref, v_gl;
  ref_mul #(.MUL_FAST(1), .MULH_FAST(1)) u_ref (.clk(clk), .rst_n(rst_n), .op(op), .op_vld(op_vld), .op_a(a), .op_b(b), .result(r_ref), .result_vld(v_ref));
  hazard3_mul_fast #(.MUL_FAST(1), .MULH_FAST(1)) u_gl (.clk(clk), .rst_n(rst_n), .op(op), .op_vld(op_vld), .op_a(a), .op_b(b), .result(r_gl), .result_vld(v_gl));
  integer i, bad = 0;
  initial begin
    #5 rst_n = 1;
    for (i = 0; i < 20000; i = i + 1) begin
      op = $random & 3;                     // M_OP_MUL..M_OP_MULHU are 0..3 in hazard3_ops.vh
      case (i % 5) 0: a = $random; 1: a = 32'h80000000; 2: a = 32'hffffffff; default: a = $random; endcase
      case (i % 7) 0: b = $random; 1: b = 32'h7fffffff; 2: b = 32'hffffffff; default: b = $random; endcase
      op_vld = 1; #5 clk = 1; #5 clk = 0; op_vld = 0; #40;
      if (r_ref !== r_gl) begin bad = bad + 1; if (bad < 5) $display("MISMATCH op %d a %h b %h ref %h gl %h", op, a, b, r_ref, r_gl); end
    end
    $display("compared %0d products, %0d mismatches", i, bad);
    $finish;
  end
endmodule
"""


def main():
    dont = ""
    if os.path.exists(EXCLUDE):
        dont = " ".join("-dont_use %s" % c.strip() for c in open(EXCLUDE) if c.strip())
    with tempfile.TemporaryDirectory() as d:
        raw = os.path.join(d, "mul.v")
        ys = os.path.join(d, "mul.ys")
        open(ys, "w").write(YS.format(hdl=HDL, src=SRC, lib=LIB, dont=dont, out=raw))
        subprocess.run(["yosys", "-q", "-l", os.path.join(d, "yosys.log"), ys], check=True)
        log = open(os.path.join(d, "yosys.log")).read()
        area = re.findall(r"Chip area for module .*: ([0-9.]+)", log)
        net = open(raw).read()
        # keep the RTL's parameter list so that the processor's instantiation (all of hazard3_config_inst.vh)
        # still elaborates; the body is fixed for the parameters above
        m = re.search(r"module hazard3_mul_fast\(([^)]*)\);", net)
        head = ("module hazard3_mul_fast #(\n`include \"hazard3_config.vh\"\n,\n`include \"hazard3_width_const.vh\"\n) (%s);\n"
                "generate if (!MUL_FAST || !MULH_FAST || MUL_FASTER) begin: wrong_parameters\n"
                "\tinitial $fatal(\"%%m: this netlist is built for MUL_FAST = 1, MULH_FAST = 1, MUL_FASTER = 0\");\n"
                "end endgenerate\n" % m.group(1))
        net = net[:m.start()] + head + net[m.end():]
        net = net.replace("wire signed", "wire")
        text = ("// Generated by scripts/gen_mul_fast.py from vendor/hazard3/hdl/arith/hazard3_mul_fast.v. Do not edit.\n"
                "// The processor's fast multiplier (MUL_FAST, MULH_FAST) as GF180MCU 9-track standard cells, with a\n"
                "// Kogge-Stone final adder. Area %s um2.\n" % (area[-1] if area else "?") + net)
        # check against the RTL before writing
        refsrc = open(SRC).read().replace("module hazard3_mul_fast", "module ref_mul")
        open(os.path.join(d, "ref.v"), "w").write(refsrc)
        open(os.path.join(d, "gl.v"), "w").write(text)
        open(os.path.join(d, "tb.v"), "w").write(TB)
        sim = os.path.join(d, "sim")
        subprocess.run(["iverilog", "-g2012", "-o", sim, "-I", HDL, "-DFUNCTIONAL", "-DUNIT_DELAY=#0",
                        os.path.join(d, "tb.v"), os.path.join(d, "ref.v"), os.path.join(d, "gl.v"),
                        os.path.join(SC, "verilog", "primitives.v"), os.path.join(SC, "verilog", "gf180mcu_fd_sc_mcu9t5v0.v")],
                       check=True)
        out = subprocess.run(["vvp", "-n", sim], capture_output=True, text=True).stdout
        res = re.search(r"compared (\d+) products, (\d+) mismatches", out)
        print(res.group(0) if res else "no simulation result")
        if not res or res.group(2) != "0":
            print(out)
            sys.exit("netlist does not match the RTL; not written")
        open(OUT, "w").write(text)
        print("wrote %s (area %s um2)" % (OUT, area[-1] if area else "?"))


if __name__ == "__main__":
    main()
