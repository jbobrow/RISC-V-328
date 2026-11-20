/* Core sanity: RAM byte/half/word access, .data/.bss init, GPIO, multiply/divide,
 * pin-change interrupt, external interrupt, reset-cause flags. */
#include "test.h"

static volatile uint32_t pc_hits, int_hits;
static uint32_t init_data = 0x12345678;
static uint8_t  buf[16];

static void pcint2_isr(void) { pc_hits++; PCIFR = 1u << 2; }
static void int0_isr(void)   { int_hits++; EIFR = 1; }

int main(void)
{
	volatile uint8_t *b = buf;
	volatile uint16_t *h = (volatile uint16_t *)buf;
	volatile uint32_t *w = (volatile uint32_t *)buf;
	volatile uint32_t x = 123456, y = 789;

	CHECK(1, CHIPID == 0x52333238u);
	CHECK(2, MCUSR & PORF);
	MCUSR = 0x3f;
	CHECK(3, MCUSR == 0);
	CHECK(4, init_data == 0x12345678);
	w[0] = 0xAABBCCDD; b[1] = 0x11; h[1] = 0x2233;
	CHECK(5, w[0] == 0x223311DD);
	b[4] = 1; b[5] = 2; b[6] = 3; b[7] = 4;
	CHECK(6, w[1] == 0x04030201 && h[2] == 0x0201);
	CHECK(7, x * y == 97406784u && x / y == 156 && x % y == 372);

	/* GPIO: outputs read back through the pads, PIN write toggles */
	DDRB = 0x0F; PORTB = 0x05;
	CHECK(8, (PINB & 0x0F) == 0x05);
	PINB = 0x03;
	CHECK(9, (PORTB & 0x0F) == 0x06 && (PINB & 0x0F) == 0x06);
	/* pull-up on an input reads high, then driven low by the testbench */
	PORTD = 0x80;
	for (volatile int i = 0; i < 4; i++) ;
	CHECK(10, PIND & 0x80);

	/* pin-change interrupt on PD7, external interrupt INT0 (PD2) falling edge */
	PORTD |= 0x04;
	PCMSK2 = 0x80; PCICR = 1u << 2; PCIFR = 0xF;
	EICRA = 2; EIFR = 3; EIMSK = 1;
	irq_attach(IRQ_PCINT2, pcint2_isr);
	irq_attach(IRQ_INT0, int0_isr);
	sei();
	TBHOOK(0x1007);                 /* testbench pulls PD7 low */
	for (volatile int i = 0; i < 40 && !pc_hits; i++) ;
	CHECK(11, pc_hits == 1 && !(PIND & 0x80));
	TBHOOK(0x1002);                 /* PD2 low: INT0 */
	for (volatile int i = 0; i < 40 && !int_hits; i++) ;
	CHECK(12, int_hits == 1);
	TBHOOK(0x1107);
	for (volatile int i = 0; i < 40 && pc_hits < 2; i++) ;
	CHECK(13, pc_hits == 2 && (PIND & 0x80));

	GPIOR0 = 0x600D600D;
	for (;;) ;
}
