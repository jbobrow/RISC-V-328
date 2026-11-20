// Clock driver for tb/bench_top.v (Verilator).
#include "Vbench_top.h"
#include "verilated.h"
int main(int argc, char **argv)
{
	Verilated::commandArgs(argc, argv);
	Vbench_top *top = new Vbench_top;
	top->clk = 0;
	top->eval();
	while (!Verilated::gotFinish()) {
		top->clk = 1; top->eval();
		top->clk = 0; top->eval();
	}
	top->final();
	delete top;
	return 0;
}
