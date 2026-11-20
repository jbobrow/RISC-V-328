/* Runs after the testbench has programmed a marker through the in-system
 * programming pass-through (RESET held low, SPI on PB2..PB5). */
#include "test.h"
int main(void)
{
	CHECK(1, REG32(0x7F00) == 0x52563332u);
	CHECK(2, MCUSR & (PORF | EXTRF));
	PASS();
}
