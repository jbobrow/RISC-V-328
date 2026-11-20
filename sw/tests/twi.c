/* TWI0 master <-> TWI1 slave: write, repeated start, read, NACK on wrong address.
 * Wiring 3: PC4-PE0 SDA, PC5-PE1 SCL with pull-ups. The slave runs from its interrupt. */
#include "test.h"
static volatile uint8_t s_log[16], s_n, s_reg[4] = { 0x11, 0x22, 0x33, 0x44 }, s_ptr, s_stat[16];
static void twi1_isr(void)
{
	uint32_t st = TWI1->SR & 0xF8;
	if (s_n < 16) s_stat[s_n] = st;
	switch (st) {
	case 0x60: s_ptr = 0xFF; break;                         /* SLA+W */
	case 0x80:                                              /* data */
		if (s_ptr == 0xFF) s_ptr = TWI1->DR & 3;
		else s_reg[s_ptr++ & 3] = TWI1->DR;
		break;
	case 0xA8: case 0xB8: TWI1->DR = s_reg[s_ptr++ & 3]; break;
	default: break;                                         /* A0, C0, C8 */
	}
	if (s_n < 16) s_n++;
	TWI1->CR = TWINT | TWEA | TWEN | TWIE;
}
static uint32_t m_op(uint32_t cr) { TWI0->CR = TWINT | TWEN | cr; while (!(TWI0->CR & TWINT)) ; return TWI0->SR & 0xF8; }
static void m_stop(void) { TWI0->CR = TWINT | TWEN | TWSTO; while (TWI0->CR & TWSTO) ; }
int main(void)
{
	irq_attach(IRQ_TWI1, twi1_isr);
	sei();
	TWI1->AR = 0x2A << 1;
	TWI1->CR = TWEA | TWEN | TWIE;
	TWI0->BR = 4;                                           /* fclk / 24 */

	/* address nobody answers */
	CHECK(1, m_op(TWSTA) == 0x08);
	TWI0->DR = 0x33 << 1;
	CHECK(2, m_op(0) == 0x20);
	m_stop();

	/* write register pointer 1, then two data bytes */
	CHECK(3, m_op(TWSTA) == 0x08);
	TWI0->DR = 0x2A << 1;      CHECK(4, m_op(0) == 0x18);
	TWI0->DR = 0x01;           CHECK(5, m_op(0) == 0x28);
	TWI0->DR = 0xAB;           CHECK(6, m_op(0) == 0x28);
	TWI0->DR = 0xCD;           CHECK(7, m_op(0) == 0x28);
	m_stop();
	delay(40);
	CHECK(8, s_reg[1] == 0xAB && s_reg[2] == 0xCD);

	/* set pointer 0, repeated start, read three bytes (ACK, ACK, NACK) */
	CHECK(9, m_op(TWSTA) == 0x08);
	TWI0->DR = 0x2A << 1;      CHECK(10, m_op(0) == 0x18);
	TWI0->DR = 0x00;           CHECK(11, m_op(0) == 0x28);
	CHECK(12, m_op(TWSTA) == 0x10);
	TWI0->DR = (0x2A << 1) | 1; CHECK(13, m_op(0) == 0x40);
	CHECK(14, m_op(TWEA) == 0x50 && TWI0->DR == 0x11);
	CHECK(15, m_op(TWEA) == 0x50 && TWI0->DR == 0xAB);
	CHECK(16, m_op(0) == 0x58 && TWI0->DR == 0xCD);
	m_stop();
	delay(40);
	/* slave saw: 60 80 80 80 A0 | 60 80 A0 A8 B8 B8 C0 */
	CHECK(17, s_stat[0] == 0x60 && s_stat[4] == 0xA0 && s_stat[8] == 0xA8 && s_stat[11] == 0xC0);
	CHECK(18, s_n == 12);
	PASS();
}
