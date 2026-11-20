/* Benchmark "logger": the classic float-heavy sensor sketch. Each pass reads two
 * analog inputs, converts a thermistor reading with logf(), runs a PID loop on a
 * PWM output and, every eighth pass, prints a line with snprintf("%.2f"). */
#include <stdio.h>
#include <math.h>
#include "hal.h"
#define WARM 8
#define RUN  32
#ifndef LOG_OUT
#define LOG_OUT serial_print
#endif

typedef struct { float kp, ki, kd, integ, prev, lo, hi; } pidc_t;

static float thermistor_c(uint16_t raw)
{
	float r = 10000.0f * (float)raw / (1023.5f - (float)raw);
	float inv = 1.0f / 298.15f + logf(r / 10000.0f) / 3950.0f;
	return 1.0f / inv - 273.15f;
}
static float pid_step(pidc_t *p, float err, float dt)
{
	float d = (err - p->prev) / dt;
	p->integ += err * dt;
	if (p->integ > 50.0f) p->integ = 50.0f;
	if (p->integ < -50.0f) p->integ = -50.0f;
	p->prev = err;
	float u = p->kp * err + p->ki * p->integ + p->kd * d;
	return u < p->lo ? p->lo : u > p->hi ? p->hi : u;
}

static char line[48];
static pidc_t pid = { 30.0f, 4.0f, 0.5f, 0.0f, 0.0f, 0.0f, 1023.0f };
static float filt = 25.0f, vbat, tmin = 1000.0f, tmax = -1000.0f;
static uint32_t last;
static unsigned duty;

static void logger_step(unsigned pass)
{
	hal_set_input(0, 2100u + 23u * (pass % 16u));
	hal_set_input(1, 3300u + 11u * (pass % 8u));
	float t = thermistor_c(analog_read(0));
	vbat = 0.9f * vbat + 0.1f * ((float)analog_read(1) * (5.0f / 1023.0f) * 3.0f);
	filt += 0.25f * (t - filt);
	if (filt < tmin) tmin = filt;
	if (filt > tmax) tmax = filt;
	uint32_t now = millis();
	float dt = (float)(now - last + 1u) * 0.001f;
	last = now;
	duty = (unsigned)pid_step(&pid, 40.0f - filt, dt);
	pwm_write(duty);
	if ((pass & 7u) == 7u) {
		snprintf(line, sizeof line, "%lu,%.2f,%.2f,%.1f,%u\r\n",
		         (unsigned long)now, (double)filt, (double)vbat, (double)(tmax - tmin), duty);
		LOG_OUT(line);
	}
}

#ifndef NO_MAIN
int main(void)
{
	hal_init();
	serial_begin(115200);
	probe_begin();
	for (unsigned pass = 0; pass < WARM + RUN; pass++) {
		if (pass == WARM) MARK(1, pass);
		logger_step(pass);
	}
	MARK(2, duty);
	DONE();
}
#endif
