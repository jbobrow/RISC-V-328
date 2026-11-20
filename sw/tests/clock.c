/* Clock sources and prescaler, measured against the independent 128 kHz
 * watchdog oscillator: one watchdog period is 2048 LF cycles = 16 ms.
 * Run with a 16 MHz external clock on PB6/XTAL1 (+extclk=62.5). */
#include "test.h"
static volatile uint32_t wdt_n, stamp;
static void wdt_isr(void) { stamp = TC1->CNT; TC1->CNT = 0; wdt_n++; WDTCSR = WDT_KEY | WDIF | WDIE; }
/* timer-1 counts in one watchdog period */
static uint32_t measure(void)
{
	uint32_t n = wdt_n;
	while (wdt_n < n + 2) sleep_cpu();
	return stamp;
}
#define NEAR(v, ref) ((v) > (ref) * 95 / 100 && (v) < (ref) * 105 / 100)
int main(void)
{
	uint32_t c;
	NVMCFG = 0;
	irq_attach(IRQ_WDT, wdt_isr);
	sei();
	WDTCSR = WDT_KEY | WDIE | 0;
	TC1->CR = TC_CS(4);                         /* clk_sys / 64 */

	c = measure(); CHECK(1, NEAR(c, 2000));     /* RC 8 MHz: 128000 / 64 */
	CLKPR = 2;
	c = measure(); CHECK(2, NEAR(c, 500));      /* / 4 */
	CLKPR = 0;

	/* external 16 MHz clock on XTAL1 */
	CHECK(3, !(CLKCR & XRDY));
	CLKCR = CLKSEL_X;                           /* refused: source not running yet */
	CHECK(4, (CLKCR & 3) == CLKSEL_RC);
	CLKCR = XEN | XMODE(0);
	while (!(CLKCR & XRDY)) ;
	CLKCR = XEN | XMODE(0) | CLKSEL_X | RCDIS;  /* switch, RC oscillator off */
	c = measure(); CHECK(5, NEAR(c, 4000));
	CLKCR = CLKSEL_RC;                          /* back to RC, external input off */
	c = measure(); CHECK(6, NEAR(c, 2000));

	/* crystal oscillator (analog macro), full-swing mode */
	CLKCR = XEN | XMODE(2);
	while (!(CLKCR & XRDY)) ;
	CLKCR = XEN | XMODE(2) | CLKSEL_X;
	c = measure(); CHECK(7, NEAR(c, 4000));
	CLKCR = CLKSEL_RC;

	/* RC trim: lower OSCCAL slows the oscillator in the model (0.5 % per step) */
	OSCCAL = 0x80 - 40;
	c = measure(); CHECK(8, NEAR(c, 1667));
	OSCCAL = 0x80;

	/* 128 kHz system clock: exactly 2048 cycles per watchdog period */
	TC1->CR = TC_CS(1);
	CLKCR = CLKSEL_LF;
	c = measure(); TBVAL(c); CHECK(9, c >= 2040 && c <= 2056);
	CLKCR = CLKSEL_RC;
	WDTCSR = WDT_KEY;

	/* PRR holds a peripheral in reset */
	TC0->OCRA = 0x55;
	PRR = 1u << 2;
	CHECK(10, TC0->OCRA == 0);
	TC0->OCRA = 0x66;
	CHECK(11, TC0->OCRA == 0);
	PRR = 0;
	TC0->OCRA = 0x77;
	CHECK(12, TC0->OCRA == 0x77);
	PASS();
}
