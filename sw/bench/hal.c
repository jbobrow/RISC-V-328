/* Benchmark runtime on the RV328: real peripherals and interrupts. */
#include "rv328.h"
#include "hal.h"

void hal_mark(unsigned n, uint32_t v) { GPIOR2 = v; GPIOR1 = 0x5000u | n; }
void hal_done(void) { GPIOR0 = 0x600D600Du; for (;;) ; }

/* ---- 8-bit timer overflow tick, as the Arduino core does it (clk/64/256) ---- */
#define TICK_US   ((64u * 256u) / (F_CPU / 1000000u))      /* 819 us */
static volatile uint32_t t0_ms;
static volatile uint16_t t0_frac;
HAL_ISR static void tc0_isr(void)
{
	uint32_t m = t0_ms;
	uint16_t f = t0_frac + (TICK_US % 1000u);
	m += TICK_US / 1000u;
	if (f >= 1000u) { f -= 1000u; m++; }
	t0_frac = f; t0_ms = m;
	TC0->IFR = TC_OVF;
}
uint32_t millis(void)
{
	uint32_t m;
	cli(); m = t0_ms; sei();
	return m;
}

/* ---- serial port with interrupt-driven transmit ring, as HardwareSerial ---- */
#define TXBUF 64u
static volatile uint8_t txb[TXBUF];
static volatile uint8_t tx_h, tx_t;
HAL_ISR static void u0_isr(void)
{
	if ((USART0->CR & UDRIE) && (USART0->SR & UDRE)) {
		if (tx_h != tx_t) { USART0->DATA = txb[tx_t]; tx_t = (tx_t + 1u) % TXBUF; }
		if (tx_h == tx_t) USART0->CR &= ~UDRIE;
	}
}
void serial_begin(uint32_t baud)
{
	USART0->FMT = USART_8N1;
	USART0->BRR = (F_CPU + baud * 8u) / (baud * 16u) - 1u;
	USART0->CR = TXEN;
	irq_attach(IRQ_USART0, u0_isr);
}
unsigned serial_tx_free(void) { return (TXBUF - 1u) - ((tx_h - tx_t) % TXBUF); }
void serial_write(uint8_t c)
{
	uint8_t n = (tx_h + 1u) % TXBUF;
	while (n == tx_t) ;                    /* ring full: wait for the interrupt to drain it */
	txb[tx_h] = c; tx_h = n;
	cli(); USART0->CR |= UDRIE; sei();
}
void serial_print(const char *s) { while (*s) serial_write((uint8_t)*s++); }

/* ---- second serial port: receive interrupt hands each byte to the program ---- */
static void (*link_rx)(uint8_t, unsigned);
HAL_ISR static void u1_isr(void)
{
	uint32_t s = USART1->SR;
	uint8_t d = (uint8_t)USART1->DATA;
	link_rx(d, (s & DOR) != 0u);
}
void link_begin(void (*rx)(uint8_t, unsigned))
{
	link_rx = rx;
	PORTB |= 0x10u;                        /* pull-up on RXD1 */
	USART1->FMT = USART_8N1; USART1->BRR = USART0->BRR;
	USART1->CR = RXEN | RXCIE;
	irq_attach(IRQ_USART1, u1_isr);
}

/* ---- ADC, polled, prescaler 128 as analogRead() ---- */
void hal_set_input(unsigned ch, unsigned mv) { GPIOR2 = mv; GPIOR1 = 0x2000u | ch; GPIOR1 = 0; }
uint16_t analog_read(unsigned ch)
{
	ADMUX = REFS_AVCC | ch;
	ADCSRA = ADEN | ADSC | ADIF | 7u;
	while (ADCSRA & ADSC) ;
	return (uint16_t)ADC;
}

/* ---- 10-bit fast PWM on OC1A, SPI master at clock/2, pins ---- */
void pwm_write(unsigned duty) { TC1->OCRA = duty; }
void spi_begin(void)
{
	DDRB |= 0x2Cu; PORTB |= 0x04u;         /* SCK, MOSI, display CS (PB2) */
	DDRC |= 0x01u; PORTC |= 0x01u;         /* card CS (PC0) */
	SPI0->CR = SPE | MSTR | SPI2X;
}
void spi_write(uint8_t c)
{
	SPI0->DATA = c;
	while (!(SPI0->SR & SPIF)) ;
	(void)SPI0->DATA;
}
void pin_cs(unsigned which, unsigned level)
{
	if (which == 0u) { if (level) PORTB |= 0x04u; else PORTB &= ~0x04u; }
	else             { if (level) PORTC |= 0x01u; else PORTC &= ~0x01u; }
}
unsigned buttons_raw(void) { return (PIND >> 5) & 7u; }
void led_write(unsigned on) { if (on) PORTB |= 0x20u; else PORTB &= ~0x20u; }

HAL_ISR static void int0_isr(void) { PINB = 1u; EIFR = 1u; }
void probe_begin(void)
{
	DDRB |= 1u;
	EICRA = 1u;                            /* any edge */
	EIFR = 1u; EIMSK = 1u;
	irq_attach(IRQ_INT0, int0_isr);
}

void hal_init(void)
{
	NVMCFG = 0;                            /* serial memory clock = system clock / 2 */
	TC0->CR = TC_CS(4);                    /* /64, normal mode */
	TC0->IER = TC_OVF;
	irq_attach(IRQ_TC0, tc0_isr);
	DDRB |= 0x22u;                         /* OC1A, LED */
	TC1->CR = TC_CS(1) | TC_WGM_FAST | TC_TOP_10BIT | TC_COMA(2);
	sei();
}
