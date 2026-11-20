/* USART0 <-> USART1 loop-back in several frame formats, with interrupts.
 * Wiring 1: TXD0(PD1)->RXD1(PB4), TXD1(PB3)->RXD0(PD0). */
#include "test.h"
static volatile uint32_t rx1_n, rx1[8];
static void u1_isr(void) { uint32_t s = USART1->SR; uint32_t d = USART1->DATA; if (rx1_n < 8) rx1[rx1_n++] = d | (s << 16); }
static void xfer(uint32_t fmt, uint32_t cr, uint32_t brr, uint32_t a, uint32_t b)
{
	USART0->FMT = fmt; USART1->FMT = fmt;
	USART0->BRR = brr; USART1->BRR = brr;
	USART0->CR = RXEN | TXEN | cr; USART1->CR = RXEN | TXEN | RXCIE | cr;
	rx1_n = 0;
	USART0->DATA = a;
	while (!(USART0->SR & UDRE)) ;
	USART0->DATA = b;                 /* back-to-back frames */
	while (rx1_n < 2) ;
	while (!(USART0->SR & TXC)) ;
	USART0->SR = TXC;
}
int main(void)
{
	irq_attach(IRQ_USART1, u1_isr);
	sei();
	/* frames must be longer than the cold-cache interrupt latency (see docs) */
	NVMCFG = 0;
	xfer(USART_8N1, 0, 31, 0xA5, 0x3C);
	CHECK(1, (rx1[0] & 0x1FF) == 0xA5 && (rx1[1] & 0x1FF) == 0x3C);
	CHECK(2, !((rx1[0] | rx1[1]) & ((FE | DOR | UPE) << 16)));
	xfer(USART_BITS(7) | USART_EVEN | USART_2STOP, U2X, 63, 0x55, 0x2A);
	CHECK(3, (rx1[0] & 0x1FF) == 0x55 && (rx1[1] & 0x1FF) == 0x2A);
	CHECK(4, !((rx1[0] | rx1[1]) & ((FE | UPE) << 16)));
	xfer(USART_BITS(9) | USART_ODD, 0, 31, 0x1A5, 0x05A);
	CHECK(5, (rx1[0] & 0x1FF) == 0x1A5 && (rx1[1] & 0x1FF) == 0x05A);

	/* parity mismatch is flagged: sender even, receiver odd */
	USART0->FMT = USART_8N1 | USART_EVEN; USART1->FMT = USART_8N1 | USART_ODD;
	rx1_n = 0; USART0->DATA = 0x42;
	while (rx1_n < 1) ;
	CHECK(6, rx1[0] & (UPE << 16));

	/* reverse direction, polled, and overrun detection */
	USART1->CR = RXEN | TXEN; USART0->FMT = USART_8N1; USART1->FMT = USART_8N1;
	USART1->DATA = 0x77;
	while (!(USART0->SR & RXC)) ;
	USART1->DATA = 0x88;
	delay(2500);                      /* well past the end of the second frame */
	CHECK(7, USART0->SR & DOR);
	CHECK(8, USART0->DATA == 0x77);
	PASS();
}
