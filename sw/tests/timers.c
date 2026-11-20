/* Timers: CTC + compare interrupt, fast PWM duty measured by input capture,
 * phase-correct PWM, external clock input, 8-bit timer overflow.
 * Wiring 4: OC1A(PB1)->ICP1(PB0), OC0A(PD6)->T1(PD5), OC2B(PD3)->INT0(PD2). */
#include "test.h"
static volatile uint32_t ticks, cap[4], ncap;
static void tc0_isr(void) { ticks++; TC0->IFR = TC_OCA; }
static void tc1_isr(void)
{
	if (ncap < 4) cap[ncap++] = TC1->ICR;
	TC1->CR ^= TC_ICES;            /* alternate edges */
	TC1->IFR = TC_IC;
}
int main(void)
{
	/* TC0: CTC, TOP = OCRA = 99, /8 -> one interrupt every 800 clocks */
	TC0->OCRA = 99; TC0->IER = TC_OCA;
	TC0->CR = TC_CS(2) | TC_WGM_NORMAL | TC_TOP_OCRA;
	irq_attach(IRQ_TC0, tc0_isr);
	sei();
	while (ticks < 3) ;
	TC0->IER = 0;
	CHECK(1, TC0->CNT < 100);

	/* TC1: 10-bit fast PWM on OC1A, duty 300/1024, measured on ICP1 with TC3?
	 * ICP1 captures TC1 itself, so high time = falling capture - rising capture. */
	DDRB = 0x02;
	TC1->OCRA = 299;
	TC1->IFR = 0xF; TC1->IER = TC_IC;
	irq_attach(IRQ_TC1, tc1_isr);
	TC1->CR = TC_CS(1) | TC_WGM_FAST | TC_TOP_10BIT | TC_COMA(2) | TC_ICES;
	while (ncap < 4) ;
	TC1->IER = 0;
	/* rising edges happen as the counter wraps to 0, falling edges after OCRA */
	/* (the very first period starts one count late, so use the second pair) */
	CHECK(2, ((cap[3] - cap[2]) & 0x3FF) == 300);
	CHECK(3, ((cap[3] - cap[1]) & 0x3FF) == 0);
	TC1->CR = 0;

	/* TC3: phase-correct PWM, TOP = ICR = 50, OCRB = 20: period 100, high 40 */
	TC3->ICR = 50; TC3->OCRB = 20;
	TC3->CR = TC_CS(1) | TC_WGM_PC | TC_TOP_ICR | TC_COMB(2);
	DDRD = 0x04;                   /* OC3B on PD2 */
	{
		uint32_t hi = 0, n = 0;
		for (int i = 0; i < 400; i++) { hi += (PIND >> 2) & 1; n++; }
		/* duty should be 40 % */
		CHECK(4, hi * 100 > n * 30 && hi * 100 < n * 50);
	}
	TC3->CR = 0; DDRD = 0;

	/* TC0 toggles OC0A (PD6) on compare; TC1 counts its rising edges on T1 (PD5) */
	DDRD = 0x40;
	TC1->CNT = 0;
	TC1->CR = TC_CS(9);
	TC0->CNT = 0; TC0->OCRA = 9;
	TC0->CR = TC_CS(1) | TC_WGM_NORMAL | TC_TOP_OCRA | TC_COMA(1);
	while (TC1->CNT < 20) ;
	TC0->CR = 0;
	CHECK(5, TC1->CNT >= 20 && TC1->CNT < 30);

	/* TC2: 8-bit overflow flag in normal mode */
	TC2->IFR = 0xF; TC2->CNT = 250; TC2->CR = TC_CS(1);
	delay(20);
	CHECK(6, TC2->IFR & TC_OVF);
	PASS();
}
