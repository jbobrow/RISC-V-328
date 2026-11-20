/* Benchmark "blink": a small control loop that fits a 2 KB cache. Fades a PWM
 * output on a time base, debounces a button and toggles an LED. */
#include "hal.h"
int main(void)
{
	unsigned duty = 0, dir = 1, deb = 0, led = 0;
	uint32_t next = 0, n = 0;
	hal_init();
	probe_begin();
	for (unsigned pass = 0; pass < 6000u; pass++) {
		if (pass == 500u) MARK(1, pass);
		uint32_t now = millis();
		if (now != next) {
			next = now;
			duty += dir ? 7u : -7u;
			if (duty > 1000u) dir = 0; else if (duty < 16u) dir = 1;
			pwm_write(duty);
		}
		unsigned b = (buttons_raw() >> 2) & 1u;
		deb = b ? deb + 1u : 0u;
		if (deb == 5u) led ^= 1u;
		if ((++n & 0x3FFu) == 0u) led ^= 1u;
		led_write(led);
	}
	MARK(2, duty);
	DONE();
}
