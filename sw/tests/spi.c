/* SPI0 master <-> SPI1 slave in all four clock modes, both bit orders.
 * Wiring 2: PB3-PE3 MOSI, PB4-PC0 MISO, PB5-PC1 SCK, PB2-PE2 SS. */
#include "test.h"
static volatile uint32_t s_rx, s_n;
static void spi1_isr(void) { s_rx = SPI1->DATA; s_n++; }
static uint32_t xfer(uint32_t v) { SPI0->DATA = v; while (!(SPI0->SR & SPIF)) ; return SPI0->DATA; }
int main(void)
{
	irq_attach(IRQ_SPI1, spi1_isr);
	sei();
	DDRB = (1 << 2) | (1 << 3) | (1 << 5);     /* SS, MOSI, SCK outputs */
	DDRC = 1 << 0;                             /* slave MISO output */
	PORTB = 1 << 2;
	for (uint32_t mode = 0; mode < 8; mode++) {
		uint32_t cfg = ((mode & 1) ? CPHA : 0) | ((mode & 2) ? CPOL : 0) | ((mode & 4) ? DORD : 0);
		SPI0->CR = 0; SPI1->CR = 0;
		SPI1->CR = SPE | SPIE | cfg;
		SPI0->CR = SPE | MSTR | cfg | 1;       /* fclk/16 */
		delay(4);
		PORTB &= ~(1u << 2);
		SPI1->DATA = 0xC3 ^ mode;              /* slave reply to the first byte */
		s_n = 0;
		uint32_t r0 = xfer(0x5A + mode);
		while (s_n < 1) ;
		CHECK(10 + mode, s_rx == 0x5A + mode);
		CHECK(20 + mode, r0 == (0xC3 ^ mode));
		SPI1->DATA = 0x0F;
		uint32_t r1 = xfer(0x81);
		while (s_n < 2) ;
		CHECK(30 + mode, s_rx == 0x81 && r1 == 0x0F);
		PORTB |= 1 << 2;
	}
	/* fastest master clock (fclk/2) loop-back onto itself is not possible, so
	 * just check the write-collision flag */
	SPI0->CR = SPE | MSTR | 3;
	SPI0->DATA = 1; SPI0->DATA = 2;
	CHECK(40, SPI0->SR & WCOL);
	PASS();
}
