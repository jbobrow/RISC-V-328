/* Sleep modes, watchdog (interrupt, wake-up, reset), software reset, external
 * reset and reset-cause reporting. The test restarts several times; progress
 * is tracked through MCUSR. */
#include "test.h"
static volatile uint32_t wdt_n, pc_n, tick_n;
static void wdt_isr(void) { wdt_n++; WDTCSR = WDT_KEY | WDIF | WDIE; }
static void pc_isr(void) { pc_n++; PCIFR = 0xF; }
static void tc0_isr(void) { tick_n++; TC0->IFR = TC_OCA; }
int main(void)
{
	uint32_t cause = MCUSR;
	MCUSR = 0x3F;
	if (cause & PORF) {
		/* ---- first pass ---- */
		/* idle sleep: woken by a timer interrupt, peripherals keep running */
		TC0->OCRA = 100; TC0->IER = TC_OCA; TC0->CR = TC_CS(2) | TC_TOP_OCRA;
		irq_attach(IRQ_TC0, tc0_isr);
		sei();
		set_sleep_mode(SLEEP_IDLE);
		sleep_cpu();
		CHECK(1, tick_n >= 1);
		TC0->CR = 0; TC0->IER = 0;

		/* power-down: system clock stops; the watchdog interrupt wakes the chip */
		irq_attach(IRQ_WDT, wdt_isr);
		WDTCSR = WDT_KEY | WDIE | 0;            /* 16 ms nominal; see tb for the scaled clock */
		set_sleep_mode(SLEEP_PWR_DOWN);
		TC1->CNT = 0; TC1->CR = TC_CS(1);       /* free-running: must not advance while asleep */
		sleep_cpu();
		{
			uint32_t c = TC1->CNT;
			CHECK(2, wdt_n == 1);
			CHECK(3, c < 6000);                 /* 16 ms awake would be 128000 counts (wraps), asleep only wake latency */
		}
		WDTCSR = WDT_KEY;                       /* watchdog off */

		/* standby: woken by a pin change on PD7 */
		PCMSK2 = 0x80; PCICR = 4; PCIFR = 0xF;
		irq_attach(IRQ_PCINT2, pc_isr);
		set_sleep_mode(SLEEP_STANDBY);
		TBHOOK(0x4007);                         /* testbench drives PD7 high after 300 us */
		sleep_cpu();
		CHECK(4, pc_n == 1);
		PCICR = 0;

		/* software reset */
		SOFT_RESET();
		for (;;) ;
	}
	if (cause & SWRF) {
		CHECK(5, cause == SWRF);
		/* watchdog reset: enable and do not service it */
		WDTCSR = WDT_KEY | WDE | 0;
		for (;;) ;
	}
	if (cause & WDRF) {
		CHECK(6, cause == WDRF);
		CHECK(7, !(WDTCSR & WDE));              /* watchdog is off again after reset */
		TBHOOK(0x3000);                         /* testbench pulses RESET low */
		for (;;) ;
	}
	CHECK(8, cause == EXTRF);
	PASS();
}
