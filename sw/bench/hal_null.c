/* Benchmark runtime without peripherals: every I/O call returns at once and
 * time is a call counter, so a run measures only the processor's own work and
 * does exactly the same work on every target. Marks and the end of the run
 * are target-specific (below). */
#include "hal.h"

static uint32_t now;
static uint16_t in_mv[8];
static void (*link_rx)(uint8_t, unsigned);
uint32_t millis(void) { return now++; }
void serial_begin(uint32_t baud) { (void)baud; }
void serial_write(uint8_t c) { if (link_rx) link_rx(c, 0); }       /* the wire to the second port */
void serial_print(const char *s) { while (*s) serial_write((uint8_t)*s++); }
/* room for a frame on every 16th call, so the receiver keeps up without a clock */
unsigned serial_tx_free(void) { static uint8_t k; return (++k & 15u) ? 0u : 63u; }
void link_begin(void (*rx)(uint8_t, unsigned)) { link_rx = rx; }
void hal_set_input(unsigned ch, unsigned mv) { in_mv[ch & 7u] = (uint16_t)mv; }
uint16_t analog_read(unsigned ch) { return (uint16_t)((uint32_t)in_mv[ch & 7u] * 1024u / 5000u); }
void pwm_write(unsigned duty) { (void)duty; }
void spi_begin(void) { }
void spi_write(uint8_t c) { (void)c; }
void pin_cs(unsigned which, unsigned level) { (void)which; (void)level; }
unsigned buttons_raw(void) { return 0; }
void led_write(unsigned on) { (void)on; }
void probe_begin(void) { }

#if defined(__AVR__)
/* ATmega328P in simavr: clocks from timer 1, text through the simulator's console register */
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/sleep.h>
#include <stdlib.h>
#include <simavr/avr/avr_mcu_section.h>
AVR_MCU(F_CPU, "atmega328p");
AVR_MCU_SIMAVR_CONSOLE(&GPIOR0);
static volatile uint16_t t1_hi;
ISR(TIMER1_OVF_vect) { t1_hi++; }
static void put(const char *s) { while (*s) GPIOR0 = (uint8_t)*s++; }
void hal_init(void) { TCCR1B = 1; TIMSK1 = 1; sei(); }
void hal_mark(unsigned n, uint32_t v)
{
	char b[12];
	uint8_t s = SREG; cli();
	uint16_t lo = TCNT1, hi = t1_hi;
	if ((TIFR1 & 1) && lo < 0x8000u) hi++;
	SREG = s;
	put("MARK "); put(utoa(n, b, 10)); put(" cyc="); put(ultoa(((uint32_t)hi << 16) | lo, b, 10));
	put(" val="); put(ultoa(v, b, 10)); put("\r");
}
void hal_done(void) { put("DONE\r"); cli(); sleep_enable(); sleep_cpu(); for (;;) ; }
#else
#include "rv328.h"
void hal_init(void) { NVMCFG = 0; }
void hal_mark(unsigned n, uint32_t v) { GPIOR2 = v; GPIOR1 = 0x5000u | n; }
void hal_done(void) { GPIOR0 = 0x600D600Du; for (;;) ; }
#endif
