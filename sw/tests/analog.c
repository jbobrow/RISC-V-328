/* ADC (single, free-running, auto-triggered, references, left adjust) and
 * analog comparator, against the behavioural analog model. */
#include "test.h"
static volatile uint32_t adc_n, adc_last, ac_n;
static void adc_isr(void) { adc_last = ADC; adc_n++; ADCSRA |= ADIF; }
static void ac_isr(void) { ac_n++; ACSR |= ACI; }
static uint32_t convert(void) { ADCSRA = ADEN | ADSC | ADIF | 2; while (ADCSRA & ADSC) ; return ADC; }
static void set_mv(unsigned ch, unsigned mv) { TBVAL(mv); TBHOOK(0x2000 | ch | (mv << 16)); }
int main(void)
{
	/* 5 V reference (AVCC): code = floor(mV * 1024 / 5000) */
	ADMUX = REFS_AVCC | 0;
	set_mv(0, 2500); CHECK(1, convert() == 512);
	set_mv(0, 1234); CHECK(2, convert() == 252);
	set_mv(0, 4999); CHECK(3, convert() == 1023);
	set_mv(0, 0);    CHECK(4, convert() == 0);
	/* another channel, left-adjusted result */
	set_mv(5, 3300);
	ADMUX = REFS_AVCC | ADLAR | 5;
	CHECK(5, convert() == (675u << 6));
	/* internal 1.1 V reference, bandgap channel reads full scale, GND reads 0 */
	ADMUX = REFS_1V1 | 14; CHECK(6, convert() == 1023);
	ADMUX = REFS_1V1 | 15; CHECK(7, convert() == 0);
	set_mv(1, 550);
	ADMUX = REFS_1V1 | 1;  CHECK(8, convert() == 512);

	/* free-running with interrupt */
	irq_attach(IRQ_ADC, adc_isr);
	sei();
	ADMUX = REFS_AVCC | 0; set_mv(0, 1000);
	ADCSRB = 0;
	ADCSRA = ADEN | ADSC | ADATE | ADIE | 5;
	while (adc_n < 3) ;
	ADCSRA = ADEN;
	CHECK(9, adc_last == 204);

	/* auto-trigger from timer 0 compare match A */
	adc_n = 0; set_mv(0, 2000);
	ADCSRB = 3;
	ADCSRA = ADEN | ADATE | ADIE | 2;
	TC0->OCRA = 200; TC0->CR = TC_CS(2) | TC_TOP_OCRA;
	while (adc_n < 2) ;
	TC0->CR = 0; ADCSRA = 0;
	CHECK(10, adc_last == 409);

	/* comparator: AIN0 vs AIN1, rising-edge interrupt, output on PE0 */
	irq_attach(IRQ_AC, ac_isr);
	TBVAL(1000); TBHOOK(0x2200);            /* AIN1 = 1.0 V */
	TBVAL(500);  TBHOOK(0x2100);            /* AIN0 = 0.5 V */
	ACSR = ACOE | ACIE | 3 | ACI;
	delay(4);
	CHECK(11, !(ACSR & ACO) && !(PINE & 1));
	TBVAL(1500); TBHOOK(0x2101);            /* AIN0 above AIN1 */
	delay(10);
	CHECK(12, (ACSR & ACO) && (PINE & 1) && ac_n == 1);
	/* bandgap (1.1 V) as positive input: 1.1 > 1.0 */
	TBVAL(0); TBHOOK(0x2102);
	ACSR = ACBG | ACI;
	delay(6);
	CHECK(13, ACSR & ACO);
	PASS();
}
